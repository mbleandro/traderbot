from typing import Literal

import typer

from trader import get_strategy_cls
from trader.account import Account
from trader.bot import BaseBot, WebsocketTradingBot
from trader.notification.notification_service import (
    NullNotificationService,
    TelegramNotificationService,
)
from trader.providers import (
    FakeJupiterPrivateAPI,
    JupiterPrivateAPI,
    JupiterPublicAPIAdapter,
)
from trader.providers.jupiter.jupiter_adapter import DryJupiterPrivateAPI

app = typer.Typer()


def get_api_instances(
    wallet_key: str | None = None,
    run_mode: Literal["real", "fake", "dry"] = "real",
):
    """
    Retorna instância das API privada baseado no tipo.

    Args:
        wallet_key: Chave pública da wallet

    Returns:
        private_api
    """
    if run_mode == "fake":
        return FakeJupiterPrivateAPI()

    assert wallet_key is not None, "wallet_key é obrigatório para modos real e dry"
    if run_mode == "dry":
        return DryJupiterPrivateAPI(wallet_public_key=wallet_key)
    if run_mode == "real":
        return JupiterPrivateAPI(wallet_public_key=wallet_key)


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
    api: str = typer.Option("jupiter", help="API to use: 'jupiter'"),
    wallet_key: str | None = typer.Option(
        ..., help="Chave pública da wallet (para Jupiter)"
    ),
    websocket: bool = typer.Option(
        True, help="Use WebSocket para atualização de preços"
    ),
    dry: bool = typer.Option(
        False, help="Se True, executa em modo dry-run (sem realizar a transacão final)"
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
        # Jupiter
        uv run python main.py run SOL-USDC dynamic_target 60 --api jupiter --wallet-key=WALLET_PUBLIC_KEY 'ema_period=20'
    """
    # Validação de credenciais
    if not api == "jupiter":
        raise ValueError(f"API type '{api}' não suportado. Use 'jupiter'")

    if api == "jupiter":
        if not wallet_key:
            raise ValueError("Para Jupiter, wallet_key é obrigatório")

    public_api = JupiterPublicAPIAdapter(use_pro=False)
    private_api = get_api_instances(wallet_key, run_mode="real" if not dry else "dry")
    account = Account(private_api, currency)
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    notification_svc = _get_notification_svc(notification_service, notification_args)

    bot = WebsocketTradingBot(public_api, strategy_obj, account, notification_svc)
    run_bot(bot)


@app.command()
def fake(
    currency: str,
    strategy: str,
    interval: int,
    api: str = typer.Option("jupiter", help="API to use: 'jupiter'"),
    websocket: bool = typer.Option(
        True, help="Use WebSocket para atualização de preços"
    ),
    notification_service: str = typer.Option(
        "null", help="Serviço de notificação: 'telegram' ou 'null'"
    ),
    notification_args: str | None = typer.Option(
        None, help="Argumentos do serviço de notificação"
    ),
    strategy_args: str | None = typer.Argument(..., help="Argumentos da estratégia"),
):
    """
    Executa o bot em modo fake (simulação com dados reais).

    Exemplos:
        # Jupiter
        uv run python main.py fake SOL-USDC dynamic_target 60 --api jupiter 'ema_period=20'
    """
    public_api = JupiterPublicAPIAdapter(use_pro=False)
    private_api = get_api_instances(None, "fake")
    account = Account(private_api, currency)
    strategy_obj = _get_strategy_obj(strategy, strategy_args)
    notification_svc = _get_notification_svc(notification_service, notification_args)

    bot = WebsocketTradingBot(public_api, strategy_obj, account, notification_svc)
    run_bot(bot)


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


def run_bot(bot: BaseBot):
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    app()
