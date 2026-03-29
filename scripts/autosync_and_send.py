from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    storage_dir = root / ".runtime" / "cron-autosync"
    python = root / ".venv" / "bin" / "python"

    autosync = subprocess.run(
        [
            str(python),
            "-m",
            "cex_tbot",
            "autosync-demo",
            "--storage-dir",
            str(storage_dir),
            "--runs",
            "1",
            "--emit-telegram-alerts",
            "--format",
            "json",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    payload = json.loads(autosync.stdout)
    alerts: list[dict[str, str]] = []
    for run in payload:
        for proposal in run.get("proposals", []):
            telegram_alert = proposal.get("telegram_alert")
            if telegram_alert:
                alerts.append(telegram_alert)

    if not alerts:
        return 0

    openclaw_bin = os.environ.get("OPENCLAW_BIN", "openclaw")
    for alert in alerts:
        subprocess.run(
            [
                openclaw_bin,
                "message",
                "send",
                "--channel",
                "telegram",
                "--target",
                str(alert["chat_id"]).replace("telegram:", ""),
                "--thread-id",
                str(alert["thread_id"]),
                "--message",
                str(alert["text"]),
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
