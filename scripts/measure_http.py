"""Repeatable, read-only baseline; processing time is separate from network time.
Usage: python scripts/measure_http.py --output reports/performance/after-http.json
Run from the same network as baseline. Never triggers an OddsPapi scan.
"""
import argparse
import datetime
import json
import subprocess
import time
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='https://basketlab.it')
parser.add_argument('--output',required=True)
parser.add_argument('--runs',type=int,default=3)
args=parser.parse_args()
paths=['/','/static/app.js','/static/hub-nav.js','/api/health','/api/nba/fixtures?date=2026-11-05','/api/match/form?date=2026-11-05&team_a=Boston%20Celtics&team_b=Atlanta%20Hawks']
rows=[]
for path in paths:
    for run in range(args.runs):
        start=time.perf_counter()
        try:
            with urllib.request.urlopen(args.base+path,timeout=45) as response:
                first=time.perf_counter()
                data=response.read()
                row=dict(path=path,run=run,status=response.status,ttfb_ms=round((first-start)*1000),total_ms=round((time.perf_counter()-start)*1000),bytes=len(data),server_timing=response.headers.get('Server-Timing'))
        except Exception as exc:
            row=dict(path=path,run=run,error=str(exc))
        rows.append(row)
        print(json.dumps(row),flush=True)
with open(args.output,'w') as stream:
    json.dump(dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),samples=rows),stream,indent=2)
