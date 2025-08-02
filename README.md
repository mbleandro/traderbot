# Trader

Trading bot para Mercado Bitcoin

## Estrutura do Projeto

```
traderbot/
├── data/                    # Dados de trading (CSV) - não versionado
├── charts/                  # Gráficos gerados - não versionado
├── trader/                  # Código principal do bot
├── charts_tools/            # Ferramentas para geração de gráficos
│   ├── generate_charts.py   # Script para gerar gráficos
│   └── CHARTS_README.md     # Documentação dos gráficos
└── pyproject.toml          # Dependências e configuração do projeto
```


## Mapa de Features
| Feature                             | Status |
|-------------------------------------|--------|
| Compra e Venda                      | ✅     |
| Conta Fake                          | ✅     |
| Persistência configurável           | ✅     |
| Geração de gráficos                 | ✅     |
| Subcontas                           | ❌     |
| Backtesting                         | ❌     |
| Relatórios de performance           | ❌     |
| Multiplos bots                      | ❌     |
| Stop loss nativo da API             | ❌     |
| Histórico de posições persistente   | ❌     |
| Orientado a mudança de preço        | ❌     |

## Instalação
```bash
make install
```

## Desenvolvimento
```bash
make install-dev
```

## Gráficos
Para usar as ferramentas de geração de gráficos:
```bash
make install-charts
```

## Uso
```bash
make run
```

### Exemplos de Execução

1. **Execução básica (sem salvar dados):**
```bash
make run ARGS='--strategy=iteration --interval=1 --currency=BTC-BRL --sell_on_iteration=10 --fake'
```

2. **Execução salvando dados em CSV:**
```bash
make run ARGS='--strategy=iteration --interval=1 --currency=BTC-BRL --sell_on_iteration=10 --fake --report=file'
```

## Opções
Para ver as opções e argumentos disponíveis:
```bash
make run ARGS='--help'
```

Para ver as opções de uma estratégia específica:
```bash
make run ARGS='--strategy=<strategy_name> --help'
```

### Opções de Persistência
- `--report=null` (padrão): Não salva dados
- `--report=file`: Salva dados em arquivo CSV na pasta `data/`

## Geração de Gráficos

O bot salva automaticamente os dados de trading em arquivos CSV na pasta `data/`. Para gerar gráficos:

1. **Instalar dependências para gráficos:**
```bash
make install-charts
```

2. **Gerar gráficos:**
```bash
make charts ARGS="trading_data_BTC_BRL.csv"
```

Para mais detalhes, consulte [charts_tools/CHARTS_README.md](charts_tools/CHARTS_README.md).

### Exemplo Completo

```bash
# 1. Instalar dependências
make install
make install-charts

# 2. Executar o bot salvando dados
make run ARGS='--strategy=iteration --interval=1 --currency=BTC-BRL --sell_on_iteration=10 --fake --report=file'

# 3. Gerar gráficos
make charts ARGS="trading_data_BTC_BRL.csv"
```


## Linting e Formatação
Este projeto usa **Ruff** como linter e formatter e **pyright** para verificação de tipos.

```bash
# Verificar código
make lint

# Verificar e corrigir automaticamente
make lint-fix

# Formatar código
make format

# Verificar formatação
make format-check

# Verificar tipos
make typing-check

# Executar lint e format em sequência
make ruff
```

### Configuração

A configuração do Ruff está no arquivo `pyproject.toml` e inclui:

- **Linting**: Regras do pycodestyle, Pyflakes, isort, flake8-bugbear, etc.
- **Formatting**: Estilo similar ao Black (aspas duplas, indentação com espaços)
- **Import sorting**: Organização automática de imports
- **Line length**: 88 caracteres (padrão do Black)

### Hook de Pré-commit

Para garantir que o código seja sempre verificado antes dos commits:

```bash
# Configurar hook de pré-commit automaticamente
make setup-pre-commit
```

Isso configurará um hook que executará automaticamente `ruff check` e `ruff format --check` antes de cada commit, impedindo commits com código mal formatado ou com problemas de linting.
