import argparse
import os
from decimal import Decimal

from dotenv import load_dotenv

from trader.account import Account
from trader.api import FakeMercadoBitcoinPrivateAPI, MercadoBitcoinPublicAPI
from trader.api.private_api import MercadoBitcoinPrivateAPI
from trader.bot import TradingBot
from trader.trading_strategy import PercentualPositionStrategy


def main():
    parser = argparse.ArgumentParser(description="Execute bot")

    # argumentos gerais
    parser.add_argument(
        "--currency", type=str, required=True, help="Moeda a ser negociada"
    )
    parser.add_argument(
        "--strategy", type=str, required=True, help="Estratégia de trading a ser usada"
    )
    parser.add_argument(
        "--interval", type=int, required=True, help="Intervalo de execução em segundos"
    )
    parser.add_argument(
        "--fake", action="store_true", help="Utiliza API privada FAKE (default: False)"
    )

    # argumentos para estratégia percentual-position
    parser.add_argument(
        "--stop-loss-percentual",
        type=float,
        default=0,
        help="Percentual de stop_loss (required if strategy = percentual-position",
    )
    parser.add_argument(
        "--gain-treshold-percentual",
        type=float,
        default=0,
        help="Percentual de threshold de ganho (required if strategy = percentual-position)",
    )

    args = parser.parse_args()
    # Carregar variáveis do arquivo .env
    load_dotenv()

    # Configurar credenciais (use variáveis de ambiente)
    if args.fake:
        account_api = FakeMercadoBitcoinPrivateAPI()
    else:
        api_key = os.getenv("MB_API_KEY")
        api_secret = os.getenv("MB_API_SECRET")
        if not api_key or not api_secret:
            print("Configure as variáveis MB_API_KEY e MB_API_SECRET")
            return
        account_api = MercadoBitcoinPrivateAPI(api_key, api_secret)

    # Inicializar API pública
    public_api = MercadoBitcoinPublicAPI()

    # Configurar estratégia
    if args.strategy == "percentual-position":
        if not args.stop_loss_percentual or not args.gain_treshold_percentual:
            print(
                "Stop loss e gain treshold são argumentos obrigatórios para estratégia percentual-position"
            )
            return
        strategy = PercentualPositionStrategy(
            percentual_stop_loss=Decimal(
                str(round(args.stop_loss_percentual / 100, 2))
            ),
            percentual_gain_treshold=Decimal(
                str(round(args.gain_treshold_percentual / 100, 2))
            ),
        )
    else:
        print("Estratégia não suportada")
        return

    # Configurar conta
    account = Account(account_api, args.currency)

    # Criar e executar bot
    bot = TradingBot(public_api, strategy, account)

    try:
        bot.run(interval=args.interval)
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    main()
