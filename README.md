# Trader

Trading bot

## Instalação
```bash
uv sync
```

## Desenvolvimento
```bash
uv sync --extra dev
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

### Hook de Pré-commit

Para garantir que o código seja sempre verificado antes dos commits:

```bash
# Configurar hook de pré-commit automaticamente
make setup-pre-commit
```

Isso configurará um hook que executará automaticamente `ruff check` e `ruff format --check` antes de cada commit, impedindo commits com código mal formatado ou com problemas de linting.
