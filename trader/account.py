from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum, auto
from typing import List, Optional

from .api import MercadoBitcoinPrivateAPIBase
from .colored_logger import get_trading_logger


class Sides(StrEnum):
    LONG = auto()
    SHORT = auto()


@dataclass
class Position:
    """Representa uma posição de trading"""

    order_id: str
    symbol: str
    side: Sides
    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime
    current_price: Optional[Decimal] = None

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calcula o PnL não realizado"""
        if self.current_price is None:
            return Decimal("0.0")

        if self.side == Sides.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:  # short
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def is_profitable(self) -> bool:
        """Verifica se a posição está lucrativa"""
        return self.unrealized_pnl > 0


@dataclass
class PositionHistory:
    """Representa o histórico de uma posição fechada"""

    entry_order_id: str
    exit_order_id: str
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    realized_pnl: Decimal


class Account:
    """Classe responsável por gerenciar balanço, posições e execução de ordens"""

    def __init__(self, api: MercadoBitcoinPrivateAPIBase, symbol: str = "BTC-BRL"):
        self.api = api
        self.symbol = symbol
        self.account_id = self.get_api_account_id("BRL")
        self.current_position: Optional[Position] = None
        self.position_history: List[PositionHistory] = []

        # Configurar logging colorido
        self.trading_logger = get_trading_logger("Account")
        self.logger = self.trading_logger.get_logger()

    def get_api_account_id(self, currency: str) -> str:
        accounts = self.api.get_accounts()
        for account in accounts:
            if account.currency == currency:
                return account.id
        raise Exception(f"Conta para {currency} não encontrada")

    def get_balance(self, currency: str) -> Decimal:
        """Obtém saldo de uma moeda específica"""
        balances = self.api.get_account_balance(self.account_id)
        for balance in balances:
            if balance.symbol == currency:
                return balance.available
        return Decimal("0.0")

    def get_position(self) -> Position | None:
        """Retorna a posição atual"""
        return self.current_position

    def can_buy(self) -> bool:
        """Verifica se é possível executar uma compra"""
        # Não pode comprar se já tem posição long
        if self.current_position is not None and self.current_position.side == "long":
            return False
        # Verifica se tem saldo suficiente em BRL
        brl_balance = self.get_balance("BRL")
        return brl_balance > Decimal("50.0")  # Mínimo para operar

    def can_sell(self) -> bool:
        """Verifica se é possível executar uma venda"""
        # Só pode vender se tem posição long
        if self.current_position is None or self.current_position.side != "long":
            return False

        # Verifica se tem BTC suficiente
        btc_balance = self.get_balance("BTC")
        return btc_balance > Decimal("0.00001")  # Mínimo para vender

    def execute_buy_order(self, price: Decimal, quantity_calculator) -> bool:
        """Executa ordem de compra"""
        if not self.can_buy():
            self.trading_logger.log_warning("Não é possível executar compra no momento")
            return False

        balance = self.get_balance("BRL")

        quantity_str = quantity_calculator(balance, price)
        quantity = Decimal(quantity_str)

        try:
            order_id = self.api.place_order(
                account_id=self.account_id,
                symbol=self.symbol,
                side="buy",
                type_order="market",
                quantity=quantity_str,
            )

            # Criar nova posição
            self.current_position = Position(
                order_id=order_id,
                symbol=self.symbol,
                side=Sides.LONG,
                quantity=quantity,
                entry_price=price,
                entry_time=datetime.now(),
                current_price=price,
            )

            return True

        except Exception as e:
            self.trading_logger.log_error("Erro ao executar compra", e)
            return False

    def execute_sell_order(self) -> bool:
        """Executa ordem de venda"""
        if not self.can_sell():
            self.trading_logger.log_warning("Não é possível executar venda no momento")
            return False

        btc_balance = self.get_balance("BTC")

        try:
            order_id = self.api.place_order(
                account_id=self.account_id,
                symbol=self.symbol,
                side="sell",
                type_order="market",
                quantity=f"{btc_balance:.8f}",
            )

            # Calcular PnL e adicionar ao histórico
            if self.current_position:
                current_price = self.current_position.current_price or Decimal("0.0")
                realized_pnl = (
                    current_price - self.current_position.entry_price
                ) * self.current_position.quantity
                position_history = PositionHistory(
                    entry_order_id=self.current_position.order_id,
                    exit_order_id=order_id,
                    symbol=self.current_position.symbol,
                    side=self.current_position.side,
                    quantity=self.current_position.quantity,
                    entry_price=self.current_position.entry_price,
                    exit_price=current_price,
                    entry_time=self.current_position.entry_time,
                    exit_time=datetime.now(),
                    realized_pnl=realized_pnl,
                )

                self.position_history.append(position_history)

                # Log colorido baseado no resultado
                if realized_pnl > 0:
                    self.logger.info(
                        f"💰 Posição fechada com LUCRO - PnL: R$ {realized_pnl:.2f}"
                    )
                else:
                    self.logger.info(
                        f"💸 Posição fechada com PREJUÍZO - PnL: R$ {realized_pnl:.2f}"
                    )

            # Limpar posição atual
            self.current_position = None

            return True

        except Exception as e:
            self.trading_logger.log_error("Erro ao executar venda", e)
            return False

    def update_position_price(self, current_price: Decimal):
        """Atualiza o preço atual da posição"""
        if self.current_position:
            self.current_position.current_price = current_price

    def get_total_realized_pnl(self) -> Decimal:
        """Retorna o PnL total realizado"""
        return Decimal(str(sum(pos.realized_pnl for pos in self.position_history)))

    def get_unrealized_pnl(self) -> Decimal:
        """Retorna o PnL não realizado da posição atual"""
        if self.current_position:
            return self.current_position.unrealized_pnl
        return Decimal("0.0")
