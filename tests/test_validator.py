from datetime import UTC, datetime, timedelta
import unittest

from cex_tbot.config import BotConfig
from cex_tbot.decision_contracts import EntrySplitLeg, ProposalValidator, TradeProposal
from cex_tbot.enums import ProposalReasonCode
from cex_tbot.universe import UniverseService, WhitelistedInstrument


class ProposalValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BotConfig(min_confidence_score=0.7)
        self.universe_service = UniverseService(self.config)
        self.validator = ProposalValidator(self.config, self.universe_service)
        now = datetime.now(UTC)
        self.instrument = WhitelistedInstrument(
            symbol="BTC_USDT",
            listing_age_hours=500,
            spread_bps=1.0,
            volume_24h=2_000_000,
            open_interest=1_500_000,
            top_book_depth=400_000,
            eligible_until=now + timedelta(minutes=30),
        )

    def _proposal(self, **overrides: object) -> TradeProposal:
        now = datetime.now(UTC)
        base = dict(
            agent_name="Luma",
            strategy_id="pullback",
            strategy_version="v1",
            market_context_id="ctx_1",
            symbol="BTC_USDT",
            timeframe="15m",
            entry_zone_min=99.0,
            entry_zone_max=100.0,
            entry_split=[
                EntrySplitLeg(1, 100.0, 60.0, 0.6, now + timedelta(minutes=15)),
                EntrySplitLeg(2, 99.2, 40.0, 0.4, now + timedelta(minutes=15)),
            ],
            stop_loss=97.0,
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
        base.update(overrides)
        return TradeProposal(**base)

    def test_valid_proposal_passes(self) -> None:
        result = self.validator.validate(self._proposal(), [self.universe_service.apply_decision(self.instrument)])
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.reason_code)

    def test_low_confidence_rejected(self) -> None:
        result = self.validator.validate(self._proposal(confidence_score=0.65), [self.universe_service.apply_decision(self.instrument)])
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.CONFIDENCE_TOO_LOW)

    def test_ineligible_symbol_rejected(self) -> None:
        stale_instrument = WhitelistedInstrument(symbol="BTC_USDT", eligible_until=datetime.now(UTC) - timedelta(minutes=1))
        result = self.validator.validate(self._proposal(), [stale_instrument])
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason_code, ProposalReasonCode.STALE_MARKET_DATA)


if __name__ == "__main__":
    unittest.main()
