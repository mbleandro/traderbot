from solders.pubkey import Pubkey
from decimal import Decimal
from typing import Dict


class Mint:
    __slots__ = ("mint", "symbol", "decimals")

    def __init__(self, mint: str, symbol: str, decimals: int):
        self.mint = mint
        self.symbol = symbol
        self.decimals = decimals

    @property
    def pubkey(self):
        return Pubkey.from_string(self.mint)

    def ui_to_raw(self, ui_amount: Decimal | int | str) -> int:
        """
        Converte valor em UI (ex: 1.23 USDC) para raw (int)
        """
        ui = Decimal(ui_amount)
        scale = Decimal(10) ** self.decimals
        return int(ui * scale)

    def raw_to_ui(self, raw_amount: int) -> Decimal:
        """
        Converte valor raw (int) para UI
        """
        scale = Decimal(10) ** self.decimals
        return Decimal(raw_amount) / scale

    def __repr__(self) -> str:
        return f"Mint(symbol={self.symbol}, decimals={self.decimals})"


class SolanaMints(dict[str, Mint]):
    def __init__(self, mints: list[Mint]):
        super().__init__({m.mint: m for m in mints})

    def get_by_symbol(self, symbol: str) -> Mint:
        for _, info in self.items():
            if info.symbol == symbol:
                return info
        raise ValueError(f"{symbol=} não existe na lista de mints salvas.")

    def decimals(self, mint: str) -> int:
        return self[mint].decimals

    def ui_to_raw(self, mint: str, ui_amount: Decimal | int | str) -> int:
        return self[mint].ui_to_raw(ui_amount)

    def raw_to_ui(self, mint: str, raw_amount: int) -> Decimal:
        return self[mint].raw_to_ui(raw_amount)

    @staticmethod
    def _normalize_key(key: Pubkey | str) -> str:
        if isinstance(key, Pubkey):
            return str(key)
        return key

    # --- overrides de dict ---
    def __getitem__(self, key: Pubkey | str) -> Mint:
        return super().__getitem__(self._normalize_key(key))

    def __contains__(self, key: Pubkey | str) -> bool:  # ty:ignore[invalid-method-override]
        return super().__contains__(self._normalize_key(key))

    def get(self, key: Pubkey | str, default=None):
        return super().get(self._normalize_key(key), default)


SOLANA_MINTS = SolanaMints(
    [
        Mint("So11111111111111111111111111111111111111112", "SOL", 9),
        Mint("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDC", 6),
        Mint("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "USDT", 6),
        Mint("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "BONK", 5),
        Mint("JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "JUP", 6),
        Mint("pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn", "PUMP", 6),
        Mint("2Dyzu65QA9zdX1UeE7Gx71k7fiwyUK6sZdrvJ7auq5wm", "TURBO", 8),
    ]
)
