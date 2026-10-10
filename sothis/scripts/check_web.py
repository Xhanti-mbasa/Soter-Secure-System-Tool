#!/usr/bin/env python3
"""Run browser checks against an isolated website with actual session middleware."""
import argparse
import hashlib
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from web.app import create_app
from web.auth import password_hash


class ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chrome')
    parser.add_argument('--chrome-zip')
    parser.add_argument('--playwright', default='playwright')
    parser.add_argument('--screenshots')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        password = secrets.token_urlsafe(24)
        app = create_app({'SOTHIS_DEV':'1','SOTHIS_PUBLIC_ORIGIN':'http://127.0.0.1:8766',
                          'SOTHIS_USERNAME':'qa','SOTHIS_PASSWORD_HASH':password_hash(password),
                          'SOTHIS_DATA':str(Path(temporary)/'data')})
        # This fixture is an already-downloaded public original. It tests delivery
        # without external network availability or a simulated HTTP API.
        raw = b'Public source fixture for website download verification.\n'
        sha = hashlib.sha256(raw).hexdigest()
        (app.runtime.store.root/'archive'/sha).write_bytes(raw)
        server = make_server('127.0.0.1',8766,app,server_class=ThreadedServer,handler_class=QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        chrome = args.chrome
        if args.chrome_zip:
            with zipfile.ZipFile(args.chrome_zip) as bundle:bundle.extractall(Path(temporary)/'browser')
            chrome = str(next((Path(temporary)/'browser').rglob('chrome-headless-shell')))
            Path(chrome).chmod(0o755)
        env = {**os.environ,'PLAYWRIGHT_MODULE':args.playwright,'SOTHIS_TEST_URL':'http://127.0.0.1:8766',
               'SOTHIS_TEST_PASSWORD':password,'SOTHIS_TEST_ARCHIVE_HASH':sha}
        if chrome:env['CHROME_EXECUTABLE']=chrome
        if args.screenshots:env['SOTHIS_SCREENSHOTS']=args.screenshots
        try:
            subprocess.run(['node',str(ROOT/'tests/web_smoke.cjs')],env=env,check=True,cwd=ROOT,timeout=150)
        finally:
            server.shutdown();server.server_close();app.close()


if __name__ == '__main__':main()
