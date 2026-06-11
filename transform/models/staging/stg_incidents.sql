-- Staging: silver incidents straight from the lake, typed and renamed.
-- DuckDB reads the Parquet directly from MinIO (S3 API).

select
    incident_id,
    town,
    lat,
    lon,
    incident_type,
    severity,
    call_text,
    is_raining,
    ambulance_id,
    station,
    hospital,
    ts_call,
    ts_dispatch,
    ts_scene,
    ts_depart,
    ts_hospital,
    minutes_to_dispatch,
    minutes_to_scene,
    minutes_on_scene,
    minutes_to_hospital,
    total_minutes,
    event_date
from read_parquet('s3://silver/incidents/*/*.parquet', hive_partitioning = true)
