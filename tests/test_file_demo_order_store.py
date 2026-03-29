from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cex_tbot.execution.demo_sync import DemoOrderRecord
from cex_tbot.storage.demo_order_files import FileDemoOrderStore


class FileDemoOrderStoreTests(unittest.TestCase):
    def test_replace_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo-orders.jsonl"
            store = FileDemoOrderStore(path)
            store.replace_for_proposal(
                "proposal_1",
                [
                    DemoOrderRecord(
                        order_id="entry_1",
                        proposal_id="proposal_1",
                        role="entry",
                        contract="BTC_USDT",
                        side="buy",
                        size=10,
                        status="open",
                    ),
                    DemoOrderRecord(
                        order_id="sl_1",
                        proposal_id="proposal_1",
                        role="stop_loss",
                        contract="BTC_USDT",
                        side="sell",
                        size=10,
                        status="open",
                        trigger_price=99.0,
                        order_price=99.0,
                        reduce_only=True,
                        linked_entry_order_id="entry_1",
                    ),
                ],
            )

            reloaded = FileDemoOrderStore(path)
            items = reloaded.list_for_proposal("proposal_1")
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0].order_id, "entry_1")
            self.assertEqual(items[1].linked_entry_order_id, "entry_1")


if __name__ == "__main__":
    unittest.main()
