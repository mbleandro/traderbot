#!/bin/bash

# Script de pré-commit para verificar código com Ruff
# Para usar: copie este arquivo para .git/hooks/pre-commit e torne-o executável

echo "🔍 Executando verificações de código com Ruff..."

# Verificar se o Ruff está instalado
if ! command -v uv &> /dev/null; then
    echo "❌ uv não encontrado. Instale o uv primeiro."
    exit 1
fi

# Executar verificação do Ruff
echo "📋 Verificando código..."
if ! uv run ruff check .; then
    echo "❌ Problemas encontrados no código. Execute 'make lint-fix' para corrigir automaticamente."
    exit 1
fi

# Verificar formatação
echo "🎨 Verificando formatação..."
if ! uv run ruff format --check .; then
    echo "❌ Código não está formatado corretamente. Execute 'make format' para formatar."
    exit 1
fi

# Verificar typing
echo "🎨 Verificando tipagem..."
if ! uv run pyright .; then
    echo "❌ Código não está tipado corretamente. Execute 'make typing-check' para listar os problemas."
    exit 1
fi

echo "✅ Todas as verificações passaram!"
exit 0
