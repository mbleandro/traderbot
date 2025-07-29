import argparse
import os

from dotenv import load_dotenv

from trader.account import Account
from trader.api import FakeMercadoBitcoinPrivateAPI, MercadoBitcoinPublicAPI
from trader.api.private_api import MercadoBitcoinPrivateAPI
from trader.bot import TradingBot
from trader.trading_strategy import IterationStrategy


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

    # argumentos para estratégia 'iteration'
    parser.add_argument(
        "--sell-on-iteration",
        type=float,
        default=0,
        help="Número de iterações para vender (required if strategy = iteration)",
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
    if args.strategy == "iteration":
        if not args.sell_on_iteration:
            print(
                "sell-on-iteration é um argumento obrigatório para estratégia 'iteration'"
            )
            return
        strategy = IterationStrategy(sell_on_iteration=10)
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
