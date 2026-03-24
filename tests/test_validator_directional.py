from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, ProposalValidator, TradeProposal
from cex_tbot.enums import ProposalReasonCode, TradeDirection
from cex_tbot.universe import UniverseService, WhitelistedInstrument


class ProposalValidatorDirectionalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BotConfig(min_confidence_score=0.7)
        self.universe_service = UniverseService(self.config)
        self.validator = ProposalValidator(self.config, self.universe_service)
        now = datetime.now(UTC)
        self.instruments = [
            self.universe_service.apply_decision(
                WhitelistedInstrument(
                    symbol="BTC_USDT",
                    listing_age_hours=500,
                    spread_bps=1.0,
                    volume_24h=2_000_000,
                    open_interest=1_500_000,
                    top_book_depth=400_000,
                    eligible_until=now + timedelta(minutes=30),
                )
            )
        ]

    def _proposal(self, direction: TradeDirection, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        payload = dict(
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            direction=direction,
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[EntrySplitLeg(1, 100.0, 100.0, 1.0, now + timedelta(minutes=10))],
            stop_loss=97.5 if direction == TradeDirection.LONG else 101.0,
            take_profit_1=102.0 if direction == TradeDirection.LONG else 98.0,
            take_profit_2=104.0 if direction == TradeDirection.LONG else 96.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=100.0,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        payload.update(overrides)
        return TradeProposal(**payload)

    def test_long_direction_requires_stop_below_zone(self) -> None:
        result = self.validator.validate(self._proposal(TradeDirection.LONG, stop_loss=99.2), self.instruments)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.STOP_LOSS_INVALID)

    def test_short_direction_requires_stop_above_zone(self) -> None:
        result = self.validator.validate(self._proposal(TradeDirection.SHORT, stop_loss=99.8), self.instruments)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.STOP_LOSS_INVALID)

    def test_short_direction_requires_descending_take_profits(self) -> None:
        result = self.validator.validate(self._proposal(TradeDirection.SHORT, take_profit_1=100.5, take_profit_2=101.0), self.instruments)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.RISK_CALCULATION_MISMATCH)


if __name__ == "__main__":
    unittest.main()
