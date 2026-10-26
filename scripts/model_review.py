"""Repeatable read-only review of archived pregame rows and exact UI tickets.

Only public archives and finalized ESPN boxes. No OddsPapi or database writes.
Current injury reports must never be used to improve a historical backtest.
"""
import argparse
import json
from collections import Counter
import requests
import calibration
import calibration_validation
import minutes_shadow
import recommendations
import settle_espn
from scripts.archive_performance import summarize_unique_opportunities


def review(archives):
    daily, skipped, history, all_original, all_verified = [], [], [], [], []
    for archive in sorted(archives, key=lambda a: a['date']):
        day = archive['date']
        try:
            verified, eligible = settle_espn.settle_archive(archive, day)
        except (ValueError, requests.RequestException) as exc:
            skipped.append({'date': day, 'reason': str(exc)[:180]})
            continue
        bins = calibration.aggregate(verified)
        for (market, bucket), stats in bins.items():
            history.append(dict(date=day, market=market, probability_bin=bucket, **stats))
        rows = archive['results']
        saved = archive.get('recommendations') or recommendations.select(rows, screen_risks=False)
        daily.append({'date': day, 'job_id': archive.get('job_id'),
                      'saved_at': archive.get('saved_at'), 'eligible_lines': eligible,
                      'verified_lines': sum(v['n'] for v in bins.values()),
                      'selection_origin': 'saved' if archive.get('recommendations') else 'reconstructed_legacy_ui',
                      'tickets': recommendations.evaluate(saved, verified),
                      'minutes_screen_comparison': recommendations.evaluate(recommendations.select(rows), verified)})
        all_original.extend(rows)
        all_verified.extend(verified)
    minutes = {}
    for flag in ('normal', 'watch', 'unknown'):
        def include(r):
            return (minutes_shadow.assess(r) == flag and isinstance(r.get('Quota'), (int, float))
                    and 1.20 <= r['Quota'] <= 2.00)
        minutes[flag] = summarize_unique_opportunities(
            [r for r in all_verified if include(r)],
            [r for r in all_original if include(r)])
    ticket_counts = {}
    for name, _, _, _ in recommendations.GROUPS:
        ticket_counts[name] = dict(Counter(d['tickets']['groups'][name]['status'] for d in daily))
    return {'daily': daily, 'skipped': skipped, 'tickets': ticket_counts,
            'calibration_validation': calibration_validation.walk_forward(history),
            'calibration_eligible': bool(calibration.approved_adjustments(history)),
            'minutes_unique_opportunities': minutes,
            'limitations': ['Four dates do not establish profitability or independent validation.',
                           'Alternate lines on one athlete are correlated; only the minutes view deduplicates them.',
                           'Legacy UI tickets are reconstructions, not proof of what a visitor saw.',
                           'Current injuries are never applied to archived predictions.',
                           'Only Over lines exist in these archives; Under performance cannot be inferred.'],
            'odds_api_calls': 0, 'database_writes': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dates', nargs='+', required=True)
    args = parser.parse_args()
    archives, unavailable = [], []
    for day in args.dates:
        response = requests.get('https://nba-stats-4.onrender.com/api/saved/archive',
                                params={'date': day}, timeout=60)
        if response.status_code == 404:
            unavailable.append(day)
            continue
        response.raise_for_status()
        archive = response.json()
        if archive.get('date') != day:
            raise ValueError('Archive date mismatch')
        archives.append(archive)
    result = review(archives)
    result['unavailable_dates'] = unavailable
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
