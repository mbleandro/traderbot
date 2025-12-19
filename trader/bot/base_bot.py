from trader.providers import JupiterPublicAPIAdapter
from trader.models.bot_config import BotConfig, create_bot_config
import logging
from abc import ABC, abstractmethod

from trader.account import Account
from trader.models.position import Position
from trader.models.public_data import TickerData
from trader.notification.notification_service import NotificationService
from trader.providers.base_api import PublicAPIBase
from trader.trading_strategy import TradingStrategy


class BaseBot(ABC):
    """Classe base para bots de trading e backtesting"""

    @classmethod
    def from_deprecated_args(
        cls,
        api: PublicAPIBase,
        strategy: TradingStrategy,
        account: Account,
        notification_service: NotificationService,
    ):
        config = create_bot_config(
            f"run-{strategy.__class__.__name__}",
            account.symbol,
            account.api,
            strategy,
            notification_service,
        )
        return cls(config)

    def __init__(
        self,
        config: BotConfig,
    ):
        self.last_position: Position | None = None
        self.is_running = False
        self.logger = logging.getLogger(self.__class__.__name__)

        public_api = JupiterPublicAPIAdapter(use_pro=False)
        self.api = public_api
        self.strategy = config.strategy
        self.symbol = config.currency
        self.account = Account(config.provider, config.currency)
        self.notification_service = config.notifier

    @abstractmethod
    def run(self, **kwargs):
        """Método abstrato para executar o bot"""
        pass

    def process_market_data(self, current_ticker: TickerData):
        position_signal = self.strategy.on_market_refresh(
            current_ticker,
            None,
            self.account.get_position(),
        )
        order = None
        if position_signal:
            if position_signal.quantity is None:
                position_signal.quantity = self.strategy.calculate_quantity(
                    self.account.get_balance("USDC"),
                    current_ticker.last,
                )
            order = self.account.place_order(
                current_ticker.last,
                position_signal.side,
                position_signal.quantity,
            )
        return order

    def stop(self):
        """Para o bot"""
        self.is_running = False
