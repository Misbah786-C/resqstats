# ADR 0001: Simulated dispatch data instead of scraped/real data

## Status
Accepted

## Context
Real ambulance dispatch records (Edhi, Chhipa, Rescue 1122) are confidential and
not published. Scraping proxies (news reports, tweets) would be sparse, fragile,
and unlabeled.

## Decision
Build a deterministic discrete-event simulator encoding Karachi's real-world
patterns: hourly incident curves, Friday-night accident/violence spikes,
April–September heat-stroke seasonality, rain effects on both incident rate and
traffic speed, and a fleet state machine (dispatch → scene → hospital → return).

## Consequences
- Unlimited, reproducible, schema-clean event volume at any scale
- Ground-truth labels (incident_type, severity) let us MEASURE the Phase-4 LLM
  classifier's accuracy instead of guessing
- The platform (Kafka → Spark → lake → warehouse) is identical to what would
  run against real CAD/dispatch feeds — swapping the source touches only the
  producer
- Tradeoff: simulated patterns are assumptions, not measurements; documented in
  `producers/simulator.py` tunables so they can be revised against any future
  real data
