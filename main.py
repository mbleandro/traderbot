import typer

from trader import get_strategy_cls
from trader.account import Account
from trader.api import FakeMercadoBitcoinPrivateAPI, MercadoBitcoinPublicAPI
from trader.api.private_api import MercadoBitcoinPrivateAPI
from trader.bot import BacktestingBot, BaseBot, TradingBot
from trader.report import ReportTerminal

app = typer.Typer()


@app.command()
def run(
    currency: str = typer.Argument("BTC-BRL", help="The trading symbol (ex: BTC-BRL)"),
    strategy: str = typer.Argument(..., help="The trading strategy to use"),
    interval: int = typer.Argument(..., help="Intervalo de execução em segundos"),
    api_key: str | None = None,
    api_secret: str | None = None,
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    # Configurar credenciais (use variáveis de ambiente)
    if not api_key or not api_secret:
        raise ValueError("Argumentos api_key e api_secret são obrigatórios")

    account = Account(MercadoBitcoinPrivateAPI(api_key, api_secret), currency)
    public_api = MercadoBitcoinPublicAPI()
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    report_obj = ReportTerminal()

    bot = TradingBot(public_api, strategy_obj, report_obj, account)
    run_bot(bot, interval)


@app.command()
def backtest(
    currency: str = typer.Argument("BTC-BRL", help="The trading symbol (ex: BTC-BRL)"),
    strategy: str = typer.Argument(..., help="The trading strategy to use"),
    interval: int = typer.Argument(..., help="Intervalo de execução em segundos"),
    start_datetime: str | None = typer.Argument(..., help="Data e hora de início"),
    end_datetime: str | None = typer.Argument(..., help="Data e hora de fim"),
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    account = Account(FakeMercadoBitcoinPrivateAPI(), currency)
    public_api = MercadoBitcoinPublicAPI()
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    report_obj = ReportTerminal()

    bot = BacktestingBot(
        public_api, strategy_obj, report_obj, account, start_datetime, end_datetime
    )
    run_bot(bot, interval)


@app.command()
def fake(
    currency: str,
    strategy: str,
    interval: int,
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    public_api = MercadoBitcoinPublicAPI()
    account = Account(FakeMercadoBitcoinPrivateAPI(), currency)
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    report_obj = ReportTerminal()

    bot = TradingBot(public_api, strategy_obj, report_obj, account)
    run_bot(bot, interval)


def _get_strategy_obj(strategy: str, strategy_args):
    def parse_kwargs(argv):
        kwargs = {}

        for arg in argv:
            key_value = arg.split("=", 1)
            if len(key_value) == 2:
                key, value = key_value
                kwargs[key] = value
            else:
                kwargs[key_value[0]] = True  # flag booleana

        return kwargs

    strategy_cls = get_strategy_cls(strategy)
    try:
        if strategy_args:
            strategy_args = parse_kwargs(strategy_args.split())
        return strategy_cls(**strategy_args)
    except ValueError as ex:
        raise Exception(f"Erro ao configurar estratégia: {ex}") from ex


def run_bot(bot: BaseBot, interval: int):
    try:
        bot.run(interval=int(interval))
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    app()
