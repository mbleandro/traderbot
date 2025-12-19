from solders.solders import FailedTransactionMetadata
from solders.rpc.responses import (
    SendTransactionResp,
    SimulateTransactionResp,
    RpcSimulateTransactionResult,
    RpcResponseContext,
)
import pytest
from solders.litesvm import LiteSVM
from solders.transaction import VersionedTransaction, Transaction
from solders.message import Message, to_bytes_versioned
from solders.system_program import transfer
from solders.pubkey import Pubkey
from solders.keypair import Keypair


from trader.providers.jupiter.async_rpc_client import AsyncRPCClient


class FakeSolanaClient:
    client = LiteSVM()

    async def is_connected(self):
        return True

    async def send_raw_transaction(self, tx: bytes):
        result = FakeSolanaClient.client.send_transaction(Transaction.from_bytes(tx))
        if isinstance(result, FailedTransactionMetadata):
            raise Exception(f"Invalid Result FailedTransactionMetadata {result}")
        signature = result.signature()
        return SendTransactionResp(value=signature)

    async def simulate_transaction(self, tx: VersionedTransaction):
        result = FakeSolanaClient.client.simulate_transaction(tx)
        if isinstance(result, FailedTransactionMetadata):
            return SimulateTransactionResp(
                value=RpcSimulateTransactionResult(err=result.err())
            )

        return SimulateTransactionResp(
            RpcSimulateTransactionResult(),
            RpcResponseContext(slot=123),  # type: ignore
        )


class FakeAsyncRPCClient(AsyncRPCClient):
    def __init__(self):
        self.is_dryrun = False
        self.client = FakeSolanaClient()


@pytest.fixture
def mock_signed_transaction():
    keypair = Keypair()
    receiver = Pubkey.new_unique()

    ixs = [
        transfer(
            {
                "from_pubkey": keypair.pubkey(),
                "to_pubkey": receiver,
                "lamports": 100_000,
            }
        )
    ]

    client = FakeSolanaClient.client
    client.airdrop(keypair.pubkey(), 1_000_000_000)
    blockhash = client.latest_blockhash()
    msg = Message.new_with_blockhash(ixs, keypair.pubkey(), blockhash)
    tx = VersionedTransaction(msg, [keypair])
    tx.signatures = [keypair.sign_message(to_bytes_versioned(msg))]
    return tx


async def test_send_transaction(mock_signed_transaction):
    resp = await FakeAsyncRPCClient().send_transaction(mock_signed_transaction)
    assert resp.value is not None


async def test_simulate_transaction(mock_signed_transaction):
    resp = await FakeAsyncRPCClient().simulate_transaction(mock_signed_transaction)
    assert resp.value is not None
