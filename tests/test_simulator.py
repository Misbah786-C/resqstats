"""Phase-1 tests: determinism, incident completeness, schema sanity."""
from datetime import datetime

from producers.schemas.events import INCIDENT_TYPES, SEVERITIES
from producers.simulator import simulate

START = datetime(2026, 6, 1)

LIFECYCLE = [
    "call_received",
    "ambulance_dispatched",
    "arrived_on_scene",
    "departed_scene",
    "arrived_hospital",
]


def _run(seed: int = 7, hours: int = 12):
    return simulate(seed=seed, start=START, hours=hours)


def test_same_seed_same_output():
    a = [e.to_json() for e in _run(seed=7)]
    b = [e.to_json() for e in _run(seed=7)]
    assert a == b


def test_different_seed_different_output():
    a = [e.to_json() for e in _run(seed=7)]
    b = [e.to_json() for e in _run(seed=8)]
    assert a != b


def test_every_incident_has_full_lifecycle_in_order():
    events = _run()
    by_incident: dict[str, list] = {}
    for e in events:
        if e.incident_id:
            by_incident.setdefault(e.incident_id, []).append(e)

    assert by_incident, "simulation produced no incidents"
    for incident_id, evs in by_incident.items():
        types = [e.event_type for e in evs]
        assert types == LIFECYCLE, f"{incident_id}: got {types}"
        timestamps = [e.event_ts for e in evs]
        assert timestamps == sorted(timestamps), f"{incident_id}: out of order"


def test_values_are_valid():
    events = _run()
    for e in events:
        if e.event_type == "call_received":
            assert e.incident_type in INCIDENT_TYPES
            assert e.severity in SEVERITIES
            assert e.call_text and e.town
            # rough Karachi bounding box
            assert 24.7 < e.lat < 25.2 and 66.8 < e.lon < 67.4


def test_ambulance_never_double_booked():
    events = _run()
    busy: dict[str, datetime] = {}  # amb_id -> busy-until
    for e in sorted(events, key=lambda x: x.event_ts):
        if e.event_type == "ambulance_dispatched":
            assert busy.get(e.ambulance_id, e.event_ts) <= e.event_ts, (
                f"{e.ambulance_id} dispatched while busy"
            )
        elif e.event_type == "ambulance_available":
            busy[e.ambulance_id] = e.event_ts
