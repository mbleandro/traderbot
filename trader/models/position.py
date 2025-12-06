from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum, auto
from typing import Optional

from trader.models.order import Order


class PositionType(StrEnum):
    LONG = auto()
    SHORT = auto()


@dataclass
class Position:
    """Representa uma posição de trading"""

    type: PositionType
    entry_order: Order
    exit_order: Optional[Order]

    def unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calcula o PnL não realizado"""
        return (current_price - self.entry_order.price) * self.entry_order.quantity

    @property
    def realized_pnl(self) -> Decimal:
        """Calcula o PnL realizado"""
        if self.exit_order:
            return (
                self.exit_order.price - self.entry_order.price
            ) * self.entry_order.quantity
        return Decimal("0.0")

    def __eq__(self, value):
        return (
            value
            and self.entry_order == value.entry_order
            and self.exit_order == value.exit_order
        )

    def to_dict(self):
        return {
            "type": self.type.value,
            "entry_price": self.entry_order.price,
            "entry_quantity": self.entry_order.quantity,
            "exit_price": self.exit_order.price if self.exit_order else None,
            "exit_quantity": self.exit_order.quantity if self.exit_order else None,
            "entry_timestamp": self.entry_order.timestamp,
            "exit_timestamp": self.exit_order.timestamp if self.exit_order else None,
            "realized_pnl": self.realized_pnl,
            "order_id": self.entry_order.order_id,
        }
