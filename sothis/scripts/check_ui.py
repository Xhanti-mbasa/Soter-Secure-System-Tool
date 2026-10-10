#!/usr/bin/env python3
"""Run UI suites against an isolated seeded engine in one process context."""
import argparse,json,os,subprocess,tempfile,threading,zipfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from engine.core import Store
from engine.server import LensServer
p=argparse.ArgumentParser();p.add_argument('--chrome');p.add_argument('--chrome-zip');p.add_argument('--playwright',default='playwright');p.add_argument('--suite',choices=('ui_smoke.cjs','features_smoke.cjs','party_smoke.cjs','visual_smoke.cjs','analytics_smoke.cjs'));args=p.parse_args()
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'data');snapshot=json.loads((ROOT/'android/app/src/main/assets/snapshot.json').read_text());store.seed_sources(snapshot['sources'])
 for d in snapshot['documents']:
  store.put_document(store.source(d['source_id']),d['url'],d['title'],d['text'],d.get('published_at'),page=d.get('page'),social_links=d.get('social_links'),category=d['category'],acquisition='bundled_snapshot')
 server=LensServer(('127.0.0.1',8765),store,web_dir=ROOT/'android/app/src/main/assets');threading.Thread(target=server.serve_forever,daemon=True).start()
 chrome=args.chrome
 if args.chrome_zip:
  with zipfile.ZipFile(args.chrome_zip) as z:z.extractall(Path(tmp)/'browser')
  chrome=str(next((Path(tmp)/'browser').rglob('chrome-headless-shell')));Path(chrome).chmod(0o755)
 env={**os.environ,'PLAYWRIGHT_MODULE':args.playwright}
 if chrome:env['CHROME_EXECUTABLE']=chrome
 try:
  for suite in ((args.suite,) if args.suite else ('ui_smoke.cjs','features_smoke.cjs','party_smoke.cjs','visual_smoke.cjs','analytics_smoke.cjs')):subprocess.run(['node',str(ROOT/'tests'/suite)],env=env,check=True,timeout=110,cwd=ROOT)
 finally:server.shutdown();server.server_close()
