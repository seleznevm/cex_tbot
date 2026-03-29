from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    storage_dir = root / ".runtime" / "cron-autosync"
    cmd = [
        sys.executable,
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
    ]
    completed = subprocess.run(
        cmd,
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={**dict(), **__import__("os").environ, "PYTHONPATH": "src"},
    )
    payload = json.loads(completed.stdout)
    alerts: list[dict[str, object]] = []
    for run in payload:
        for proposal in run.get("proposals", []):
            telegram_alert = proposal.get("telegram_alert")
            if telegram_alert:
                alerts.append(telegram_alert)
    print(json.dumps({"alerts": alerts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
