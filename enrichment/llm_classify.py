"""Phase 4b - LLM classifier + accuracy evaluation.

Reads incidents from the silver lake, asks a free LLM (Groq) to classify each
call_text into {incident_type, severity}, then measures accuracy against the
simulator's ground-truth labels. Writes:
  - enrichment/eval/predictions.csv   (every prediction vs truth)
  - enrichment/eval/results.md        (accuracy report for the README)

The LLM only structures text. All metrics are computed in Python/SQL.

Usage (host machine, with MinIO running and silver built):
    python -m enrichment.llm_classify --limit 100

Needs GROQ_API_KEY in .env (free key: https://console.groq.com).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import requests

from enrichment.prompts import (
    SYSTEM_PROMPT,
    normalize_severity,
    normalize_type,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# ----------------------------------------------------------------------------
# LLM call with rate-limit handling (free tier = strict limits; handle them)
# ----------------------------------------------------------------------------


def parse_response(content: str) -> tuple[str | None, str | None]:
    """LLM JSON -> (incident_type, severity), normalized; (None, None) if junk."""
    try:
        # tolerate accidental markdown fences
        cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        data = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return None, None
    return normalize_type(data.get("incident_type")), normalize_severity(data.get("severity"))


def classify_text(text: str, api_key: str, model: str,
                  session: requests.Session, max_retries: int = 5) -> tuple[str | None, str | None]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Call: \"{text}\""},
        ],
        "temperature": 0.0,
        "max_tokens": 60,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(max_retries):
        resp = session.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            return parse_response(resp.json()["choices"][0]["message"]["content"])
        if resp.status_code == 429:  # rate limited - respect Retry-After
            wait = float(resp.headers.get("retry-after", 2 ** attempt))
            time.sleep(min(wait, 30))
            continue
        if resp.status_code >= 500:  # transient server error - backoff
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:200]}")
    return None, None


# ----------------------------------------------------------------------------
# Lake IO
# ----------------------------------------------------------------------------


def read_silver(endpoint: str, access_key: str, secret_key: str, limit: int, seed: int):
    import pyarrow.dataset as ds
    from pyarrow import fs

    s3 = fs.S3FileSystem(
        endpoint_override=endpoint,
        access_key=access_key,
        secret_key=secret_key,
    )
    table = ds.dataset("silver/incidents", filesystem=s3, format="parquet").to_table(
        columns=["incident_id", "call_text", "incident_type", "severity", "town"]
    )
    df = table.to_pandas()
    if len(df) > limit:
        df = df.sample(n=limit, random_state=seed).reset_index(drop=True)
    return df


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Classify silver call texts with Groq + evaluate")
    parser.add_argument("--limit", type=int, default=100, help="How many incidents to classify")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed")
    parser.add_argument("--model", default="llama-3.1-8b-instant")
    parser.add_argument("--minio-endpoint", default=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"))
    args = parser.parse_args()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        sys.exit("GROQ_API_KEY missing. Get a free key at https://console.groq.com, put it in .env")

    access_key = os.getenv("MINIO_ROOT_USER", "resqadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "resqstats123")

    print(f"reading silver incidents from {args.minio_endpoint} ...")
    df = read_silver(args.minio_endpoint, access_key, secret_key, args.limit, args.seed)
    print(f"classifying {len(df)} calls with {args.model} (free tier - this is rate-limited, be patient)")

    session = requests.Session()
    pred_types, pred_sevs = [], []
    for i, row in df.iterrows():
        ptype, psev = classify_text(row["call_text"], api_key, args.model, session)
        pred_types.append(ptype)
        pred_sevs.append(psev)
        done = i + 1
        if done % 10 == 0 or done == len(df):
            print(f"  {done}/{len(df)}")

    df["pred_type"] = pred_types
    df["pred_severity"] = pred_sevs

    # ---- evaluation (plain Python - the LLM never touches the math) ----
    n = len(df)
    parse_fails = int(df["pred_type"].isna().sum())
    type_acc = float((df["pred_type"] == df["incident_type"]).mean())
    sev_acc = float((df["pred_severity"] == df["severity"]).mean())

    per_type: dict[str, str] = {}
    for itype, group in df.groupby("incident_type"):
        acc = float((group["pred_type"] == itype).mean())
        per_type[str(itype)] = f"{acc:.0%} ({len(group)} calls)"

    confusion = Counter(
        (t, p) for t, p in zip(df["incident_type"], df["pred_type"]) if p is not None and t != p
    )
    confusion_lines = [f"- {t} -> {p}: {c}x" for (t, p), c in confusion.most_common(5)]
    if not confusion_lines:
        confusion_lines = ["- none"]

    out_dir = Path(__file__).parent / "eval"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "predictions.csv", index=False)

    report = [
        "# LLM Classifier Evaluation",
        "",
        f"- Model: `{args.model}` (Groq free tier), temperature 0",
        f"- Sample: {n} incidents (seed {args.seed}), ground truth = simulator labels",
        f"- **incident_type accuracy: {type_acc:.1%}**",
        f"- **severity accuracy: {sev_acc:.1%}**",
        f"- unparseable responses: {parse_fails}",
        "",
        "## Per-type accuracy",
        "",
        *[f"- {k}: {v}" for k, v in sorted(per_type.items())],
        "",
        "## Top confusions (truth -> predicted)",
        "",
        *confusion_lines,
        "",
        "_Severity is genuinely ambiguous from text alone (a 'serious' accident and a",
        "'moderate' one can sound identical), so type accuracy is the headline metric._",
    ]
    (out_dir / "results.md").write_text("\n".join(report), encoding="utf-8")

    print(f"\ntype accuracy: {type_acc:.1%} | severity accuracy: {sev_acc:.1%} "
          f"| parse failures: {parse_fails}")
    print(f"report -> {out_dir / 'results.md'}\npredictions -> {out_dir / 'predictions.csv'}")


if __name__ == "__main__":
    main()
