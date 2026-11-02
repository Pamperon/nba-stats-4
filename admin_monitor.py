"""Bounded, read-only operational summaries. No bookmaker or ESPN requests."""
from datetime import datetime, timezone
import storage
from scripts.audit_calibration import summarize


def report():
    with storage.connection() as conn:
        # A timeout bounds dashboard work; never load full prediction payloads.
        conn.execute("SET LOCAL statement_timeout = '5s'")
        coverage = conn.execute('''
            SELECT scan_date,prediction_count,matched_count
            FROM nba_calibration_settled ORDER BY scan_date DESC LIMIT 60
        ''').fetchall()
        bins = conn.execute('''
            SELECT d.market,d.probability_bin,SUM(d.n),SUM(d.wins),SUM(d.sum_p),SUM(d.sum_brier)
            FROM nba_calibration_daily d JOIN nba_calibration_settled s
              ON s.scan_date=d.scan_date AND s.snapshot_job_id=d.snapshot_job_id
            GROUP BY d.market,d.probability_bin ORDER BY d.market,d.probability_bin
        ''').fetchall()
        scans = conn.execute('''
            SELECT scan_date,state,created_at,
              payload->>'odds_feed_fetched_at',payload->>'odds_feed_source',
              payload->'odds_api_http_requests_scan',payload->'quote_lines_scan',
              payload->'issues',payload->'timings',payload->'minutes_audit'
            FROM nba_scan_snapshots ORDER BY created_at DESC LIMIT 12
        ''').fetchall()
        attempts = conn.execute('''
            SELECT scan_date,state,stage,updated_at,heartbeat_at
            FROM nba_scan_attempts ORDER BY created_at DESC LIMIT 12
        ''').fetchall()
        requests = conn.execute('''
            SELECT state,COUNT(*) FROM nba_odds_request_log
            WHERE created_at >= NOW() - INTERVAL '24 hours' GROUP BY state
        ''').fetchall()
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'read_only': True, 'odds_api_calls': 0,
        'database_pool': storage.pool_stats(),
        'calibration_note': 'Tutte le linee; osservazioni correlate, non campioni indipendenti. Nessuna promozione automatica del modello.',
        'coverage': [{'date': str(day), 'expected': expected, 'matched': matched,
                      'gap': expected-matched,
                      'coverage_pct': 100*matched/expected if expected else None}
                     for day,expected,matched in coverage],
        'calibration': summarize(bins),
        'scans': [{'date': str(day), 'state': state, 'saved_at': saved.isoformat(),
                   'odds_fetched_at': fetched, 'odds_source': source,
                   'http_requests': http, 'quote_lines': lines,
                   'issues': issues or [], 'timings': timings or {},
                   'minutes_audit': minutes or {}}
                  for day,state,saved,fetched,source,http,lines,issues,timings,minutes in scans],
        'attempts': [{'date': str(day), 'state': state, 'stage': stage,
                      'updated_at': updated.isoformat(), 'heartbeat_at': heartbeat.isoformat()}
                     for day,state,stage,updated,heartbeat in attempts],
        'odds_requests_24h': dict(requests),
    }
