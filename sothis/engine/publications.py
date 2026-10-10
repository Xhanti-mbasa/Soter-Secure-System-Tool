"""Resolve explicit article publication metadata, separately from index age."""
import json
import hashlib
import urllib.parse
from html.parser import HTMLParser
from .connectors import Fetcher, canonical
from .core import date_value, now


class PublicationPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.candidates=[]
        self.json_script=None
        self.script=[]

    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        key=(a.get('property') or a.get('name') or '').lower()
        if tag=='meta' and key in ('article:published_time','datepublished','pubdate'):
            self.candidates.append((a.get('content'), 'Source metadata · '+key))
        if a.get('itemprop','').lower()=='datepublished':
            self.candidates.append((a.get('content') or a.get('datetime'), 'Source metadata · datePublished'))
        if tag=='script':
            self.json_script=a.get('type')=='application/ld+json'
            self.script=[]

    def handle_data(self, data):
        if self.json_script:self.script.append(data)

    def handle_endtag(self, tag):
        if tag=='script' and self.json_script:
            try:self.structured(json.loads(''.join(self.script)))
            except (ValueError,TypeError):pass
            self.json_script=None

    def structured(self, node):
        if isinstance(node,list):
            for n in node:self.structured(n)
        elif isinstance(node,dict):
            kind=node.get('@type', [])
            kind=[kind] if isinstance(kind,str) else kind if isinstance(kind,list) else []
            if any(k in ('Article','NewsArticle','BlogPosting','Report','WebPage') for k in kind):
                self.candidates.append((node.get('datePublished'), 'Source structured data · datePublished'))
            for n in node.values():
                if isinstance(n,(dict,list)):self.structured(n)

    def result(self):
        dates=[(date_value(d),label) for d,label in self.candidates if isinstance(d,str)]
        dates=[(d,label) for d,label in dates if d]
        if len({d for d,_ in dates})>1:
            return dict(published_at=None,publication_date_source=None,date_status='conflicting_metadata')
        return dict(published_at=dates[0][0] if dates else None,
                    publication_date_source=dates[0][1] if dates else None,
                    date_status='explicit_metadata' if dates else 'not_published')


def publication(url, fetcher=None):
    url=canonical(url)
    host=urllib.parse.urlsplit(url).hostname
    raw,mime,final,charset=(fetcher or Fetcher()).fetch(url,{host})
    if mime not in ('text/html','application/xhtml+xml'):
        raise ValueError('Publication metadata lookup requires an HTML article')
    parser=PublicationPage();parser.feed(raw.decode(charset,errors='replace'))
    return {**parser.result(),'publication_source_url':final,'publication_content_hash':hashlib.sha256(raw).hexdigest(),'date_checked_at':now()}
