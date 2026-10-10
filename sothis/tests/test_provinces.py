import datetime as dt
import hashlib
import json
import unittest
from pathlib import Path
from engine.provinces import FEED, ProvinceNews, parse_feed, select_news, snapshot, province


class ProvinceTests(unittest.TestCase):
    def fixture(self):
        return b'''<rss><channel>
        <item><title>Eastern Cape public notice</title><link>https://www.sanews.gov.za/node/1</link><description>Gqeberha statement</description><pubDate>Fri, 09 Oct 2026 12:00:00 +0200</pubDate></item>
        <item><title>Eastern Cape old news</title><link>https://www.sanews.gov.za/node/2</link><pubDate>Fri, 01 May 2026 12:00:00 +0200</pubDate></item>
        <item><title>Eastern Cape no date</title><link>https://www.sanews.gov.za/node/3</link></item>
        <item><title>Eastern Cape future notice</title><link>https://www.sanews.gov.za/node/4</link><pubDate>Fri, 09 Oct 2027 12:00:00 +0200</pubDate></item>
        <item><title>Western Cape notice</title><link>https://www.sanews.gov.za/node/5</link><pubDate>Fri, 09 Oct 2026 12:00:00 +0200</pubDate></item>
        <item><title>Eastern Cape hostile link</title><link>https://example.com/news</link></item>
        <item><title>Eastern Cape duplicate</title><link>https://www.sanews.gov.za/node/1#duplicate</link><pubDate>Fri, 09 Oct 2026 12:00:00 +0200</pubDate></item>
        </channel></rss>'''

    def test_dated_indicators_and_denominators(self):
        data=snapshot();self.assertEqual(len(data['provinces']),9)
        self.assertEqual(data['sources']['population']['period'],'Census 2022')
        self.assertEqual(data['sources']['labour']['published_at'],'2026-08-11')
        for p in data['provinces']:
            self.assertAlmostEqual(p['labour']['employed_thousands']/p['labour']['working_age_thousands']*100,p['labour']['absorption'],delta=.12)
            self.assertAlmostEqual(p['nsc']['achieved']/p['nsc']['wrote']*100,p['nsc']['pass_rate'],delta=.01)
            self.assertNotEqual(p['labour']['absorption'],100-p['labour']['unemployment'])
        self.assertEqual(province('Western Cape')['population'],7433019)

    def test_education_sectors_and_registry_provenance(self):
        data=snapshot();self.assertEqual(sum(len(p['universities']) for p in data['provinces']),26)
        self.assertEqual(sum(len(p['tvet_colleges']) for p in data['provinces']),50)
        self.assertEqual(next(s for s in data['education_outcomes'] if s['id']=='ieb')['geography'],'National IEB candidates')
        registers=json.loads((Path(__file__).resolve().parent.parent/'android/app/src/main/assets/education-registers.json').read_text())['registers']
        self.assertEqual([r['updated_at'] for r in registers],['2026-08-12','2026-09-16'])
        self.assertEqual([len(r['pages']) for r in registers],[212,99])
        self.assertTrue(all(len(r['pdf_sha256'])==64 for r in registers))
        for register in registers:
            for page in register['pages']:
                self.assertEqual(hashlib.sha256(page['text'].encode()).hexdigest(),page['text_hash'])
                self.assertEqual(len(page['source_text_hash']),64)
        self.assertIn('cancellation',registers[0]['coverage'])

    def test_feed_dates_hosts_deduplication_and_hash(self):
        items=parse_feed(self.fixture(),'2026-10-10T00:00:00Z')
        self.assertEqual(len(items),5);self.assertFalse(any('example.com' in h['url'] for h in items))
        h=next(h for h in items if h['url'].endswith('/1'))
        self.assertEqual(h['published_at'],'2026-10-09T10:00:00Z')
        self.assertEqual(h['content_hash'],hashlib.sha256((h['title']+'\n'+h['description']).encode()).hexdigest())
        self.assertEqual(h['acquisition'],'publisher_feed')

    def test_location_and_window_exclude_future_old_and_undated(self):
        results,undated=select_news(parse_feed(self.fixture()),'Eastern Cape',30,dt.date(2026,10,10))
        self.assertEqual(len(results),1);self.assertEqual(len(undated),1)
        results,_=select_news(parse_feed(self.fixture()),'Eastern Cape',0,dt.date(2026,10,10))
        self.assertEqual(len(results),2)
        for invalid in ['Eastern Cape?url=http://127.0.0.1','Atlantis']:
            with self.assertRaises(ValueError):province(invalid)
        with self.assertRaises(ValueError):select_news([], 'Eastern Cape',True)

    def test_feed_rejects_entities_and_non_feed_responses(self):
        for bad in [b'<!DOCTYPE rss [<!ENTITY e "test">]><rss/>',b'<html><body>blocked</body></html>',b'x'*(2*1024*1024+1)]:
            with self.assertRaises(ValueError):parse_feed(bad)

    def test_feed_cache_and_separate_discovery_fallback(self):
        reads=[];searches=[]
        class Services:
            def discover(self,*args,**kwargs):searches.append(args);return {'results':[{'title':'Index candidate','published_at':None}],'statuses':[]}
        service=ProvinceNews(Services(),lambda url:reads.append(url) or self.fixture())
        # Fixture publication may age; zero days always retains past items.
        service.news('Eastern Cape',0);service.news('Western Cape',0)
        self.assertEqual(reads,[FEED]);self.assertEqual(searches,[])
        result=service.news('Limpopo',0);self.assertEqual(result['results'],[])
        self.assertIsNone(result['candidates'][0]['published_at']);self.assertEqual(searches[0][0],'Limpopo')
        service.news('Eastern Cape',0,True);self.assertEqual(len(reads),2)

    def test_failed_feed_is_visible_and_search_can_still_return(self):
        class Services:
            def discover(self,*args,**kwargs):return {'results':[],'statuses':[{'service':'Search','status':'unavailable'}]}
        def blocked(url):raise ValueError('Publisher unavailable')
        result=ProvinceNews(Services(),blocked).news('Eastern Cape')
        self.assertEqual(result['statuses'][0]['status'],'unavailable')
        self.assertEqual(result['results'],[])

if __name__=='__main__':unittest.main()
