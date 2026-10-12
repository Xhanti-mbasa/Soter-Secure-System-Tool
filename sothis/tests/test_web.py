import hashlib
import io
import json
import sqlite3
import tempfile
import time
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from web.app import create_app
from web.auth import Auth, password_hash, verify_password
from web.backup import make_backup


class WebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'temporary-test-password'
        cls.encoded = password_hash(cls.password)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = {'SOTHIS_PUBLIC_ORIGIN':'https://sothis.example.org','SOTHIS_USERNAME':'researcher',
                       'SOTHIS_PASSWORD_HASH':self.encoded,'SOTHIS_DATA':self.tmp.name}
        self.app = create_app(self.config)
        self.cookie, self.csrf = '', ''

    def tearDown(self):
        self.app.close()
        self.tmp.cleanup()

    def request(self, path, method='GET', data=None, origin=None, csrf=None, host=None, raw=None, content_type='application/json'):
        path, _, query = path.partition('?')
        body = raw if raw is not None else json.dumps(data or {}).encode()
        env = {'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':query,
               'HTTP_HOST':host or 'sothis.example.org','HTTP_COOKIE':self.cookie,
               'REMOTE_ADDR':'127.0.0.1','wsgi.input':io.BytesIO(body),'CONTENT_LENGTH':str(len(body)),
               'CONTENT_TYPE':content_type}
        if method == 'POST':
            env['HTTP_ORIGIN'] = origin if origin is not None else self.config['SOTHIS_PUBLIC_ORIGIN']
            env['HTTP_X_SOTHIS_CSRF'] = self.csrf if csrf is None else csrf
        response = {}
        def start(status, headers):
            response.update(status=int(status.split()[0]), headers=dict(headers))
        response['body'] = b''.join(self.app(env,start))
        if response['headers']['Content-Type'].startswith('application/json'):
            response['json'] = json.loads(response['body'])
        return response

    def login(self):
        result = self.request('/auth/login','POST',{'username':'researcher','password':self.password})
        self.assertEqual(result['status'],200)
        self.cookie = result['headers']['Set-Cookie'].split(';')[0]
        self.csrf = result['json']['csrf']
        return result

    def test_no_default_login_and_https_required(self):
        for config in ({**self.config,'SOTHIS_PASSWORD_HASH':''},{**self.config,'SOTHIS_PUBLIC_ORIGIN':'http://sothis.example.org'},
                       {**self.config,'SOTHIS_PUBLIC_ORIGIN':'https://sothis.example.org/path'},
                       {**self.config,'SOTHIS_DEV':'1','SOTHIS_PUBLIC_ORIGIN':'http://public.example.org'}):
            with self.assertRaises(ValueError):create_app(config)
        self.assertTrue(verify_password(self.password,self.encoded))
        self.assertFalse(verify_password('wrong',self.encoded))

    def test_private_api_and_archives_require_login(self):
        self.assertEqual(self.request('/')['headers']['Location'],'/login')
        for path in ('/api/cases','/api/alerts','/api/sources','/api/evidence/'+'a'*64+'/download'):
            self.assertEqual(self.request(path)['status'],401)
        self.assertFalse(self.request('/api/session')['json']['authenticated'])
        self.assertEqual(self.request('/snapshot.json')['status'],302)
        self.assertEqual(self.request('/healthz')['json'],{'ok':True})

    def test_province_assets_and_news_use_private_web_gateway(self):
        self.assertEqual(self.request('/api/provinces')['status'],401)
        self.login()
        self.assertEqual(len(self.request('/api/provinces')['json']['provinces']),9)
        for asset in ('provinces.js','provinces.css','province-data.json','education-registers.json','company-details.js'):
            self.assertEqual(self.request('/'+asset)['status'],200)
        self.app.runtime.province_news.reader=lambda url:b'<rss><channel><item><title>Western Cape fixture</title><link>https://www.sanews.gov.za/node/999</link><pubDate>Fri, 09 Oct 2026 12:00:00 +0200</pubDate></item></channel></rss>'
        result=self.request('/api/province/news','POST',{'province':'Western Cape','days':0})
        self.assertEqual(result['status'],200);self.assertEqual(result['json']['results'][0]['acquisition'],'publisher_feed')
        self.assertEqual(self.request('/api/province/news','POST',{'province':'Invalid','days':30})['status'],400)

    def test_analytics_assets_and_metadata_endpoint_keep_session_boundaries(self):
        for path in ('/api/analytics','/api/publication'):
            self.assertEqual(self.request(path)['status'],401)
        for path in ('/analytics-data.json','/analytics.js','/analytics.css','/navigation.js'):
            self.assertEqual(self.request(path)['status'],302)
        self.login()
        analytics=self.request('/api/analytics')['json']
        self.assertEqual(sum(analytics['national_elections'][-1]['seats'].values()),400)
        for path in ('/analytics-data.json','/analytics.js','/analytics.css','/navigation.js'):
            self.assertEqual(self.request(path)['status'],200)
        self.assertEqual(self.request('/api/publication','POST',{'url':'http://127.0.0.1/private'})['status'],400)
        self.assertEqual(self.request('/api/publication','POST',{'url':'https://example.org/article'},csrf='wrong')['status'],403)

    def test_daily_routes_keep_authentication_and_local_files_boundaries(self):
        from engine.daily import DailyService
        from test_daily import RSS, JOB
        self.assertEqual(self.request('/api/daily/news','POST',{})['status'],401)
        self.login()
        self.app.runtime.daily=DailyService(lambda url: JOB if 'erecruitment' in url else RSS)
        self.assertEqual(self.request('/api/daily/news','POST',{},csrf='wrong')['status'],403)
        result=self.request('/api/daily/news','POST',{'province':'Eastern Cape'})
        self.assertEqual(result['status'],200);self.assertEqual(len(result['json']['results']),1)
        self.assertEqual(self.request('/api/daily/opportunities','POST',{})['json']['results'][0]['title'],'Library Assistant')
        self.assertEqual(self.request('/api/daily/article','POST',{'url':'https://example.org/reader'})['status'],400)
        for path in ['/daily.js','/personal.js','/share-cards.js','/daily.css','/vendor/pdf.js','/vendor/pdf.worker.js']:
            self.assertEqual(self.request(path)['status'],200)
        self.assertEqual(self.request('/vendor/../../engine/daily.py')['status'],404)

    def test_cookie_policy_csp_and_same_origin_session(self):
        result = self.login()
        self.assertIn('__Host-sothis=',result['headers']['Set-Cookie'])
        for part in ('HttpOnly','Secure','SameSite=Lax','Path=/'):
            self.assertIn(part,result['headers']['Set-Cookie'])
        self.assertEqual(self.request('/api/session')['json']['csrf'],self.csrf)
        page = self.request('/')
        self.assertEqual(page['status'],200)
        self.assertIn(b'/web-runtime.js',page['body'])
        self.assertLess(page['body'].index(b'/web-runtime.js'),page['body'].index(b'features.js'))
        self.assertIn(b'<script nonce=',page['body'])
        self.assertIn("frame-ancestors 'none'",page['headers']['Content-Security-Policy'])
        self.assertNotIn("script-src 'self' 'unsafe-inline'",page['headers']['Content-Security-Policy'])
        self.assertEqual(page['headers']['Cache-Control'],'no-store')

    def test_cross_origin_and_missing_csrf_cannot_mutate(self):
        self.login()
        for origin, csrf in (('https://evil.example',''),('',self.csrf),(None,''),(None,'wrong')):
            self.assertEqual(self.request('/api/cases','POST',{'title':'Blocked'},origin=origin,csrf=csrf)['status'],403)
        self.assertEqual(self.request('/api/cases')['json'],[])
        self.assertEqual(self.request('/auth/login','POST',{'username':'researcher','password':self.password},origin='https://evil.example')['status'],403)

    def test_hostname_and_static_boundaries(self):
        self.login()
        self.assertEqual(self.request('/api/cases',host='evil.example')['status'],400)
        for path in ('/images/../../engine/core.py','/web/../auth.py','/.env','/secrets/cloudflare-token','/fonts/OFL.txt'):
            self.assertEqual(self.request(path)['status'],404)
        for path, mime in (('/nothing.css','text/css'),('/web-runtime.js','application/javascript'),('/images/cape-town.webp','image/webp'),('/fonts/doto.ttf','font/ttf')):
            self.assertEqual(self.request(path)['headers']['Content-Type'],mime)
        self.assertEqual(self.request('/',method='HEAD')['body'],b'')

    def test_json_limits_and_types(self):
        self.login()
        self.assertEqual(self.request('/api/cases','POST',raw=b'[]')['status'],400)
        self.assertEqual(self.request('/api/cases','POST',raw=b'{')['status'],400)
        self.assertEqual(self.request('/api/cases','POST',content_type='text/plain')['status'],415)
        self.assertEqual(self.request('/api/cases','POST',raw=b'x'*(2*1024*1024+1))['status'],413)

    def test_cases_search_and_rules_persist_on_restart(self):
        self.login()
        record = self.request('/api/cases','POST',{'title':'Website investigation','notes':'Sourced notes','pins':[]})
        self.assertEqual(record['status'],201)
        rule = self.request('/api/monitors','POST',{'query':'Public research','services':['government'],'condition':'new_hit','interval_minutes':120,'enabled':False})
        self.assertEqual(rule['status'],201)
        self.assertGreater(self.request('/api/search?q=Ramaphosa')['json']['total'],0)
        self.app.close()
        self.app = create_app(self.config)
        self.assertEqual(self.request('/api/cases')['json'][0]['notes'],'Sourced notes')
        self.assertEqual(self.request('/api/monitors')['json'][0]['id'],rule['json']['id'])
        self.assertTrue(self.request('/api/session')['json']['authenticated'])

    def test_password_reset_revokes_existing_sessions(self):
        self.login()
        self.app.close()
        self.app = create_app({**self.config,'SOTHIS_PASSWORD_HASH':password_hash('another-temporary-password')})
        self.assertEqual(self.request('/api/cases')['status'],401)

    def test_logout_and_expiry(self):
        self.login()
        result = self.request('/auth/logout','POST')
        self.assertEqual(result['status'],200)
        self.assertIn('Max-Age=0',result['headers']['Set-Cookie'])
        self.assertEqual(self.request('/api/cases')['status'],401)
        self.login()
        with self.app.auth.connect() as db:db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
        self.assertEqual(self.request('/api/cases')['status'],401)

    def test_login_rate_limit_survives_restart(self):
        for _ in range(20):
            self.assertEqual(self.request('/auth/login','POST',{'username':'researcher','password':'wrong'})['status'],401)
        self.app.close()
        self.app = create_app(self.config)
        self.assertEqual(self.request('/auth/login','POST',{'username':'researcher','password':self.password})['status'],429)

    def test_auth_connections_commit_or_rollback_then_close(self):
        auth=self.app.auth
        committed=auth.connect()
        with committed as db:
            db.execute('INSERT INTO config VALUES (?,?)',('lifecycle','committed'))
        with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
            committed.execute('SELECT 1')
        failed=auth.connect()
        with self.assertRaisesRegex(RuntimeError,'failed authentication transaction'):
            with failed as db:
                db.execute('UPDATE config SET value=? WHERE key=?',('rolled-back','lifecycle'))
                raise RuntimeError('failed authentication transaction')
        with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
            failed.execute('SELECT 1')
        with auth.connect() as db:
            self.assertEqual(db.execute('SELECT value FROM config WHERE key=?',('lifecycle',)).fetchone()[0],'committed')

    def test_auth_initialization_and_session_calls_close_connections(self):
        connections=[]
        original=Auth.connect
        def record(auth):
            connection=original(auth);connections.append(connection);return connection
        with patch.object(Auth,'connect',record):
            auth=Auth(self.tmp.name,'researcher',self.encoded)
            self.assertTrue(auth.allow_login('127.0.0.1'))
            token,csrf=auth.login('researcher',self.password)
            self.assertEqual(auth.session(token)['csrf'],csrf)
            auth.logout(token)
            self.assertIsNone(auth.session(token))
        self.assertEqual(len(connections),6)
        for connection in connections:
            with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
                connection.execute('SELECT 1')

    def test_original_download_and_bundle_hashes(self):
        self.login()
        raw = b'Original public evidence\n'
        sha = hashlib.sha256(raw).hexdigest()
        (Path(self.tmp.name)/'archive'/sha).write_bytes(raw)
        self.assertEqual(self.request('/api/evidence/'+sha+'/download')['body'],raw)
        payload = {'title':'Evidence','report':'# Sourced report','evidence':[{'sha256':sha,'url':'https://example.org/document'}]}
        result = self.request('/api/bundle','POST',payload)
        self.assertEqual(result['status'],200)
        with zipfile.ZipFile(io.BytesIO(result['body'])) as z:
            manifest = json.loads(z.read('manifest.json'))
            self.assertEqual(z.read(manifest['evidence'][0]['bundle_path']),raw)
            self.assertEqual(z.read('report.md'),b'# Sourced report')
        payload['evidence'][0]['sha256'] = '../lens.sqlite3'
        self.assertEqual(self.request('/api/bundle','POST',payload)['status'],400)
        payload['evidence'][0]['sha256'] = sha
        (Path(self.tmp.name)/'archive'/sha).write_bytes(b'Corrupt original')
        self.assertEqual(self.request('/api/bundle','POST',payload)['status'],400)

    def test_backup_preserves_research_and_originals(self):
        self.login()
        self.request('/api/cases','POST',{'title':'Backup research','notes':'Saved notes'})
        raw = b'Public original'
        sha = hashlib.sha256(raw).hexdigest()
        (Path(self.tmp.name)/'archive'/sha).write_bytes(raw)
        output = io.BytesIO()
        connections=[]
        original=sqlite3.connect
        def record(*args,**kwargs):
            connection=original(*args,**kwargs);connections.append(connection);return connection
        with patch('web.backup.sqlite3.connect',side_effect=record):
            make_backup(self.tmp.name,output)
        self.assertEqual(len(connections),4)
        for connection in connections:
            with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
                connection.execute('SELECT 1')
        with tempfile.TemporaryDirectory() as restored, zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive:
            archive.extractall(restored)
            with closing(sqlite3.connect(Path(restored)/'lens.sqlite3')) as db:
                self.assertEqual(json.loads(db.execute('SELECT data FROM cases').fetchone()[0])['notes'],'Saved notes')
            self.assertEqual((Path(restored)/'archive'/sha).read_bytes(),raw)
            self.assertTrue((Path(restored)/'auth.sqlite3').is_file())

    def test_backup_closes_both_connections_when_copy_fails(self):
        class FailedBackup(sqlite3.Connection):
            def backup(self,destination):
                raise sqlite3.OperationalError('backup failed')
        connections=[]
        original=sqlite3.connect
        def record(*args,**kwargs):
            connection=original(*args,factory=FailedBackup,**kwargs);connections.append(connection);return connection
        with patch('web.backup.sqlite3.connect',side_effect=record):
            with self.assertRaisesRegex(sqlite3.OperationalError,'backup failed'):
                make_backup(self.tmp.name,io.BytesIO())
        self.assertEqual(len(connections),2)
        for connection in connections:
            with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
                connection.execute('SELECT 1')
        self.assertGreater(self.app.runtime.store.stats()['documents'],0)

    def test_backup_closes_origin_when_destination_cannot_open(self):
        connections=[]
        original=sqlite3.connect
        def record(*args,**kwargs):
            if connections:raise sqlite3.OperationalError('destination unavailable')
            connection=original(*args,**kwargs);connections.append(connection);return connection
        with patch('web.backup.sqlite3.connect',side_effect=record):
            with self.assertRaisesRegex(sqlite3.OperationalError,'destination unavailable'):
                make_backup(self.tmp.name,io.BytesIO())
        self.assertEqual(len(connections),1)
        with self.assertRaisesRegex(sqlite3.ProgrammingError,'closed database'):
            connections[0].execute('SELECT 1')


if __name__ == '__main__':unittest.main()
