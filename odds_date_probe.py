"""One-shot comparison for the reported November 5 feed discrepancy.

No quote cache, snapshot or prediction writes. Maximum three billable calls.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
import storage
from odds_provider_probe import Caller, ProbeError, account_summary, fixtures_list, coverage

DAY = '2026-11-05'
TEST_ID = 'nba-date-feed-20261105-v1'
BUDGET = 3


def summarize(payload, target_ids, catalog):
    rows = fixtures_list(payload)
    found = {str(row['fixtureId']): row for row in rows}
    return {'fixture_count': len(rows),
            'target_fixture_count': sum(fid in found for fid in target_ids),
            'target_coverage': [coverage(found.get(fid, {'fixtureId': fid}), catalog)
                                for fid in target_ids],
            'sample_dates': sorted({str(row.get('startTime', ''))[:10] for row in rows})[:20]}


def run_once(api_key):
    # Cache reads are not provider calls. Reuse the exact fixture IDs scanned
    # by the production job and the same market definitions.
    with storage.connection() as conn:
        existing = conn.execute('SELECT result FROM nba_provider_probe WHERE test_id=%s', (TEST_ID,)).fetchone()
        if existing:
            return {'reused': True, **existing[0]}
        active = conn.execute("SELECT COUNT(*) FROM nba_scan_attempts WHERE state IN ('queued','running') AND heartbeat_at > NOW()-INTERVAL '2 minutes'").fetchone()[0]
        if active:
            raise ProbeError('Scan active; diagnostic not started')
        calendar = conn.execute("SELECT payload FROM nba_player_cache WHERE cache_key='odds:fixtures:v1'").fetchone()
        markets = conn.execute("SELECT payload FROM nba_player_cache WHERE cache_key='odds:markets:v1'").fetchone()
        if not calendar or not markets:
            raise ProbeError('Saved calendar/catalog unavailable; diagnostic not started')
        targets = []
        for row in fixtures_list(calendar[0].get('data')):
            raw = row.get('startTime')
            try:
                start = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if start.tzinfo and start.astimezone(ZoneInfo('Europe/Rome')).date().isoformat() == DAY:
                    targets.append(str(row['fixtureId']))
            except (ValueError, TypeError, AttributeError):
                continue
        if not targets:
            raise ProbeError('Target fixtures unavailable; diagnostic not started')
        catalog = markets[0].get('data')
        if not isinstance(catalog, dict):
            raise ProbeError('Saved catalog invalid; diagnostic not started')
        reserved = conn.execute('INSERT INTO nba_provider_probe(test_id,result) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING test_id',
                                (TEST_ID, Jsonb({'state':'reserved','billable_request_budget':BUDGET}))).fetchone()
        if not reserved:
            return {'reused':True,'state':'reserved'}
    caller = Caller(api_key, limit=BUDGET, job_id=TEST_ID)
    report = {'test_id':TEST_ID,'date':DAY,'state':'running','billable_request_budget':BUDGET}
    try:
        report['account'] = account_summary(caller.get('account'))
        for label, parameter in [('plural','bookmakers'),('singular','bookmaker')]:
            payload = caller.get('odds-by-tournaments', tournamentIds='132', verbosity=3, **{parameter:'bet365.it'})
            report[label] = summarize(payload, targets, catalog)
        # Prefer a target seen in either bulk response so a successful line set
        # can be compared; otherwise inspect one exact missing fixture only.
        candidates = [r['fixture_id'] for label in ('singular','plural')
                      for r in report[label]['target_coverage'] if r['active_selections']]
        fid = candidates[0] if candidates else targets[0]
        report['single'] = coverage(caller.get('odds', fixtureId=fid, bookmakers='bet365.it', verbosity=3), catalog)
        report['state'] = 'done'
    except ProbeError as exc:
        report.update(state='error', error=str(exc))
    except Exception:
        report.update(state='error', error='Internal date diagnostic error; no automatic retry')
    finally:
        report['billable_calls'] = caller.count
        report['requests'] = caller.history
        with storage.connection() as conn:
            conn.execute('UPDATE nba_provider_probe SET result=%s WHERE test_id=%s', (Jsonb(report),TEST_ID))
    return report
