-- Fact table: one row per emergency incident. The base for every mart.

select
    incident_id,
    town,
    incident_type,
    severity,
    is_raining,
    ambulance_id,
    station,
    hospital,
    ts_call,
    extract(hour from ts_call) as call_hour,
    dayname(ts_call) as call_day,
    date_trunc('month', ts_call) as call_month,
    minutes_to_dispatch,
    minutes_to_scene,          -- RESPONSE TIME: call -> ambulance on scene
    minutes_on_scene,
    minutes_to_hospital,
    total_minutes,             -- call -> patient at hospital
    event_date
from {{ ref('stg_incidents') }}
