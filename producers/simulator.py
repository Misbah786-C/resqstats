"""ResQStats emergency simulator.

Plays out Karachi's ambulance operations as a discrete-event simulation:
incidents appear with realistic time-of-day / day-of-week / seasonal rhythms,
the nearest free ambulance is dispatched, drives at hour-dependent Karachi
traffic speeds, delivers the patient to the nearest hospital, and returns to
its station. Every step emits a schema-validated event.

Deterministic: the same --seed always produces identical output.

Usage:
    python -m producers.simulator --seed 42 --hours 24
    python -m producers.simulator --seed 42 --days 7 --sink file --out data/week1.jsonl
    python -m producers.simulator --seed 42 --hours 24 --sink kafka --bootstrap localhost:9092
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from producers.karachi_data import HOSPITALS, STATIONS, TOWNS
from producers.schemas.events import Event

# ----------------------------------------------------------------------------
# Tunables (why: encode Karachi's real-world rhythms, all in one place)
# ----------------------------------------------------------------------------

# Relative incident intensity by hour of day (24 values, avg ~1.0)
HOUR_CURVE = [
    0.55, 0.45, 0.40, 0.35, 0.35, 0.45, 0.60, 0.90,
    1.20, 1.15, 1.05, 1.00, 1.05, 1.00, 1.00, 1.05,
    1.20, 1.40, 1.45, 1.40, 1.30, 1.15, 0.95, 0.75,
]

# Ambulance speed (km/h) by hour - Karachi traffic is the real enemy
def _speed_kmh(hour: int, raining: bool) -> float:
    if 8 <= hour <= 11 or 17 <= hour <= 21:
        speed = 16.0  # rush hours
    elif 23 <= hour or hour <= 5:
        speed = 34.0  # empty roads at night
    else:
        speed = 24.0
    return speed * (0.65 if raining else 1.0)


ROAD_FACTOR = 1.4  # straight-line distance -> road distance approximation

BASE_TYPE_WEIGHTS = {
    "road_accident": 0.28,
    "cardiac": 0.15,
    "violence": 0.07,
    "fall": 0.10,
    "respiratory": 0.10,
    "maternity": 0.09,
    "heat_stroke": 0.0,  # seasonal, added below
    "other": 0.21,
}

SEVERITY_BY_TYPE = {
    "road_accident": [("critical", 0.25), ("serious", 0.35), ("moderate", 0.25), ("minor", 0.15)],
    "cardiac":       [("critical", 0.45), ("serious", 0.35), ("moderate", 0.15), ("minor", 0.05)],
    "heat_stroke":   [("critical", 0.20), ("serious", 0.40), ("moderate", 0.30), ("minor", 0.10)],
    "violence":      [("critical", 0.30), ("serious", 0.35), ("moderate", 0.25), ("minor", 0.10)],
    "fall":          [("critical", 0.05), ("serious", 0.25), ("moderate", 0.40), ("minor", 0.30)],
    "respiratory":   [("critical", 0.20), ("serious", 0.40), ("moderate", 0.30), ("minor", 0.10)],
    "maternity":     [("critical", 0.10), ("serious", 0.40), ("moderate", 0.40), ("minor", 0.10)],
    "other":         [("critical", 0.05), ("serious", 0.20), ("moderate", 0.40), ("minor", 0.35)],
}

# Bilingual call-text templates (raw material for the Phase-4 LLM classifier)
CALL_TEXTS = {
    "road_accident": [
        "Accident hua hai {town} mein, bike wala gir gaya hai, khoon beh raha hai",
        "Car accident near {town}, two people injured, one unconscious",
        "Bus ne takkar maari hai {town} ke paas, jaldi ambulance bhejo",
    ],
    "cardiac": [
        "Mere walid ko seenay mein dard ho raha hai, saans nahi aa rahi, {town}",
        "Heart patient collapsed at home in {town}, not responding",
        "Chest pain emergency {town} mein, buzurg aadmi hai",
    ],
    "heat_stroke": [
        "Garmi se banda behosh ho gaya hai {town} mein, bahar kaam kar raha tha",
        "Heat stroke case in {town}, labourer collapsed on road",
        "Dhoop mein behosh aurat mili hai {town} ke paas",
    ],
    "violence": [
        "Firing hui hai {town} mein, aik banda zakhmi hai",
        "Fight injury in {town}, person bleeding from head",
        "Larai mein chaqu lag gaya hai kisi ko, {town}",
    ],
    "fall": [
        "Buzurg seerhiyon se gir gaye hain {town} mein, utth nahi rahe",
        "Construction worker fell from scaffolding in {town}",
        "Bachcha chhat se gir gaya hai {town} mein",
    ],
    "respiratory": [
        "Asthma attack ho raha hai, inhaler kaam nahi kar raha, {town}",
        "Old woman cannot breathe properly in {town}, lips turning blue",
        "Saans ki takleef hai bachay ko {town} mein, bohat tez",
    ],
    "maternity": [
        "Meri biwi ko dard shuru ho gaye hain, hospital le jana hai, {town}",
        "Pregnant lady in labour in {town}, need ambulance fast",
        "Delivery case hai {town} mein, paani toot gaya hai",
    ],
    "other": [
        "Tabiyat bohat kharab hai, samajh nahi aa raha kya hua, {town}",
        "Unknown emergency in {town}, person lying on street",
        "Koi behosh para hai {town} ke paas, madad chahiye",
    ],
}

ON_SCENE_MINUTES = {  # (min, max) time spent treating/loading at the scene
    "critical": (6, 12),
    "serious": (8, 16),
    "moderate": (10, 20),
    "minor": (8, 15),
}

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _travel_minutes(lat1: float, lon1: float, lat2: float, lon2: float,
                    hour: int, raining: bool, rng: random.Random) -> float:
    km = haversine_km(lat1, lon1, lat2, lon2) * ROAD_FACTOR
    minutes = km / _speed_kmh(hour, raining) * 60.0
    return max(2.0, minutes * rng.uniform(0.85, 1.25))  # noise; never < 2 min


def _poisson(lam: float, rng: random.Random) -> int:
    """Knuth's algorithm - fine for small lambda."""
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def _weighted_choice(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in pairs)
    x = rng.uniform(0, total)
    acc = 0.0
    for value, w in pairs:
        acc += w
        if x <= acc:
            return value
    return pairs[-1][0]


def _type_weights(dt: datetime) -> list[tuple[str, float]]:
    """Incident-type mix, adjusted for season / hour / weekend nights."""
    w = dict(BASE_TYPE_WEIGHTS)
    # Heat stroke: April-September, strongest 11:00-17:00
    if 4 <= dt.month <= 9:
        w["heat_stroke"] = 0.16 if 11 <= dt.hour <= 17 else 0.04
    # Friday/Saturday nights: more accidents and violence
    if dt.weekday() in (4, 5) and (dt.hour >= 20 or dt.hour <= 2):
        w["road_accident"] *= 1.6
        w["violence"] *= 1.8
    return list(w.items())


# ----------------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------------


@dataclass
class Ambulance:
    amb_id: str
    station: str
    lat: float
    lon: float
    free_at: datetime


def simulate(seed: int, start: datetime, hours: int, base_rate: float = 10.0) -> list[Event]:
    """Run the simulation and return ALL events sorted by timestamp.

    base_rate: average incidents per hour city-wide (before hourly curve).
    """
    rng = random.Random(seed)

    fleet = [
        Ambulance(f"AMB-{code}-{i + 1}", name, lat, lon, start)
        for name, code, lat, lon, count in STATIONS
        for i in range(count)
    ]

    # Rain: ~10% of days, whole-day flag (simple but effective)
    rain: dict[str, bool] = {}
    day = start.date()
    for _ in range(hours // 24 + 2):
        rain[day.isoformat()] = rng.random() < 0.10
        day += timedelta(days=1)

    # 1) Generate all call times first (chronological)
    calls: list[datetime] = []
    for h in range(hours):
        hour_start = start + timedelta(hours=h)
        raining = rain[hour_start.date().isoformat()]
        lam = base_rate * HOUR_CURVE[hour_start.hour] * (1.5 if raining else 1.0)
        for _ in range(_poisson(lam, rng)):
            calls.append(hour_start + timedelta(seconds=rng.uniform(0, 3599)))
    calls.sort()

    # 2) Play out each incident
    events: list[Event] = []
    seq_per_day: dict[str, int] = {}

    for call_ts in calls:
        day_key = call_ts.strftime("%Y%m%d")
        seq_per_day[day_key] = seq_per_day.get(day_key, 0) + 1
        incident_id = f"INC-{day_key}-{seq_per_day[day_key]:04d}"
        raining = rain[call_ts.date().isoformat()]

        # Where + what
        town, t_lat, t_lon, _ = rng.choices(
            TOWNS, weights=[w for _, _, _, w in TOWNS]
        )[0]
        lat = t_lat + rng.uniform(-0.018, 0.018)
        lon = t_lon + rng.uniform(-0.018, 0.018)
        itype = _weighted_choice(rng, _type_weights(call_ts))
        severity = _weighted_choice(rng, SEVERITY_BY_TYPE[itype])
        call_text = rng.choice(CALL_TEXTS[itype]).format(town=town)

        ctx = dict(incident_id=incident_id, town=town, lat=round(lat, 5),
                   lon=round(lon, 5), incident_type=itype, severity=severity,
                   is_raining=raining)

        events.append(Event(event_type="call_received", event_ts=call_ts,
                            call_text=call_text, **ctx))

        # Pick the ambulance that can ARRIVE first (free time + travel)
        processing = timedelta(minutes=rng.uniform(1.0, 4.0))  # operator handling

        # Estimate WITHOUT random noise (noise inside a min() scan would
        # consume rng draws per candidate and hurt determinism/clarity);
        # real travel noise is applied once after selection.
        def deterministic_eta(amb: Ambulance) -> datetime:
            dispatch = max(call_ts + processing, amb.free_at)
            km = haversine_km(amb.lat, amb.lon, lat, lon) * ROAD_FACTOR
            mins = max(2.0, km / _speed_kmh(dispatch.hour, raining) * 60.0)
            return dispatch + timedelta(minutes=mins)

        amb = min(fleet, key=deterministic_eta)
        dispatch_ts = max(call_ts + processing, amb.free_at)

        to_scene = _travel_minutes(amb.lat, amb.lon, lat, lon,
                                   dispatch_ts.hour, raining, rng)
        scene_ts = dispatch_ts + timedelta(minutes=to_scene)

        lo, hi = ON_SCENE_MINUTES[severity]
        depart_ts = scene_ts + timedelta(minutes=rng.uniform(lo, hi))

        hosp_name, h_lat, h_lon = min(
            HOSPITALS, key=lambda h: haversine_km(lat, lon, h[1], h[2])
        )
        to_hosp = _travel_minutes(lat, lon, h_lat, h_lon,
                                  depart_ts.hour, raining, rng)
        hospital_ts = depart_ts + timedelta(minutes=to_hosp)

        handoff = timedelta(minutes=rng.uniform(5, 12))
        back = _travel_minutes(h_lat, h_lon, amb.lat, amb.lon,
                               hospital_ts.hour, raining, rng)
        amb.free_at = hospital_ts + handoff + timedelta(minutes=back)

        fleet_ctx = dict(ambulance_id=amb.amb_id, station=amb.station)
        events.append(Event(event_type="ambulance_dispatched", event_ts=dispatch_ts,
                            **ctx, **fleet_ctx))
        events.append(Event(event_type="arrived_on_scene", event_ts=scene_ts,
                            **ctx, **fleet_ctx))
        events.append(Event(event_type="departed_scene", event_ts=depart_ts,
                            **ctx, **fleet_ctx, hospital=hosp_name))
        events.append(Event(event_type="arrived_hospital", event_ts=hospital_ts,
                            **ctx, **fleet_ctx, hospital=hosp_name))
        events.append(Event(event_type="ambulance_available", event_ts=amb.free_at,
                            **fleet_ctx))

    events.sort(key=lambda e: (e.event_ts, e.incident_id or "", e.event_type))
    return events


# ----------------------------------------------------------------------------
# CLI / sinks
# ----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="ResQStats emergency simulator")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=str, default="2026-06-01",
                        help="Simulation start date (YYYY-MM-DD)")
    parser.add_argument("--hours", type=int, default=None)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--rate", type=float, default=10.0,
                        help="Average incidents/hour city-wide")
    parser.add_argument("--sink", choices=["stdout", "file", "kafka"], default="stdout")
    parser.add_argument("--out", type=str, default="data/events.jsonl")
    parser.add_argument("--bootstrap", type=str, default="localhost:9092")
    parser.add_argument("--topic", type=str, default="emergency_events")
    args = parser.parse_args()

    hours = args.hours if args.hours else (args.days or 1) * 24
    start = datetime.fromisoformat(args.start_date)

    events = simulate(seed=args.seed, start=start, hours=hours, base_rate=args.rate)
    incidents = sum(1 for e in events if e.event_type == "call_received")

    if args.sink == "stdout":
        for e in events:
            print(e.to_json())
    elif args.sink == "file":
        import pathlib
        path = pathlib.Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(e.to_json() + "\n")
        print(f"wrote {len(events)} events ({incidents} incidents) -> {path}",
              file=sys.stderr)
    elif args.sink == "kafka":
        from kafka import KafkaProducer  # lazy import: only needed for this sink
        producer = KafkaProducer(
            bootstrap_servers=args.bootstrap,
            value_serializer=lambda e: e.encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        for e in events:
            producer.send(args.topic, key=e.incident_id or e.ambulance_id, value=e.to_json())
        producer.flush()
        print(f"produced {len(events)} events ({incidents} incidents) "
              f"-> kafka topic '{args.topic}'", file=sys.stderr)

    print(f"[summary] {incidents} incidents, {len(events)} events, "
          f"{hours}h simulated from {start.isoformat()}", file=sys.stderr)


if __name__ == "__main__":
    main()
