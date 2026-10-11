import datetime as dt
import unittest
from engine.daily import DailyService, JobsProvider, NewsProvider, ProviderCache, EC_URL
from engine.provinces import FEED

RSS=b'''<rss><channel><item><title>Eastern Cape libraries</title><link>https://www.sanews.gov.za/node/123</link><description>Library programme in Gqeberha</description><pubDate>Fri, 09 Oct 2026 12:00:00 +0200</pubDate></item></channel></rss>'''
JOB=b'''<table><tr><td><span id="gvAllJobs_ctl02_lblJobTitle">Library <b>Assistant</b></span><span id="gvAllJobs_ctl02_lblDepartment">Arts</span><span id="gvAllJobs_ctl02_lblCity">Gqeberha</span><span id="gvAllJobs_ctl02_lblDescription">Grade 12<br/>Library skills</span><span id="gvAllJobs_ctl02_lblPackage">R200 000 per annum</span><span id="gvAllJobs_ctl02_lblPostDate">01/01/2020</span><span id="gvAllJobs_ctl02_lblClosingDate">23/10/2099</span></td></tr><tr><td><span id="gvAllJobs_ctl03_lblJobTitle">Expired</span><span id="gvAllJobs_ctl03_lblClosingDate">01/01/2020</span></td></tr></table>'''

class DailyTests(unittest.TestCase):
 def test_jobs_nested_fields_expiry_and_source(self):
  jobs=JobsProvider(lambda url:JOB).collect()
  self.assertEqual(len(jobs),1);j=jobs[0]
  self.assertEqual(j['title'],'Library Assistant');self.assertEqual(j['description'],'Grade 12 Library skills')
  self.assertEqual(j['salary'],'R200 000 per annum');self.assertEqual(j['closing_at'],'2099-10-23')
  self.assertEqual(j['url'],EC_URL);self.assertEqual(j['application_method'],'official_portal_handoff')
 def test_feed_rights_dedup_and_link_validation(self):
  raw=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Headline</title><link href="https://example.org/article#fragment"/><published>2026-10-09T10:00:00Z</published><summary>Do not republish this</summary></entry><entry><title>Duplicate</title><link href="https://example.org/article"/></entry><entry><title>Private</title><link href="http://127.0.0.1/a"/></entry></feed>'''
  items=NewsProvider(lambda url:raw).collect('https://example.org/feed');self.assertEqual(len(items),1)
  self.assertFalse(items[0]['reader_allowed']);self.assertEqual(items[0]['description'],'');self.assertEqual(items[0]['url'],'https://example.org/article')
  default=NewsProvider(lambda url:RSS).collect();self.assertTrue(default[0]['reader_allowed'])
 def test_invalid_feed_and_limits(self):
  for raw in [b'<!DOCTYPE rss [<!ENTITY e "bad">]><rss/>',b'<html/>',b'x'*(2*1024*1024+1)]:
   with self.assertRaises((ValueError,Exception)):NewsProvider(lambda url:raw).collect('https://example.org/feed')
  with self.assertRaises(ValueError):NewsProvider(lambda url:RSS).collect('http://example.org/feed')
 def test_filter_cache_refresh_and_partial_failure(self):
  calls=[]
  def reader(url):
   calls.append(url)
   if url==FEED:return RSS
   if url==EC_URL:return JOB
   raise ValueError('Provider offline')
  svc=DailyService(reader);r=svc.collect('news',{'province':'Eastern Cape','query':'libraries','feeds':['https://example.org/feed']})
  self.assertEqual(len(r['results']),1);self.assertEqual(r['statuses'][1]['status'],'unavailable')
  svc.collect('news',{});self.assertEqual(calls.count(FEED),1)
  svc.collect('news',{'refresh':True});self.assertEqual(calls.count(FEED),2)
  self.assertFalse(svc.collect('news',{'province':'Western Cape'})['results'])
  self.assertEqual(len(svc.collect('opportunities',{'province':'Eastern Cape','query':'library'})['results']),1)
  self.assertFalse(svc.collect('opportunities',{'province':'Western Cape'})['results'])
 def test_configuration_validation(self):
  s=DailyService(lambda url:RSS)
  for data in [{'province':'Atlantis'},{'feeds':['https://example.org']*4},{'feeds':'bad'}]:
   with self.assertRaises(ValueError):s.collect('news',data)
  with self.assertRaises(ValueError):s.collect('other',{})
 def test_reader_restricted_to_supported_publisher(self):
  p=NewsProvider(lambda url:b'<html><head><title>A story</title></head><body><nav>Menu</nav><article><p>Credited text</p></article></body></html>')
  self.assertIn('Credited text',p.article('https://www.sanews.gov.za/node/1')['text'])
  for url in ['https://example.org/article','http://www.sanews.gov.za/article','https://www.sanews.gov.za.evil.test/a']:
   with self.assertRaises(ValueError):p.article(url)


class ProviderCacheTests(unittest.TestCase):
 def test_same_provider_requests_share_one_fetch(self):
  import threading
  from concurrent.futures import ThreadPoolExecutor
  cache=ProviderCache();calls=[];entered=threading.Event();release=threading.Event();start=threading.Barrier(4)
  def loader():
   calls.append(1);entered.set();self.assertTrue(release.wait(3));return ['record']
  def request():start.wait(3);return cache.get('same',loader)
  with ThreadPoolExecutor(max_workers=4) as pool:
   futures=[pool.submit(request) for _ in range(4)]
   self.assertTrue(entered.wait(3));release.set()
   self.assertEqual([f.result(3) for f in futures],[['record']]*4)
  self.assertEqual(len(calls),1);self.assertFalse(cache.pending)
 def test_unrelated_providers_can_fetch_concurrently(self):
  import threading
  from concurrent.futures import ThreadPoolExecutor
  cache=ProviderCache();together=threading.Barrier(2)
  def load():together.wait(3);return 7
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(cache.get,'a',load);b=pool.submit(cache.get,'b',load)
   self.assertEqual([a.result(4),b.result(4)],[7,7])
 def test_bounded_lru_and_failure_recovery(self):
  cache=ProviderCache(capacity=2)
  for n in range(3):cache.get(n,lambda:n)
  self.assertEqual(list(cache.values),[1,2])
  with self.assertRaises(ValueError):cache.get('failure',lambda:(_ for _ in ()).throw(ValueError('offline')))
  self.assertFalse(cache.pending);self.assertEqual(cache.get('failure',lambda:'recovered'),'recovered')
