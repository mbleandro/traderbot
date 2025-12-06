from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PriceLog:
    coin_symbol: str
    price: Decimal
    pnl: Decimal | None = None

    def to_dict(self):
        return {
            "coin_symbol": self.coin_symbol,
            "price": self.price,
            "pnl": self.pnl,
        }
