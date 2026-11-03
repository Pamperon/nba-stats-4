import asyncio
import unittest
from unittest.mock import patch
from api_timing import ApiTimingMiddleware


class TimingTests(unittest.TestCase):
    def test_streaming_chunks_are_forwarded_and_header_measures_time_to_headers(self):
        messages=[]
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/plain')]})
            await send({'type':'http.response.body','body':b'first','more_body':True})
            await send({'type':'http.response.body','body':b'last','more_body':False})
        async def send(message):messages.append(message)
        with patch('api_timing.perf_counter',side_effect=[1.,1.025]):
            asyncio.run(ApiTimingMiddleware(app)({'type':'http','path':'/api/test'},None,send))
        self.assertIn((b'server-timing',b'app;dur=25.00'),messages[0]['headers'])
        self.assertEqual([m['body'] for m in messages[1:]],[b'first',b'last'])

    def test_static_pages_are_not_instrumented(self):
        async def app(scope,receive,send):pass
        with patch('api_timing.perf_counter',side_effect=AssertionError('No timer on static pages')):
            asyncio.run(ApiTimingMiddleware(app)({'type':'http','path':'/'},None,None))
