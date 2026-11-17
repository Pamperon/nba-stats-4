"""Verify the deployed fix and one requested recovery scan, without HTTP replays."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import scheduled_scan as scheduler


def main():
    expected = os.environ['EXPECTED_COMMIT']
    date = os.environ.get('RECOVERY_DATE', '2026-11-18')
    dt.date.fromisoformat(date)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        try:
            health = scheduler.call('/api/health', timeout=20)
            if health.get('deployment_commit') == expected:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(20)
    else:
        raise RuntimeError('Expected deployment unavailable; no scan requested')
    assert health['scan_tracking_ready'] and health['status'] == 'ok'
    print('Verified deployment:', expected, flush=True)
    if os.environ.get('RECOVERY_ACTION') == 'monitor':
        monitor = scheduler.call('/api/admin/monitor')
        print(json.dumps({'read_only': monitor['read_only'], 'odds_api_calls': monitor['odds_api_calls'],
            'database_pool': monitor['database_pool'], 'coverage_days': len(monitor['coverage']),
            'recent_scans': monitor['scans'][:4],
            'odds_requests_24h': monitor['odds_requests_24h']}, ensure_ascii=False), flush=True)
        return
    if os.environ.get('RECOVERY_ACTION') == 'diagnose':
        report = scheduler.call('/api/diagnostics/odds-coverage?date=' + date, method='POST', timeout=90)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if report.get('state') != 'done':
            raise RuntimeError('Diagnostic incomplete; inspect saved report before retrying')
        return
    # POST is sent exactly once. A timeout must be investigated using durable
    # status, never replayed automatically because the scan may already exist.
    job = scheduler.call('/api/scan?date=' + date + '&source=github', method='POST')
    print('Recovery job:', job['job_id'], 'reused:', job.get('reused'), flush=True)
    scheduler.wait_for_scan(job['job_id'], date)
    result = scheduler.call('/api/saved/time?date=' + date)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    try:
        monitor = scheduler.call('/api/admin/monitor')
        print(json.dumps({'database_pool': monitor['database_pool'],
                          'recent_scans': monitor['scans'][:4],
                          'odds_requests_24h': monitor['odds_requests_24h']}, ensure_ascii=False), flush=True)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        print('Optional monitoring unavailable:', type(exc).__name__, flush=True)
    if not result.get('quote_lines_scan'):
        raise RuntimeError('Recovery completed but provider coverage is still empty; inspect report before another paid scan')


if __name__ == '__main__':
    main()
