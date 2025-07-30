import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .account import Position


class BasePersistence:
    """Classe base para persistência de dados do trading bot"""

    def __init__(self, currency: str = "BTC-BRL"):
        pass

    def save_iteration_data(
        self,
        timestamp: datetime,
        symbol: str,
        current_price: Decimal,
        position: Optional[Position],
        unrealized_pnl: Decimal,
        realized_pnl: Decimal,
        position_signal: Optional[str] = None,
    ) -> None:
        """Salva dados de uma iteração do bot"""
        raise NotImplementedError


class NullPersistence(BasePersistence):
    """Implementação de persistência que não salva dados (padrão)"""

    def save_iteration_data(
        self,
        timestamp: datetime,  # noqa: ARG002
        symbol: str,  # noqa: ARG002
        current_price: Decimal,  # noqa: ARG002
        position: Optional[Position],  # noqa: ARG002
        unrealized_pnl: Decimal,  # noqa: ARG002
        realized_pnl: Decimal,  # noqa: ARG002
        position_signal: Optional[str] = None,  # noqa: ARG002
    ) -> None:
        """Não salva dados - implementação nula"""
        pass


class InFilePersistence(BasePersistence):
    """Implementação de persistência em arquivo CSV"""

    def __init__(self, currency: str = "BTC-BRL"):
        # Criar diretório de dados se não existir
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)

        # Configurar nome do arquivo baseado na moeda
        filename = f"trading_data_{currency.replace('-', '_')}.csv"
        self.filename = os.path.join(data_dir, filename)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Garante que o arquivo existe e tem cabeçalho"""
        if not os.path.exists(self.filename):
            with open(self.filename, "w") as f:
                f.write(
                    "timestamp,symbol,price,position_side,position_quantity,position_entry_price,unrealized_pnl,realized_pnl,signal\n"
                )

    def save_iteration_data(
        self,
        timestamp: datetime,
        symbol: str,
        current_price: Decimal,
        position: Optional[Position],
        unrealized_pnl: Decimal,
        realized_pnl: Decimal,
        position_signal: Optional[str] = None,
    ) -> None:
        """Salva dados da iteração em arquivo CSV"""
        position_side = position.side if position else ""
        position_quantity = position.quantity if position else Decimal("0")
        position_entry_price = position.entry_price if position else Decimal("0")
        signal = position_signal or ""

        # Arredondar valores monetários para 2 casas decimais
        current_price_rounded = round(float(current_price), 2)
        position_entry_price_rounded = round(float(position_entry_price), 2)
        unrealized_pnl_rounded = round(float(unrealized_pnl), 2)
        realized_pnl_rounded = round(float(realized_pnl), 2)

        line = (
            f"{timestamp.isoformat()},"
            f"{symbol},"
            f"{current_price_rounded:.2f},"
            f"{position_side},"
            f"{position_quantity},"
            f"{position_entry_price_rounded:.2f},"
            f"{unrealized_pnl_rounded:.2f},"
            f"{realized_pnl_rounded:.2f},"
            f"{signal}\n"
        )

        with open(self.filename, "a") as f:
            f.write(line)


# Mapeamento de persistências disponíveis
PERSISTENCE_CLASSES = {
    "null": NullPersistence,
    "file": InFilePersistence,
}


def get_persistence_cls(persistence_name: str):
    """Retorna a classe de persistência baseada no nome"""
    if persistence_name not in PERSISTENCE_CLASSES:
        available = ", ".join(PERSISTENCE_CLASSES.keys())
        raise ValueError(
            f"Persistência '{persistence_name}' não encontrada. Disponíveis: {available}"
        )

    return PERSISTENCE_CLASSES[persistence_name]


def list_persistence_options() -> list[str]:
    """Retorna lista de opções de persistência disponíveis"""
    return list(PERSISTENCE_CLASSES.keys())
