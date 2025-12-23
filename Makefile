.PHONY: test test-verbose test-coverage install install-dev clean build help run

help: ## Mostra esta mensagem de ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instala as dependências do projeto
	uv sync

install-dev: ## Instala as dependências de desenvolvimento
	uv sync --extra dev

pipe: ## Roda uma especie de pipeline. Formata, builda e testa
	uv format
	uv run ruff format
	uv run ruff check --fix
	uv build
	uv run pytest .

test: ## Executa os testes
	uv run pytest .

build: ## Constrói o pacote
	uv build

clean: ## Remove arquivos temporários e cache
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +

rundry: ## Executa o bot principal com dados reais, mas com a estrategia com parametros pra não comprar
	uv run --env-file .env main.py run dry SOL-USDC random 'sell_chance=20 buy_chance=40'

rundry2:
	uv run --env-file .env main.py run dry NOBODY-USDC random 'sell_chance=100 buy_chance=100'

rundrycomposer_sol:
	uv run --env-file .env main.py run dry SOL-USDC composer 'buy_mode=all sell_mode=any'

startdry:
	uv run --env-file .env main.py start dry


run: ## Executa o bot principal
	uv run main.py run $(ARGS)

lint: ## Executa verificação de código com Ruff
	uv run ruff check .

lint-fix: ## Executa verificação e corrige automaticamente problemas com Ruff
	uv run ruff check --fix .

typing-check: ## Executa verificação de typing com pyright
	uv run pyright .


format: ## Formata o código com Ruff
	uv run ruff check --fix .
	uv run ruff format .
	uv run pyright ./trader/*

setup-pre-commit: ## Configura hook de pré-commit para verificação automática
	cp scripts/pre-commit.sh .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "✅ Hook de pré-commit configurado! O código será verificado automaticamente antes de cada commit."
