"""Per-property receive/source clocks for the volatile MQTT inventory.

Independent OSD and state clocks never renew unrelated fields. Equal source
times may introduce disjoint partial properties; conflicting equal-time writes
are ignored. Arrays are one versioned property, dictionaries merge by leaf.
"""
from copy import deepcopy
from datetime import timezone


def leaves(values, prefix=''):
    for key, value in values.items():
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(value, dict) and value:
            yield from leaves(value, path)
        else:
            yield path, value


def assign(values, path, value):
    parts = path.split('.')
    for key in parts[:-1]:
        if not isinstance(values.get(key), dict):
            values[key] = {}
        values = values[key]
    values[parts[-1]] = deepcopy(value)


def merge_fields(previous, incoming, clocks, received, timestamp, channel):
    """Stage accepted fields and clocks; callers commit only after validation."""
    values, staged, changed = deepcopy(previous), deepcopy(clocks), []
    for path, value in leaves(incoming):
        old = clocks.get(path)
        if old:
            earlier = old['source_timestamp_ms']
            # Missing source times cannot supersede dated data. Identical
            # timestamps cannot renew old values through retained/replayed MQTT.
            if earlier is not None and (timestamp is None or timestamp <= earlier):
                continue
        assign(values, path, value)
        staged[path] = {'received_at': received, 'source_timestamp_ms': timestamp,
                        'channel': channel}
        changed.append(path)
    return values, staged, changed


def clock_view(clock, now, stale_after):
    received = clock['received_at']
    delta = (now - received).total_seconds()
    timestamp = clock['source_timestamp_ms']
    source_age = None if timestamp is None else now.timestamp() - timestamp / 1000
    if delta < -1 or (source_age is not None and source_age < -1):
        state = 'clock_skew'
    else:
        age = max(delta, source_age if source_age is not None else delta, 0)
        state = 'fresh' if age <= stale_after else 'stale'
    return {'freshness': state, 'received_at': received.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'age_seconds': round(max(0, delta), 3), 'source_timestamp_ms': timestamp,
            'source_age_seconds': None if source_age is None else round(max(0, source_age), 3),
            'channel': clock['channel']}


def project_fields(sample, clocks, now, stale_after):
    current, metadata = deepcopy(sample), {}
    for path, clock in clocks.items():
        info = metadata[path] = clock_view(clock, now, stale_after)
        if info['freshness'] != 'fresh':
            assign(current, path, None)
    return current, metadata
