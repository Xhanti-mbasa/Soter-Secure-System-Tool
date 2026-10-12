"""Public discovery and procurement adapters; no private platform APIs are assumed."""
import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse as urlparse
import urllib.request
from html.parser import HTMLParser
from .core import now, digest, date_value

PLATFORMS = {'instagram.com':'Instagram','facebook.com':'Facebook','linkedin.com':'LinkedIn',
             'x.com':'X / Twitter','twitter.com':'X / Twitter','tiktok.com':'TikTok','youtube.com':'YouTube'}
BIZPORTAL = 'https://www.bizportal.gov.za/'
TENDERPORTAL = 'https://www.etenders.gov.za/Home/opportunities'
MAX_RESPONSE = 8*1024*1024

def registration(value):
    compact = re.sub(r'[\s/\-]', '', value)
    return compact[:4]+'/'+compact[4:10]+'/'+compact[10:] if re.fullmatch(r'(?:19|20)\d{10}', compact) else None

def text(value):
    return re.sub(r'\s+',' ',value or '').strip()

def read(url, headers=None):
    # All callers use constant provider endpoints. No arbitrary URL proxy here.
    request = urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; Sothis/0.2)',
         'Accept':'application/json,text/html', **(headers or {})})
    with urllib.request.urlopen(request,timeout=18) as response:
        raw=response.read(MAX_RESPONSE+1)
        if len(raw)>MAX_RESPONSE: raise ValueError('Provider response exceeded 8 MiB')
        return raw.decode('utf-8',errors='replace')

class SearchPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.anchor=None;self.results=[];self.heading=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='a' and ('l1' in a.get('class','').split() or 'result-link' in a.get('class','').split()):
            href=a.get('href','')
            if href.startswith('//duckduckgo.com/l/'):
                href=urlparse.parse_qs(urlparse.urlsplit(href).query).get('uddg',[''])[0]
            if href.startswith(('https://','http://')):
                self.anchor={'url':href,'title':'','description':''};self.heading=False
        if self.anchor and tag in ('div','span') and ('title' in a.get('class','').split() or 'snippet-title' in a.get('class','')):
            self.heading=True
    def handle_data(self, value):
        if self.anchor:
            self.anchor['description'] += ' '+value
            if self.heading:self.anchor['title']+=' '+value
    def handle_endtag(self,tag):
        if tag=='a' and self.anchor:
            self.anchor['title']=text(self.anchor['title']) or text(self.anchor['description'])
            self.anchor['description']=text(self.anchor['description']);self.results.append(self.anchor);self.anchor=None

def public_search_rows(markup):
    parser=SearchPage();parser.feed(markup)
    if parser.results:return parser.results
    lowered=markup.casefold()
    if any(value in lowered for value in ('captcha','verify you are human','too many requests','anomaly-modal','challenge-form')):
        raise ValueError('Provider requires a browser check; open browser search or try again later.')
    if not any(value in lowered for value in ('no results found','no results were found','no more results','no results for','did not match any')):
        raise ValueError('Provider returned an unreadable search page; open browser search or try again later.')
    return []

def tender_matches(row,query,search_by):
    if not query:return True
    if search_by=='number':
        number=re.sub(r'[^\w]','',query.casefold())
        return bool(number) and number in re.sub(r'[^\w]','',str(row.get('tender_No','')).casefold())
    if search_by in ('company','supplier'):
        def values(item):
            if isinstance(item,dict):return ' '.join(values(value) for value in item.values())
            if isinstance(item,list):return ' '.join(values(value) for value in item)
            return str(item) if item is not None else ''
        value=' '.join(values(row.get(key)) for key in ('awards','company','supplierNumber','supplier_number'))
    else:
        value=' '.join(str(row.get(key) or '') for key in ('description','tenderDescription','tender_No','organ_of_State','department','category'))
    return all(token in value.casefold() for token in query.casefold().split())

def profile(url):
    p=urlparse.urlsplit(url);host=(p.hostname or '').removeprefix('www.').removeprefix('m.')
    platform=PLATFORMS.get(host);parts=[x for x in p.path.split('/') if x]
    if not platform:return None
    if any(x.lower().startswith(('share','sharer','intent')) for x in parts):return None
    if any(x.lower() in {'p','reel','reels','posts','post','status','statuses','video','videos','watch','discover',
                       'share','sharer','intent','search','hashtag','groups','login','accounts','stories','events'} for x in parts):return None
    if host=='linkedin.com':valid=len(parts)==2 and parts[0]=='in'
    elif host=='tiktok.com':valid=len(parts)==1 and parts[0].startswith('@')
    elif host=='youtube.com':valid=(len(parts)==1 and parts[0].startswith('@')) or (len(parts)==2 and parts[0] in ('channel','c','user'))
    elif host=='facebook.com' and p.path=='/profile.php':valid=bool(urlparse.parse_qs(p.query).get('id'))
    else:valid=len(parts)==1 and parts[0].lower() not in ('home','explore','help','about','privacy','terms')
    return platform if valid else None

def normalize_hit(hit,query):
    url=hit.get('url','');p=urlparse.urlsplit(url)
    if p.scheme not in ('https','http') or not p.hostname or p.username:return None
    url=urlparse.urlunsplit((p.scheme,p.netloc,p.path.rstrip('/') or '/',p.query if p.path=='/profile.php' else '', ''))
    title=text(hit.get('title',''))[:500];description=text(hit.get('description',''))[:1500]
    hay=(title+' '+description+' '+urlparse.unquote(url)).casefold()
    reg=registration(query)
    if reg:
        if re.sub(r'\D','',reg) not in re.sub(r'\D','',hay) and reg not in hay:return None
    else:
        terms=re.findall(r'\w+',query.casefold())
        if not terms or not all(t in hay for t in terms):return None
    kind=profile(url);host=(p.hostname or '').lower()
    category='social' if kind else 'government' if host.endswith('.gov.za') or host.endswith('.parliament.gov.za') else 'web'
    exact=query.casefold() in (title+' '+description).casefold()
    score=(90 if exact else 65)+(5 if kind else 0)
    return dict(id=digest(url)[:24],url=url,title=title or url,description=description,
        platform=kind,category=category,match_score=score,match_label='Strong name match' if exact else 'Name terms match',
        match_reason='Name appears in indexed text. Ranking measures text relevance, not identity.',
        ownership='unreviewed',retrieved_at=now(),published_at=None,index_date=date_value(hit.get('page_age')),
        content_hash=digest(title+'\n'+description),acquisition='search_index')

class PublicServices:
    def __init__(self, reader=None):
        self.read=reader or read;self.cache={};self.lock=threading.Lock()
    def discover(self,query,scope='all',fresh=False,topic=''):
        query=text(query)[:160]
        if len(query)<2:raise ValueError('Enter at least two characters')
        if scope not in ('all','social','government','company'):raise ValueError('Unknown discovery scope')
        topics={'':'', 'education':'(education OR university OR qualifications OR degree)', 'remuneration':'(salary OR salaries OR remuneration)', 'news':'news'}
        if topic not in topics:raise ValueError('Unknown discovery topic')
        key=(query.casefold(),scope,topic)
        with self.lock:cached=self.cache.get(key)
        if cached and not fresh and time.time()-cached[0]<300:return {**cached[1],'cached':True}
        reg=registration(query);q=(reg or query).replace('"','')
        social='(site:instagram.com OR site:facebook.com OR site:linkedin.com/in OR site:x.com OR site:twitter.com OR site:tiktok.com/@ OR site:youtube.com/@)'
        queries=[q] if scope=='all' else [q+' '+social] if scope=='social' else [q+' (site:gov.za OR site:parliament.gov.za)'] if scope=='government' else [q+' (company OR CIPC OR enterprise)']
        if topic:queries=[search+' '+topics[topic] for search in queries]
        key_api=os.getenv('SOTHIS_BRAVE_API_KEY','');hits={};statuses=[]
        for search in queries:
            try:
                if key_api:
                    response=json.loads(self.read('https://api.search.brave.com/res/v1/web/search?'+urlparse.urlencode({'q':search,'count':20,'country':'ZA'}),{'X-Subscription-Token':key_api}))
                    rows=response.get('web',{}).get('results',[]);provider='Brave Search API'
                else:
                    try:
                        html=self.read('https://search.brave.com/search?'+urlparse.urlencode({'q':search,'source':'web'}));rows=public_search_rows(html);provider='Brave public search (best effort)'
                    except Exception:
                        html=self.read('https://lite.duckduckgo.com/lite/?'+urlparse.urlencode({'q':search}));rows=public_search_rows(html);provider='DuckDuckGo public search (best effort)'
                for row in rows:
                    try:hit=normalize_hit(row,reg or query)
                    except (ValueError,TypeError):continue
                    if hit and (scope!='social' or hit['platform']) and (scope!='government' or hit['category']=='government'):
                        previous=hits.get(hit['url'])
                        if not previous or len(hit['description'])>len(previous['description']):hits[hit['url']]=hit
                statuses.append({'service':provider,'status':'completed','retrieved':len(rows)})
            except Exception as e:statuses.append({'service':'Web discovery','status':'unavailable','detail':str(e)[:240]})
        companies=[]
        if reg:
            try:
                rows=json.loads(self.read('https://www.etenders.gov.za/Home/GetCompanies?'+urlparse.urlencode({'search':reg})))
                companies=[{'record':x,'source_url':TENDERPORTAL,'authority':'eTenders supplier index; not a CIPC registration certificate'} for x in rows if re.sub(r'\D','',reg) in re.sub(r'\D','',json.dumps(x))][:20] if isinstance(rows,list) else []
                statuses.append({'service':'eTenders supplier index','status':'completed','retrieved':len(companies)})
            except Exception as e:statuses.append({'service':'eTenders supplier index','status':'unavailable','detail':str(e)[:240]})
        result=dict(query=query,topic=topic,registration_number=reg,results=sorted(hits.values(),key=lambda r:-r['match_score']),
            hit_count=len(hits),account_count=sum(bool(r['platform']) for r in hits.values()),statuses=statuses,
            companies=companies,cipc={'status':'authorised_access_required','url':BIZPORTAL,
             'detail':'BizProfile requires login. Import an authorised disclosure to search and monitor CIPC records in your engine.'},
            retrieved_at=now(),cached=False,coverage='Counts describe retrieved, deduplicated index hits. No provider indexes every account. Name matches do not establish account ownership.')
        if any(status['status']=='completed' for status in statuses):
            with self.lock:
                if len(self.cache)>=100:self.cache.pop(next(iter(self.cache)))
                self.cache[key]=(time.time(),result)
        return result
    def tenders(self,query='',status='open',start=0,search_by='keyword'):
        if status not in ('open','awarded','closed','cancelled'):raise ValueError('Unknown tender status')
        if search_by not in ('keyword','company','supplier','number'):raise ValueError('Unknown tender search field')
        start=max(0,min(int(start),100000));query=text(query)[:160]
        # The public portal currently ignores DataTables keyword search. Scan one
        # bounded window and verify the returned text rather than claiming its
        # whole notice total is a query match count.
        length=90 if query else 30
        params={'status':{'open':1,'awarded':2,'closed':3,'cancelled':4}[status],'draw':1,'start':start,'length':length,
                'search[value]':query,'order[0][column]':2,'order[0][dir]':'desc'}
        endpoint='PaginatedTenderOpportunities'
        if search_by in ('company','supplier','number') and query:
            endpoint='TenderFilter/'
            params['search[value]']=''
            params[{'company':'company','supplier':'supplierNumber','number':'tenderNumber'}[search_by]]=query
        data=json.loads(self.read('https://www.etenders.gov.za/Home/'+endpoint+'?'+urlparse.urlencode(params)))
        if not isinstance(data,dict) or not isinstance(data.get('data'),list):raise ValueError('Tender provider returned an unreadable response; open the official portal.')
        raw=data['data'][:length]
        if any(not isinstance(row,dict) or row.get('id') is None for row in raw):raise ValueError('Tender provider returned invalid notice data.')
        provider_total=max(0,int(data.get('recordsFiltered',len(raw))))
        rows=[row for row in raw if tender_matches(row,query,search_by)]
        next_offset=start+len(raw)
        return {'query':query,'status':status,'results':rows,'total':None if query else provider_total,
            'provider_total':provider_total,'scanned':len(raw),'offset':start,'next_offset':next_offset,
            'has_more':bool(raw) and next_offset<provider_total,'filtered_locally':bool(query),
            'retrieved_at':now(),'source_url':TENDERPORTAL,
            'coverage':('Matches are verified within each fetched window of up to 90 notices. Load more to check the next window; this is not a complete match count. ' if query else 'Portal publication coverage. ')+
                'Verify requirements, amendments and submission method in the original notice.'}

class Monitoring:
    def __init__(self,store,services):
        self.store=store;self.services=services;self.lock=threading.Lock();self.stop=threading.Event()
        with store.connect() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS monitors(id TEXT PRIMARY KEY,data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,data TEXT NOT NULL);')
        threading.Thread(target=self.loop,daemon=True,name='sothis-monitors').start()
    def list(self,table='monitors'):
        if table not in ('monitors','alerts'):raise ValueError('Unknown collection')
        with self.store.connect() as c:return [json.loads(r[0]) for r in c.execute('SELECT data FROM '+table+' ORDER BY rowid DESC')]
    def save(self,data):
        old=next((r for r in self.list() if r['id']==data.get('id')),{});query=text(data.get('query',old.get('query','')))[:160]
        if len(query)<2:raise ValueError('Monitoring query must have at least two characters')
        selected=data.get('services',old.get('services',['web']))
        if not isinstance(selected,list) or not selected or any(s not in ('web','social','government','cipc','tenders') for s in selected):raise ValueError('Choose supported monitoring services')
        condition=data.get('condition',old.get('condition','new_hit'))
        if condition not in ('new_hit','changed_hit'):raise ValueError('Unknown trigger condition')
        interval=max(15,min(int(data.get('interval_minutes',old.get('interval_minutes',120))),10080))
        reset=query!=old.get('query') or selected!=old.get('services') or condition!=old.get('condition') or text(data.get('required_text',''))!=old.get('required_text','')
        rule={**old, 'id':old.get('id') or digest(query+now()+str(time.time_ns()))[:20], 'query':query,
          'services':selected,'condition':condition,'interval_minutes':interval,'enabled':bool(data.get('enabled',True)),
          'created_at':old.get('created_at',now()),'updated_at':now(), 'revision':str(time.time_ns()), 'required_text':text(data.get('required_text',''))[:160]}
        if reset:rule.update(seen={},baselines=[],last_checked=None,status='pending')
        with self.store.connect() as c:c.execute('INSERT OR REPLACE INTO monitors VALUES (?,?)',(rule['id'],json.dumps(rule)))
        return rule
    def run(self,rule_id):
        if not self.lock.acquire(blocking=False):raise ValueError('A monitoring check is already running')
        try:
            rule=next((x for x in self.list() if x['id']==rule_id),None)
            if not rule:raise KeyError('Monitor not found')
            seen=rule.get('seen',{});baselines=set(rule.get('baselines',[]));statuses=[];alerts=[]
            for service in rule['services']:
                try:
                    if service=='cipc':
                        sources=[s['id'] for s in self.store.sources() if 'cipc' in s['name'].lower()]
                        if not sources:raise ValueError('CIPC source unavailable')
                        rows=[]
                        for sid in sources:rows+=self.store.search(q=rule['query'],source_id=sid,limit=100)['results']
                        statuses.append({'service':service,'status':'indexed_only','detail':'Checks imported/previously collected disclosures; no automatic registry connection.'})
                    elif service=='tenders':
                        data=self.services.tenders(rule['query']);rows=[{'id':str(x.get('id',digest(json.dumps(x,sort_keys=True))[:24])),'url':TENDERPORTAL,'title':text(str(x.get('description',x.get('tenderDescription','Tender')))),'content_hash':digest(json.dumps(x,sort_keys=True))} for x in data['results']]
                        statuses.append({'service':service,'status':'completed'})
                    else:
                        data=self.services.discover(rule['query'],'all' if service=='web' else service,True)
                        if not any(s['status']=='completed' for s in data['statuses']):raise ValueError('Provider unavailable; baseline preserved')
                        rows=data['results'];statuses.append({'service':service,'status':'completed'})
                    for hit in rows:
                        if rule.get('required_text') and rule['required_text'].casefold() not in json.dumps(hit,ensure_ascii=False).casefold():continue
                        key=service+':'+hit['id'];signature=hit.get('content_hash') or digest(json.dumps(hit,sort_keys=True))
                        previous=seen.get(key)
                        changed=(previous is None) if rule['condition']=='new_hit' else previous is not None and previous!=signature
                        if service in baselines and changed:
                            alert={'id':digest(rule_id+key+signature)[:24],'rule_id':rule_id,'query':rule['query'],'service':service,
                                   'condition':rule['condition'],'hit':hit,'created_at':now(),'read':False}
                            with self.store.connect() as c:
                                cursor=c.execute('INSERT OR IGNORE INTO alerts VALUES (?,?)',(alert['id'],json.dumps(alert)))
                                if cursor.rowcount:alerts.append(alert)
                        seen[key]=signature
                    baselines.add(service)
                except Exception as e:statuses.append({'service':service,'status':'unavailable','detail':str(e)[:240]})
            # Preserve a concurrent user's edit/pause instead of replacing it with a stale check.
            latest=next(x for x in self.list() if x['id']==rule_id)
            if latest.get('revision')==rule.get('revision'):
                rule.update(seen=seen,baselines=sorted(baselines),last_checked=now(),statuses=statuses,
                    status='checked' if any(s['status'] in ('completed','indexed_only') for s in statuses) else 'unavailable')
                with self.store.connect() as c:c.execute('UPDATE monitors SET data=? WHERE id=?',(json.dumps(rule),rule_id))
            return {'rule':rule,'new_alerts':alerts,'baseline_note':'First successful check per service establishes a baseline; only subsequent changes trigger alerts.'}
        finally:self.lock.release()
    def mark_read(self):
        with self.store.connect() as c:
            for row in c.execute('SELECT id,data FROM alerts').fetchall():
                a=json.loads(row['data']);a['read']=True;c.execute('UPDATE alerts SET data=? WHERE id=?',(json.dumps(a),row['id']))
    def loop(self):
        while not self.stop.wait(30):
            for rule in self.list():
                if self.stop.is_set():return
                last=rule.get('last_checked');due=not last or (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(last)).total_seconds()>=rule['interval_minutes']*60
                if rule['enabled'] and due:
                    try:self.run(rule['id'])
                    except Exception:pass
