"""Same-origin API processing timing, without collecting visitor data."""
from time import perf_counter


class ApiTimingMiddleware:
    """Measure until response headers, including serialization/compression work.

    This is not total download time or a network percentile. Streaming bodies
    are forwarded untouched and are never buffered by this middleware.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path', '').startswith('/api/'):
            return await self.app(scope, receive, send)
        started = perf_counter()
        async def timed_send(message):
            if message['type'] == 'http.response.start':
                elapsed = max(0, (perf_counter()-started)*1000)
                message = {**message, 'headers': [*message.get('headers', []),
                            (b'server-timing', f'app;dur={elapsed:.2f}'.encode('ascii'))]}
            await send(message)
        await self.app(scope, receive, timed_send)
