import sys

from dotenv import load_dotenv

from trader import NotImplementedStrategy, get_strategy_cls
from trader.account import Account
from trader.api import FakeMercadoBitcoinPrivateAPI, MercadoBitcoinPublicAPI
from trader.api.private_api import MercadoBitcoinPrivateAPI
from trader.bot import TradingBot


def main(
    currency: str,
    strategy: str,
    interval: int,
    fake: bool,
    api_key: str | None = None,
    api_secret: str | None = None,
    **strategy_args,
):
    """
    Função principal do trading bot.

    Args:
        --help              Mostra mensagem de ajuda
        --currency          Par de moedas para negociar (ex: 'BTC-BRL')
        --strategy_name     Nome da estratégia de trading a ser utilizada
        --interval          Intervalo em segundos entre verificações de mercado
        --fake              Se True, usa API fake para simulação; se False, usa API real
        --api_key           Chave da API do Mercado Bitcoin (obrigatória se fake=False)
        --api_secret        Segredo da API do Mercado Bitcoin (obrigatório se fake=False)
        **strategy_args     Argumentos específicos da estratégia selecionada (execute main.py --strategy_name=<nome> --help para mais informações)
    """
    # Configurar credenciais (use variáveis de ambiente)
    if fake:
        account_api = FakeMercadoBitcoinPrivateAPI()
    else:
        if not api_key or not api_secret:
            print("Argumentos api_key e api_secret são obrigatórios se fake=False")
            return
        account_api = MercadoBitcoinPrivateAPI(api_key, api_secret)

    # Inicializar API pública
    public_api = MercadoBitcoinPublicAPI()

    # Configurar estratégia
    try:
        strategy_cls = get_strategy_cls(strategy)
    except NotImplementedStrategy:
        print(f"Estratégia {strategy} não suportada")
        return

    try:
        strategy_obj = strategy_cls(**strategy_args)
    except ValueError as e:
        print(f"Erro ao configurar estratégia: {e}")
        return
    # Configurar conta
    account = Account(account_api, currency)

    # Criar e executar bot
    bot = TradingBot(public_api, strategy_obj, account)

    try:
        bot.run(interval=int(interval))
    except KeyboardInterrupt:
        bot.stop()


def parse_kwargs(argv):
    kwargs = {}

    for arg in argv:
        if arg.startswith("--"):
            key_value = arg[2:].split("=", 1)
            if len(key_value) == 2:
                key, value = key_value
                kwargs[key] = value
            else:
                kwargs[key_value[0]] = True  # flag booleana

    return kwargs


def _help(strategy: str | None = None, **kwargs):
    if strategy:
        try:
            strategy_cls = get_strategy_cls(strategy)
        except NotImplementedStrategy:
            print(f"Estratégia {strategy} não suportada")
            return
        return print(strategy_cls.__doc__)
    else:
        return print(main.__doc__)


if __name__ == "__main__":
    kwargs = parse_kwargs(sys.argv[1:])
    load_dotenv()
    print("args = ", kwargs)
    if kwargs.get("help"):
        _help(**kwargs)
    else:
        main(**kwargs)
