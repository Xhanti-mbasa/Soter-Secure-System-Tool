"""Bounded, allowlisted HTTP collection. No account or anti-bot bypass."""
import concurrent.futures
import io
import ipaddress
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse as urlparse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from html.parser import HTMLParser

from .core import PROVINCES, date_value, digest

USER_AGENT = 'ZALensResearch/0.1 (+public-records; bounded crawler)'
MAX_BYTES = 12 * 1024 * 1024
SOCIAL_HOSTS = ('x.com','twitter.com','facebook.com','instagram.com','youtube.com','linkedin.com')

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.meta, self.title = [], [], {}, []
        self.skip = 0
        self.in_title = False
        self.anchor = None
        self.published = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script','style','nav','footer','header','noscript','svg'):
            self.skip += 1
        if tag == 'title': self.in_title = True
        if tag == 'meta':
            key = a.get('property', a.get('name','')).lower()
            self.meta[key] = a.get('content','')
        if tag == 'time' and a.get('datetime') and not self.published:
            self.published = a['datetime']
        if tag == 'a' and a.get('href'):
            self.anchor = [a['href'], []]
        if tag in ('p','div','section','article','h1','h2','h3','li','br','tr') and not self.skip:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script','style','nav','footer','header','noscript','svg'):
            self.skip = max(0, self.skip - 1)
        if tag == 'title': self.in_title = False
        if tag == 'a' and self.anchor:
            self.links.append((self.anchor[0], ' '.join(self.anchor[1]).strip()))
            self.anchor = None

    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if self.anchor: self.anchor[1].append(data)
        if not self.skip and not self.in_title: self.parts.append(data.strip() + ' ')

    @property
    def text(self):
        return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[^\S\n]+', ' ', ''.join(self.parts))).strip()

    @property
    def date(self):
        candidates = [self.meta.get(k) for k in ('article:published_time','date','dc.date','dcterms.created','pubdate')] + [self.published]
        for d in candidates:
            if date_value(d): return date_value(d)
        # Only an explicit date close to the start, not copyright/footer years.
        match = re.search(r'\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b', self.text[:1500])
        return date_value(match.group(0)) if match else None

def canonical(url):
    p = urlparse.urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
        raise ValueError('Only HTTP(S) URLs without credentials are allowed')
    host = p.hostname.lower()
    port = p.port
    if port and port not in (80,443):
        raise ValueError('Only standard web ports are allowed')
    path = p.path or '/'
    return urlparse.urlunsplit((p.scheme, host, path, p.query, ''))

def public_url(url, allowed_hosts=None):
    url = canonical(url)
    host = urlparse.urlsplit(url).hostname
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError('URL is outside this connector host allowlist')
    try:
        literal = ipaddress.ip_address(host)
        if not literal.is_global:
            raise ValueError('Private or reserved addresses cannot be crawled')
    except ValueError:
        if re.match(r'^[0-9.:]+$', host):
            raise ValueError('IP literals are not supported as public sources')
    if host == 'localhost' or host.endswith(('.local','.localhost','.internal')):
        raise ValueError('Local hosts cannot be crawled')
    try:
        addrs = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # Some controlled egress proxies resolve public DNS remotely. This explicit
        # opt-in delegates DNS validation to that trusted proxy, never by default.
        proxies = urllib.request.getproxies()
        if allowed_hosts and os.environ.get('ZALENS_TRUST_PROXY_DNS') == '1' and proxies.get('https'):
            return url
        raise
    if not addrs or any(not ipaddress.ip_address(a[4][0]).is_global for a in addrs):
        raise ValueError('Private, loopback, or reserved addresses cannot be crawled')
    return url

class GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts): self.hosts = hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked = public_url(urlparse.urljoin(req.full_url, newurl), self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, checked)

class Fetcher:
    def __init__(self):
        self.robots, self.last, self.locks = {}, {}, {}
        self.global_lock = threading.Lock()

    def fetch_raw(self, url, hosts):
        checked = public_url(url, hosts)
        opener = urllib.request.build_opener(GuardedRedirect(hosts))
        req = urllib.request.Request(checked, headers={'User-Agent': USER_AGENT, 'Accept-Encoding':'identity'})
        with opener.open(req, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Document exceeds 12 MiB collection limit')
            return raw, response.headers.get_content_type(), response.geturl(), response.headers.get_content_charset() or 'utf-8'

    def fetch(self, url, hosts):
        host = urlparse.urlsplit(url).hostname
        with self.global_lock:
            lock = self.locks.setdefault(host, threading.Lock())
        with lock:
            origin = urlparse.urlsplit(url).scheme + '://' + host
            if origin not in self.robots:
                rp = urllib.robotparser.RobotFileParser()
                try:
                    raw, _, _, charset = self.fetch_raw(origin + '/robots.txt', hosts)
                    rp.parse(raw.decode(charset, errors='replace').splitlines())
                except urllib.error.HTTPError as e:
                    if e.code == 404: rp.parse([])
                    else: raise ValueError('robots.txt unavailable; collection paused') from e
                self.robots[origin] = rp
            rp = self.robots[origin]
            if not rp.can_fetch(USER_AGENT, url):
                raise ValueError('robots.txt disallows this URL')
            delay = max(1.0, float(rp.crawl_delay(USER_AGENT) or rp.crawl_delay('*') or 0))
            if delay > 15:
                raise ValueError('Long crawl delay; use an authorised manual import')
            wait = delay - (time.monotonic() - self.last.get(host,0))
            if wait > 0: time.sleep(wait)
            try:
                return self.fetch_raw(url, hosts)
            finally:
                self.last[host] = time.monotonic()

def category_for(url, default):
    u = url.lower()
    for category, terms in [
        ('interests', ['register-members','members-interests','members%20interests']),
        ('remuneration',['remuneration','salary','salaries','54179gon7159']),
        ('gazettes',['gazette','egazette']), ('jobs',['vacanc','career','/psvc','government-jobs']),
        ('tenders',['tender','procurement']), ('news',['/news','press-release','media-and-news','/speeches'])]:
        if any(t in u for t in terms): return category
    return default

def extract(store, source, url, raw, mime, charset='utf-8', acquisition='crawl'):
    ids, links = [], []
    if mime == 'application/pdf' or raw.startswith(b'%PDF-'):
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ValueError('Install pypdf to index PDF documents') from e
        reader = PdfReader(io.BytesIO(raw))
        if len(reader.pages) > 800: raise ValueError('PDF exceeds 800 pages')
        title = str((reader.metadata or {}).get('/Title') or urlparse.unquote(url.rsplit('/',1)[-1]))
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            if len(text.strip()) >= 40:
                ids.append(store.put_document(source, url, title, text, page=i, raw=raw,
                           category=category_for(url, source['category']), acquisition=acquisition))
        if not ids: raise ValueError('PDF has no extractable text; OCR required')
    elif mime in ('application/rss+xml','application/atom+xml','application/xml','text/xml'):
        root = ET.fromstring(raw)
        for node in root.iter():
            if node.tag.split('}')[-1] in ('link','loc'):
                value = node.attrib.get('href') or (node.text or '').strip()
                if value: links.append((value,''))
    elif mime in ('text/html','application/xhtml+xml','text/plain'):
        p = Page(); p.feed(raw.decode(charset, errors='replace'))
        title = p.meta.get('og:title') or ''.join(p.title).strip() or url
        socials = []
        for link, label in p.links:
            full = urlparse.urljoin(url,link)
            social_url = urlparse.urlsplit(full)
            h = (social_url.hostname or '').lower()
            if any(h == s or h.endswith('.'+s) for s in SOCIAL_HOSTS):
                if any(t in social_url.path.lower() for t in ('/share','/sharer','/intent/')):
                    continue
                if any(s['url']==full for s in socials): continue
                socials.append({'url':full,'label':label[:100],
                                'status':'publisher link; person ownership unverified','evidence_url':url})
        if len(p.text) >= 40:
            ids.append(store.put_document(source, url, title, p.text, p.date, raw=raw,
                       social_links=socials, category=category_for(url, source['category']), acquisition=acquisition))
        links = p.links
    else:
        raise ValueError('Unsupported content type: ' + mime)
    return ids, links

class Connector:
    def __init__(self, store, fetcher=None):
        self.store = store
        self.fetcher = fetcher or Fetcher()

    def crawl(self, source_id, pages=8, depth=1):
        source = self.store.source(source_id)
        if not source: raise ValueError('Unknown source')
        if source.get('access') != 'public' or not source.get('enabled'):
            self.store.event(source_id, source.get('access','disabled'), 'Source requires manual review or authorised access')
            return dict(source_id=source_id, fetched=0, indexed=0, errors=['Connector is not enabled for public collection'])
        hosts = set(source['allowed_hosts'])
        queue = deque((u,0) for u in source['seeds'])
        visited, errors, indexed, fetched = set(), [], 0, 0
        while queue and fetched < min(max(int(pages),1),50):
            url, level = queue.popleft()
            try:
                url = canonical(url)
                if url in visited: continue
                visited.add(url); fetched += 1
                raw, mime, final_url, charset = self.fetcher.fetch(url, hosts)
                ids, links = extract(self.store, source, final_url, raw, mime, charset)
                indexed += len(ids)
                if level < min(int(depth),2):
                    candidates = []
                    for href, label in links:
                        try:
                            full = canonical(urlparse.urljoin(final_url,href))
                            p = urlparse.urlsplit(full)
                            if p.hostname not in hosts or full in visited: continue
                            scopes = source.get('path_prefixes')
                            if scopes and not any(p.path.startswith(scope) for scope in scopes): continue
                            if any(t in p.path.lower() for t in ('/login','/logout','/register','/cart')): continue
                            if re.search(r'\.(?:png|jpg|jpeg|gif|css|js|zip|docx?|xlsx?|mp4)$',p.path,re.I): continue
                            priority = 0 if category_for(full,'government') != 'government' or full.lower().endswith('.pdf') else 1
                            candidates.append((priority, full))
                        except (ValueError, TypeError): continue
                    for _, full in sorted(set(candidates))[:150]: queue.append((full,level+1))
            except Exception as e:
                errors.append(url + ': ' + str(e)[:250])
        status = 'indexed' if indexed else 'unavailable'
        self.store.event(source_id, status, f'{indexed} indexed passages; {fetched} requests; {len(errors)} failures')
        return dict(source_id=source_id, fetched=fetched, indexed=indexed, errors=errors)

def source_record(name, url, province='National', category='government', access='public', enabled=True, **extra):
    url = canonical(url)
    host = urlparse.urlsplit(url).hostname
    hosts = [host]
    hosts.append(host[4:] if host.startswith('www.') else 'www.' + host)
    return dict(id=digest(province + '|' + name + '|' + url)[:16], name=name, url=url,
                province=province, category=category, access=access, enabled=enabled,
                adapter='public_web' if access=='public' else 'manual_import',
                allowed_hosts=hosts, seeds=[url], status='not_indexed', **extra)

class DirectoryPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.main = 0; self.heading = None; self.anchor = None
        self.province = 'National'; self.links = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'main': self.main += 1
        if tag in ('h2','h3','h4') and self.main: self.heading = []
        if tag == 'a' and self.main and a.get('href'): self.anchor = [a['href'],[]]
    def handle_data(self, data):
        if self.heading is not None: self.heading.append(data)
        if self.anchor: self.anchor[1].append(data)
    def handle_endtag(self, tag):
        if tag == 'main': self.main = max(0,self.main-1)
        if tag in ('h2','h3','h4') and self.heading is not None:
            title = ''.join(self.heading).strip()
            if title in PROVINCES: self.province=title
            self.heading=None
        if tag == 'a' and self.anchor:
            self.links.append((self.province,self.anchor[0],''.join(self.anchor[1]).strip()))
            self.anchor=None

def discover(directory_url, province_default='National'):
    """Produce candidates; directory membership alone does not validate a live site."""
    host = urlparse.urlsplit(directory_url).hostname
    raw, _, _, charset = Fetcher().fetch(directory_url, {host})
    p = DirectoryPage(); p.province=province_default; p.feed(raw.decode(charset, errors='replace'))
    records, seen = [], set()
    for province, href, name in p.links:
        if not name or not href.startswith(('https://','http://')): continue
        try:
            url = canonical(href)
            h = urlparse.urlsplit(url).hostname
            if h in ('www.gov.za','gov.za') or any(h==s or h.endswith('.'+s) for s in SOCIAL_HOSTS): continue
            if (province,name,url) in seen: continue
            seen.add((province,name,url))
            government_host = h.endswith('.gov.za')
            records.append(source_record(name,url,province,enabled=government_host,
                           access='public' if government_host else 'review_required',
                           discovered_from=directory_url, discovery_note='Listed by government directory; health and jurisdiction still require review'))
        except ValueError: continue
    return records
