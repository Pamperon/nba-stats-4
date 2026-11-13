import json
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_delivery import VersionedStaticFiles


class WebBundleTests(unittest.TestCase):
    def test_order_cache_validation_head_and_original_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.js').write_text('window.first = 1')
            (root / 'b.js').write_text('window.second = window.first + 1')
            (root / 'bundles.json').write_text(json.dumps({'site-app.js': ['a.js', 'b.js']}))
            app = FastAPI()
            app.mount('/static', VersionedStaticFiles(directory=root))
            with TestClient(app) as client:
                response = client.get('/static/site-app.js?v=1')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.text, 'window.first = 1\n;\nwindow.second = window.first + 1')
                self.assertIn('text/javascript', response.headers['content-type'])
                self.assertEqual(response.headers['cache-control'], 'public, max-age=86400')
                self.assertEqual(client.get('/static/site-app.js', headers={'If-None-Match': response.headers['etag']}).status_code, 304)
                head = client.head('/static/site-app.js?v=1')
                self.assertEqual(head.content, b'')
                self.assertEqual(head.headers['content-length'], response.headers['content-length'])
                self.assertEqual(client.get('/static/a.js').text, 'window.first = 1')
                self.assertEqual(client.get('/static/missing.js').status_code, 404)
                self.assertEqual(client.get('/static/site-app.js').headers['cache-control'], 'no-cache')

    def test_manifest_cannot_bundle_private_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'bundles.json').write_text(json.dumps({'site-app.js': ['../private.txt']}))
            with self.assertRaises(ValueError):
                VersionedStaticFiles(directory=root)
