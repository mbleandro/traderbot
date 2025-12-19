import httpx
from trader.models import JupiterRoutePlan, JupiterSwapInfo, JupiterQuoteResponse
import os
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from solana.rpc.async_api import AsyncClient as SolanaClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.solders import (
    Account,
    GetAccountInfoResp,
    GetTokenAccountsByOwnerResp,
    LiteSVM,
    Message,
    RpcKeyedAccount,
    RpcResponseContext,
    to_bytes_versioned,
    transfer,
    MessageV0,
)
from solders.transaction import VersionedTransaction

from trader.models.account_data import AccountBalanceData
from trader.providers.jupiter.async_jupiter_svc import AsyncJupiterService


@pytest.fixture()
def setenvvar(monkeypatch):
    with mock.patch.dict(os.environ, clear=True):
        envvars = {
            "HELIUS_RPC_URL": "https://mock.com",
            "SOLANA_PRIVATE_KEY": "4YFq9y5f5hi77Bq8kDCE6VgqoAqKGSQN87yW9YeGybpNfqKUG4WxnwhboHGUeXjY7g8262mhL1kCCM9yy8uGvdj7",
        }
        for k, v in envvars.items():
            monkeypatch.setenv(k, v)
        yield  # This is the magical bit which restore the environment after


@pytest.fixture()
def mock_is_connected():
    with mock.patch.object(SolanaClient, "is_connected", return_value=True):
        yield


@pytest.fixture()
def mock_get_account_info():
    with mock.patch.object(
        SolanaClient,
        "get_account_info",
        return_value=GetAccountInfoResp(
            value=Account(
                lamports=123456789,
                owner=Pubkey.from_string("E6W4RLUxZLQN5mjVfTAv7hTrdLR5Y6nrNvFiW8p1Q1m"),
                data=b"",
                executable=False,
            ),
            context=RpcResponseContext(slot=0),
        ),
    ):
        yield


@pytest.fixture()
def mock_get_token_accounts_by_owner():
    with mock.patch.object(
        SolanaClient,
        "get_token_accounts_by_owner",
        return_value=GetTokenAccountsByOwnerResp(
            value=[
                RpcKeyedAccount(
                    pubkey=Pubkey.from_string(
                        "E6W4RLUxZLQN5mjVfTAv7hTrdLR5Y6nrNvFiW8p1Q1m"
                    ),
                    account=Account(
                        lamports=123456789,
                        owner=Pubkey.from_string(
                            "E6W4RLUxZLQN5mjVfTAv7hTrdLR5Y6nrNvFiW8p1Q1m"
                        ),
                        data=b"4YFq9y5f5hi77Bq8kDCE6VgqoAqKGSQN87yW9YeGybpNfqKUG4WxnwhboHGUeXjY7g8262mhL1kCCM9yy8uGvdj7",
                        executable=False,
                    ),
                )
            ],
            context=RpcResponseContext(slot=0),
        ),
    ):
        yield


class TestAsyncJupiterService:
    def test_init(self, setenvvar):
        keypair = Keypair()
        api = AsyncJupiterService(keypair)
        assert api.rpc_client.rpc_url == "https://mock.com"

        assert isinstance(api.wallet, Pubkey)
        assert isinstance(api.rpc_client.client, SolanaClient)
        assert isinstance(api.keypair, Keypair)
        assert api.keypair == keypair

    async def test_get_account_balance(
        self,
        setenvvar,
        mock_get_account_info,
        mock_get_token_accounts_by_owner,
        mock_is_connected,
    ):
        api = AsyncJupiterService(Keypair())

        balance = await api.get_account_balance()
        assert balance == [
            AccountBalanceData(
                available=Decimal("0.123456789"),
                on_hold=Decimal("0"),
                symbol="SOL",
                total=Decimal("0.123456789"),
            )
        ]


class TestPlaceOrder:
    @pytest.fixture(autouse=True)
    def setup_tests(self, setenvvar):
        self.api = AsyncJupiterService(Keypair())

    @mock.patch.object(httpx.AsyncClient, "request", new_callable=mock.AsyncMock)
    async def test_get_quote_with_route(self, mock_get):
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "inAmount": "1000000000",
            "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
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

        mock_get.return_value = mock_response
        quote = await self.api._get_quote_with_route(
            mint_in="So11111111111111111111111111111111111111112",
            mint_out="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount_in=1000000000,
            slippage_bps=50,
        )
        assert quote == JupiterQuoteResponse(
            inputMint="So11111111111111111111111111111111111111112",
            inAmount="1000000000",
            outputMint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            outAmount="50000000",
            otherAmountThreshold="49500000",
            swapMode="ExactIn",
            slippageBps=50,
            platformFee=None,
            priceImpactPct="0.5",
            routePlan=[
                JupiterRoutePlan(
                    swapInfo=JupiterSwapInfo(
                        ammKey="key",
                        label="Raydium",
                        inputMint="mint1",
                        outputMint="mint2",
                        inAmount="1000",
                        outAmount="500",
                        feeAmount="10",
                        feeMint="mint1",
                    ),
                    percent=100,
                )
            ],
            contextSlot=123456789,
            timeTaken=0.5,
        )

    @mock.patch.object(httpx.AsyncClient, "request", new_callable=mock.AsyncMock)
    async def test_get_quote_with_route_no_route(self, mock_get):
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "inAmount": "1000000000",
            "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "outAmount": "50000000",
            "otherAmountThreshold": "49500000",
            "swapMode": "ExactIn",
            "slippageBps": 50,
            "platformFee": None,
            "priceImpactPct": "0.5",
            "routePlan": [],
            "contextSlot": 123456789,
            "timeTaken": 0.5,
        }

        mock_get.return_value = mock_response
        with pytest.raises(Exception, match="Nenhuma rota encontrada!"):
            await self.api._get_quote_with_route(
                mint_in="So11111111111111111111111111111111111111112",
                mint_out="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount_in=1000000000,
                slippage_bps=50,
            )

    @mock.patch.object(httpx.AsyncClient, "post", new_callable=mock.AsyncMock)
    async def test_get_swap_transaction(self, mock_post):
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "swapTransaction": "AbuRLtc5C9bZtAUT4F4Y2H5SRRUK1HwOFZOK3V4qm/78MDJt+M2de/RCCaI3iTyodDepmrkUWbss0XRHS0lk5AOAAQABAzfDSQC/GjcggrLsDpYz7jAlT+Gca846HqtFb8UQMM9cCWPIi4AX32PV8HrY7/1WgoRc3IATttceZsUMeQ1qx7UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2dTRgcJmzcoGH1R3c2WqtHah2H19KvbC1p6BxLDqfoAQICAAEMAgAAAADKmjsAAAAAAA=="
        }

        mock_post.return_value = mock_response

        tx = await self.api._get_swap_transaction(
            quote=JupiterQuoteResponse(
                inputMint="So11111111111111111111111111111111111111112",
                inAmount="1000000000",
                outputMint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
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
        )
        assert isinstance(tx, VersionedTransaction)

    async def test_get_signed_transaction(self, mock_is_connected):
        keypair = Keypair()
        receiver = Pubkey.new_unique()

        api = AsyncJupiterService(keypair=keypair)
        api.keypair = keypair
        ixs = [
            transfer(
                {
                    "from_pubkey": keypair.pubkey(),
                    "to_pubkey": receiver,
                    "lamports": 100_000,
                }
            )
        ]

        client = LiteSVM()
        client.airdrop(keypair.pubkey(), 1_000_000_000)
        blockhash = client.latest_blockhash()

        async def latest_block():
            return SimpleNamespace(value=SimpleNamespace(blockhash=blockhash))

        api.rpc_client.client.get_latest_blockhash = latest_block  # type: ignore
        msg = Message.new_with_blockhash(ixs, keypair.pubkey(), blockhash)
        message = MessageV0(
            header=msg.header,
            account_keys=msg.account_keys,
            recent_blockhash=blockhash,
            instructions=msg.instructions,
            address_table_lookups=[],
        )
        tx = VersionedTransaction(message, [keypair])
        signed_tx = await api._get_signed_transaction(tx=tx)
        assert isinstance(signed_tx, VersionedTransaction)
        assert signed_tx.signatures[0].verify(
            keypair.pubkey(), to_bytes_versioned(signed_tx.message)
        )

    async def test_send_signed_transaction(self, mock_is_connected):
        keypair = Keypair()
        receiver = Pubkey.new_unique()

        service = AsyncJupiterService(keypair=keypair)
        service.keypair = keypair
        ixs = [
            transfer(
                {
                    "from_pubkey": keypair.pubkey(),
                    "to_pubkey": receiver,
                    "lamports": 100_000,
                }
            )
        ]

        client = LiteSVM()
        client.airdrop(keypair.pubkey(), 1_000_000_000)
        blockhash = client.latest_blockhash()
        msg = Message.new_with_blockhash(ixs, keypair.pubkey(), blockhash)
        tx = VersionedTransaction(msg, [keypair])
        tx.signatures = [keypair.sign_message(to_bytes_versioned(msg))]

        async def _simulate_transaction(x):
            # signature = client.simulate_transaction(x).meta().signature()

            return SimpleNamespace(value=SimpleNamespace(err=None))

        async def _send_raw_transaction(x):
            signature = client.simulate_transaction(tx).meta().signature()

            return SimpleNamespace(value=signature)

        service.rpc_client.client.simulate_transaction = _simulate_transaction  # type: ignore
        service.rpc_client.client.send_raw_transaction = _send_raw_transaction  # type: ignore
        resp = await service._send_signed_transaction(tx)
        assert resp.value is not None
