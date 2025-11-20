import typer

from trader import get_strategy_cls
from trader.account import Account
from trader.api import (
    FakeJupiterPrivateAPI,
    FakeMercadoBitcoinPrivateAPI,
    JupiterPrivateAPIAdapter,
    JupiterPublicAPIAdapter,
    MercadoBitcoinPrivateAPI,
    MercadoBitcoinPublicAPI,
)
from trader.bot import BacktestingBot, BaseBot, TradingBot, WebsocketTradingBot
from trader.notification.notification_service import (
    NullNotificationService,
    TelegramNotificationService,
)
from trader.report import ReportTerminal

app = typer.Typer()


def get_api_instances(
    api_type: str,
    api_key: str | None = None,
    api_secret: str | None = None,
    wallet_key: str | None = None,
):
    """
    Retorna instâncias das APIs pública e privada baseado no tipo.

    Args:
        api_type: 'mercadobitcoin' ou 'jupiter'
        api_key: Chave da API (para Mercado Bitcoin)
        api_secret: Secret da API (para Mercado Bitcoin)
        wallet_key: Chave pública da wallet (para Jupiter)

    Returns:
        Tuple (public_api, private_api)
    """
    if api_type == "mercadobitcoin":
        public_api = MercadoBitcoinPublicAPI()
        if api_key and api_secret:
            private_api = MercadoBitcoinPrivateAPI(api_key, api_secret)
        else:
            private_api = FakeMercadoBitcoinPrivateAPI()
        return public_api, private_api

    elif api_type == "jupiter":
        public_api = JupiterPublicAPIAdapter(use_pro=False)
        if wallet_key:
            private_api = JupiterPrivateAPIAdapter(wallet_public_key=wallet_key)
        else:
            private_api = FakeJupiterPrivateAPI()
        return public_api, private_api

    else:
        raise ValueError(
            f"API type '{api_type}' não suportado. Use 'mercadobitcoin' ou 'jupiter'"
        )


def _get_notification_svc(
    notification_service: str, notification_args: str | None = None
):
    if notification_service == "telegram":
        if not notification_args:
            raise ValueError(
                "Para notificação via Telegram, é necessário informar os argumentos chat_id e token"
            )
        args = parse_kwargs(notification_args.split())
        return TelegramNotificationService(args["chat_id"], args["token"])
    return NullNotificationService()


@app.command()
def run(
    currency: str = typer.Argument(
        "BTC-BRL", help="The trading symbol (ex: BTC-BRL for MB, SOL-USDC for Jupiter)"
    ),
    strategy: str = typer.Argument(..., help="The trading strategy to use"),
    interval: int = typer.Argument(..., help="Intervalo de execução em segundos"),
    api: str = typer.Option(
        "mercadobitcoin", help="API to use: 'mercadobitcoin' or 'jupiter'"
    ),
    api_key: str | None = typer.Option(..., help="API key (para Mercado Bitcoin)"),
    api_secret: str | None = typer.Option(
        ..., help="API secret (para Mercado Bitcoin)"
    ),
    wallet_key: str | None = typer.Option(
        ..., help="Chave pública da wallet (para Jupiter)"
    ),
    websocket: bool = typer.Option(
        False, help="Use WebSocket para atualização de preços"
    ),
    notification_service: str = typer.Option(
        "null", help="Serviço de notificação: 'telegram' ou 'null'"
    ),
    notification_args: str | None = typer.Option(
        ..., help="Argumentos do serviço de notificação"
    ),
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    """
    Executa o bot em modo produção.

    Exemplos:
        # Mercado Bitcoin
        uv run python main.py run BTC-BRL dynamic_target 60 --api mercadobitcoin --api-key=KEY --api-secret=SECRET 'ema_period=20'

        # Jupiter
        uv run python main.py run SOL-USDC dynamic_target 60 --api jupiter --wallet-key=WALLET_PUBLIC_KEY 'ema_period=20'
    """
    # Validação de credenciais
    if api == "mercadobitcoin":
        if not api_key or not api_secret:
            raise ValueError(
                "Para Mercado Bitcoin, api_key e api_secret são obrigatórios"
            )
    elif api == "jupiter":
        if not wallet_key:
            raise ValueError("Para Jupiter, wallet_key é obrigatório")

    public_api, private_api = get_api_instances(api, api_key, api_secret, wallet_key)
    account = Account(private_api, currency)
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    report_obj = ReportTerminal()
    notification_svc = _get_notification_svc(notification_service, notification_args)

    if websocket:
        bot = WebsocketTradingBot(
            public_api, strategy_obj, report_obj, account, notification_svc
        )
    else:
        bot = TradingBot(
            public_api, strategy_obj, report_obj, account, notification_svc
        )
    run_bot(bot, interval)


@app.command()
def backtest(
    currency: str = typer.Argument(
        "BTC-BRL", help="The trading symbol (ex: BTC-BRL for MB, SOL-USDC for Jupiter)"
    ),
    strategy: str = typer.Argument(..., help="The trading strategy to use"),
    interval: int = typer.Argument(..., help="Intervalo de execução em segundos"),
    start_datetime: str | None = typer.Argument(..., help="Data e hora de início"),
    end_datetime: str | None = typer.Argument(..., help="Data e hora de fim"),
    api: str = typer.Option(
        "mercadobitcoin", help="API to use: 'mercadobitcoin' or 'jupiter'"
    ),
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    """
    Executa backtest com dados históricos.

    NOTA: Jupiter não fornece dados históricos de candles.
    Para backtesting com Jupiter, use dados de provedores externos.

    Exemplos:
        # Mercado Bitcoin
        uv run python main.py backtest BTC-BRL dynamic_target 3600 2025-06-01 2025-06-15 --api mercadobitcoin 'ema_period=20'
    """
    public_api, private_api = get_api_instances(api)
    account = Account(private_api, currency)
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
    api: str = typer.Option(
        "mercadobitcoin", help="API to use: 'mercadobitcoin' or 'jupiter'"
    ),
    websocket: bool = typer.Option(
        False, help="Use WebSocket para atualização de preços"
    ),
    notification_service: str = typer.Option(
        "null", help="Serviço de notificação: 'telegram' ou 'null'"
    ),
    notification_args: str | None = typer.Option(
        ..., help="Argumentos do serviço de notificação"
    ),
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    """
    Executa o bot em modo fake (simulação com dados reais).

    Exemplos:
        # Mercado Bitcoin
        uv run python main.py fake BTC-BRL dynamic_target 60 --api mercadobitcoin 'ema_period=20'

        # Jupiter
        uv run python main.py fake SOL-USDC dynamic_target 60 --api jupiter 'ema_period=20'
    """
    public_api, private_api = get_api_instances(api)
    account = Account(private_api, currency)
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    report_obj = ReportTerminal()

    notification_svc = _get_notification_svc(notification_service, notification_args)

    if websocket:
        bot = WebsocketTradingBot(
            public_api, strategy_obj, report_obj, account, notification_svc
        )
    else:
        bot = TradingBot(
            public_api, strategy_obj, report_obj, account, notification_svc
        )
    run_bot(bot, interval)


def parse_kwargs(argv: list[str]) -> dict[str, str]:
    kwargs = {}

    for arg in argv:
        key_value = arg.split("=", 1)
        if len(key_value) == 2:
            key, value = key_value
            kwargs[key] = value
        else:
            kwargs[key_value[0]] = True  # flag booleana

    return kwargs


def _get_strategy_obj(strategy: str, strategy_args: str | None = None):
    strategy_cls = get_strategy_cls(strategy)
    try:
        if strategy_args:
            args = parse_kwargs(strategy_args.split())
        return strategy_cls(**args)
    except ValueError as ex:
        raise Exception(f"Erro ao configurar estratégia: {ex}") from ex


def run_bot(bot: BaseBot, interval: int):
    try:
        bot.run(interval=int(interval))
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    app()
