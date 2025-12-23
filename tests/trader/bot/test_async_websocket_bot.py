import base64
from decimal import Decimal

from solana.rpc.types import TokenAccountOpts
from solders.keypair import Keypair
from solders.solders import (
    TOKEN_PROGRAM_ID,
    Account,
    FailedTransactionMetadata,
    GetAccountInfoResp,
    GetLatestBlockhashResp,
    GetTokenAccountsByOwnerResp,
    LiteSVM,
    Pubkey,
    RpcBlockhash,
    RpcKeyedAccount,
    RpcResponseContext,
    RpcSimulateTransactionResult,
    SendTransactionResp,
    SimulateTransactionResp,
    TokenAccount,
    TokenAccountState,
    Transaction,
    VersionedTransaction,
    get_associated_token_address,
)

from trader.models import OrderSide, OrderSignal, Position
from trader.trading_strategy import TradingStrategy


class FakeSolanaClient:
    keypair = Keypair()

    def __init__(self):
        self.client = LiteSVM()
        self.setup()

    def setup(self):
        owner = FakeSolanaClient.keypair.pubkey()
        usdc_mint = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        ata = get_associated_token_address(owner, usdc_mint)
        usdc_to_own = 1_000_000_000_000
        token_acc = TokenAccount(
            mint=usdc_mint,
            owner=owner,
            amount=usdc_to_own,
            delegate=None,
            state=TokenAccountState.Initialized,
            is_native=None,
            delegated_amount=0,
            close_authority=None,
        )
        client = self.client
        client.set_account(
            ata,
            Account(
                lamports=1_000_000_000,
                data=bytes(token_acc),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
            ),
        )
        client.set_account(
            owner,
            Account(
                lamports=1_000_000_000,
                data=bytes(token_acc),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
            ),
        )
        raw_account = client.get_account(ata)
        assert raw_account is not None
        raw_account_data = raw_account.data
        assert TokenAccount.from_bytes(raw_account_data).amount == usdc_to_own

    async def is_connected(self):
        return True

    async def send_raw_transaction(self, tx: bytes):
        result = self.client.send_transaction(Transaction.from_bytes(tx))
        if isinstance(result, FailedTransactionMetadata):
            raise Exception(f"Invalid Result FailedTransactionMetadata {result}")
        signature = result.signature()
        return SendTransactionResp(value=signature)

    async def simulate_transaction(self, tx: VersionedTransaction):
        return SimulateTransactionResp(
            RpcSimulateTransactionResult(),
            RpcResponseContext(slot=123),  # type: ignore
        )

    async def get_account_info(self, pubkey: Pubkey):
        account = self.client.get_account(pubkey)
        return GetAccountInfoResp(value=account, context=RpcResponseContext(slot=123))

    async def get_token_accounts_by_owner(self, owner: Pubkey, opts: TokenAccountOpts):
        return GetTokenAccountsByOwnerResp(
            value=[
                RpcKeyedAccount(
                    pubkey=owner,
                    account=Account(
                        lamports=123456789,
                        owner=Pubkey.from_string(
                            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        ),
                        data=base64.b64decode(
                            "xvp6877brTo9ZfNqq8l0MbG75MLS9uDkfKYCA0UvXWGWLa9jbECytyNphzh7LQSyyvt90dqHEa5Ir7Dj07qtEhXNWwcAAAAA"
                        ),
                        executable=False,
                    ),
                )
            ],
            context=RpcResponseContext(slot=0),
        )

    async def get_latest_blockhash(self):
        self.client.set_blockhash_check(False)
        return GetLatestBlockhashResp(
            RpcBlockhash(self.client.latest_blockhash(), 1),
            context=RpcResponseContext(slot=0),
        )


class FakeStrategy(TradingStrategy):
    def __init__(self):
        self.count = 0

    def on_market_refresh(
        self,
        price: Decimal,
        spread: Decimal | None,
        balance: Decimal,
        current_position: Position | None,
    ) -> OrderSignal | None:
        self.count += 1
        if self.count > 2:
            # gambiarra pra forcar o bot parar depois de comprar e vender uma vez
            raise KeyboardInterrupt()
        if current_position:
            return OrderSignal(OrderSide.SELL, current_position.entry_order.quantity)
        else:
            return OrderSignal(OrderSide.BUY, self.calculate_quantity(balance, price))


# async def test_async_websocket_bot_complete():
#     keypair = FakeSolanaClient.keypair
#     strategy=FakeStrategy()
#     client=FakeSolanaClient()
#     config = BotConfig(
#         id="id-bot-config-teste-complete",
#         name="name-bot-config-teste-complete",
#         input_mint="So11111111111111111111111111111111111111112",
#         output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
#         wallet=keypair,
#         provider=AsyncJupiterProvider(
#             keypair=keypair,
#             rpc_client=AsyncRPCClient(client=client),
#             jupiter_client=AsyncJupiterClient(),
#         ),
#         strategy=strategy,
#         notifier=NullNotificationService(),
#     )

#     bot = AsyncWebsocketTradingBot(config)
#     await bot._run()
#     assert strategy.count == 3
#     # bot.stop()
