import os
import time

from motor.motor_asyncio import AsyncIOMotorClient as MongoClient

from trader.models.log import PriceLog
from trader.models.order import Order, OrderSide
from trader.models.position import Position, PositionType
from trader.persistence import Persistence


class MongoPersistence(Persistence):
    async def __init__(self, execution_id: str):
        await super().__init__(execution_id)
        db_url = os.getenv("MONGO_URL")
        assert db_url, "MONGO_URL não definida"
        self.client = MongoClient(db_url)
        self.db = self.client["trader"]

        if "positions" not in await self.db.list_collection_names():
            await self.db.create_collection("positions")
        self.positions = self.db["positions"]

        if "logs" not in await self.db.list_collection_names():
            await self.db.create_collection("logs")
        self.logs = self.db["logs"]

    async def save_position(self, data: Position) -> None:
        await self.positions.insert_one(
            {
                "execution_id": self.execution_id,
                "timestamp": time.time(),
                **data.to_dict(),
            }
        )

    async def save_log(self, log: PriceLog) -> None:
        await self.logs.insert_one(
            {
                "execution_id": self.execution_id,
                "timestamp": time.time(),
                **log.to_dict(),
            }
        )

    async def get_position(self) -> Position | None:
        position = await self.positions.find_one(
            {"execution_id": self.execution_id}, sort=[("timestamp", -1)]
        )
        if not position:
            return None
        return Position(
            type=PositionType(position["type"]),
            entry_order=Order(
                order_id=position["entry_order"]["order_id"],
                symbol=position["entry_order"]["symbol"],
                quantity=position["entry_order"]["quantity"],
                price=position["entry_order"]["price"],
                side=OrderSide(position["entry_order"]["side"]),
                timestamp=position["entry_order"]["timestamp"],
            ),
            exit_order=Order(
                order_id=position["exit_order"]["order_id"],
                symbol=position["exit_order"]["symbol"],
                quantity=position["exit_order"]["quantity"],
                price=position["exit_order"]["price"],
                side=OrderSide(position["exit_order"]["side"]),
                timestamp=position["exit_order"]["timestamp"],
            )
            if position["exit_order"]
            else None,
        )

    async def get_logs(self) -> list[PriceLog]:
        logs = await self.logs.find({"execution_id": self.execution_id}).to_list(None)
        return [
            PriceLog(coin_symbol=log["coin_symbol"], price=log["price"], pnl=log["pnl"])
            for log in logs
        ]
