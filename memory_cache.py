"""Bound retained payload bytes, rather than assuming every response is small.

Estimates include nested Python containers and pandas object columns. Cache
budgets are not an RSS limit: requests, serialization and native allocators
also need headroom. Callers retain responsibility for their existing locks.
"""
import sys
from cachetools import TTLCache


def payload_size(value):
    seen = set()

    def size(item):
        identity = id(item)
        if identity in seen:
            return 0
        seen.add(identity)
        # DataFrame.__sizeof__ already includes deep column/index memory.
        total = sys.getsizeof(item)
        if isinstance(item, dict):
            total += sum(size(key) + size(val) for key, val in item.items())
        elif isinstance(item, (list, tuple, set, frozenset)):
            total += sum(size(val) for val in item)
        return total

    return max(1, size(value))


def bounded_cache(mebibytes, ttl):
    return TTLCache(maxsize=int(mebibytes * 1024 * 1024), ttl=ttl,
                    getsizeof=payload_size)


def remember(cache, key, value):
    """An unusually large response remains usable, without breaking a request."""
    try:
        cache[key] = value
    except ValueError:
        # A replacement that exceeds the budget must not leave an older value
        # under this key: callers must fall back to current persisted evidence.
        cache.pop(key, None)
        return False
    return True
