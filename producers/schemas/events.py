"""Event schemas - the single source of truth for what flows through Kafka.

Every producer and consumer imports from here. Never duplicate these
definitions elsewhere (AGENTS.md rule).
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

EventType = Literal[
    "call_received",
    "ambulance_dispatched",
    "arrived_on_scene",
    "departed_scene",
    "arrived_hospital",
    "ambulance_available",
]

IncidentType = Literal[
    "road_accident",
    "cardiac",
    "heat_stroke",
    "violence",
    "fall",
    "respiratory",
    "maternity",
    "other",
]

Severity = Literal["critical", "serious", "moderate", "minor"]

INCIDENT_TYPES: tuple[str, ...] = IncidentType.__args__  # type: ignore[attr-defined]
SEVERITIES: tuple[str, ...] = Severity.__args__  # type: ignore[attr-defined]


class Event(BaseModel):
    """One event in an incident's lifecycle (or a fleet-status event)."""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    event_ts: datetime
    incident_id: Optional[str] = None

    # incident context (set on call_received, repeated on later events for convenience)
    town: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    incident_type: Optional[IncidentType] = None
    severity: Optional[Severity] = None
    call_text: Optional[str] = None
    is_raining: Optional[bool] = None

    # fleet context
    ambulance_id: Optional[str] = None
    station: Optional[str] = None
    hospital: Optional[str] = None

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)
