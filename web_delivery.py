"""Explicit caching for public static assets; API data is never handled here."""
from fastapi.staticfiles import StaticFiles
from urllib.parse import parse_qs
from pathlib import Path
import hashlib
import json
from starlette.responses import Response

class VersionedStaticFiles(StaticFiles):
    def __init__(self, *, directory, **kwargs):
        super().__init__(directory=directory, **kwargs)
        root = Path(directory).resolve()
        manifest = root / 'bundles.json'
        self.bundles = {}
        if manifest.exists():
            for name, sources in json.loads(manifest.read_text()).items():
                if Path(name).name != name or Path(name).suffix not in ('.css', '.js'):
                    raise ValueError('Invalid public bundle name')
                parts = []
                for source in sources:
                    path = (root / source).resolve()
                    if not path.is_relative_to(root):
                        raise ValueError('Bundle source outside public assets')
                    parts.append(path.read_bytes())
                # Semicolons preserve statement boundaries between independent scripts.
                separator = b'\n;\n' if name.endswith('.js') else b'\n'
                body = separator.join(parts)
                self.bundles[name] = (body, '"' + hashlib.sha256(body).hexdigest() + '"')

    async def get_response(self,path,scope):
        if path in self.bundles:
            body, etag = self.bundles[path]
            headers = {key.lower(): value for key, value in scope.get('headers', [])}
            cache = 'public, max-age=86400' if parse_qs(scope.get('query_string', b'').decode()).get('v') else 'no-cache'
            metadata = {'ETag': etag, 'Cache-Control': cache}
            if headers.get(b'if-none-match', b'').decode() == etag:
                return Response(status_code=304, headers=metadata)
            metadata['Content-Length'] = str(len(body))
            return Response(body if scope.get('method') != 'HEAD' else b'', headers=metadata,
                            media_type='text/javascript' if path.endswith('.js') else 'text/css')
        response=await super().get_response(path,scope)
        if response.status_code==200:
            version=parse_qs(scope.get('query_string',b'').decode('ascii',errors='ignore')).get('v')
            response.headers['Cache-Control']='public, max-age=86400' if version else 'no-cache'
        return response
