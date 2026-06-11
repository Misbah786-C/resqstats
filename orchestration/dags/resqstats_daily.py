"""ResQStats daily pipeline - the manager that runs the platform unattended.

Every day at 06:00:
  1. check_lake        - is the silver lake reachable and non-empty?
  2. dbt_build         - rebuild all warehouse models + run all quality tests
  3. response_spike_alert - any town with dangerously degraded response times?

Failures retry twice, then page via Telegram (or the task log if Telegram
isn't configured). See alert_utils.py.

NOTE (documented tradeoff): the Spark silver rebuild stays a manually-triggered
batch job (`docker compose --profile batch up spark-silver`) because running
Docker-in-Docker from Airflow adds complexity this project doesn't need. In a
production deployment the same task would be a DockerOperator/KubernetesPodOperator.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from alert_utils import notify, notify_failure

log = logging.getLogger("resqstats.dag")

S3_SETTINGS = """
INSTALL httpfs; LOAD httpfs;
SET s3_endpoint='{endpoint}';
SET s3_access_key_id='{key}';
SET s3_secret_access_key='{secret}';
SET s3_use_ssl=false;
SET s3_url_style='path';
"""


def check_lake() -> None:
    """Fail loudly if the silver lake is missing or empty."""
    import duckdb

    con = duckdb.connect()
    con.execute(
        S3_SETTINGS.format(
            endpoint=os.getenv("MINIO_S3_HOST", "minio:9000"),
            key=os.getenv("MINIO_ROOT_USER", "resqadmin"),
            secret=os.getenv("MINIO_ROOT_PASSWORD", "resqstats123"),
        )
    )
    # Plain count first (no hive partitioning) - keeps the health check simple
    # and avoids a DuckDB internal-error edge case seen when aggregating the
    # partition column and count(*) in one query over httpfs.
    rows = con.sql(
        "select count(*) from read_parquet('s3://silver/incidents/*/*.parquet')"
    ).fetchone()[0]
    if not rows:
        raise ValueError("silver lake is EMPTY - upstream pipeline broken?")

    try:
        max_date = con.sql(
            "select max(event_date) from read_parquet("
            "'s3://silver/incidents/*/*.parquet', hive_partitioning=true)"
        ).fetchone()[0]
    except Exception as exc:  # freshness date is nice-to-have, not critical
        log.warning("could not read max event_date (%s)", exc)
        max_date = "unknown"
    log.info("silver lake OK: %s incidents, latest event_date %s", rows, max_date)


def response_spike_alert() -> None:
    """Alert on towns whose response times look dangerously bad."""
    import duckdb

    con = duckdb.connect("/opt/airflow/data/resqstats.duckdb", read_only=True)
    bad = con.sql(
        """
        select town, median_response_min, pct_over_15min
        from mart_coverage_gaps
        where incidents >= 5
          and (median_response_min > 20 or pct_over_15min > 80)
        order by median_response_min desc
        """
    ).fetchall()
    if bad:
        lines = "\n".join(
            f"- {town}: median {med} min, {pct}% over 15 min" for town, med, pct in bad
        )
        notify(f"⚠️ ResQStats: degraded response times detected\n{lines}")
    else:
        log.info("no response-time spikes - all towns within thresholds")


default_args = {
    "owner": "resqstats",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="resqstats_daily",
    description="Warehouse rebuild + data quality + response-time alerting",
    schedule="0 6 * * *",
    start_date=datetime(2026, 6, 1),
    catchup=False,
    default_args=default_args,
    tags=["resqstats"],
) as dag:
    t_check_lake = PythonOperator(task_id="check_lake", python_callable=check_lake)

    t_dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /opt/airflow/transform && dbt build --profiles-dir .",
    )

    t_spike_alert = PythonOperator(
        task_id="response_spike_alert", python_callable=response_spike_alert
    )

    t_check_lake >> t_dbt_build >> t_spike_alert
