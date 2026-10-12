import json
import tempfile
import unittest
from engine.core import Store
from engine.connectors import source_record
from engine.services import PublicServices,Monitoring,registration,profile

HTML='''<a class="result l1" href="https://instagram.com/alexexample/?hl=en"><div class="title">Alex Example (@alexexample)</div>Alex Example artist</a><a class="l1" href="https://instagram.com/alexexample/"><div class="title">Alex Example</div></a><a class="l1" href="https://facebook.com/alexexample/posts/123"><div class="title">Alex Example in the news</div></a><a class="l1" href="https://linkedin.com/in/wrong-person"><div class="title">Somebody Else</div></a>'''
class ServiceTests(unittest.TestCase):
    def test_registration_identifiers(self):
        for q in ('2023/662808/07','202366280807','2023-662808-07',' 2023 / 662808 / 07 '):self.assertEqual(registration(q),'2023/662808/07')
        self.assertIsNone(registration('2023662808'))
    def test_discovery_filters_dedupes_and_preserves_ambiguity(self):
        service=PublicServices(lambda u,h=None:HTML)
        r=service.discover('Alex Example')
        self.assertEqual(r['hit_count'],2);self.assertEqual(r['account_count'],1)
        self.assertEqual(r['results'][0]['ownership'],'unreviewed')
        self.assertIn('not identity',r['results'][0]['match_reason'])
        self.assertTrue(service.discover('Alex Example')['cached'])
    def test_posts_share_urls_never_inflate_account_count(self):
        for u in ('https://instagram.com/p/abc','https://facebook.com/person/posts/123','https://x.com/name/status/1','https://tiktok.com/discover/alex','https://linkedin.com/company/example','https://facebook.com/sharer.php?u=x'):
            self.assertIsNone(profile(u),u)
        self.assertEqual(profile('https://linkedin.com/in/alex'),'LinkedIn')
    def test_public_search_falls_back_without_bypassing_challenge(self):
        calls=[]
        def reader(u,h=None):
            calls.append(u)
            if 'brave.com' in u:raise ValueError('HTTP 429')
            return '<a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ffacebook.com%2Falexexample%2F&amp;rut=test">Alex Example</a>'
        r=PublicServices(reader).discover('Alex Example')
        self.assertEqual(r['account_count'],1);self.assertEqual(len(calls),2)
    def test_provider_failure_is_visible_and_not_company_nonexistence(self):
        def failure(u,h=None):raise ValueError('HTTP 429')
        r=PublicServices(failure).discover('202366280807')
        self.assertEqual(r['registration_number'],'2023/662808/07')
        self.assertEqual(r['cipc']['status'],'authorised_access_required')
        self.assertTrue(all(s['status']=='unavailable' for s in r['statuses']))
    def test_tender_api_passes_real_search_and_status(self):
        calls=[]
        def reader(u,h=None):calls.append(u);return json.dumps({'data':[{'id':1,'description':'Construction services','eSubmission':False}],'recordsFiltered':15})
        r=PublicServices(reader).tenders('construction','awarded',30)
        self.assertIsNone(r['total']);self.assertEqual(r['provider_total'],15);self.assertEqual(len(r['results']),1);self.assertIn('status=2',calls[0]);self.assertIn('start=30',calls[0]);self.assertIn('construction',calls[0])
    def test_alert_baseline_dedupe_failure_and_changed_trigger(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);body=[HTML]
            def reader(u,h=None):
                if body[0]=='FAIL':raise ValueError('Provider offline')
                return body[0]
            monitors=Monitoring(store,PublicServices(reader));monitors.stop.set()
            rule=monitors.save({'query':'Alex Example','services':['social'],'condition':'new_hit'})
            self.assertFalse(monitors.run(rule['id'])['new_alerts'])
            body[0]='FAIL';self.assertFalse(monitors.run(rule['id'])['new_alerts'])
            body[0]=HTML+'<a class="l1" href="https://tiktok.com/@alexexample"><div class="title">Alex Example</div></a>'
            self.assertEqual(len(monitors.run(rule['id'])['new_alerts']),1)
            self.assertFalse(monitors.run(rule['id'])['new_alerts'])
            monitors.mark_read();self.assertTrue(monitors.list('alerts')[0]['read'])
            changed=monitors.save({**rule,'condition':'changed_hit'});self.assertFalse(monitors.run(changed['id'])['new_alerts'])
            body[0]=body[0].replace('Alex Example artist','Alex Example broadcaster')
            self.assertEqual(len(monitors.run(changed['id'])['new_alerts']),1)
    def test_cipc_monitor_watches_only_imported_records(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);source=source_record('CIPC','https://eservices.cipc.co.za/','National','company',access='login_required',enabled=False);store.seed_sources([source])
            monitor=Monitoring(store,PublicServices(lambda u,h=None:HTML));monitor.stop.set()
            r=monitor.save({'query':'Alex Example','services':['cipc']});self.assertFalse(monitor.run(r['id'])['new_alerts'])
            store.put_document(source,'https://eservices.cipc.co.za/disclosure/example','Example company disclosure','Alex Example is mentioned in this imported company disclosure. Authenticity and relationship require review.',acquisition='manual_import')
            result=monitor.run(r['id']);self.assertEqual(len(result['new_alerts']),1);self.assertEqual(result['rule']['statuses'][0]['status'],'indexed_only')
    def test_compact_number_searches_imported_company_text(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);source=source_record('CIPC','https://eservices.cipc.co.za/','National','company',access='login_required',enabled=False);store.seed_sources([source])
            store.put_document(source,'https://eservices.cipc.co.za/disclosure/company','Company record','Registration 2023/662808/07. A manually imported company record for review.',acquisition='manual_import')
            self.assertEqual(store.search('202366280807')['total'],1)
            self.assertEqual(store.search('2023-662808-07')['total'],1)
    def test_supplier_awards_use_official_company_filter(self):
        urls=[]
        service=PublicServices(lambda u,h=None:urls.append(u) or '{"data":[],"recordsFiltered":0}')
        service.tenders('Example Company','awarded',0,'company')
        self.assertIn('/Home/TenderFilter/',urls[0]);self.assertIn('company=Example+Company',urls[0]);self.assertIn('status=2',urls[0])
if __name__=='__main__':unittest.main()
