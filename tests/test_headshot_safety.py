"""Validate real image conversion and reject excessive/unexpected decoders."""
import importlib
import io
import os
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
from fastapi.testclient import TestClient

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token'}):
    main = importlib.import_module('main')


class HeadshotSafetyTests(unittest.TestCase):
    def setUp(self):
        main.headshot_cache.clear()
        self.addCleanup(main.headshot_cache.clear)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def response(self, size=(350, 254), format='PNG'):
        output = io.BytesIO()
        with Image.new('RGB', size, 'orange') as image:
            image.save(output, format=format)
        return MagicMock(status_code=200, headers={'Content-Type': 'image/png'},
                         content=output.getvalue())

    def test_png_becomes_small_webp_and_second_request_reuses_cache(self):
        with patch.object(main.requests, 'get', return_value=self.response()) as get:
            first = self.client.get('/api/players/headshot/123')
            second = self.client.get('/api/players/headshot/123')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers['content-type'], 'image/webp')
        with Image.open(io.BytesIO(first.content)) as image:
            self.assertLessEqual(max(image.size), 180)
        self.assertEqual(first.content, second.content)
        get.assert_called_once()

    def test_small_compressed_png_with_excessive_pixels_is_rejected(self):
        with patch.object(main.requests, 'get', return_value=self.response((2001, 2000))):
            self.assertEqual(self.client.get('/api/players/headshot/123').status_code, 502)
        self.assertNotIn(123, main.headshot_cache)

    def test_other_formats_cannot_select_unneeded_decoders(self):
        with patch.object(main.requests, 'get', return_value=self.response(format='GIF')):
            self.assertEqual(self.client.get('/api/players/headshot/123').status_code, 502)

    def test_decompression_bomb_does_not_escape_as_internal_server_error(self):
        with patch.object(main.requests, 'get', return_value=self.response()), \
             patch.object(main.Image, 'open', side_effect=Image.DecompressionBombError('private detail')):
            response = self.client.get('/api/players/headshot/123')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private detail', response.text)
