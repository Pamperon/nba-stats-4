"""Small read-only player explorer projection, with no provider requests."""
import math

FIELDS = ('ESPN ID', 'Giocatore', 'Squadra', 'Partita', 'Mercato', 'Linea',
          'Scelta', 'Quota', 'Prob. stimata %')

def project(snapshot):
    rows = []
    for row in snapshot.get('results', []):
        try:
            valid = math.isfinite(float(row.get('Quota', 0))) and float(row['Quota']) > 1
        except (TypeError, ValueError):
            valid = False
        if valid and row.get('Mercato') in ('PTS', 'REB', 'AST'):
            rows.append({key: row.get(key) for key in FIELDS})
    names = {r['Giocatore'] for r in rows}
    logs = {}
    for name, games in snapshot.get('player_logs', {}).items():
        if name not in names or not isinstance(games, list):
            continue
        dated = [g for g in games if isinstance(g, dict) and g.get('GAME_DATE')]
        logs[name] = [{k: g.get(k) for k in ('GAME_DATE', 'PTS', 'REB', 'AST')}
                      for g in sorted(dated, key=lambda g: str(g['GAME_DATE']), reverse=True)[:10]]
    return {'date': snapshot.get('date'), 'saved_at': snapshot.get('saved_at'),
            'rows': rows, 'logs': logs, 'odds_api_calls': 0}
