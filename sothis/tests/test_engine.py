import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from engine.core import Store
from engine.connectors import Page, Connector, source_record, public_url, GuardedRedirect, extract
from engine.server import LensServer

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
            req=urllib.request.Request(url+'/api/search?q=Geordin',headers={'Authorization':'Bearer test-token'})
            self.assertEqual(json.load(urllib.request.urlopen(req))['total'],2)
            req=urllib.request.Request(url+'/api/cases',json.dumps({'title':'API investigation','pins':[self.id]}).encode(),{'Authorization':'Bearer test-token','Content-Type':'application/json'})
            case=json.load(urllib.request.urlopen(req))
            req=urllib.request.Request(url+'/api/cases/'+case['id']+'/export',headers={'Authorization':'Bearer test-token'})
            self.assertIn('Evidence register',json.load(urllib.request.urlopen(req))['content'])
        finally:server.shutdown();server.server_close()
    def test_remote_binding_requires_token(self):
        with self.assertRaises(ValueError):LensServer(('0.0.0.0',0),self.store)
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

if __name__=='__main__':unittest.main()
