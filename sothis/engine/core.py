import datetime as dt
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path

PROVINCES = ['Eastern Cape', 'Free State', 'Gauteng', 'KwaZulu-Natal', 'Limpopo',
             'Mpumalanga', 'North West', 'Northern Cape', 'Western Cape']
CATEGORIES = ['government', 'news', 'gazettes', 'interests', 'remuneration', 'jobs',
              'tenders', 'company', 'courts']

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def date_value(value):
    if not value:
        return None
    value = str(value).strip()
    try:
        return dt.date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        pass
    for pattern in ('%d %B %Y', '%d %b %Y', '%B %d, %Y', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None

class Store:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'archive').mkdir(exist_ok=True)
        self.path = self.root / 'lens.sqlite3'
        with self.connect() as c:
            c.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, data TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS documents(
                id TEXT PRIMARY KEY, url TEXT NOT NULL, title TEXT NOT NULL,
                source_id TEXT NOT NULL, province TEXT NOT NULL, category TEXT NOT NULL,
                published_at TEXT, retrieved_at TEXT NOT NULL, content_hash TEXT NOT NULL,
                raw_hash TEXT, page INTEGER, text TEXT NOT NULL, social_links TEXT NOT NULL,
                acquisition TEXT NOT NULL DEFAULT 'crawl', UNIQUE(url, page));
              CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(id UNINDEXED, title, text);
              CREATE TABLE IF NOT EXISTS versions(id TEXT, content_hash TEXT,
                retrieved_at TEXT, raw_hash TEXT, title TEXT, text TEXT,
                PRIMARY KEY(id,content_hash));
              CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, data TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,
                source_id TEXT, time TEXT, status TEXT, detail TEXT);
            ''')

    def connect(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def seed_sources(self, sources):
        with self.connect() as c:
            for source in sources:
                old = c.execute('SELECT data FROM sources WHERE id=?', (source['id'],)).fetchone()
                if old:
                    for k in ('last_attempt', 'last_success', 'status', 'detail'):
                        if k in json.loads(old['data']):
                            source[k] = json.loads(old['data'])[k]
                c.execute('INSERT OR REPLACE INTO sources VALUES (?,?)',
                          (source['id'], json.dumps(source)))

    def sources(self):
        with self.connect() as c:
            sources = [json.loads(r['data']) for r in c.execute('SELECT data FROM sources')]
            counts = dict(c.execute('SELECT source_id,count(*) FROM documents GROUP BY source_id'))
        for s in sources:
            s['indexed_documents'] = counts.get(s['id'], 0)
        return sorted(sources, key=lambda s: (s['province'], s['name']))

    def source(self, source_id):
        return next((s for s in self.sources() if s['id'] == source_id), None)

    def event(self, source_id, status, detail):
        stamp = now()
        with self.connect() as c:
            c.execute('INSERT INTO events(source_id,time,status,detail) VALUES (?,?,?,?)',
                      (source_id, stamp, status, detail[:500]))
            row = c.execute('SELECT data FROM sources WHERE id=?', (source_id,)).fetchone()
            if row:
                s = json.loads(row['data'])
                s.update(last_attempt=stamp, status=status, detail=detail[:500])
                if status == 'indexed':
                    s['last_success'] = stamp
                c.execute('UPDATE sources SET data=? WHERE id=?', (json.dumps(s), source_id))

    def put_document(self, source, url, title, text, published_at=None, page=None,
                     raw=None, social_links=None, category=None, acquisition='crawl'):
        text = text.strip()
        if len(text) < 40:
            raise ValueError('No searchable text; this document may need OCR or JavaScript rendering.')
        doc_id = digest(url + '#' + str(page or 0))[:24]
        raw_hash = hashlib.sha256(raw).hexdigest() if raw else None
        if raw:
            path = self.root / 'archive' / raw_hash
            if not path.exists():
                path.write_bytes(raw)
        d = dict(id=doc_id, url=url, title=title.strip()[:400], source_id=source['id'],
                 province=source['province'], category=category or source['category'],
                 published_at=date_value(published_at), retrieved_at=now(),
                 content_hash=digest(text), raw_hash=raw_hash, page=page, text=text[:500000],
                 social_links=json.dumps(social_links or []), acquisition=acquisition)
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO documents (' + ','.join(d) + ') VALUES (' +
                      ','.join('?' for _ in d) + ')', tuple(d.values()))
            c.execute('DELETE FROM docs_fts WHERE id=?', (doc_id,))
            c.execute('INSERT INTO docs_fts VALUES (?,?,?)', (doc_id, d['title'], d['text']))
            c.execute('INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?,?)',
                      (doc_id, d['content_hash'], d['retrieved_at'], raw_hash, d['title'], d['text']))
        return doc_id

    @staticmethod
    def serialize(row, query=''):
        d = dict(row)
        d['social_links'] = json.loads(d['social_links'])
        d['match_status'] = 'Document mention; identity and relationships require review'
        text = d.pop('text')
        tokens = re.findall(r'\w+', query.lower())
        positions = [text.lower().find(t) for t in tokens if text.lower().find(t) >= 0]
        start = max(0, min(positions, default=0) - 100)
        d['excerpt'] = ('…' if start else '') + text[start:start + 440] + ('…' if start + 440 < len(text) else '')
        return d

    def search(self, q='', province='', category='', source_id='', after='', before='',
               include_national=False, sort='relevance', offset=0, limit=30):
        q = q.strip()[:240]
        original_q = q
        region = next((p for p in PROVINCES if p.casefold() == q.casefold()), None)
        if region:
            province, q = region, ''
        where, args = [], []
        if province and province != 'All regions':
            if province not in PROVINCES + ['National']:
                raise ValueError('Unknown province')
            where.append('(d.province=? OR d.province=?)' if include_national else 'd.province=?')
            args += [province, 'National'] if include_national else [province]
        if category:
            if category not in CATEGORIES:
                raise ValueError('Unknown category')
            where.append('d.category=?'); args.append(category)
        if source_id:
            where.append('d.source_id=?'); args.append(source_id)
        for value, op in ((after, '>='), (before, '<=')):
            if value:
                parsed = date_value(value)
                if not parsed:
                    raise ValueError('Dates must use YYYY-MM-DD')
                where.append('d.published_at ' + op + ' ?'); args.append(parsed)
        tokens = re.findall(r'\w+', q, flags=re.UNICODE)
        join = ''
        order = 'd.retrieved_at DESC'
        if tokens:
            # Quote each token: users cannot inject FTS operators or SQL.
            join = 'JOIN docs_fts ON docs_fts.id=d.id'
            where.append('docs_fts MATCH ?')
            args.append(' AND '.join('"' + t + '"' for t in tokens))
            order = 'bm25(docs_fts,0,6,1), d.retrieved_at DESC'
        if sort == 'recent':
            order = 'd.published_at IS NULL, d.published_at DESC, d.retrieved_at DESC'
        clause = ' WHERE ' + ' AND '.join(where) if where else ''
        base = ' FROM documents d ' + join + clause
        with self.connect() as c:
            total = c.execute('SELECT count(*)' + base, args).fetchone()[0]
            rows = c.execute('SELECT d.*' + base + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?',
                             args + [max(1, min(int(limit), 100)), max(0, int(offset))]).fetchall()
            facets = dict(c.execute('SELECT d.category,count(*)' + base + ' GROUP BY d.category', args))
        suggestions = []
        if re.search(r'jordan.*(hill|lewis)', original_q, re.I):
            suggestions = [{'query': 'Geordin Hill-Lewis', 'reason': 'Possible intended spelling; confirm before searching.'}]
        return dict(query=original_q, effective_query=q, province=province, total=total,
                    offset=int(offset), results=[self.serialize(r, q) for r in rows],
                    facets=facets, suggestions=suggestions,
                    coverage='Results cover indexed documents only. Zero results do not prove absence.')

    def document(self, doc_id):
        with self.connect() as c:
            row = c.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
            versions = c.execute('SELECT content_hash,retrieved_at,raw_hash FROM versions WHERE id=?',
                                 (doc_id,)).fetchall()
        if not row:
            return None
        d = self.serialize(row)
        d['text'] = row['text']
        d['versions'] = [dict(v) for v in versions]
        return d

    def stats(self):
        with self.connect() as c:
            n = c.execute('SELECT count(*) FROM documents').fetchone()[0]
            urls = c.execute('SELECT count(DISTINCT url) FROM documents').fetchone()[0]
            last = c.execute('SELECT max(retrieved_at) FROM documents').fetchone()[0] or ''
        sources = self.sources()
        return dict(documents=n, unique_urls=urls, sources=len(sources),
                    indexed_sources=sum(bool(s['indexed_documents']) for s in sources),
                    provinces=PROVINCES, categories=CATEGORIES,
                    last_retrieved=last)

    def cases(self):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute('SELECT data FROM cases ORDER BY rowid DESC')]

    def save_case(self, data, case_id=None):
        old = next((x for x in self.cases() if x['id'] == case_id), None)
        if case_id and not old:
            raise KeyError('Investigation not found')
        if old:
            data = {**old, **data}
        title = str(data.get('title','')).strip()[:160]
        if not title:
            raise ValueError('Investigation title is required')
        pins = list(dict.fromkeys(str(p) for p in data.get('pins', [])))[:200]
        if any(not self.document(p) for p in pins):
            raise ValueError('An evidence document is missing')
        case = dict(id=case_id or digest(title + now())[:20], title=title,
                    query=str(data.get('query',''))[:240], notes=str(data.get('notes',''))[:50000],
                    pins=pins, created_at=(old or {}).get('created_at', now()), updated_at=now())
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO cases VALUES (?,?)', (case['id'], json.dumps(case)))
        return case

    def export(self, case_id, fmt='md'):
        case = next((x for x in self.cases() if x['id'] == case_id), None)
        if not case:
            raise KeyError('Investigation not found')
        lines = ['# ' + case['title'], '', 'Research brief · generated ' + now(), '',
                 '## Research question', '', case['query'] or case['title'], '',
                 '## Researcher notes', '', case['notes'] or 'No notes added.', '',
                 '## Evidence register', '']
        for i, doc_id in enumerate(case['pins'], 1):
            d = self.document(doc_id)
            lines += [f'### [{i}] {d["title"]}', '',
                      f'Source: {d["url"]}' + (f' · PDF page {d["page"]}' if d['page'] else ''),
                      f'Region: {d["province"]} · Category: {d["category"]}',
                      f'Published: {d["published_at"] or "Unknown"} · Retrieved: {d["retrieved_at"]}',
                      'SHA-256 of extracted text: ' + d['content_hash'], '',
                      'Evidence locator: ' + d['excerpt'][:440], '',
                      'This is a document mention. Confirm identity, context, and any claimed relationship.', '']
        lines += ['## Gaps and checks before publication', '',
                  '- This brief covers selected indexed evidence, not every public record.',
                  '- Notes are researcher assertions; they are not independently verified by the engine.',
                  '- Verify person identity, current roles, dates, and source context.',
                  '- Pay scales and statutory upper limits do not establish actual personal pay.',
                  '- CIPC records require an authorised lookup/import; names alone do not prove directorship.',
                  '- Social links in a document belong to its publisher unless ownership is confirmed.', '']
        content = '\n'.join(lines)
        if fmt == 'html':
            return '<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(case['title']) + '</title><style>body{font:16px/1.7 system-ui;max-width:850px;margin:auto;padding:32px;color:#122338}pre{white-space:pre-wrap;font:inherit}@media print{body{padding:0}}</style><body><pre>' + html.escape(content) + '</pre></body></html>'
        return content

    def snapshot(self):
        with self.connect() as c:
            rows = c.execute('SELECT * FROM documents ORDER BY retrieved_at DESC LIMIT 1000').fetchall()
        records = []
        for r in rows:
            d = self.serialize(r)
            # Device snapshot stores searchable text and metadata, not raw downloaded files.
            d['text'] = r['text'][:60000]
            records.append(d)
        return dict(generated_at=now(), stats=self.stats(), sources=self.sources(), documents=records,
                    notice='Bundled snapshot: use Connect engine for newer or larger collections.')
