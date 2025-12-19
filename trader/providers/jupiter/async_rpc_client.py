from solders.signature import Signature
from solana.rpc.types import TokenAccountOpts
from spl.token.constants import TOKEN_2022_PROGRAM_ID
from decimal import Decimal
from solders.pubkey import Pubkey
from solders.rpc.responses import SendTransactionResp
from solders.keypair import Keypair
from solders.message import MessageV0, to_bytes_versioned
import time
from solders.solders import (
    TransactionConfirmationStatus,
    VersionedTransaction,
    TOKEN_PROGRAM_ID,
)
import os
from solana.rpc.async_api import AsyncClient


class AsyncRPCClient:
    def __init__(self):
        self.rpc_url = os.getenv("HELIUS_RPC_URL")
        assert self.rpc_url, "RPC URL não definida"
        self.client = AsyncClient(self.rpc_url)

    async def wait_for_confirmation(self, signature, timeout=30) -> bool:
        start = time.time()

        while True:
            result = await self.client.get_signature_statuses([signature])
            status = result.value[0]

            if status is not None:
                # Se a transação foi processada
                if status.confirmation_status in [
                    TransactionConfirmationStatus.Confirmed,
                    TransactionConfirmationStatus.Finalized,
                ]:
                    return True
                if status.err is not None:
                    raise Exception(f"Transação falhou: {status.err}")

            # Timeout
            if time.time() - start > timeout:
                raise TimeoutError("Transação não foi confirmada a tempo.")

            time.sleep(1)

    async def sign_transaction(
        self, tx: VersionedTransaction, keypair: Keypair
    ) -> VersionedTransaction:
        latest = await self.client.get_latest_blockhash()
        blockhash = latest.value.blockhash
        message = tx.message
        message = MessageV0(
            header=tx.message.header,
            account_keys=tx.message.account_keys,
            recent_blockhash=blockhash,
            instructions=tx.message.instructions,
            address_table_lookups=tx.message.address_table_lookups,  # type: ignore
        )

        new_tx = VersionedTransaction(
            message=message,
            keypairs=[keypair],
        )

        signature = keypair.sign_message(to_bytes_versioned(message))

        new_tx.signatures = [signature]
        return new_tx

    async def simulate_transaction(self, new_tx: VersionedTransaction):
        simulation = await self.client.simulate_transaction(new_tx)
        if simulation.value.err:
            raise Exception(f"Erro ao simular transação: {simulation.value}")

    async def send_transaction(
        self, new_tx: VersionedTransaction
    ) -> SendTransactionResp:
        # resp = await self.client.send_raw_transaction(bytes(new_tx))
        # signature = resp.value

        # return resp
        return SendTransactionResp(value=Signature.new_unique())

    async def get_balance(self, pubkey: Pubkey) -> Decimal:
        resp = await self.client.get_account_info(pubkey)
        if resp.value:
            lamports = resp.value.lamports
            return Decimal(lamports)

        raise Exception(f"Não foi possivel obter o balanco da pubkey: {str(pubkey)}")

    async def get_lamports(self, pubkey: Pubkey) -> Decimal:
        resp = await self.client.get_account_info(pubkey)
        if resp.value:
            lamports = resp.value.lamports
            return Decimal(lamports)

        raise Exception(f"Não foi possivel obter o balanco da pubkey: {str(pubkey)}")

    async def get_account_balance(self, owner: Pubkey) -> dict[Pubkey, Decimal]:
        balances: dict[Pubkey, Decimal] = {}

        # ====================================================
        # 2 - Listar todas as contas SPL pertencentes à wallet
        # ====================================================
        for token in [TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID]:
            token_accounts = await self.client.get_token_accounts_by_owner(
                owner, TokenAccountOpts(program_id=token)
            )

            for token_acc in token_accounts.value:
                info = token_acc.account.data  # base64 data
                decoded = bytes(info)
                mint = Pubkey(decoded[0:32])
                amount = int.from_bytes(decoded[64:72], "little")
                balances[mint] = Decimal(amount)

        return balances
