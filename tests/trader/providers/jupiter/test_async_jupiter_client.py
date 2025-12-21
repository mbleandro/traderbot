import httpx
from unittest import mock

from trader.providers.jupiter.async_jupiter_client import AsyncJupiterClient
from trader.providers.jupiter.jupiter_data import (
    JupiterQuoteResponse,
    JupiterRoutePlan,
    JupiterSwapInfo,
)


class TestAsyncJupiterClient:
    class TestGetQuote:
        fake_request_get_quote = httpx.Response(
            200,
            request=httpx.Request("GET", ""),
            json={
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
                            "ammKey": "FksffEqnBRixYGR791Qw2MgdU7zNCpHVFYBL4Fa4qVuH",
                            "label": "HumidiFi",
                            "inputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                            "outputMint": "So11111111111111111111111111111111111111112",
                            "inAmount": "1000000000",
                            "outAmount": "7106793162",
                            "feeAmount": "0",
                            "feeMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        },
                        "percent": 100,
                    }
                ],
                "contextSlot": 123456789,
                "timeTaken": 0.5,
            },
        )

        def _assert_response(self, response: JupiterQuoteResponse):
            assert response == JupiterQuoteResponse(
                inputMint="So11111111111111111111111111111111111111112",
                inAmount="1000000000",
                outputMint="EPjFWdd5Au...",
                outAmount="50000000",
                otherAmountThreshold="49500000",
                swapMode="ExactIn",
                slippageBps=50,
                platformFee=None,
                priceImpactPct="0.5",
                routePlan=[
                    JupiterRoutePlan(
                        swapInfo=JupiterSwapInfo(
                            ammKey="FksffEqnBRixYGR791Qw2MgdU7zNCpHVFYBL4Fa4qVuH",
                            label="HumidiFi",
                            inputMint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                            outputMint="So11111111111111111111111111111111111111112",
                            inAmount="1000000000",
                            outAmount="7106793162",
                            feeAmount="0",
                            feeMint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        ),
                        percent=100,
                    )
                ],
                contextSlot=123456789,
                timeTaken=0.5,
            )

        @mock.patch.object(
            httpx.AsyncClient,
            "get",
            return_value=fake_request_get_quote,
        )
        async def test_get_quote(self, mock_make_request):
            client = AsyncJupiterClient()
            response = await client.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
                slippage_bps=50,
            )
            self._assert_response(response)
            mock_make_request.assert_called_once_with(
                "https://lite-api.jup.ag/swap/v1/quote",
                params={
                    "inputMint": "So11111111111111111111111111111111111111112",
                    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "amount": "1000000000",
                    "slippageBps": "50",
                },
            )

        @mock.patch.object(
            httpx.AsyncClient,
            "get",
            return_value=fake_request_get_quote,
        )
        async def test_only_direct_routes(self, mock_make_request):
            client = AsyncJupiterClient()
            response = await client.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
                slippage_bps=50,
                only_direct_routes=True,
            )
            self._assert_response(response)
            mock_make_request.assert_called_once_with(
                "https://lite-api.jup.ag/swap/v1/quote",
                params={
                    "inputMint": "So11111111111111111111111111111111111111112",
                    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "amount": "1000000000",
                    "slippageBps": "50",
                    "onlyDirectRoutes": "true",
                },
            )

        @mock.patch.object(
            httpx.AsyncClient,
            "get",
            return_value=fake_request_get_quote,
        )
        async def test_max_accounts(self, mock_make_request):
            client = AsyncJupiterClient()
            response = await client.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
                slippage_bps=50,
                max_accounts=5,
            )
            self._assert_response(response)
            mock_make_request.assert_called_once_with(
                "https://lite-api.jup.ag/swap/v1/quote",
                params={
                    "inputMint": "So11111111111111111111111111111111111111112",
                    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "amount": "1000000000",
                    "slippageBps": "50",
                    "maxAccounts": "5",
                },
            )
