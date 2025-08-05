import traceback
from datetime import datetime
from decimal import Decimal

from trader.base_bot import BaseBot
from trader.colored_logger import log_progress_bar
from trader.models.public_data import Candles


class BacktestingBot(BaseBot):
    """Bot para backtesting com dados históricos"""

    def __init__(self, api, strategy, report, account):
        # Desabilitar logging para backtesting
        super().__init__(api, strategy, report, account, enable_logging=False)

    INTERVAL_TO_RESOLUTION = {
        60: "1m",
        900: "15m",
        3600: "1h",
        10800: "3h",
        86400: "1d",
        604800: "1w",
        2592000: "1M",
    }

    def get_historical_prices(
        self, start_date: datetime, end_date: datetime, resolution: str
    ) -> Candles:
        return self.api.get_candles(self.symbol, start_date, end_date, resolution)

    def run(self, start_date: datetime, end_date: datetime, interval: int = 60):
        """Executa o backtesting com dados históricos"""
        self.is_running = True

        candles = self.get_historical_prices(
            start_date, end_date, self.INTERVAL_TO_RESOLUTION[interval]
        )

        total_candles = len(candles.c)
        print(f"🚀 Iniciando backtesting com {total_candles} candles...")

        # Inicializar barra de progresso
        log_progress_bar(0.0, overwrite=False)

        for index, str_price in enumerate(candles.c):
            current_price = Decimal(str_price)
            try:
                timestamp = datetime.fromtimestamp(candles.t[index])

                # Usar método da classe base para processar dados de mercado
                self.process_market_data(current_price, timestamp)

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
