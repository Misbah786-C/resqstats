"""Alert helper: Telegram if configured, log otherwise.

Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the environment (.env) to get
real phone notifications. Without them, alerts go to the Airflow task log -
the pipeline never breaks just because chat isn't configured.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("resqstats.alerts")


def notify(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        try:
            import requests

            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=15,
            )
            if resp.status_code == 200:
                return
            log.warning("telegram returned %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:  # alerting must never crash the pipeline
            log.warning("telegram send failed: %s", exc)
    log.warning("[ALERT] %s", message)


def notify_failure(context) -> None:
    """Airflow on_failure_callback - fires when any task fails."""
    ti = context.get("task_instance")
    notify(
        f"🚨 ResQStats pipeline FAILED\n"
        f"task: {ti.task_id if ti else '?'}\n"
        f"run: {context.get('run_id', '?')}\n"
        f"check Airflow logs."
    )
