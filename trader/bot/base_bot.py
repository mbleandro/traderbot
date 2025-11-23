import logging
from abc import ABC, abstractmethod

from trader.account import Account
from trader.api.base_api import PublicAPIBase
from trader.models.position import Position
from trader.models.public_data import TickerData
from trader.notification.notification_service import NotificationService
from trader.report import ReportBase
from trader.trading_strategy import TradingStrategy


class BaseBot(ABC):
    """Classe base para bots de trading e backtesting"""

    def __init__(
        self,
        api: PublicAPIBase,
        strategy: TradingStrategy,
        report: ReportBase | None,
        account: Account,
        notification_service: NotificationService,
    ):
        self.api = api
        self.strategy = strategy
        self.symbol = account.symbol
        self.is_running = False
        self.account = account
        self.report = report
        self.notification_service = notification_service

        self.ticker_history: list[TickerData] = []
        self.last_position: Position | None = None

        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def run(self, **kwargs):
        """Método abstrato para executar o bot"""
        pass

    def process_market_data(self, current_ticker: TickerData):
        self.ticker_history.append(current_ticker)

        position_signal = self.strategy.on_market_refresh(
            current_ticker,
            self.account.get_balance("USDC"),
            self.account.get_position(),
            self.account.position_history,
        )
        order = None
        if position_signal:
            order = self.account.place_order(
                current_ticker.last,
                position_signal.side,
                position_signal.quantity,
            )
        return order

    def stop(self):
        """Para o bot"""
        self.is_running = False
        if self.report:
            self.report.add_ticker_history(self.ticker_history)
            self.report.add_position_history(self.account.position_history)
            self.report.generate_report()
