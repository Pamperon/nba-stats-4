"""Explicit one-shot current-feed diagnosis, with at most one billable request."""
from datetime import datetime
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
import storage
from odds_provider_probe import Caller, ProbeError, account_summary, compare, coverage


def cached_report(date):
    calendar = storage.cache_read('odds:fixtures:v1', 48) or {}
    markets = storage.cache_read('odds:markets:v1', 48) or {}
    feed = storage.cache_read('odds:nba:bet365.it:v1', 48) or {}
    catalog = markets.get('data') or {}
    fixtures = calendar.get('data') or []
    targets = []
    for fixture in fixtures:
        try:
            start = datetime.fromisoformat(fixture['startTime'].replace('Z', '+00:00'))
            if start.tzinfo and start.astimezone(ZoneInfo('Europe/Rome')).date().isoformat() == date:
                targets.append(fixture)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    data = feed.get('data') or {}
    counts, days = {}, {}
    for fixture in data.values():
        for slug in (fixture.get('bookmakerOdds') or {}):
            counts[slug] = counts.get(slug, 0) + 1
        day = str(fixture.get('startTime') or '')[:10]
        days[day] = days.get(day, 0) + 1
    report = {'date': date, 'feed_identity': feed.get('identity'),
              'feed_fetched_at': feed.get('fetched_at'), 'feed_fixture_count': len(data),
              'feed_bookmaker_counts': counts, 'feed_dates': days,
              'target_coverage': [{**coverage(data.get(str(f['fixtureId']), {}), catalog),
                  'expected_fixture_id': str(f['fixtureId']),
                  'match': f.get('participant1Name', '') + ' - ' + f.get('participant2Name', ''),
                  'present_in_bulk': str(f['fixtureId']) in data} for f in targets]}
    return report, targets, data, catalog


def run_once(date, api_key):
    datetime.strptime(date, '%Y-%m-%d')
    key = 'nba-feed-coverage:' + date + ':v1'
    with storage.connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS nba_provider_probe (
            test_id TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            result JSONB NOT NULL DEFAULT '{}'::jsonb)''')
        existing = conn.execute('SELECT result FROM nba_provider_probe WHERE test_id=%s', (key,)).fetchone()
        if existing:
            return {'reused': True, **existing[0]}
        active = conn.execute("""SELECT COUNT(*) FROM nba_scan_attempts
            WHERE state IN ('queued','running') AND heartbeat_at>NOW()-INTERVAL '2 minutes'""").fetchone()[0]
        if active:
            raise ProbeError('Scan active; diagnostic not started')
        saved = conn.execute('''INSERT INTO nba_provider_probe(test_id,result) VALUES(%s,%s)
            ON CONFLICT DO NOTHING RETURNING test_id''',
            (key, Jsonb({'state': 'reserved', 'billable_request_budget': 1}))).fetchone()
        if not saved:
            return {'reused': True, 'state': 'reserved'}
    caller = Caller(api_key, limit=1, job_id=key)
    report = {'state': 'running', 'test_id': key, 'billable_request_budget': 1}
    try:
        cached, targets, bulk, catalog = cached_report(date)
        report.update(cached)
        report['account'] = account_summary(caller.get('account'))
        # One exact future fixture; no stale hard-coded November 5 matches.
        now = datetime.now(ZoneInfo('UTC'))
        future = [f for f in targets if datetime.fromisoformat(f['startTime'].replace('Z', '+00:00')) > now]
        if not future:
            raise ProbeError('No future fixture in cached calendar; no paid request made')
        fixture = future[0]
        fid = str(fixture['fixtureId'])
        single = caller.get('odds', fixtureId=fid, bookmakers='bet365.it', verbosity=3)
        if not isinstance(single, dict) or str(single.get('fixtureId')) != fid:
            raise ProbeError('Single-fixture identity mismatch')
        report['comparison'] = compare(bulk.get(fid, {}), single, catalog)
        report['single_bookmaker_slugs'] = sorted((single.get('bookmakerOdds') or {}).keys())
        report['state'] = 'done'
    except ProbeError as exc:
        report.update(state='error', error=str(exc))
    except Exception:
        report.update(state='error', error='Current feed diagnostic unavailable; no automatic retry')
    finally:
        report['billable_http_attempts'] = caller.count
        report['requests'] = caller.history
        with storage.connection() as conn:
            conn.execute('UPDATE nba_provider_probe SET result=%s WHERE test_id=%s', (Jsonb(report), key))
    return {'reused': False, **report}
