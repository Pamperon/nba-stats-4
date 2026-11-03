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


UNFILTERED_ID = 'nba-unfiltered-feed-20261105-v2'


def bet365_sources(fixture, fid, catalog):
    result = confirmed_coverage(fixture, fid, catalog)
    result['sources'] = {}
    for slug, book in (fixture.get('bookmakerOdds') or {}).items():
        if 'bet365' in slug.lower():
            mapped = {**fixture, 'bookmakerOdds': {'bet365.it': book}}
            result['sources'][slug] = confirmed_coverage(mapped, fid, catalog)
    return result


def run_unfiltered_once(api_key):
    """Read-only comparison: metadata, one known game, and NBA bulk, at most 3 calls."""
    with storage.connection() as conn:
        existing = conn.execute('SELECT result FROM nba_provider_probe WHERE test_id=%s', (UNFILTERED_ID,)).fetchone()
        if existing:
            return {'reused': True, **existing[0]}
        active = conn.execute("SELECT COUNT(*) FROM nba_scan_attempts WHERE state IN ('queued','running') AND heartbeat_at > NOW()-INTERVAL '2 minutes'").fetchone()[0]
        if active:
            raise ProbeError('Scan active; diagnostic not started')
        saved = conn.execute("SELECT payload FROM nba_player_cache WHERE cache_key='odds:markets:v1'").fetchone()
        catalog = saved[0].get('data') if saved else None
        if not isinstance(catalog, dict):
            raise ProbeError('Saved catalog unavailable; no provider requests made')
        reserved = conn.execute('INSERT INTO nba_provider_probe(test_id,result) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING test_id',
                                (UNFILTERED_ID, Jsonb({'state':'reserved','billable_request_budget':3}))).fetchone()
        if not reserved:
            return {'reused':True,'state':'reserved'}
    caller = Caller(api_key, limit=3, job_id=UNFILTERED_ID)
    report = {'test_id':UNFILTERED_ID,'state':'running','billable_request_budget':3}
    try:
        metadata = caller.get('bookmakers')
        rows = metadata if isinstance(metadata, list) else metadata.get('bookmakers', metadata.get('data', []))
        if isinstance(rows, dict):
            rows = list(rows.values())
        report['bookmakers'] = [{k: row.get(k) for k in ('bookmakerName','slug','cloneOf','liveOdds')}
                                for row in rows if isinstance(row, dict) and 'bet365' in str(row.get('slug', '')).lower()]
        fid = next(iter(CONFIRMED))
        report['single'] = bet365_sources(caller.get('odds', fixtureId=fid, verbosity=3), fid, catalog)
        bulk = fixtures_list(caller.get('odds-by-tournaments', tournamentIds='132', verbosity=3))
        report['bulk_fixture_count'] = len(bulk)
        report['bulk_confirmed'] = [bet365_sources(row, str(row['fixtureId']), catalog)
                                    for row in bulk if str(row.get('fixtureId')) in CONFIRMED]
        report['state'] = 'done'
    except ProbeError as exc:
        report.update(state='error',error=str(exc))
    except Exception:
        report.update(state='error',error='Unfiltered diagnostic error; no automatic retry')
    finally:
        report['billable_calls'] = caller.count
        report['requests'] = caller.history
        with storage.connection() as conn:
            conn.execute('UPDATE nba_provider_probe SET result=%s WHERE test_id=%s', (Jsonb(report),UNFILTERED_ID))
    return report


CONFIRMED_ID = 'nba-confirmed-props-20261105-v1'
# Exact games and Italian times provided in the user's Bet365 screenshot.
CONFIRMED = {
    'id1100013273719518': ('Washington Wizards', 'Atlanta Hawks', '2026-11-05T01:00:00+01:00'),
    'id1100013273719524': ('New York Knicks', 'Chicago Bulls', '2026-11-05T01:30:00+01:00'),
    'id1100013273719530': ('Oklahoma City Thunder', 'Cleveland Cavaliers', '2026-11-05T02:00:00+01:00'),
}


def confirmed_coverage(fixture, fid, catalog, fixtures=CONFIRMED):
    if str(fixture.get('fixtureId')) != fid:
        raise ProbeError('Single response fixture ID mismatch')
    home, away, expected = fixtures[fid]
    try:
        actual = datetime.fromisoformat(fixture['startTime'].replace('Z', '+00:00'))
        if actual.tzinfo is None or actual != datetime.fromisoformat(expected):
            raise ValueError('Time mismatch')
        if {fixture['participant1Name'], fixture['participant2Name']} != {home, away}:
            raise ValueError('Team mismatch')
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ProbeError('Single response does not match confirmed game/date') from None
    book = (fixture.get('bookmakerOdds') or {}).get('bet365.it') or {}
    markets = book.get('markets') or {}
    all_players = sum(bool(player.get('active') and player.get('playerName')
                           and isinstance(player.get('price'), (int,float)) and player['price'] > 1)
                      for market in markets.values() if market.get('marketActive') is True
                      for outcome in (market.get('outcomes') or {}).values()
                      for player in (outcome.get('players') or {}).values())
    return {**coverage(fixture,catalog), 'home':home,'away':away,'start_at_italy':expected,
            'bookmaker_slugs':sorted((fixture.get('bookmakerOdds') or {}).keys()),
            'bookmaker_active':book.get('bookmakerIsActive'),
            'markets_total':len(markets),'active_player_outcomes_all_markets':all_players}


def run_confirmed_once(api_key, evening=False):
    test_id = CONFIRMED_ID
    fixtures = CONFIRMED
    budget = 3
    if evening:
        test_id = 'nba-confirmed-props-20261105-evening-v1'
        fixtures = dict(CONFIRMED)
        del fixtures['id1100013273719530']
        fixtures['id1100013273719520'] = (
            'Boston Celtics', 'Milwaukee Bucks', '2026-11-05T01:30:00+01:00')
        budget = 4
    with storage.connection() as conn:
        existing = conn.execute('SELECT result FROM nba_provider_probe WHERE test_id=%s', (test_id,)).fetchone()
        if existing:
            return {'reused':True,**existing[0]}
        active = conn.execute("SELECT COUNT(*) FROM nba_scan_attempts WHERE state IN ('queued','running') AND heartbeat_at > NOW()-INTERVAL '2 minutes'").fetchone()[0]
        if active:
            raise ProbeError('Scan active; confirmed diagnostic not started')
        saved = conn.execute("SELECT payload FROM nba_player_cache WHERE cache_key='odds:markets:v1'").fetchone()
        catalog = saved[0].get('data') if saved else None
        if not isinstance(catalog, dict):
            raise ProbeError('Saved catalog unavailable; no provider requests made')
        reserved = conn.execute('INSERT INTO nba_provider_probe(test_id,result) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING test_id',
                                (test_id,Jsonb({'state':'reserved','billable_request_budget':budget}))).fetchone()
        if not reserved:
            return {'reused':True,'state':'reserved'}
    caller = Caller(api_key,limit=budget,job_id=test_id)
    report = {'test_id':test_id,'state':'running','billable_request_budget':budget,'fixtures':[]}
    try:
        bulk = {}
        if evening:
            rows = fixtures_list(caller.get('odds-by-tournaments', tournamentIds='132',
                                            bookmakers='bet365.it', verbosity=3))
            bulk = {str(row['fixtureId']): row for row in rows}
        for fid in fixtures:
            fixture = caller.get('odds',fixtureId=fid,bookmakers='bet365.it',verbosity=3)
            item = confirmed_coverage(fixture, fid, catalog, fixtures)
            if evening:
                item['bulk_present'] = fid in bulk
                bulk_coverage = coverage(bulk.get(fid, {}), catalog)
                item['bulk_active_selections'] = bulk_coverage['active_selections']
                item['bulk_by_market_type'] = bulk_coverage['by_market_type']
            report['fixtures'].append(item)
        report['state'] = 'done'
    except ProbeError as exc:
        report.update(state='error',error=str(exc))
    except Exception:
        report.update(state='error',error='Confirmed diagnostic error; no automatic retry')
    finally:
        report['billable_calls']=caller.count;report['requests']=caller.history
        with storage.connection() as conn:
            conn.execute('UPDATE nba_provider_probe SET result=%s WHERE test_id=%s',(Jsonb(report),test_id))
    return report
