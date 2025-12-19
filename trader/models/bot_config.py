from solders.pubkey import Pubkey
from trader.providers import JupiterPrivateAPI
import os
import uuid
from dataclasses import dataclass
from enum import StrEnum, auto
from trader.notification.notification_service import (
    NotificationService,
    NullNotificationService,
)
from trader.providers.jupiter.jupiter_adapter import DryJupiterPrivateAPI
from trader.providers.jupiter.jupiter_public_api import SOLANA_TOKENS_BY_MINT
from trader.trading_strategy import TradingStrategy, StrategyComposer, RandomStrategy
from trader.providers.base_api import PrivateAPIBase
from solders.keypair import Keypair


# class RunningMode(StrEnum):
#     REAL = auto()
#     DRY = auto()
#     FAKE = auto()


@dataclass
class BotConfig:
    id: str
    name: str  # unique friendly name

    mint_in: str
    mint_out: str
    # mode: RunningMode
    wallet: Keypair
    provider: PrivateAPIBase
    strategy: TradingStrategy
    notifier: NotificationService

    @property
    def currency(self):
        _in = SOLANA_TOKENS_BY_MINT[self.mint_in]
        _out = SOLANA_TOKENS_BY_MINT[self.mint_out]
        return f"{_out}-{_in}"


private_key = os.getenv("SOLANA_PRIVATE_KEY")
assert private_key, "Chave privada não definida"
keypair = Keypair.from_base58_string(private_key)

# pub_key_str = os.getenv("SOLANA_PUBLIC_KEY")
# assert pub_key_str, "Chave publica não definida"
# public_key = Pubkey.from_string(pub_key_str)

# assert keypair.pubkey() == public_key

MY_CONFIG = BotConfig(
    id=uuid.uuid4().hex,
    name="my_config",
    mint_in="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    mint_out="So11111111111111111111111111111111111111112",
    # mode=RunningMode.DRY,
    wallet=keypair,
    provider=DryJupiterPrivateAPI(str(keypair.pubkey())),
    # strategy=StrategyComposer(sell_mode="any", buy_mode="all"),
    strategy=RandomStrategy(sell_chance=20, buy_chance=40),
    notifier=NullNotificationService(),
)
