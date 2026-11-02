"""Explain every historical calibration gap without database writes or paid calls.

Run: python scripts/settlement_gap_audit.py --output /path/report.json
Optional --input is a local JSON export of the query below, for reproducibility.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage
import settle_espn
from settlement_audit import diagnose


def load():
    with storage.connection() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        rows = conn.execute('''
            SELECT s.scan_date,s.snapshot_job_id,s.prediction_count,s.matched_count,
                   a.payload->'results',a.payload->>'scan_finished_at',a.created_at
            FROM nba_calibration_settled s
            JOIN nba_scan_snapshots a ON a.job_id=s.snapshot_job_id
            ORDER BY s.scan_date
        ''').fetchall()
    return [dict(scan_date=str(day),snapshot_job_id=job,prediction_count=n,matched_count=m,
                 snapshot=dict(results=results,scan_finished_at=finished,saved_at=saved.isoformat()))
            for day,job,n,m,results,finished,saved in rows]


def audit(items):
    evidence = {}
    # Fetch each date once; final_events also inspects neighboring league dates.
    for day in sorted({item['scan_date'] for item in items}):
        evidence[('events',day)] = settle_espn.final_events(day,require_all_final=False)
    ids = {event['id'] for events in evidence.values() for event in events}
    def box(eid):
        try:
            return eid,settle_espn.fetch(settle_espn.BASE+'/summary',event=eid)
        except (ValueError,settle_espn.requests.RequestException):
            return eid,None
    with ThreadPoolExecutor(max_workers=4) as pool:
        for eid,summary in pool.map(box,sorted(ids)):
            if summary is not None:
                evidence[('summary',eid)] = summary
    reports,totals = [],Counter()
    for item in items:
        report,_ = diagnose(item['snapshot'],item['scan_date'],evidence)
        report.update(snapshot_job_id=item['snapshot_job_id'],
                      stored_expected=item['prediction_count'],stored_matched=item['matched_count'])
        report['matches_stored_counts'] = (report['eligible']==item['prediction_count']
                                          and report['reasons'].get('matched',0)==item['matched_count'])
        totals.update(report['reasons'])
        reports.append(report)
    return {'read_only':True,'database_writes':0,'odds_api_calls':0,
            'reasons':dict(totals),'days':reports,
            'note':'Absent boxscore athletes are unresolved, not assumed losses or confirmed DNP. Different lines for one player-game are correlated.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    items=json.loads(args.input.read_text()) if args.input else load()
    result=audit(items)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'reasons':result['reasons'],'days':len(result['days']),
                      'reconciled':all(d['matches_stored_counts'] for d in result['days'])}))


if __name__=='__main__':
    main()
