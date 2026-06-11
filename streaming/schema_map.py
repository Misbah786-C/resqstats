"""Bronze table field map - MUST stay in sync with producers/schemas/events.py.

Kept as plain Python (no pyspark import) so the sync test can run anywhere.
tests/test_bronze_schema.py enforces the sync automatically.
"""

# (field_name, spark_type)
FIELDS: list[tuple[str, str]] = [
    ("event_type", "string"),
    ("event_ts", "timestamp"),
    ("incident_id", "string"),
    ("town", "string"),
    ("lat", "double"),
    ("lon", "double"),
    ("incident_type", "string"),
    ("severity", "string"),
    ("call_text", "string"),
    ("is_raining", "boolean"),
    ("ambulance_id", "string"),
    ("station", "string"),
    ("hospital", "string"),
]
