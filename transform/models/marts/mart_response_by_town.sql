-- HEADLINE TABLE: how fast does help arrive, per town per month?

select
    town,
    call_month,
    count(*) as incidents,
    round(median(minutes_to_scene), 1) as median_response_min,
    round(quantile_cont(minutes_to_scene, 0.90), 1) as p90_response_min,
    round(avg(minutes_to_scene), 1) as avg_response_min
from {{ ref('fct_incidents') }}
group by town, call_month
order by call_month, median_response_min desc
