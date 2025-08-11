import time
import traceback

from trader.base_bot import BaseBot
from trader.models.public_data import TickerData


class TradingBot(BaseBot):
    """Bot para trading em tempo real"""

    def get_current_price(self) -> TickerData:
        """Obtém preço atual do par"""
        ticker = self.api.get_ticker(self.symbol)
        return ticker

    def run(self, interval: int = 60):
        """Executa o bot de trading em tempo real"""
        self.is_running = True
        self.trading_logger.log_bot_start(self.symbol)

        while self.is_running:
            try:
                current_ticker = self.get_current_price()
                self.trading_logger.log_price(self.symbol, float(current_ticker.last))

                # Usar método da classe base para processar dados de mercado
                self.process_market_data(current_ticker)

                time.sleep(interval)

            except KeyboardInterrupt:
                self.logger.warning("Bot interrompido pelo usuário")
                self.stop()
            except Exception as ex:
                self.logger.error(f"Erro no loop principal: {str(ex)}")
                traceback.print_exc()
                time.sleep(interval)
