import html
import importlib
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from fastapi.testclient import TestClient
import seo


class SeoPagesTests(unittest.TestCase):
    def test_each_page_has_its_own_metadata_and_native_navigation(self):
        with patch.object(seo, 'saved_players', return_value=()):
            for path, (title, description) in seo.PAGES.items():
                document = seo.render(path)
                self.assertIn('<title>' + html.escape(title) + '</title>', document)
                self.assertIn('rel="canonical" href="https://basketlab.it' + path + '"', document)
                self.assertIn('<a href="/pronostici"', document)
                self.assertIn('<a href="/giocatori"', document)
                self.assertEqual(document.count('rel="canonical"'), 1)
                self.assertEqual(document.count('name="description"'), 1)
                self.assertIn('google-adsense-account', document)
                self.assertIn('google-site-verification', document)

    def test_sitemap_contains_real_player_urls_without_filter_duplicates(self):
        players = [{'id':'22', 'name':'Álex Test'}, {'id':'22','name':'Álex Test'}]
        tree = ET.fromstring(seo.sitemap(players))
        urls = [e.text for e in tree.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertIn('https://basketlab.it/giocatori/alex-test-22', urls)
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all('?' not in u and '#' not in u for u in urls))
        self.assertNotIn('https://basketlab.it/partite', urls)

    def test_bundle_and_lazy_urls_change_when_their_sources_change(self):
        document = seo.render('/', ())
        bundle = re.search(r'/static/site-app.js\?v=([a-f0-9]{12})', document)[1]
        with patch.object(seo, '_asset_version', return_value='changed-source'):
            changed = seo.render('/', ())
        self.assertNotIn('/static/site-app.js?v=' + bundle, changed)
        self.assertNotEqual(
            json.loads(re.search(r'id="bl-asset-versions">(.*?)</script>', document)[1]),
            json.loads(re.search(r'id="bl-asset-versions">(.*?)</script>', changed)[1]))
        self.assertEqual(document.count('/static/site-app.js?v=' + bundle), 2)
        self.assertIn('rel="preload" as="image" href="/static/home-lab-', document)
        self.assertNotIn('rel="preload" as="image" href="/static/home-lab-', seo.render('/nba', ()))

    def test_metadata_is_escaped_and_transient_match_pages_not_indexed(self):
        document = seo.render('/giocatori/alex-test-22', [{'id':'22','name':'Alex </script><script>bad</script>'}])
        self.assertNotIn('<script>bad</script>', document)
        page = json.loads(re.search(r'id="bl-page-schema">(.*?)</script>', document)[1])
        self.assertIn('Alex', page['name'])
        self.assertIn('noindex,follow', seo.render('/analisi-partita'))

    def test_progressive_content_links_rosters_and_escaped_saved_stats(self):
        players = [{'id':'22', 'name':'Alex Test', 'team_id':'2', 'team':'Boston Celtics'}]
        with patch.object(seo, '_saved_log', return_value=[{'GAME_DATE':'2026-11-10', 'MATCHUP':'BOS < NY', 'PTS':25, 'REB':8, 'AST':4}]):
            document = seo.render('/giocatori/alex-test-22', players)
        self.assertIn('BOS &lt; NY', document)
        self.assertIn('<td>25</td>', document)
        self.assertIn('href="/squadre/boston-celtics-2"', document)
        team = seo.render('/squadre/boston-celtics-2', players)
        self.assertIn('href="/giocatori/alex-test-22"', team)
        self.assertIn('id="bl-initial-content"', team)
        self.assertNotIn('id="bl-initial-content"', seo.render('/', ()))

    def test_http_routes_aliases_queries_and_unknown_ids(self):
        with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
            main = importlib.import_module('main')
        client = TestClient(main.app)
        try:
            with patch.object(main.storage, 'cache_read', side_effect=AssertionError('No database access for static pages')):
                for path in seo.PAGES:
                    response = client.get(path + '?utm_source=test')
                    canonical = '/nba' if path == '/partite' else path
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('href="https://basketlab.it' + canonical + '"', response.text)
                    self.assertEqual(response.headers['cache-control'], 'no-cache')
            alias = client.get('/statistiche?mercato=PTS', follow_redirects=False)
            self.assertEqual(alias.status_code, 301)
            self.assertEqual(alias.headers['location'], '/giocatori?mercato=PTS')
            with patch.object(seo, 'saved_players', return_value=({'id':'22','name':'Alex Test'},)):
                self.assertEqual(client.get('/giocatori/alex-test-22').status_code, 200)
                self.assertEqual(client.get('/giocatori/missing-23').status_code, 404)
                self.assertEqual(client.get('/giocatori/invalid').status_code, 404)
                self.assertIn('/giocatori/alex-test-22', client.get('/sitemap.xml').text)
                redirect = client.get('/giocatori/wrong-name-22?mercato=REB', follow_redirects=False)
                self.assertEqual(redirect.status_code, 301)
                self.assertEqual(redirect.headers['location'], '/giocatori/alex-test-22?mercato=REB')
            redirect = client.get('/squadre/wrong-name-2', follow_redirects=False)
            self.assertEqual(redirect.status_code, 301)
            self.assertEqual(redirect.headers['location'], '/squadre/boston-celtics-2')
            redirect = client.get('/partite?data=2026-11-14', follow_redirects=False)
            self.assertEqual(redirect.status_code, 301)
            self.assertEqual(redirect.headers['location'], '/nba?data=2026-11-14')
            with patch.object(seo, 'saved_players', return_value=()):
                self.assertEqual(client.get('/giocatori/fake-22').status_code, 503)
            for path in ('/api/missing', '/static/missing.js', '/missing'):
                self.assertEqual(client.get(path).status_code, 404)
            self.assertEqual(client.get('/static/modules/router.js?v=seo-pages-1').headers['cache-control'], 'public, max-age=86400')
            self.assertEqual(client.get('/static/sw.js').headers['cache-control'], 'no-cache')
        finally:
            client.close()


if __name__ == '__main__':
    unittest.main()
