import json
import threading
from pathlib import Path

from engine.core import Store
from engine.parties import PartyService
from engine.server import Handler
from engine.services import Monitoring, PublicServices

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'android/app/src/main/assets'


class Runtime:
    """One process owns collection jobs and monitoring; request threads share it."""
    def __init__(self, data_dir):
        self.store = Store(data_dir)
        self.store.seed_sources(json.loads((ROOT / 'sources.json').read_text()))
        if self.store.stats()['documents'] == 0:
            for document in json.loads((ASSETS / 'snapshot.json').read_text()).get('documents', []):
                source = self.store.source(document['source_id'])
                if not source or len(document.get('text', '')) < 40:
                    continue
                doc_id = self.store.put_document(source, document['url'], document['title'], document['text'],
                    document.get('published_at'), page=document.get('page'), social_links=document.get('social_links'),
                    category=document['category'], acquisition='bundled_snapshot')
                with self.store.connect() as db:
                    db.execute('UPDATE documents SET retrieved_at=? WHERE id=?', (document['retrieved_at'], doc_id))
                    db.execute('UPDATE versions SET retrieved_at=? WHERE id=?', (document['retrieved_at'], doc_id))
        self.job, self.job_lock = None, threading.Lock()
        self.services = PublicServices()
        self.parties = PartyService()
        self.monitoring = Monitoring(self.store, self.services)

    def close(self):
        self.monitoring.stop.set()


class APIAdapter(Handler):
    """Reuse the existing API without opening or exposing the development server."""
    def __init__(self, runtime):
        self.server = runtime
        self.response = None

    def send(self, status, body, mime='application/json; charset=utf-8'):
        self.response = (status, body, mime)
        return self.response
