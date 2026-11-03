"""Deep links use the same shell; unknown API and asset paths remain 404."""
import os
import importlib
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

class SpaRoutesTests(unittest.TestCase):
    def test_all_routes_serve_identical_shell_without_data_access(self):
        with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
            main=importlib.import_module('main')
        with patch.object(main.storage,'cache_read',side_effect=AssertionError('Shell must not read data')):
            client=TestClient(main.app)
            shell=client.get('/')
            for route in ['pronostici','partite','analisi-partita','archivio','statistiche','analisi-quote','come-funziona']:
                response=client.get('/'+route)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.content,shell.content)
                self.assertEqual(response.headers['cache-control'],'no-cache')
            for route in ['/api/missing','/static/missing.js','/missing']:
                self.assertEqual(client.get(route).status_code,404)
            versioned=client.get('/static/modules/router.js?v=routes-1')
            self.assertEqual(versioned.headers['cache-control'],'public, max-age=86400')
            self.assertEqual(client.get('/static/sw.js').headers['cache-control'],'no-cache')
            client.close()
