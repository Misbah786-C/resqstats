-- Fleet load heatmap: dispatches and response speed by station and hour.
-- Answers: is the fleet positioned where/when the demand is?

select
    station,
    call_hour,
    count(*) as dispatches,
    round(avg(minutes_to_scene), 1) as avg_response_min,
    round(avg(total_minutes), 1) as avg_total_min
from {{ ref('fct_incidents') }}
group by station, call_hour
order by station, call_hour
