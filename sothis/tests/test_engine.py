import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from engine.core import Store
from engine.connectors import Page, Connector, source_record, public_url, GuardedRedirect, extract
from engine.server import LensServer
from web.runtime import APIAdapter

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        self.wc=source_record('WC','https://www.westerncape.gov.za/','Western Cape')
        self.ec=source_record('EC','https://ecprov.gov.za/','Eastern Cape')
        self.n=source_record('Parliament','https://www.parliament.gov.za/','National','interests')
        self.store.seed_sources([self.wc,self.ec,self.n])
        self.id=self.store.put_document(self.wc,'https://www.westerncape.gov.za/a','Geordin Hill-Lewis statement','Geordin Hill-Lewis appears in this public government statement about transport funding.', '2026-01-01')
        self.store.put_document(self.ec,'https://ecprov.gov.za/a','EC vacancies','An advertised jobs notice in Eastern Cape provincial government.', '2025-01-01',category='jobs')
        self.store.put_document(self.n,'https://www.parliament.gov.za/a','Register','Geordin Hill-Lewis is mentioned in a historical register of members interests.', '2020-01-01')
    def tearDown(self):self.tmp.cleanup()
    def test_region_query_is_filter(self):
        r=self.store.search('Western Cape');self.assertEqual(r['total'],1);self.assertEqual(r['effective_query'],'')
    def test_region_category_dates(self):
        self.assertEqual(self.store.search('Geordin Hill-Lewis','Western Cape',after='2026-01-01')['total'],1)
        self.assertEqual(self.store.search('Geordin Hill-Lewis','Western Cape',before='2025-12-31')['total'],0)
        self.assertEqual(self.store.search('','Eastern Cape','jobs')['total'],1)
        self.assertEqual(self.store.search('Geordin Hill-Lewis','Western Cape',include_national=True)['total'],2)
    def test_name_and_fts_escaping(self):
        self.assertEqual(self.store.search('" OR * DROP TABLE documents; --')['total'],0)
        r=self.store.search('Jordan Hill Lewis');self.assertEqual(r['total'],0);self.assertTrue(r['suggestions'])
    def test_versions_dedupe(self):
        self.store.put_document(self.wc,'https://www.westerncape.gov.za/a','Update','Geordin Hill-Lewis appears in a changed transport announcement with updated funding figures.')
        self.assertEqual(self.store.stats()['documents'],3)
        self.assertEqual(len(self.store.document(self.id)['versions']),2)
    def test_case_pins_export(self):
        c=self.store.save_case({'title':'Transport investigation','pins':[self.id],'notes':'Review original.'})
        report=self.store.export(c['id']);self.assertIn('https://www.westerncape.gov.za/a',report);self.assertIn('SHA-256',report)
        with self.assertRaises(ValueError):self.store.save_case({'title':'Bad','pins':['absent']})
    def test_html_parser(self):
        p=Page();p.feed('<html><title>Test</title><meta property="article:published_time" content="2026-02-03T11:00:00Z"><nav>Ignore navigation</nav><main><p>A real public document containing useful searchable text.</p><a href="/news">News</a></main></html>')
        self.assertNotIn('Ignore navigation',p.text);self.assertEqual(p.date,'2026-02-03');self.assertIn(('/news','News'),p.links)
    def test_social_links_are_publisher_candidates(self):
        raw=b'<title>Public statement</title><main>A sufficiently long government statement mentioning an office bearer.</main><a href="https://x.com/Department">Follow</a>'
        ids,_=extract(self.store,self.wc,'https://www.westerncape.gov.za/social',raw,'text/html')
        self.assertIn('ownership unverified',self.store.document(ids[0])['social_links'][0]['status'])
    def test_private_urls_and_off_allowlist(self):
        with self.assertRaises(ValueError):public_url('https://evil.example/',{'www.gov.za'})
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):public_url('https://www.gov.za/',{'www.gov.za'})
    def test_auth_and_http_round_trip(self):
        server=LensServer(('127.0.0.1',0),self.store,'test-token')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1])
        try:
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url+'/api/health')
            self.assertEqual(e.exception.code,401)
            e.exception.close()
            req=urllib.request.Request(url+'/api/search?q=Geordin',headers={'Authorization':'Bearer test-token'})
            with urllib.request.urlopen(req) as response:
                self.assertEqual(json.load(response)['total'],2)
            req=urllib.request.Request(url+'/api/cases',json.dumps({'title':'API investigation','pins':[self.id]}).encode(),{'Authorization':'Bearer test-token','Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:
                case=json.load(response)
            req=urllib.request.Request(url+'/api/cases/'+case['id']+'/export',headers={'Authorization':'Bearer test-token'})
            with urllib.request.urlopen(req) as response:
                self.assertIn('Evidence register',json.load(response)['content'])
        finally:server.shutdown();server.server_close()
    def test_remote_binding_requires_token(self):
        with self.assertRaises(ValueError):LensServer(('0.0.0.0',0),self.store)
    def test_discovery_forwards_only_boolean_refresh(self):
        discover=Mock(return_value={'results':[]})
        adapter=APIAdapter(SimpleNamespace(store=self.store,services=SimpleNamespace(discover=discover)))
        for value in (True,False,'true',1,None):
            with self.subTest(refresh=value):
                discover.reset_mock()
                adapter.api('POST','/api/discover',{}, {'query':'Public query','scope':'web','topic':'transport','refresh':value})
                discover.assert_called_once_with('Public query','web',fresh=value is True,topic='transport')
                self.assertEqual(adapter.response[0],200)
        discover.reset_mock()
        adapter.api('POST','/api/discover',{}, {'query':'Public query'})
        discover.assert_called_once_with('Public query','all',fresh=False,topic='')
    def test_gated_source_never_fetches(self):
        s=source_record('CIPC','https://www.bizportal.gov.za/',access='login_required',enabled=False)
        self.store.seed_sources([s]);r=Connector(self.store).crawl(s['id']);self.assertEqual(r['fetched'],0)
    def test_crawler_path_scope(self):
        s=source_record('Scoped directory','https://www.gov.za/western-cape/',province='Western Cape',path_prefixes=['/western-cape/'])
        self.store.seed_sources([s])
        class MockFetcher:
            def __init__(self):self.urls=[]
            def fetch(self,url,hosts):
                self.urls.append(url)
                return (b'<title>Public directory</title><main>A useful public directory with enough extractable text to index.</main><a href="/national-news">Unrelated national news</a><a href="/western-cape/document">Scoped document</a>','text/html',url,'utf-8')
        fetcher=MockFetcher();r=Connector(self.store,fetcher).crawl(s['id'],5,1)
        self.assertEqual(r['indexed'],2);self.assertNotIn('https://www.gov.za/national-news',fetcher.urls)
    def test_share_links_are_not_accounts(self):
        raw=b'<title>Record</title><main>A government record with sufficiently long text to index properly.</main><a href="https://twitter.com/intent/tweet">Share</a><a href="https://x.com/OfficialPublisher">Account</a>'
        ids,_=extract(self.store,self.wc,'https://www.westerncape.gov.za/share',raw,'text/html')
        links=self.store.document(ids[0])['social_links']
        self.assertEqual(len(links),1);self.assertEqual(links[0]['url'],'https://x.com/OfficialPublisher')
    def test_pdf_pages_and_ocr_signal(self):
        from pypdf import PdfWriter
        import io
        writer=PdfWriter();writer.add_blank_page(width=200,height=200);out=io.BytesIO();writer.write(out)
        with self.assertRaisesRegex(ValueError,'OCR required'):
            extract(self.store,self.n,'https://www.parliament.gov.za/scanned.pdf',out.getvalue(),'application/pdf')

class ConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def assert_closed(self,connection):
        with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
            connection.execute('SELECT 1')

    def test_transaction_commits_and_closes(self):
        connection=self.store.connect()
        self.assertIsInstance(connection,sqlite3.Connection)
        with connection as db:
            db.execute('INSERT INTO cases VALUES (?,?)',('committed','{"title":"Committed"}'))
            self.assertIsInstance(db.execute('SELECT * FROM cases').fetchone(),sqlite3.Row)
        self.assert_closed(connection)
        self.assertEqual(self.store.cases(),[{'title':'Committed'}])

    def test_transaction_rolls_back_and_closes(self):
        connection=self.store.connect()
        with self.assertRaisesRegex(RuntimeError,'failed operation'):
            with connection as db:
                db.execute('INSERT INTO cases VALUES (?,?)',('rolled-back','{}'))
                raise RuntimeError('failed operation')
        self.assert_closed(connection)
        self.assertEqual(self.store.cases(),[])

    def test_commit_failure_rolls_back_and_closes(self):
        connection=self.store.connect()
        with self.assertRaises(sqlite3.IntegrityError):
            with connection as db:
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('CREATE TABLE parents(id INTEGER PRIMARY KEY)')
                db.execute('CREATE TABLE children(parent INTEGER REFERENCES parents(id) DEFERRABLE INITIALLY DEFERRED)')
                db.execute('INSERT INTO children VALUES (99)')
        self.assert_closed(connection)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM children').fetchone()[0],0)

    def test_internal_failure_closes_and_rolls_back_partial_work(self):
        connections=[]
        original=self.store.connect
        def record():
            connection=original();connections.append(connection);return connection
        source=source_record('Transaction fixture','https://www.gov.za/')
        with patch.object(self.store,'connect',side_effect=record):
            with self.assertRaises(KeyError):
                self.store.seed_sources([source,{}])
        self.assertTrue(connections)
        for connection in connections:self.assert_closed(connection)
        self.assertEqual(self.store.sources(),[])

    def test_raw_connection_still_allows_explicit_lifetime(self):
        connection=self.store.connect()
        try:
            connection.execute('INSERT INTO cases VALUES (?,?)',('direct','{"title":"Direct"}'))
            connection.commit()
            self.assertEqual(connection.execute('SELECT count(*) FROM cases').fetchone()[0],1)
        finally:
            connection.close()
        self.assert_closed(connection)
        self.assertEqual(self.store.cases(),[{'title':'Direct'}])

    def test_threads_keep_independent_connections(self):
        barrier=threading.Barrier(4)
        def read(_):
            with self.store.connect() as connection:
                barrier.wait(timeout=5)
                self.assertEqual(connection.execute('SELECT count(*) FROM cases').fetchone()[0],0)
            self.assert_closed(connection)
            return connection
        with ThreadPoolExecutor(max_workers=4) as workers:
            connections=list(workers.map(read,range(4)))
        self.assertEqual(len({id(connection) for connection in connections}),4)

if __name__=='__main__':unittest.main()
