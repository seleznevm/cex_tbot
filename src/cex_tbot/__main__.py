from __future__ import annotations

import argparse
import json
from pathlib import Path

from cex_tbot.bootstrap import build_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap cex_tbot runtime wiring")
    parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for bootstrap status",
    )
    args = parser.parse_args()

    app = build_app(storage_dir=args.storage_dir)
    payload = {
        "status": "ok",
        "storage": "file" if args.storage_dir is not None else "memory",
        "storage_dir": str(args.storage_dir) if args.storage_dir is not None else None,
        "execution_mode": app.config.execution_mode,
        "exchange": app.config.exchange.value,
        "market_type": app.config.market_type.value,
        "session_summary": app.backend.get_session_summary_payload(),
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("cex_tbot bootstrap: OK")
        print(f"storage={payload['storage']}")
        print(f"execution_mode={payload['execution_mode']}")
        print(f"exchange={payload['exchange']} market_type={payload['market_type']}")
        print(
            "session="
            f"proposals={payload['session_summary']['total_proposals']} "
            f"commands={payload['session_summary']['operator_commands']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
