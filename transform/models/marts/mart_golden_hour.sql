-- Golden hour: % of CRITICAL patients reaching hospital within 60 minutes.
-- The single most important number for an emergency service.

select
    call_month,
    count(*) filter (where severity = 'critical') as critical_incidents,
    round(
        100.0
        * count(*) filter (where severity = 'critical' and total_minutes <= 60)
        / nullif(count(*) filter (where severity = 'critical'), 0),
        1
    ) as golden_hour_pct,
    round(
        median(total_minutes) filter (where severity = 'critical'), 1
    ) as median_critical_total_min
from {{ ref('fct_incidents') }}
group by call_month
order by call_month
