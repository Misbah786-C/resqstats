"""Enforce sync between the pydantic event schema and the Spark bronze schema.

If someone adds a field to Event and forgets schema_map.py (or vice versa),
this test fails - that's the point. No pyspark needed to run it.
"""
from producers.schemas.events import Event
from streaming.schema_map import FIELDS


def test_bronze_fields_match_event_schema():
    event_fields = list(Event.model_fields.keys())
    bronze_fields = [name for name, _ in FIELDS]
    assert bronze_fields == event_fields, (
        f"schema drift!\n  events.py:     {event_fields}\n  schema_map.py: {bronze_fields}"
    )


def test_bronze_types_are_known():
    allowed = {"string", "double", "timestamp", "boolean"}
    for name, spark_type in FIELDS:
        assert spark_type in allowed, f"{name}: unknown spark type '{spark_type}'"
