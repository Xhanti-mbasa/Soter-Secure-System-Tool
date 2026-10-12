import atexit
import hmac
import json
import logging
import mimetypes
import os
import re
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .auth import Auth, valid_hash
from .bundles import evidence_bundle
from .runtime import APIAdapter, ASSETS, ROOT, Runtime

STATIC = Path(__file__).parent / 'static'
MAX_BODY = 2 * 1024 * 1024


class RequestError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class App:
    def __init__(self, config):
        self.origin = config.get('SOTHIS_PUBLIC_ORIGIN', '').rstrip('/')
        parsed = urlsplit(self.origin)
        self.dev = config.get('SOTHIS_DEV', '') == '1'
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('Set SOTHIS_PUBLIC_ORIGIN to the website origin without a path.')
        if parsed.scheme != 'https' and not (self.dev and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Production websites require an HTTPS public origin.')
        username = config.get('SOTHIS_USERNAME', '')
        password = config.get('SOTHIS_PASSWORD_HASH', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', username) or not valid_hash(password):
            raise ValueError('Run python3 -m web.setup to configure the workspace login.')
        self.host = parsed.netloc.lower()
        self.secure = parsed.scheme == 'https'
        self.cookie_name = '__Host-sothis' if self.secure else 'sothis-dev'
        self.runtime = Runtime(config.get('SOTHIS_DATA', str(ROOT / 'data')))
        self.auth = Auth(self.runtime.store.root, username, password)
        atexit.register(self.close)

    def close(self):
        self.runtime.close()

    def cookie(self, token='', clear=False):
        value = f'{self.cookie_name}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={0 if clear else self.auth.lifetime}'
        return value + ('; Secure' if self.secure else '')

    def json_body(self, env):
        if env.get('CONTENT_TYPE', '').split(';')[0].strip().lower() != 'application/json':
            raise RequestError(415, 'Use application/json.')
        try:
            length = int(env.get('CONTENT_LENGTH', '0'))
        except ValueError:
            raise RequestError(400, 'Invalid request length.')
        if not 0 < length <= MAX_BODY:
            raise RequestError(413, 'Request size limit is 2 MiB.')
        try:
            raw = env['wsgi.input'].read(length)
            if len(raw) != length:
                raise ValueError()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, UnicodeDecodeError):
            raise RequestError(400, 'A valid JSON object is required.')

    def html(self, file, nonce):
        source = file.read_text()
        if file == ASSETS / 'index.html':
            source = source.replace('<link rel="stylesheet" href="nothing.css">', '<link rel="stylesheet" href="nothing.css"><link rel="stylesheet" href="/web.css">')
            source = source.replace('<script>', f'<script nonce="{nonce}">')
            source = source.replace('<script src="visuals.js">', '<script src="/web-runtime.js"></script><script src="visuals.js">')
            source = source.replace('</body>', '<script src="/web-ui.js"></script></body>')
        return source

    def route(self, env, nonce):
        method, path = env['REQUEST_METHOD'], env.get('PATH_INFO', '/')
        if method not in ('GET', 'HEAD', 'POST'):
            raise RequestError(405, 'Method not allowed.')
        if path == '/healthz' and method in ('GET', 'HEAD'):
            return 200, {'ok': True}, 'application/json', []
        if env.get('HTTP_HOST', '').lower() != self.host:
            raise RequestError(400, 'Unexpected website hostname.')
        cookies = SimpleCookie()
        try:
            cookies.load(env.get('HTTP_COOKIE', ''))
        except Exception:
            pass
        token = cookies[self.cookie_name].value if self.cookie_name in cookies else ''
        session = self.auth.session(token)
        if path == '/api/session' and method in ('GET', 'HEAD'):
            return 200, {'authenticated': bool(session), **(session or {})}, 'application/json', []
        data = {}
        if method == 'POST':
            if env.get('HTTP_ORIGIN', '') != self.origin:
                raise RequestError(403, 'Request must originate from this website.')
            if path != '/auth/login':
                if not session:
                    raise RequestError(401, 'Sign in to your workspace.')
                if not hmac.compare_digest(env.get('HTTP_X_SOTHIS_CSRF', '').encode(), session['csrf'].encode()):
                    raise RequestError(403, 'Refresh the page and try again.')
            data = self.json_body(env)
        if path == '/auth/login' and method == 'POST':
            if not self.auth.allow_login(env.get('REMOTE_ADDR', '')):
                raise RequestError(429, 'Too many sign-in attempts. Try again in 10 minutes.')
            result = self.auth.login(data.get('username'), data.get('password'))
            if not result:
                raise RequestError(401, 'Username or password is incorrect.')
            self.auth.logout(token)  # Rotate any previous session in this browser.
            token, csrf = result
            return 200, {'ok': True, 'csrf': csrf}, 'application/json', [('Set-Cookie', self.cookie(token))]
        if path == '/auth/logout' and method == 'POST':
            self.auth.logout(token)
            return 200, {'ok': True}, 'application/json', [('Set-Cookie', self.cookie(clear=True))]
        if method in ('GET', 'HEAD') and path in ('/login', '/login.js', '/web.css', '/nothing.css', '/fonts/doto.ttf', '/images/cape-town.webp'):
            if path == '/login':
                if session:
                    return 302, '', 'text/plain', [('Location', '/')]
                return 200, self.html(STATIC / 'login.html', nonce), 'text/html; charset=utf-8', []
            file = STATIC / path.lstrip('/') if path in ('/login.js', '/web.css') else ASSETS / path.lstrip('/')
            return self.file(file)
        if not session:
            if path.startswith('/api/'):
                raise RequestError(401, 'Sign in to your workspace.')
            return 302, '', 'text/plain', [('Location', '/login')]
        if path.startswith('/api/'):
            params = parse_qs(env.get('QUERY_STRING', ''))
            if path == '/api/bundle' and method == 'POST':
                return 200, evidence_bundle(self.runtime.store.root, data), 'application/zip', [('Content-Disposition', 'attachment; filename="sothis-evidence.zip"')]
            match = re.fullmatch(r'/api/evidence/([a-f0-9]{64})/download', path)
            if match and method in ('GET', 'HEAD'):
                file = self.runtime.store.root / 'archive' / match[1]
                if not file.is_file() or file.is_symlink():
                    raise RequestError(404, 'Archived original not found.')
                status, body, mime, headers = self.file(file, 'application/octet-stream')
                headers.append(('Content-Disposition', f'attachment; filename="sothis-evidence-{match[1][:16]}.bin"'))
                return status, body, mime, headers
            adapter = APIAdapter(self.runtime)
            adapter.api('GET' if method == 'HEAD' else method, path, params, data)
            status, body, mime = adapter.response
            return status, body, mime, []
        if method == 'POST':
            raise RequestError(404, 'Not found.')
        if path in ('/', '/index.html'):
            return 200, self.html(ASSETS / 'index.html', nonce), 'text/html; charset=utf-8', []
        if path in ('/web-runtime.js', '/web-ui.js'):
            return self.file(STATIC / path.lstrip('/'))
        allowed = ('/snapshot.json', '/features.js', '/parties.js', '/party-data.json', '/visuals.js','/icons.js', '/photo-credits.json', '/analytics.js', '/analytics.css', '/analytics-data.json', '/dock.js','/dock.css','/navigation.js', '/provinces.js', '/provinces.css', '/province-data.json', '/education-registers.json','/company-details.js','/daily.js','/personal.js','/share-cards.js','/daily.css','/personal.css','/vendor/pdf.js','/vendor/pdf.worker.js')
        resource = path.startswith(('/images/', '/fonts/', '/icons/')) and Path(path).suffix.lower() in ('.webp', '.jpg', '.png', '.svg', '.ttf', '.woff2')
        file = (ASSETS / path.lstrip('/')).resolve()
        if (path in allowed or resource) and ASSETS.resolve() in file.parents and file.is_file():
            return self.file(file)
        raise RequestError(404, 'Not found.')

    def file(self, file, mime=None):
        if not file.is_file():
            raise RequestError(404, 'Not found.')
        mime = mime or {'.js': 'application/javascript', '.css': 'text/css', '.ttf': 'font/ttf'}.get(file.suffix) or mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        return 200, file.read_bytes(), mime, []

    def __call__(self, env, start_response):
        nonce = secrets.token_urlsafe(20)
        try:
            status, body, mime, extra = self.route(env, nonce)
        except RequestError as exc:
            status, body, mime, extra = exc.status, {'error': exc.message}, 'application/json', []
        except KeyError:
            status, body, mime, extra = 404, {'error': 'Record not found.'}, 'application/json', []
        except (ValueError, TypeError):
            status, body, mime, extra = 400, {'error': 'Invalid request. Check the values and try again.'}, 'application/json', []
        except Exception as exc:
            # The exception type is useful operationally; private request values are not logged.
            logging.error('Sothis request failed (%s)', type(exc).__name__)
            status, body, mime, extra = 500, {'error': 'Server error. Try again or check server health.'}, 'application/json', []
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        headers = [('Content-Type', mime), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'strict-origin-when-cross-origin'),
            ('Content-Security-Policy', f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; img-src 'self' https://www.parliament.gov.za https://parliament.gov.za data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"),
            ('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=(self), web-share=(self)'), *extra]
        start_response(f'{status} {HTTPStatus(status).phrase}', headers)
        return [b'' if env['REQUEST_METHOD'] == 'HEAD' else body]


def create_app(config=None):
    return App(dict(os.environ) if config is None else config)
