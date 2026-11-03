"""Compact transport projections. Never edit archived rows or probabilities."""


def explanation_logs(snapshot):
    recommendations = snapshot.get('recommendations')
    if not isinstance(recommendations, dict):
        recommendations = {}
    supported = (isinstance(recommendations.get('lines'), list)
                 or isinstance(recommendations.get('groups'), dict))
    selected = list(recommendations.get('lines') or [])
    groups = recommendations.get('groups')
    for group in (groups if isinstance(groups, dict) else {}).values():
        if isinstance(group, dict):
            selected.extend(group.get('legs') or [])
    selected.extend(snapshot.get('preliminary_top5') or [])
    for field in ('official_single', 'preliminary_single'):
        if isinstance(snapshot.get(field), dict):
            selected.append(snapshot[field])
    names = {row.get('Giocatore') for row in selected if isinstance(row, dict)}
    # Unsupported legacy snapshots retain their existing compact behavior.
    return {name: [{key: game[key] for key in ('GAME_DATE','PTS','AST','REB') if key in game}
                   for game in games]
            for name,games in snapshot.get('player_logs', {}).items()
            if not supported or name in names}
