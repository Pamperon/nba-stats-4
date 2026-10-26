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
        groups[name] = {'status': status, 'legs': legs, 'combined_odds': round(odds, 4),
                        'unit_profit': odds - 1 if status == 'won' else -1 if status == 'lost' else None}
    return {'policy': saved.get('policy'), 'groups': groups}


def settle_snapshots(day):
    """Retain every versioned pregame ticket after raw snapshot cleanup.

    Idempotent per job, independent of the snapshot chosen for calibration.
    Current injuries and newly computed selections are never consulted here.
    """
    import storage
    import settle_espn
    from psycopg.types.json import Jsonb
    with storage.connection() as conn:
        snapshots = conn.execute("""
            SELECT job_id,payload,created_at FROM nba_scan_snapshots
            WHERE scan_date=%s AND payload ? 'recommendations'
              AND NOT EXISTS (SELECT 1 FROM nba_recommendation_results r
                              WHERE r.snapshot_job_id=nba_scan_snapshots.job_id)
            ORDER BY created_at
        """, (day,)).fetchall()
    count = 0
    evidence = {}
    for job_id, payload, created_at in snapshots:
        saved = payload.get('recommendations')
        if not isinstance(saved, dict):
            continue
        snapshot = {**payload, 'job_id': job_id, 'saved_at': created_at.isoformat()}
        verified, _ = settle_espn.settle_archive(snapshot, day, evidence=evidence)
        report = evaluate(saved, verified)
        if payload.get('model_shadow'):
            import shadow_study
            report['model_shadow'] = shadow_study.evaluate(payload['model_shadow'], verified)
        with storage.connection() as conn:
            conn.execute("""
                INSERT INTO nba_recommendation_results(snapshot_job_id,scan_date,report)
                VALUES (%s,%s,%s) ON CONFLICT(snapshot_job_id) DO NOTHING
            """, (job_id, day, Jsonb(report)))
        count += 1
    return count
