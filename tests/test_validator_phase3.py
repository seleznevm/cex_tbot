from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, ProposalValidator, TradeProposal
from cex_tbot.enums import ProposalReasonCode
from cex_tbot.universe import UniverseService, WhitelistedInstrument


class ProposalValidatorPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BotConfig(min_confidence_score=0.7)
        self.universe_service = UniverseService(self.config)
        self.validator = ProposalValidator(self.config, self.universe_service)
        now = datetime.now(UTC)
        base_instrument = WhitelistedInstrument(
            symbol="BTC_USDT",
            listing_age_hours=500,
            spread_bps=1.0,
            volume_24h=2_000_000,
            open_interest=1_500_000,
            top_book_depth=400_000,
            eligible_until=now + timedelta(minutes=30),
        )
        self.instruments = [self.universe_service.apply_decision(base_instrument)]

    def _proposal(self, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        payload = dict(
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[
                EntrySplitLeg(1, 100.0, 60.0, 0.6, now + timedelta(minutes=10)),
                EntrySplitLeg(2, 99.4, 40.0, 0.4, now + timedelta(minutes=10)),
            ],
            stop_loss=97.5,
            take_profit_1=102.0,
            take_profit_2=104.0,
            risk_percent=0.5,
            risk_usd=5.0,
            position_size=100.0,
            confidence_score=0.8,
            thesis="structure intact",
            invalidity_condition="swing low breaks",
            liquidity_check="ok",
            data_freshness_ms=100,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        payload.update(overrides)
        return TradeProposal(**payload)

    def test_rejects_leg_outside_entry_zone(self) -> None:
        proposal = self._proposal(entry_split=[EntrySplitLeg(1, 101.5, 100.0, 1.0, datetime.now(UTC) + timedelta(minutes=10))])
        result = self.validator.validate(proposal, self.instruments)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.ENTRY_SPLIT_INVALID)

    def test_rejects_stop_loss_inside_entry_zone(self) -> None:
        result = self.validator.validate(self._proposal(stop_loss=99.5), self.instruments)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.STOP_LOSS_INVALID)

    def test_rejects_non_progressive_take_profit(self) -> None:
        result = self.validator.validate(self._proposal(take_profit_2=102.0), self.instruments)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.RISK_CALCULATION_MISMATCH)


if __name__ == "__main__":
    unittest.main()
