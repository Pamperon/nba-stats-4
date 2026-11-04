"""Read-only explanation of the current single using its saved pregame evidence."""
from datetime import datetime, timedelta, timezone
import math
from psycopg.types.json import Jsonb
import storage


def saved_history(session, selection):
    official = session.get('official_top5') or {}
    jobs = list((official.get('snapshot_job_ids') or {}).values())
    cutoff = official.get('published_at') or session.get('saved_at')
    if not cutoff:
        return [], None
    identity = {key: selection[key] for key in
                ('Giocatore', 'Partita', 'Mercato', 'Scelta', 'Linea', 'Quota', 'Prob. stimata %')
                if key in selection}
    day = session['date']
    tomorrow = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
    with storage.connection() as conn:
        row = conn.execute("""
            SELECT payload->'player_logs'->%s, created_at
            FROM nba_scan_snapshots
            WHERE scan_date IN (%s,%s) AND state IN ('done','partial')
              AND created_at <= %s AND payload->'results' @> %s
              AND (%s OR job_id = ANY(%s))
            ORDER BY created_at DESC LIMIT 1
        """, (selection['Giocatore'], day, tomorrow, cutoff, Jsonb([identity]),
              not bool(jobs), jobs)).fetchone()
    return ((row[0] or []), row[1].isoformat()) if row else ([], None)


def build(session, load_history=saved_history):
    official = session.get('official_top5')
    selection = session.get('official_single') if official else session.get('preliminary_single')
    result = {'date': session.get('date'), 'state': 'official' if official else 'preview',
              'selection': selection, 'cutoff_at': session.get('publication_cutoff_at'),
              'saved_at': session.get('saved_at'), 'published_at': (official or {}).get('published_at'),
              'games': [], 'history_saved_at': None, 'odds_api_calls': 0}
    if not selection:
        return result
    games, at = load_history(session, selection)
    games = games if isinstance(games, list) else []
    cutoff = datetime.fromisoformat(at.replace('Z', '+00:00')) if at else None
    market = selection.get('Mercato')
    seen, valid = set(), []
    for game in sorted(games, key=lambda row: str(row.get('GAME_DATE') or ''), reverse=True):
        stamp = str(game.get('GAME_DATE') or '')
        try:
            instant = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
            if cutoff and instant >= cutoff:
                continue
            value = float(game[market])
        except (ValueError, TypeError, KeyError):
            continue
        if not math.isfinite(value):
            continue
        key = str(game.get('GAME_ID') or stamp[:10])
        if key in seen:
            continue
        seen.add(key)
        valid.append({key: game[key] for key in ('GAME_DATE', 'GAME_ID', 'MATCHUP', 'MIN', market) if key in game})
    result.update(games=valid[:20], history_saved_at=at)
    return result
