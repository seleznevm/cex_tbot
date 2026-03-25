from __future__ import annotations

import argparse
import json
from pathlib import Path

from cex_tbot.bootstrap import build_app
from cex_tbot.demo import render_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cex_tbot local runtime entrypoint")
    parser.add_argument(
        "--storage-dir",
        type=Path,
        help="Optional base directory for file-backed session state (works for default status mode and subcommands)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for default status mode and subcommands",
    )
    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser("status", help="Print bootstrap/runtime status")
    status_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    status_parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format for bootstrap status")

    demo_parser = subparsers.add_parser("demo", help="Run deterministic semi-auto demo flow")
    demo_parser.add_argument("--storage-dir", type=Path, help="Optional base directory for file-backed session state")
    demo_parser.add_argument("--format", choices=("text", "json"), default="text", help="Demo output format")
    demo_parser.add_argument(
        "--flow",
        choices=("approve-execute", "approve-then-execute"),
        default="approve-execute",
        help="Choose immediate execution or explicit two-step execution",
    )
    return parser


def _resolve_common_option(args: argparse.Namespace, name: str):
    command_value = getattr(args, name, None)
    if command_value is not None:
        return command_value
    return getattr(args, f"global_{name}")


def render_status(*, storage_dir: Path | None, fmt: str) -> str:
    app = build_app(storage_dir=storage_dir)
    payload = {
        "status": "ok",
        "storage": "file" if storage_dir is not None else "memory",
        "storage_dir": str(storage_dir) if storage_dir is not None else None,
        "execution_mode": app.config.execution_mode,
        "exchange": app.config.exchange.value,
        "market_type": app.config.market_type.value,
        "session_summary": app.backend.get_session_summary_payload(),
    }
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False)
    return "\n".join(
        [
            "cex_tbot bootstrap: OK",
            f"storage={payload['storage']}",
            f"execution_mode={payload['execution_mode']}",
            f"exchange={payload['exchange']} market_type={payload['market_type']}",
            "session="
            f"proposals={payload['session_summary']['total_proposals']} "
            f"commands={payload['session_summary']['operator_commands']}",
        ]
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Preserve backward compatibility with the old smoke command:
    # `python -m cex_tbot --storage-dir ... --format json`
    # still renders status when no explicit subcommand is provided.
    setattr(args, "global_storage_dir", getattr(args, "storage_dir", None))
    setattr(args, "global_format", getattr(args, "format", "text"))

    command = args.command or "status"
    storage_dir = _resolve_common_option(args, "storage_dir")
    fmt = _resolve_common_option(args, "format")

    if command == "demo":
        print(render_demo(flow=args.flow, storage_dir=storage_dir, fmt=fmt))
        return 0

    print(render_status(storage_dir=storage_dir, fmt=fmt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
