"""Isolated API tests: never writes the real vocabulary or user files."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import vocabulary as v

def main():
    with tempfile.TemporaryDirectory() as folder, patch.object(v, 'DB_PATH', Path(folder) / 'test.sqlite3'), patch.object(v, 'get_user_by_token', side_effect=lambda t: {'a': 'alice', 'b': 'bob'}.get(t)), patch.object(v, 'get_user_info', return_value={'role': 'viewer'}):
        app = FastAPI()
        app.include_router(v.router)
        client = TestClient(app)
        a, b = {'Authorization': 'Bearer a'}, {'Authorization': 'Bearer b'}
        entry = dict(word='cloud', meaning='meaning one', article_id='zhenti_2010_5', article_title='Part B', sentence='Clouds cloud the view.', sentence_idx='0-0')
        assert client.get('/data/vocabulary').status_code == 401
        assert client.post('/data/vocabulary', json={'entries': [entry]}).status_code == 401
        assert client.post('/data/vocabulary', headers=a, json={'entries': [entry]}).status_code == 200
        assert len(client.get('/data/vocabulary', headers=a).json()['entries']) == 1
        assert client.get('/data/vocabulary', headers=b).json()['entries'] == []
        entry['meaning'] = 'updated'
        client.post('/data/vocabulary', headers=a, json={'entries': [entry]})
        saved = client.get('/data/vocabulary', headers=a).json()['entries']
        assert len(saved) == 1 and saved[0]['meaning'] == 'updated'
        entry['article_id'] = 'article_3'
        client.post('/data/vocabulary', headers=a, json={'entries': [entry]})
        assert len(client.get('/data/vocabulary', headers=a).json()['entries']) == 2
        # New app/client reads the same persisted data.
        other = FastAPI(); other.include_router(v.router)
        assert len(TestClient(other).get('/data/vocabulary', headers=a).json()['entries']) == 2
        print('PASS: auth, account isolation, persistence, deduplication, multiple sources, Part B identity')

if __name__ == '__main__':
    main()
