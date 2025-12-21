from solders.keypair import Keypair
from trader.models import SOLANA_MINTS
from trader.providers import AsyncJupiterProvider
import re
from decimal import Decimal
from unittest import mock

import pytest

from trader.models.public_data import TickerData
from trader.providers.jupiter.async_jupiter_client import AsyncJupiterClient
from trader.providers.jupiter.jupiter_data import JupiterQuoteResponse


class TestGetTicker:
    @staticmethod
    async def fake_get_quote(*args, **kwargs) -> JupiterQuoteResponse:
        data = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "inAmount": "1000000000",
            "outputMint": "EPjFWdd5Au...",
            "outAmount": "50000000",
            "otherAmountThreshold": "49500000",
            "swapMode": "ExactIn",
            "slippageBps": 50,
            "platformFee": None,
            "priceImpactPct": "0.5",
            "routePlan": [
                {
                    "swapInfo": {
                        "ammKey": "key",
                        "label": "Raydium",
                        "inputMint": "mint1",
                        "outputMint": "mint2",
                        "inAmount": "1000",
                        "outAmount": "500",
                        "feeAmount": "10",
                        "feeMint": "mint1",
                    },
                    "percent": 100,
                }
            ],
            "contextSlot": 123456789,
            "timeTaken": 0.5,
        }
        return JupiterQuoteResponse.from_dict(data)

    @mock.patch.object(AsyncJupiterClient, "get_price", return_value=Decimal("2"))
    async def test_get_ticker(self, mock_get_quote):
        adapter = AsyncJupiterProvider(Keypair(), rpc_client=object)
        ticker = await adapter.get_price_ticker_data(
            SOLANA_MINTS.get_by_symbol("SOL").pubkey
        )
        buy_price = Decimal("2")
        assert ticker == TickerData(
            buy=buy_price,
            timestamp=mock.ANY,
            high=buy_price,
            last=buy_price,
            low=buy_price,
            open=buy_price,
            pair="ignored",
            sell=buy_price,
            vol=Decimal("0"),
            spread=None,
        )
        mock_get_quote.assert_has_calls(
            [mock.call("So11111111111111111111111111111111111111112")]
        )
