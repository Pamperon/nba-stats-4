"""Versioned pregame selection policy, stored with each scan for later audit.

Risk screening does not change a player's empirical probability.
"""
import math
import minutes_shadow

VERSION = "risk-screen-v1"
GROUPS = (("Singola", 1, 1.70, 2.00), ("Doppia", 2, 1.40, 1.69),
          ("Tripla", 3, 1.20, 1.39))
BLOCKED = {"out", "doubtful", "questionable", "day-to-day", "suspension"}


def rejection_reasons(row, screen_risks=True):
    reasons = []
    try:
        p, price, games, season, minutes, recent = (
            float(row[k]) for k in ("Prob. stimata %", "Quota", "Partite",
                                   "Stagione %", "Minuti medi", "Minuti ultime 5"))
        if not all(math.isfinite(x) for x in (p, price, games, season, minutes, recent)):
            return ["dati incompleti"]
    except (KeyError, ValueError, TypeError):
        return ["dati incompleti"]
    if row.get("Stato analisi") != "Valutabile (stima empirica)":
        reasons.append("analisi non valutabile")
    if not 0 < p < 100 or price <= 1:
        return reasons + ["stima o quota non valida"]
    if games < 10 or season < 50 or minutes < 15:
        reasons.append("storico insufficiente")
    if recent < 0.65 * minutes or (screen_risks and minutes_shadow.assess(row) == "watch"):
        reasons.append("minutaggio in calo")
    if p - 100 / price < 3:
        reasons.append("value insufficiente")
    availability = row.get("Disponibilità ESPN")
    if screen_risks and availability in BLOCKED:
        reasons.append("disponibilità incerta o assenza segnalata")
    if screen_risks and availability == "unknown":
        reasons.append("disponibilità non verificata")
    return reasons


def select(rows, screen_risks=True):
    eligible = [row for row in rows if not rejection_reasons(row, screen_risks)]
    eligible.sort(key=lambda r: (-float(r["Prob. stimata %"]),
                                -float(r.get("Value stimato %") or 0)))
    output = {}
    for name, count, low, high in GROUPS:
        chosen, used = [], set()
        for row in eligible:
            key = str(row.get("Giocatore") or "").strip().lower()
            if not key or key in used or not low <= float(row["Quota"]) <= high:
                continue
            used.add(key)
            chosen.append(dict(row))
            if len(chosen) == count:
                break
        output[name] = {"complete": len(chosen) == count, "legs": chosen}
    return {"policy": VERSION if screen_risks else "reconstructed-legacy-ui", "groups": output}



DAILY_VERSION = "daily-lines-v1"
DAILY_MIN_ODDS = 1.20
DAILY_MAX_ODDS = 2.20
# Conservative provisional reliability floor; validate against settled history.
DAILY_MIN_PROBABILITY = 0.70


def select_daily(rows, screen_risks=True):
    """Prospective, variable-size selections: one line per athlete and game.

    Rank by estimated hit probability, then estimated expected value. No forced
    picks and no hindsight outcomes. Keep the risk screen unchanged.
    """
    eligible = []
    for row in rows:
        if rejection_reasons(row, screen_risks):
            continue
        price = float(row["Quota"])
        probability = float(row["Prob. stimata %"]) / 100
        if not DAILY_MIN_ODDS <= price <= DAILY_MAX_ODDS:
            continue
        if probability < DAILY_MIN_PROBABILITY:
            continue
        eligible.append((probability, probability * price - 1, row))
    eligible.sort(key=lambda item: (-item[0], -item[1],
                                    str(item[2].get("Giocatore") or ""),
                                    str(item[2].get("Mercato") or ""),
                                    str(item[2].get("Linea") or "")))
    chosen, used = [], set()
    for _, _, row in eligible:
        athlete = str(row.get("ESPN ID") or row.get("Giocatore") or "").strip().casefold()
        fixture = str(row.get("Partita") or "").strip().casefold()
        if not athlete or not fixture or (fixture, athlete) in used:
            continue
        used.add((fixture, athlete))
        chosen.append(dict(row))
    return {"policy": DAILY_VERSION, "lines": chosen}



def select_single(rows):
    """One independent daily candidate, subject to the existing risk screen."""
    candidates = []
    for row in rows:
        if rejection_reasons(row):
            continue
        try:
            price = float(row['Quota'])
            probability = float(row['Prob. stimata %'])
        except (KeyError, TypeError, ValueError):
            continue
        if not (1.70 <= price <= 2.20 and probability >= 60
                and probability - 100 / price >= 5):
            continue
        candidates.append((probability * price / 100 - 1, probability, row))
    candidates.sort(key=lambda item: (-item[0], -item[1],
                                      str(item[2].get('Giocatore') or ''),
                                      str(item[2].get('Mercato') or '')))
    return dict(candidates[0][2]) if candidates else None

def evaluate(saved, verified):
    """Evaluate exact saved legs, never substitute a hindsight winning player.

    Missing athletes remain unresolved; no assumption about bookmaker refunds.
    """
    def key(row):
        return (row.get('Partita'), row.get('Squadra'),
                str(row.get('ESPN ID') or row.get('Giocatore')),
                row.get('Mercato'), str(row.get('Scelta', '')).lower(),
                float(row['Linea']))
    lookup = {key(row): row for row in verified if row.get('played') is True}
    if "lines" in saved:
        legs = []
        for row in saved["lines"]:
            match = lookup.get(key(row))
            actual = float(match["actual"]) if match is not None else None
            line = float(row["Linea"])
            win = None if actual is None or actual == line else (
                actual > line if str(row["Scelta"]).lower() == "over" else actual < line)
            legs.append({"player": row.get("Giocatore"), "market": row["Mercato"],
                         "choice": row["Scelta"], "line": line, "odds": row["Quota"],
                         "estimated_probability": row.get("Prob. stimata %"),
                         "actual": actual, "win": win})
        return {"policy": saved.get("policy"), "lines": legs}
    groups = {}
    for name, count, _, _ in GROUPS:
        chosen = saved.get('groups', {}).get(name, {}).get('legs', [])
        legs = []
        odds = 1.0
        for row in chosen:
            match = lookup.get(key(row))
            actual = float(match['actual']) if match is not None else None
            line = float(row['Linea'])
            win = None if actual is None or actual == line else (
                actual > line if str(row['Scelta']).lower() == 'over' else actual < line)
            odds *= float(row['Quota'])
            legs.append({'player': row.get('Giocatore'), 'market': row['Mercato'],
                         'choice': row['Scelta'], 'line': line, 'odds': row['Quota'],
                         'estimated_probability': row.get('Prob. stimata %'),
                         'actual': actual, 'win': win})
        complete = len(legs) == count
        status = ('incomplete' if not complete else 'lost' if any(r['win'] is False for r in legs)
                  else 'unresolved' if any(r['win'] is None for r in legs) else 'won')
        distinct_games = all(r.get('Partita') for r in chosen) and len({str(r['Partita']).strip().lower() for r in chosen}) == len(chosen)
        price_available = complete and distinct_games
        groups[name] = {'status': status, 'legs': legs,
                        'combined_odds': round(odds, 4) if price_available else None,
                        'unit_profit': (odds - 1 if status == 'won' else -1 if status == 'lost' else None) if price_available else None,
                        'price_basis': 'product_of_saved_odds' if price_available else 'combination_price_unavailable'}
    return {'policy': saved.get('policy'), 'groups': groups}


def settle_snapshots(day):
    """Incrementally verify published singles and Top 5, preserving prior evidence."""
    import storage
    import settle_espn
    from psycopg.types.json import Jsonb
    with storage.connection() as conn:
        snapshots = conn.execute("""
            SELECT s.job_id,s.payload,s.created_at,r.report
            FROM nba_scan_snapshots s
            LEFT JOIN nba_recommendation_results r ON r.snapshot_job_id=s.job_id
            WHERE s.scan_date=%s AND s.payload ? 'recommendations'
            ORDER BY s.created_at
        """, (day,)).fetchall()
    count, evidence = 0, {}
    for job_id, payload, created_at, prior in snapshots:
        saved = payload.get('recommendations')
        if not isinstance(saved, dict) or not payload.get('results'):
            continue
        snapshot = {**payload, 'job_id': job_id, 'saved_at': created_at.isoformat()}
        try:
            verified = settle_espn.settle_completed_fixtures(snapshot, day, evidence=evidence)
        except (ValueError, KeyError) as exc:
            import logging
            logging.getLogger(__name__).warning('ESPN settlement pending %s %s: %s', day, job_id, exc)
            continue
        if not verified:
            continue
        report = evaluate(saved, verified)
        # Never discard a previously confirmed outcome on later partial retries.
        if isinstance(prior, dict):
            def merge_legs(old, new):
                for old_leg, new_leg in zip(old, new):
                    if old_leg.get('actual') is not None:
                        new_leg['actual'] = old_leg['actual']
                        new_leg['win'] = old_leg['win']
            if 'lines' in report:
                merge_legs(prior.get('lines', []), report['lines'])
            else:
                for group_name, group in report.get('groups', {}).items():
                    old_group = prior.get('groups', {}).get(group_name, {})
                    merge_legs(old_group.get('legs', []), group.get('legs', []))
                    wins = [leg.get('win') for leg in group.get('legs', [])]
                    if group.get('status') != 'incomplete':
                        group['status'] = ('lost' if False in wins else
                                           'unresolved' if None in wins else 'won')
        if payload.get('model_shadow'):
            import shadow_study
            report['model_shadow'] = shadow_study.evaluate(payload['model_shadow'], verified)
        with storage.connection() as conn:
            conn.execute("""
                INSERT INTO nba_recommendation_results(snapshot_job_id,scan_date,report)
                VALUES (%s,%s,%s)
                ON CONFLICT(snapshot_job_id) DO UPDATE SET report=EXCLUDED.report
            """, (job_id, day, Jsonb(report)))
            single_row = conn.execute("""
                SELECT selection,outcome FROM nba_official_daily_singles
                WHERE scan_date=%s AND snapshot_job_id=%s
            """, (day, job_id)).fetchone()
            if single_row and single_row[0] and (
                    not single_row[1] or single_row[1].get('status') == 'unresolved'):
                leg = evaluate({'lines': [single_row[0]]}, verified)['lines'][0]
                if leg['win'] is not None:
                    conn.execute("""
                        UPDATE nba_official_daily_singles SET outcome=%s
                        WHERE scan_date=%s AND snapshot_job_id=%s
                          AND (outcome IS NULL OR outcome->>'status'='unresolved')
                    """, (Jsonb({'status': 'won' if leg['win'] else 'lost',
                                 'actual': leg['actual']}), day, job_id))
        count += 1
    return count
