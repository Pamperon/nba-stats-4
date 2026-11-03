"""Bounded discovery over free NBA calendars. Never requests odds or writes data."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROME = ZoneInfo('Europe/Rome')
LOOKAHEAD_DAYS = 7


def upcoming(game, now):
    if not game.get('upcoming'):
        return False
    try:
        tipoff = datetime.fromisoformat(game['start_at'])
        return tipoff.tzinfo is not None and tipoff > now
    except (KeyError, ValueError, TypeError):
        return False


def next_publication_session(start_day, now, load_manifest):
    """Keep exact session dates: never move tomorrow's 18:00 cutoff to today."""
    first = None
    for offset in range(LOOKAHEAD_DAYS):
        day = (start_day + timedelta(days=offset)).isoformat()
        manifest = load_manifest(day)
        if first is None:
            first = (day, manifest)
        if any(upcoming(game, now) for game in manifest['games']):
            return day, manifest
    return first


def scan_schedules(scan_day, load_calendar):
    """Preserve today/tomorrow; cross an empty gap using free calendars only.

    At most two calendar dates are ever returned for odds scans. A future
    overnight-only date needs no following date; evening fixtures can span two.
    An unavailable or malformed calendar fails closed, before slot reservation.
    """
    def read(day):
        date = day.isoformat()
        try:
            payload = load_calendar(date)
            if not isinstance(payload, dict) or not isinstance(payload.get('games'), list):
                raise ValueError('Invalid calendar')
            if any(not isinstance(game, dict) or type(game.get('upcoming')) is not bool
                   for game in payload['games']):
                raise ValueError('Invalid game entry')
        except Exception as exc:
            raise RuntimeError('ESPN calendar unavailable for ' + date +
                               '; no slot claimed and no paid scan started') from exc
        return date, payload

    initial = [read(scan_day + timedelta(days=offset)) for offset in (0, 1)]
    if any(game['upcoming'] for _, payload in initial for game in payload['games']):
        return initial
    for offset in range(2, LOOKAHEAD_DAYS):
        day = scan_day + timedelta(days=offset)
        item = read(day)
        games = [game for game in item[1]['games'] if game['upcoming']]
        if not games:
            continue
        result = [item]
        # A missing/ambiguous timestamp must not expand paid work speculatively.
        evening = False
        for game in games:
            try:
                start = datetime.fromisoformat(game['start_at'])
                evening |= start.tzinfo is not None and start.astimezone(ROME).hour >= 18
            except (KeyError, ValueError, TypeError):
                pass
        if evening and offset + 1 < LOOKAHEAD_DAYS:
            result.append(read(day + timedelta(days=1)))
        return result
    return initial
