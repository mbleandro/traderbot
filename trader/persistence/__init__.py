from abc import ABC, abstractmethod

from trader.models.log import PriceLog
from trader.models.position import Position


class Persistence(ABC):
    async def __init__(self, execution_id: str):
        self.execution_id = execution_id
        logs = self.get_logs(execution_id)
        if logs:
            raise Exception(f"Execution ID {execution_id} already exists")

    @abstractmethod
    async def save_position(self, data: Position) -> bool:
        pass

    @abstractmethod
    async def save_log(self, log: PriceLog) -> dict:
        pass

    @abstractmethod
    async def get_position(self, execution_id: str) -> dict:
        pass

    @abstractmethod
    async def get_logs(self, execution_id: str) -> list[dict]:
        pass


class NullPersistence(Persistence):
    async def save_position(self, data: Position) -> bool:
        return True

    async def save_log(self, log: PriceLog) -> bool:
        return True

    async def get_position(self) -> Position | None:
        return None

    async def get_logs(self) -> list[PriceLog]:
        return []
