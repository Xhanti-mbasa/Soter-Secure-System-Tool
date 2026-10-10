import hmac
import mimetypes
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .connectors import Connector
from .core import now, digest
from .services import PublicServices, Monitoring
from .parties import PartyService

class LensServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, store, token='', web_dir=None):
        if address[0] not in ('127.0.0.1','localhost','::1') and len(token) < 24:
            raise ValueError('A token of at least 24 characters is required when listening beyond localhost')
        super().__init__(address, Handler)
        self.store, self.token = store, token
        self.web_dir = Path(web_dir) if web_dir else None
        self.job = None
        self.job_lock = threading.Lock()
        self.services = PublicServices()
        self.parties = PartyService()
        from .provinces import ProvinceNews
        self.province_news = ProvinceNews(self.services)
        from engine.daily import DailyService
        self.daily = DailyService()
        self.monitoring = Monitoring(store,self.services)

    def server_close(self):
        self.monitoring.stop.set()
        super().server_close()

class Handler(BaseHTTPRequestHandler):
    server_version = 'ZALens/0.1'
    def log_message(self, fmt, *args):
        # Do not log query strings, tokens, case notes, or document bodies.
        pass

    def send(self, status, body, mime='application/json; charset=utf-8'):
        if isinstance(body, (dict,list)): body = json.dumps(body,ensure_ascii=False).encode()
        elif isinstance(body,str): body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')

    def route(self, method):
        try:
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            if path.startswith('/api/'):
                expected = self.server.token
                got = self.headers.get('Authorization','')
                if expected and not hmac.compare_digest(got,'Bearer '+expected):
                    return self.send(401,{'error':'Engine access token required'})
                if method == 'POST':
                    if self.headers.get_content_type() != 'application/json':
                        return self.send(415,{'error':'Use application/json'})
                    length = int(self.headers.get('Content-Length','0'))
                    if not 0 < length <= 2*1024*1024:
                        return self.send(413,{'error':'Request size limit is 2 MiB'})
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data,dict): raise ValueError('JSON object required')
                else: data = {}
                return self.api(method,path,urllib.parse.parse_qs(parsed.query),data)
            public_files = ('/','/index.html','/snapshot.json','/features.js','/parties.js','/party-data.json','/visuals.js','/nothing.css','/photo-credits.json','/analytics.js','/analytics.css','/analytics-data.json','/navigation.js','/provinces.js','/provinces.css','/province-data.json','/education-registers.json','/company-details.js','/daily.js','/personal.js','/share-cards.js','/daily.css','/vendor/pdf.js','/vendor/pdf.worker.js')
            resource = path.startswith(('/images/','/fonts/','/icons/')) and Path(path).suffix.lower() in ('.webp','.jpg','.png','.svg','.ttf','.woff2')
            if method == 'GET' and self.server.web_dir and (path in public_files or resource):
                name = 'index.html' if path in ('/','/index.html') else path.lstrip('/')
                root = self.server.web_dir.resolve()
                file = (root/name).resolve()
                if root in file.parents and file.is_file():
                    mime = {'css':'text/css','js':'application/javascript','ttf':'font/ttf'}.get(file.suffix.lstrip('.'),mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
                    return self.send(200,file.read_bytes(),mime)
            self.send(404,{'error':'Not found'})
        except KeyError as e: self.send(404,{'error':str(e)})
        except (ValueError,TypeError,json.JSONDecodeError) as e: self.send(400,{'error':str(e)[:250]})
        except Exception: self.send(500,{'error':'Engine error. Check local engine state.'})

    def api(self, method, path, params, data):
        store = self.server.store
        if method == 'GET' and path == '/api/health':
            return self.send(200,{'ok':True,'version':'0.7.0',**store.stats()})
        if path in ('/api/daily/news', '/api/daily/opportunities') and method == 'POST':
            return self.send(200,self.server.daily.collect(path.rsplit('/',1)[-1],data))
        if path == '/api/daily/article' and method == 'POST':
            return self.send(200,self.server.daily.news_provider.article(data.get('url','')))
        if path == '/api/provinces' and method == 'GET':
            from .provinces import snapshot
            return self.send(200,snapshot())
        if path == '/api/province/news' and method == 'POST':
            result=self.server.province_news.news(data.get('province',''),data.get('days',30),data.get('refresh') is True)
            from .connectors import source_record
            feed_source=source_record('SAnews public news','https://www.sanews.gov.za/','National','news')
            index_source=source_record('Public web discovery','https://search.brave.com/','National','news')
            store.seed_sources([feed_source,index_source])
            for hit in result['results']+result['undated']+result['candidates']:
                is_feed=hit.get('acquisition')=='publisher_feed'
                description=hit['title']+'\n'+hit.get('description','')+'\nPublished: '+str(hit.get('published_at') or 'Unavailable')+'\n'+('Publisher feed; province location mention.' if is_feed else 'Public search-index candidate; publication date and identity require review.')
                hit['document_id']=store.put_document(feed_source if is_feed else index_source,hit['url'],hit['title'],description,hit.get('published_at'),acquisition='publisher_feed' if is_feed else 'search_index',category='news')
            return self.send(200,result)
        if path == '/api/analytics' and method == 'GET':
            from .analytics import snapshot
            return self.send(200,snapshot())
        if path == '/api/publication' and method == 'POST':
            from .publications import publication
            return self.send(200,publication(data.get('url','')))
        if path == '/api/parties' and method == 'GET':
            return self.send(200,self.server.parties.catalog(params.get('q',[''])[0]))
        if path == '/api/party' and method == 'POST':
            return self.send(200,self.server.parties.party(data.get('code',''),data.get('refresh') is True))
        if path == '/api/member' and method == 'POST':
            return self.send(200,self.server.parties.member(data.get('id',''),data.get('refresh') is True))
        if path == '/api/discover' and method == 'POST':
            result = self.server.services.discover(data.get('query',''),data.get('scope','all'),topic=data.get('topic',''))
            # Persist index metadata as evidence, distinct from downloaded originals.
            from .connectors import source_record
            source = source_record('Public web discovery','https://search.brave.com/','National','news')
            store.seed_sources([source])
            for hit in result['results']:
                description = hit['title']+'\n'+hit['description']+'\nSearch-index candidate. Account ownership unverified.'
                hit['document_id'] = store.put_document(source,hit['url'],hit['title'],description,
                    acquisition='search_index',category='government' if hit['category']=='government' else 'news')
            return self.send(200,result)
        if path == '/api/tenders' and method == 'POST':
            return self.send(200,self.server.services.tenders(data.get('query',''),data.get('status','open'),data.get('start',0),data.get('search_by','keyword')))
        if path == '/api/monitors':
            if method == 'GET':return self.send(200,self.server.monitoring.list())
            return self.send(201,self.server.monitoring.save(data))
        if path == '/api/monitors/check' and method == 'POST':
            return self.send(200,self.server.monitoring.run(data.get('id','')))
        if path == '/api/alerts':
            if method == 'POST':self.server.monitoring.mark_read()
            return self.send(200,self.server.monitoring.list('alerts'))
        if path == '/api/evidence' and method == 'POST':
            from .connectors import Fetcher,canonical
            import hashlib
            url=canonical(data.get('url',''));host=urllib.parse.urlsplit(url).hostname
            raw,mime,final,charset=Fetcher().fetch(url,{host})
            sha=hashlib.sha256(raw).hexdigest();(store.root/'archive'/sha).write_bytes(raw)
            return self.send(201,{'url':final,'sha256':sha,'bytes':len(raw),'mime':mime,'retrieved_at':now(),'location':'engine_archive'})
        if method == 'GET' and path == '/api/sources': return self.send(200,store.sources())
        if method == 'GET' and path == '/api/search':
            allowed = ('q','province','category','source_id','after','before','sort','offset','limit')
            kwargs = {k:params[k][0] for k in allowed if k in params}
            kwargs['include_national'] = params.get('include_national',['false'])[0]=='true'
            return self.send(200,store.search(**kwargs))
        if method == 'GET' and path.startswith('/api/documents/'):
            doc = store.document(path.rsplit('/',1)[-1])
            if not doc: raise KeyError('Document not found')
            return self.send(200,doc)
        if path == '/api/cases':
            if method == 'GET': return self.send(200,store.cases())
            if method == 'POST': return self.send(201,store.save_case(data))
        if path.startswith('/api/cases/'):
            parts = path.strip('/').split('/')
            case_id = parts[2]
            if len(parts)==4 and parts[3]=='export' and method=='GET':
                fmt = params.get('format',['md'])[0]
                return self.send(200,{'content':store.export(case_id,fmt),'format':fmt})
            if len(parts)==3:
                if method=='POST': return self.send(200,store.save_case(data,case_id))
                case = next((c for c in store.cases() if c['id']==case_id),None)
                if not case: raise KeyError('Investigation not found')
                return self.send(200,case)
        if path=='/api/import' and method=='POST':
            source = store.source(data.get('source_id'))
            if not source: raise ValueError('A registered source_id is required')
            from .connectors import canonical
            url = canonical(data.get('url',''))
            # A disclosure imported from a portal can lack a unique downloadable URL.
            # Keep an explicit local import anchor, distinct from an official record ID.
            record_key=str(data.get('record_key',''))
            if record_key:
                import re
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',record_key):raise ValueError('Invalid local import key')
                url+='#sothis-import-'+record_key
            text = str(data.get('text',''))
            doc_id = store.put_document(source,url,str(data.get('title','Imported record')),text,
                                        data.get('published_at'),page=data.get('page'),acquisition='manual_import')
            return self.send(201,{'id':doc_id,'status':'Imported; source authenticity and identity require review'})
        if path=='/api/jobs' and method=='GET':
            with self.server.job_lock: job = self.server.job
            return self.send(200,job or {'status':'idle'})
        if path=='/api/crawl' and method=='POST':
            ids = data.get('source_ids',[])
            if not isinstance(ids,list) or not 1 <= len(ids) <= 10:
                raise ValueError('Choose 1–10 registered source IDs')
            if any(not store.source(s) for s in ids): raise ValueError('Unknown source ID')
            pages = min(max(int(data.get('pages',5)),1),10)
            with self.server.job_lock:
                if self.server.job and self.server.job['status']=='running':
                    return self.send(409,{'error':'A collection job is already running'})
                job = {'id':digest(now())[:16],'status':'running','started_at':now(),'results':[]}
                self.server.job=job
            def work():
                connector = Connector(store)
                try:
                    for source_id in ids:
                        with self.server.job_lock: job.update(current_source=source_id,current_url=store.source(source_id)['url'])
                        def progress(url,fetched,indexed):
                            with self.server.job_lock:job.update(current_url=url,fetched=fetched,indexed=indexed)
                        result = connector.crawl(source_id,pages,1,progress=progress)
                        with self.server.job_lock: job['results'].append(result)
                    with self.server.job_lock: job.update(status='completed',finished_at=now())
                except Exception as e:
                    with self.server.job_lock: job.update(status='failed',error=str(e)[:250])
            threading.Thread(target=work,daemon=True).start()
            return self.send(202,job)
        self.send(404,{'error':'API route not found'})
