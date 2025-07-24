# Trader

Trading bot para Mercado Bitcoin

## Instalação
```bash
make install
```


## Desenvolvimento
```bash
make install-dev
```

## Uso
```bash
make run
```

## Linting e Formatação
Este projeto usa **Ruff** como linter e formatter.

```bash
# Verificar código
make lint

# Verificar e corrigir automaticamente
make lint-fix

# Formatar código
make format

# Verificar formatação
make format-check

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
