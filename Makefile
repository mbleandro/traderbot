.PHONY: test test-verbose test-coverage install install-dev clean build help

# Variáveis
PYTHON := python
UV := uv
PYTEST := pytest

help: ## Mostra esta mensagem de ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instala as dependências do projeto
	$(UV) sync

install-dev: ## Instala as dependências de desenvolvimento
	$(UV) sync --extra dev

test: ## Executa os testes
	$(UV) run $(PYTEST) .

build: ## Constrói o pacote
	$(UV) build

clean: ## Remove arquivos temporários e cache
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +

run: ## Executa o bot principal
	$(UV) run $(PYTHON) main.py $(ARGS)

runfake: ## Executa o bot principal com API fake e estratégia burra
	$(UV) run $(PYTHON) main.py --strategy=iteration --interval=1 --currency=BTC-BRL --sell_on_iteration=3 --fake

format: ## Formata o código com Ruff
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	$(UV) run pyright ./trader/*

setup-pre-commit: ## Configura hook de pré-commit para verificação automática
	cp scripts/pre-commit.sh .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "✅ Hook de pré-commit configurado! O código será verificado automaticamente antes de cada commit."
