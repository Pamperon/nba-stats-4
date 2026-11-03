"""Explicit caching for public static assets; API data is never handled here."""
from fastapi.staticfiles import StaticFiles
from urllib.parse import parse_qs

class VersionedStaticFiles(StaticFiles):
    async def get_response(self,path,scope):
        response=await super().get_response(path,scope)
        if response.status_code==200:
            version=parse_qs(scope.get('query_string',b'').decode('ascii',errors='ignore')).get('v')
            response.headers['Cache-Control']='public, max-age=86400' if version else 'no-cache'
        return response
