"""Everyday public content. Providers publish capabilities, never inferred submissions."""
import datetime as dt
from collections import OrderedDict
from concurrent.futures import Future
import hashlib
import re
import threading
import time
import urllib.parse as up
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .connectors import Fetcher, Page, canonical
from .core import now
from .provinces import FEED, parse_feed, mentions, snapshot

EC_URL = 'https://erecruitment.ecotp.gov.za/Process/JobTitle.aspx'


class Provider:
    def __init__(self, reader=None):
        self.reader = reader
        self.fetcher = Fetcher()

    def read(self, url):
        host = up.urlsplit(url).hostname
        if self.reader:
            raw = self.reader(url)
        else:
            raw = self.fetcher.fetch(url, {host})[0]
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Provider response exceeds 2 MiB')
        return raw


class NewsProvider(Provider):
    def collect(self, url=FEED):
        url = canonical(url)
        if up.urlsplit(url).scheme != 'https':
            raise ValueError('Feeds require HTTPS')
        raw = self.read(url)
        if url == FEED:
            return [{**i, 'reader_allowed': True, 'credit': 'SAnews.gov.za'} for i in parse_feed(raw)]
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('Unsupported feed XML')
        from .provinces import published
        root = ET.fromstring(raw)
        if root.tag.rsplit('}', 1)[-1] not in ('rss', 'feed', 'RDF'):
            raise ValueError('Not an RSS/Atom feed')
        result = {}
        for node in root.iter():
            if node.tag.rsplit('}', 1)[-1] not in ('item', 'entry'):
                continue
            fields = {n.tag.rsplit('}', 1)[-1]: n.attrib.get('href') or ''.join(n.itertext()) for n in node}
            try:
                link = canonical(fields.get('link', ''))
                p = up.urlsplit(link)
                if p.scheme != 'https' or p.hostname in ('localhost', '127.0.0.1', '::1'):
                    continue
            except ValueError:
                continue
            title = re.sub('<[^>]+>', '', fields.get('title', ''))[:500].strip()
            if title:
                result[link] = dict(id=hashlib.sha256(link.encode()).hexdigest()[:24], url=link, title=title,
                    description='', publisher=up.urlsplit(url).hostname, published_at=published(fields.get('pubDate', fields.get('published', ''))),
                    retrieved_at=now(), reader_allowed=False, acquisition='custom_feed_metadata')
            if len(result) >= 100:
                break
        return list(result.values())

    def article(self, url):
        url = canonical(url)
        if up.urlsplit(url).hostname not in ('www.sanews.gov.za', 'sanews.gov.za') or not url.startswith('https://'):
            raise ValueError('Reader enabled only for credited SAnews content; open other publishers directly')
        page = Page(); page.feed(self.read(url).decode('utf-8', errors='replace'))
        return dict(url=url, title=' '.join(page.title), text=page.text[:40000], publisher='SAnews.gov.za',
                    published_at=page.date, retrieved_at=now(), credit='SAnews.gov.za', reader_allowed=True)


class ECPage(HTMLParser):
    """Capture ASP.NET vacancy fields without executing postbacks or logging in."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0; self.active = []; self.rows = {}

    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'img', 'input', 'meta', 'link', 'hr'):
            if tag == 'br':
                for _, _, parts in self.active: parts.append(' ')
            return
        self.depth += 1
        value = dict(attrs).get('id', '')
        match = re.fullmatch(r'(gvAllJobs_ctl\d+)_(lbl\w+)', value)
        if match:
            parts = []; self.rows.setdefault(match[1], {})[match[2]] = parts
            self.active.append((self.depth, value, parts))

    def handle_endtag(self, tag):
        if tag in ('br', 'img', 'input', 'meta', 'link', 'hr'): return
        self.active = [a for a in self.active if a[0] != self.depth]
        self.depth = max(0, self.depth - 1)

    def handle_data(self, value):
        for _, _, parts in self.active: parts.append(value)


class JobsProvider(Provider):
    def collect(self, url=EC_URL):
        if url != EC_URL: raise ValueError('Unknown vacancy provider')
        parser = ECPage(); parser.feed(self.read(url).decode('utf-8', errors='replace'))
        rows = []
        def date(s):
            try: return dt.datetime.strptime(s.strip(), '%d/%m/%Y').date().isoformat()
            except ValueError: return None
        for fields in parser.rows.values():
            f = {k: re.sub(r'\s+', ' ', ''.join(v)).strip() for k, v in fields.items()}
            title = f.get('lblJobTitle', '')
            if not title: continue
            close = date(f.get('lblClosingDate', ''))
            if close and close < dt.datetime.now(dt.timezone.utc).date().isoformat(): continue
            identity = title+'|'+f.get('lblCity', '')+'|'+str(close)
            rows.append(dict(id=hashlib.sha256(identity.encode()).hexdigest()[:24], title=title[:500],
                description=f.get('lblDescription', '')[:8000], salary=f.get('lblPackage', ''), employer=f.get('lblDepartment', ''),
                location=f.get('lblCity', ''), province='Eastern Cape', url=EC_URL, published_at=date(f.get('lblPostDate', '')),
                closing_at=close, retrieved_at=now(), publisher='Eastern Cape Provincial eRecruitment',
                application_method='official_portal_handoff', verified_listing=True))
        if not rows and not parser.rows: raise ValueError('No readable current vacancies; use the official portal')
        return rows[:100]


class ProviderCache:
    """Bounded LRU with per-key in-flight sharing; unrelated providers run independently."""
    def __init__(self, capacity=32, ttl=300):
        self.capacity, self.ttl = capacity, ttl
        self.values = OrderedDict(); self.pending = {}; self.lock = threading.Lock()

    def get(self, key, loader, refresh=False):
        with self.lock:
            cached = self.values.get(key)
            if cached and not refresh and time.monotonic()-cached[0] < self.ttl:
                self.values.move_to_end(key); return cached[1]
            future = self.pending.get(key)
            owner = future is None
            if owner:
                if len(self.pending) >= self.capacity: raise ValueError('Provider queue is busy; retry shortly')
                future = Future(); self.pending[key] = future
        if not owner: return future.result(timeout=60)
        try:
            result = loader()
            with self.lock:
                self.values[key] = (time.monotonic(), result); self.values.move_to_end(key)
                while len(self.values) > self.capacity: self.values.popitem(last=False)
            future.set_result(result); return result
        except Exception as error:
            future.set_exception(error); raise
        finally:
            with self.lock: self.pending.pop(key, None)


class DailyService:
    def __init__(self, reader=None):
        self.news_provider = NewsProvider(reader); self.jobs_provider = JobsProvider(reader)
        self.providers = {'news': self.news_provider, 'opportunities': self.jobs_provider}
        self.cache = ProviderCache()

    def collect(self, kind, data):
        if kind not in self.providers: raise ValueError('Unknown collection')
        name = str(data.get('province', ''))
        definitions = snapshot()['provinces']
        if name and name not in [p['name'] for p in definitions]: raise ValueError('Unknown province')
        query = str(data.get('query', ''))[:200].lower().strip()
        feeds = data.get('feeds', [])
        if not isinstance(feeds, list) or len(feeds) > 3 or any(not isinstance(u, str) for u in feeds):
            raise ValueError('Choose up to three custom HTTPS feeds')
        urls = list(dict.fromkeys([FEED, *feeds] if kind == 'news' else [EC_URL]))
        rows, statuses = [], []
        for url in urls:
            try:
                key = (kind, canonical(url))
                loader = lambda: self.providers[kind].collect(url)
                items = self.cache.get(key, loader, bool(data.get('refresh')))
                rows.extend(items); statuses.append(dict(provider=url, status='completed', count=len(items)))
            except Exception as exc:
                statuses.append(dict(provider=str(url), status='unavailable', detail=str(exc)[:180]))
        p = next((p for p in definitions if p['name'] == name), None)
        seen, result = set(), []; today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        for item in rows:
            if item['id'] in seen: continue
            text = item['title']+' '+item.get('description', '')+' '+item.get('location', '')
            if query and not all(t in text.lower() for t in query.split()): continue
            if p and not (kind == 'opportunities' and item.get('province') == name) and not mentions(text, p['keywords']): continue
            if item.get('published_at') and item['published_at'][:10] > today: continue
            if item.get('closing_at') and item['closing_at'] < today: continue
            seen.add(item['id']); result.append(item)
        return dict(results=sorted(result, key=lambda i: i.get('published_at') or '', reverse=True), statuses=statuses,
                    retrieved_at=now(), coverage='Current publisher feed items and supported public listings. Other providers are available as official browser handoffs.')
