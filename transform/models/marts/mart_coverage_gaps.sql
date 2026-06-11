-- Coverage gaps: towns where response is consistently worst.
-- The "where should the next ambulance station go?" shortlist.

with town_stats as (
    select
        town,
        count(*) as incidents,
        round(median(minutes_to_scene), 1) as median_response_min,
        round(quantile_cont(minutes_to_scene, 0.90), 1) as p90_response_min,
        round(
            100.0 * count(*) filter (where minutes_to_scene > 15) / count(*), 1
        ) as pct_over_15min
    from {{ ref('fct_incidents') }}
    group by town
)

select
    *,
    rank() over (order by median_response_min desc) as worst_rank
from town_stats
where incidents >= 5  -- ignore towns with too little data to judge
order by worst_rank
