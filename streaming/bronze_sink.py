"""Phase 3 - Bronze sink: Kafka -> Parquet on the MinIO data lake.

Spark Structured Streaming job that:
  1. reads events from the `emergency_events` Kafka topic
  2. parses the JSON against the shared schema (streaming/schema_map.py)
  3. keeps the ORIGINAL raw JSON alongside (bronze = immutable raw, AGENTS.md rule)
  4. writes Parquet to s3a://bronze/, partitioned by event_date
  5. checkpoints progress -> kill it, restart it, no loss and no duplicates

Run inside Docker (recommended, see docker-compose.yml):
    docker compose --profile streaming up spark-bronze

Or directly (needs Java + pyspark):
    spark-submit \
      --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.apache.hadoop:hadoop-aws:3.3.4 \
      streaming/bronze_sink.py --once
"""
from __future__ import annotations

import argparse
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from streaming.schema_map import FIELDS

_TYPE_MAP = {
    "string": StringType(),
    "double": DoubleType(),
    "timestamp": TimestampType(),
    "boolean": BooleanType(),
}


def build_event_schema() -> StructType:
    return StructType([StructField(name, _TYPE_MAP[t], True) for name, t in FIELDS])


def build_spark(minio_endpoint: str, access_key: str, secret_key: str) -> SparkSession:
    return (
        SparkSession.builder.appName("resqstats-bronze-sink")
        # talk to MinIO over the S3 API
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        # keep local resource use sane
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Kafka -> bronze Parquet sink")
    parser.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "redpanda:29092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC", "emergency_events"))
    parser.add_argument("--minio-endpoint",
                        default=os.getenv("MINIO_ENDPOINT", "http://minio:9000"))
    parser.add_argument("--lake-path", default="s3a://bronze/emergency_events")
    parser.add_argument("--checkpoint", default="s3a://bronze/_checkpoints/emergency_events")
    parser.add_argument("--once", action="store_true",
                        help="Process everything currently in the topic, then exit "
                             "(good for demos and scheduled batch runs)")
    parser.add_argument("--interval", default="30 seconds",
                        help="Micro-batch trigger interval for continuous mode")
    args = parser.parse_args()

    access_key = os.getenv("MINIO_ROOT_USER", "resqadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "resqstats123")

    spark = build_spark(args.minio_endpoint, access_key, secret_key)
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", args.bootstrap)
        .option("subscribe", args.topic)
        .option("startingOffsets", "earliest")
        .load()
    )

    parsed = (
        raw.select(
            F.col("value").cast("string").alias("raw_json"),
            F.col("timestamp").alias("kafka_ts"),
        )
        .withColumn("e", F.from_json(F.col("raw_json"), build_event_schema()))
        .select("e.*", "raw_json", "kafka_ts")
        .withColumn("event_date", F.to_date(F.col("event_ts")))
    )

    writer = (
        parsed.writeStream.format("parquet")
        .option("path", args.lake_path)
        .option("checkpointLocation", args.checkpoint)
        .partitionBy("event_date")
        .outputMode("append")
    )

    if args.once:
        query = writer.trigger(availableNow=True).start()
    else:
        query = writer.trigger(processingTime=args.interval).start()

    print(f"[bronze-sink] {args.topic} @ {args.bootstrap} -> {args.lake_path} "
          f"({'once' if args.once else 'continuous, ' + args.interval})")
    query.awaitTermination()


if __name__ == "__main__":
    main()
