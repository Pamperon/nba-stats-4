#!/usr/bin/env python3
"""Non-destructive HTTP baseline for Basket Lab. No paid or write endpoints."""
import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

PATHS = ("/", "/static/app.js", "/static/hub-nav.js", "/static/style.css", "/api/health")

def sample(base, path, timeout):
    req = urllib.request.Request(base.rstrip("/") + path, headers={"User-Agent": "BasketLab-Baseline/1.0", "Accept": "*/*"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return {"status": response.status, "ms": round((time.perf_counter()-start)*1000, 2),
                    "bytes": len(body), "cache_control": response.headers.get("Cache-Control"),
                    "content_encoding": response.headers.get("Content-Encoding")}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"error": str(exc), "ms": round((time.perf_counter()-start)*1000, 2)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://basketlab.it")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--output", default="baseline-http.json")
    args = parser.parse_args()
    if args.runs < 1 or args.runs > 30:
        parser.error("--runs must be between 1 and 30")
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "base": args.base,
              "scope": "HTTP only; not browser navigation, mobile Core Web Vitals, or API match analysis",
              "paths": {}}
    for path in PATHS:
        observations = [sample(args.base, path, args.timeout) for _ in range(args.runs)]
        successful = [x["ms"] for x in observations if x.get("status") == 200]
        report["paths"][path] = {"samples": observations,
                                 "median_ms": round(statistics.median(successful), 2) if successful else None,
                                 "max_ms": max(successful) if successful else None}
    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
