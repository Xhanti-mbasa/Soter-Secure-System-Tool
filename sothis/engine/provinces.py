import html
"""Dated province evidence and bounded public-news feeds.

Only the configured public publisher feed is fetched. Province selection is not
an arbitrary URL proxy. A location mention describes relevance, not jurisdiction.
"""
import datetime as dt
import email.utils
import json
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from .core import digest, now
from .services import text

ASSETS = Path(__file__).resolve().parent.parent/'android/app/src/main/assets'
FEED = 'https://www.sanews.gov.za/south-africa-news-stories.xml'

@lru_cache(maxsize=1)
def snapshot():
    return json.loads((ASSETS/'province-data.json').read_text())

def province(name):
    found=next((p for p in snapshot()['provinces'] if p['name']==name),None)
    if not found:raise ValueError('Select a South African province')
    return found

def mentions(value, keywords):
    return any(re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',value,re.I) for word in keywords)

def published(value):
    try:
        date=email.utils.parsedate_to_datetime(value)
    except (ValueError,TypeError):
        try:date=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        except (ValueError,TypeError):return None
    if date.tzinfo is None:date=date.replace(tzinfo=dt.timezone.utc)
    return date.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')

def feed_text(value):
    # RSS descriptions may contain HTML whose entities are escaped inside XML/CDATA.
    decoded=html.unescape(html.unescape(value))
    return text(re.sub('<[^>]+>',' ',decoded))

def parse_feed(raw, retrieved_at=None):
    if isinstance(raw,str):raw=raw.encode()
    if len(raw)>2*1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported or oversized news feed')
    root=ET.fromstring(raw);items={};stamp=retrieved_at or now()
    for item in root.iter():
        if item.tag.rsplit('}',1)[-1] not in ('item','entry'):continue
        fields={}
        for node in item:
            tag=node.tag.rsplit('}',1)[-1]
            fields[tag]=node.attrib.get('href','') if tag=='link' and node.attrib.get('href') else ''.join(node.itertext())
        url=fields.get('link','').strip();parts=urllib.parse.urlsplit(url)
        if parts.scheme!='https' or parts.hostname not in ('www.sanews.gov.za','sanews.gov.za') or parts.username:continue
        # Preserve the publisher's URL query; different articles may use node URLs.
        url=urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
        title=feed_text(fields.get('title',''))[:500]
        description=feed_text(fields.get('description',fields.get('summary','')))[:1200]
        if not title:continue
        date=published(fields.get('pubDate',fields.get('published',fields.get('date',''))))
        items[url]={'id':digest(url)[:24],'title':title,'description':description,'url':url,'category':'government','publisher':'SAnews / GCIS','published_at':date,'publication_date_source':'Publisher RSS publication field' if date else None,'retrieved_at':stamp,'content_hash':digest(title+'\n'+description),'acquisition':'publisher_feed'}
        if len(items)>=100:break
    if root.tag.rsplit('}',1)[-1] not in ('rss','feed','RDF'):raise ValueError('Publisher returned an unsupported feed')
    return list(items.values())

def select_news(items, name, days=30, today=None):
    p=province(name);today=today or dt.datetime.now(dt.timezone.utc).date()
    if isinstance(days,bool) or days not in (7,30,90,0):raise ValueError('News window must be 7, 30, 90 or 0 days')
    start=today-dt.timedelta(days=days) if days else None
    results=[];undated=[]
    for item in items:
        if not mentions(item['title']+' '+item.get('description',''),p['keywords']):continue
        date=published(item.get('published_at') or '')
        if not date:undated.append(item);continue
        date=dt.date.fromisoformat(date[:10])
        if date>today or start and date<start:continue
        results.append(item)
    return sorted(results,key=lambda x:x['published_at'],reverse=True)[:40],undated[:20]

class ProvinceNews:
    def __init__(self, services, reader=None):
        self.services=services;self.reader=reader;self.cache=None;self.lock=threading.Lock()
    def feed(self, fresh=False):
        with self.lock:
            if self.cache and not fresh and time.time()-self.cache[0]<300:return self.cache[1],True
            if self.reader:raw=self.reader(FEED)
            else:
                from .connectors import Fetcher
                raw,_,_,_=Fetcher().fetch(FEED,{'www.sanews.gov.za','sanews.gov.za'})
            items=parse_feed(raw);self.cache=(time.time(),items);return items,False
    def news(self,name,days=30,fresh=False):
        province(name)
        if isinstance(days,bool) or days not in (7,30,90,0):raise ValueError('Invalid news window')
        results=[];undated=[];statuses=[];cached=False
        try:
            items,cached=self.feed(fresh);results,undated=select_news(items,name,days)
            statuses.append({'service':'SAnews publisher feed','status':'completed','retrieved':len(items),'matched':len(results)})
        except Exception as e:statuses.append({'service':'SAnews publisher feed','status':'unavailable','detail':str(e)[:160]})
        # Widen an empty provincial feed to public-index candidates, separately labelled.
        candidates=[]
        if not results:
            discovery=self.services.discover(name,'all',fresh=fresh,topic='news')
            candidates=discovery['results'];statuses+=discovery['statuses']
        return {'province':name,'days':days,'results':results,'undated':undated,'candidates':candidates,'statuses':statuses,'retrieved_at':now(),'cached':cached,'source_url':FEED,'coverage':'Dated articles mention this province or a listed locality. Feed coverage is limited to recent publisher items. Public-index candidates have no verified publication date until their original metadata is checked.'}
