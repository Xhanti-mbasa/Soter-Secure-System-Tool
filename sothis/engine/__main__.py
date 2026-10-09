import argparse
import json
import os
from pathlib import Path
from .core import Store
from .connectors import Connector, discover
from .server import LensServer

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description='ZA Lens public-records engine')
    parser.add_argument('--data',default=str(ROOT/'data'))
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    d=sub.add_parser('discover');d.add_argument('--url',required=True);d.add_argument('--output')
    c=sub.add_parser('crawl');c.add_argument('--source');c.add_argument('--province');c.add_argument('--pages',type=int,default=5);c.add_argument('--depth',type=int,default=1)
    s=sub.add_parser('search');s.add_argument('query');s.add_argument('--province',default='');s.add_argument('--category',default='')
    ss=sub.add_parser('snapshot');ss.add_argument('--output',default=str(ROOT/'android/app/src/main/assets/snapshot.json'))
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8765)
    imp=sub.add_parser('import');imp.add_argument('file')
    args=parser.parse_args();store=Store(args.data)
    if args.command=='init':
        sources=json.loads((ROOT/'sources.json').read_text());store.seed_sources(sources)
        snapshot_path=ROOT/'android/app/src/main/assets/snapshot.json'
        if store.stats()['documents']==0 and snapshot_path.exists():
            snapshot=json.loads(snapshot_path.read_text())
            for d in snapshot.get('documents',[]):
                source=store.source(d['source_id'])
                if not source or len(d.get('text',''))<40: continue
                doc_id=store.put_document(source,d['url'],d['title'],d['text'],d.get('published_at'),
                                          page=d.get('page'),social_links=d.get('social_links'),
                                          category=d['category'],acquisition='bundled_snapshot')
                with store.connect() as c:
                    c.execute('UPDATE documents SET retrieved_at=? WHERE id=?',(d['retrieved_at'],doc_id))
                    c.execute('UPDATE versions SET retrieved_at=? WHERE id=?',(d['retrieved_at'],doc_id))
        print(json.dumps(store.stats(),indent=2))
    elif args.command=='discover':
        found=discover(args.url)
        output=Path(args.output) if args.output else ROOT/'directory-candidates.json'
        output.write_text(json.dumps(found,indent=2))
        print(f'{len(found)} directory candidates saved to {output}; review before adding to sources.json')
    elif args.command=='crawl':
        connector=Connector(store)
        sources=store.sources()
        if args.source: sources=[s for s in sources if s['id']==args.source]
        if args.province: sources=[s for s in sources if s['province']==args.province]
        sources=[s for s in sources if s.get('enabled') and s.get('access')=='public']
        if not sources: raise SystemExit('No enabled sources match. Run init or choose a valid source/province.')
        for source in sources:
            print(json.dumps(connector.crawl(source['id'],args.pages,args.depth)),flush=True)
    elif args.command=='search': print(json.dumps(store.search(args.query,args.province,args.category),indent=2,ensure_ascii=False))
    elif args.command=='snapshot':
        Path(args.output).write_text(json.dumps(store.snapshot(),ensure_ascii=False))
        print('Snapshot written:',args.output)
    elif args.command=='import':
        records=json.loads(Path(args.file).read_text())
        if isinstance(records,dict): records=[records]
        for r in records:
            source=store.source(r['source_id'])
            if not source: raise SystemExit('Unknown registered source_id')
            print(store.put_document(source,r['url'],r['title'],r['text'],r.get('published_at'),
                                     page=r.get('page'),acquisition='manual_import'))
    elif args.command=='serve':
        token=os.environ.get('ZALENS_API_TOKEN','')
        server=LensServer((args.host,args.port),store,token,ROOT/'android/app/src/main/assets')
        print(f'ZA Lens listening on {args.host}:{args.port}',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:server.server_close()

if __name__=='__main__':main()
