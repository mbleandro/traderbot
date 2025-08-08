import traceback
from datetime import datetime

from trader.api.public_api import IntervalResolution
from trader.base_bot import BaseBot
from trader.colored_logger import log_progress_bar
from trader.models.public_data import Candles


class BacktestingBot(BaseBot):
    """Bot para backtesting com dados históricos"""

    def __init__(self, api, strategy, report, account, start_datetime, end_datetime):
        # Desabilitar logging para backtesting
        super().__init__(api, strategy, report, account, enable_logging=False)
        self.start_date_datetime = datetime.fromisoformat(start_datetime)
        self.end_date_datetime = datetime.fromisoformat(end_datetime)

    def get_historical_prices(self, resolution: str) -> Candles:
        return self.api.get_candles(
            self.symbol, self.start_date_datetime, self.end_date_datetime, resolution
        )

    def run(self, interval: int = 60):
        """Executa o backtesting com dados históricos"""

        candles = self.get_historical_prices(IntervalResolution.to_resolution(interval))
        self.strategy.initialize_historical_data(
            interval, self.start_date_datetime, self.symbol, self.api
        )

        total_candles = len(candles.close)
        print(f"🚀 Iniciando backtesting com {total_candles} candles...")

        # Inicializar barra de progresso
        log_progress_bar(0.0, overwrite=False)

        for index in range(len(candles.close)):
            current_ticker = candles.get_ticker_from_index(index)
            try:
                timestamp = datetime.fromtimestamp(candles.timestamp[index])

                # Usar método da classe base para processar dados de mercado
                self.process_market_data(current_ticker, timestamp)

                # Atualizar barra de progresso
                progress_percent = ((index + 1) / total_candles) * 100
                log_progress_bar(progress_percent)

            except KeyboardInterrupt:
                print("\n🛑 Bot interrompido pelo usuário")
                self.stop()
                return
            except Exception as e:
                print(f"❌ Erro no loop principal: {str(e)}")
                traceback.print_exc()

        print("\n📈 Simulação finalizada")
        self.stop()
