"""Phase 4a - Silver builder: bronze events -> one clean row per incident.

Spark BATCH job (not streaming) that:
  1. reads all bronze Parquet from the lake
  2. stitches each incident's lifecycle events into a single row
     (call -> dispatch -> scene -> depart -> hospital, all timestamps)
  3. computes the durations the whole project exists for:
       minutes_to_dispatch, minutes_to_scene (RESPONSE TIME),
       minutes_on_scene, minutes_to_hospital, total_minutes
  4. drops incomplete/inconsistent incidents (counts are printed - data quality)
  5. writes Parquet to s3a://silver/incidents, partitioned by event_date

Idempotent: mode=overwrite, so re-running always rebuilds silver from bronze.

Run: docker compose --profile batch up spark-silver
"""
from __future__ import annotations

import os

from pyspark.sql import functions as F

from streaming.bronze_sink import build_spark


def main() -> None:
    bronze_path = os.getenv("BRONZE_PATH", "s3a://bronze/emergency_events")
    silver_path = os.getenv("SILVER_PATH", "s3a://silver/incidents")
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "resqadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "resqstats123")

    spark = build_spark(minio_endpoint, access_key, secret_key)
    spark.sparkContext.setLogLevel("WARN")

    bronze = spark.read.parquet(bronze_path)
    incident_events = bronze.filter(F.col("incident_id").isNotNull())
    n_incidents_in = incident_events.select("incident_id").distinct().count()

    def ts_of(event_type: str):
        return F.min(F.when(F.col("event_type") == event_type, F.col("event_ts")))

    stitched = incident_events.groupBy("incident_id").agg(
        F.first("town", ignorenulls=True).alias("town"),
        F.first("lat", ignorenulls=True).alias("lat"),
        F.first("lon", ignorenulls=True).alias("lon"),
        F.first("incident_type", ignorenulls=True).alias("incident_type"),
        F.first("severity", ignorenulls=True).alias("severity"),
        F.first("call_text", ignorenulls=True).alias("call_text"),
        F.first("is_raining", ignorenulls=True).alias("is_raining"),
        F.first("ambulance_id", ignorenulls=True).alias("ambulance_id"),
        F.first("station", ignorenulls=True).alias("station"),
        F.first("hospital", ignorenulls=True).alias("hospital"),
        ts_of("call_received").alias("ts_call"),
        ts_of("ambulance_dispatched").alias("ts_dispatch"),
        ts_of("arrived_on_scene").alias("ts_scene"),
        ts_of("departed_scene").alias("ts_depart"),
        ts_of("arrived_hospital").alias("ts_hospital"),
    )

    def mins(later: str, earlier: str):
        return F.round(
            (F.unix_timestamp(F.col(later)) - F.unix_timestamp(F.col(earlier))) / 60.0, 2
        )

    enriched = (
        stitched
        .withColumn("minutes_to_dispatch", mins("ts_dispatch", "ts_call"))
        .withColumn("minutes_to_scene", mins("ts_scene", "ts_call"))  # RESPONSE TIME
        .withColumn("minutes_on_scene", mins("ts_depart", "ts_scene"))
        .withColumn("minutes_to_hospital", mins("ts_hospital", "ts_depart"))
        .withColumn("total_minutes", mins("ts_hospital", "ts_call"))
        .withColumn("event_date", F.to_date(F.col("ts_call")))
    )

    # Data quality gate: complete lifecycle + sane ordering only
    clean = enriched.filter(
        F.col("ts_call").isNotNull()
        & F.col("ts_dispatch").isNotNull()
        & F.col("ts_scene").isNotNull()
        & F.col("ts_depart").isNotNull()
        & F.col("ts_hospital").isNotNull()
        & (F.col("minutes_to_dispatch") >= 0)
        & (F.col("minutes_to_scene") > 0)
        & (F.col("minutes_on_scene") >= 0)
        & (F.col("minutes_to_hospital") >= 0)
    )
    n_clean = clean.count()

    clean.write.mode("overwrite").partitionBy("event_date").parquet(silver_path)

    print(f"[silver-builder] incidents in bronze: {n_incidents_in}, "
          f"clean rows written: {n_clean}, "
          f"dropped: {n_incidents_in - n_clean} -> {silver_path}")

    spark.stop()


if __name__ == "__main__":
    main()
