#!/bin/bash

# Policy Engine - скрипт автоматической установки
# Запуск: chmod +x install.sh && ./install.sh

set -e

echo "🚀 Policy Engine - Автоматическая установка"
echo "=========================================="

# Определение ОС
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    echo "❌ Неподдерживаемая ОС: $OSTYPE"
    exit 1
fi

echo "📍 Обнаружена ОС: $OS"

# Проверка наличия uv
if command -v uv &> /dev/null; then
    echo "✅ uv найден, используем его для установки"
    PACKAGE_MANAGER="uv"
else
    echo "⚠️  uv не найден, используем pip"
    PACKAGE_MANAGER="pip"
fi

# Создание виртуального окружения и установка зависимостей
if [[ "$PACKAGE_MANAGER" == "uv" ]]; then
    echo "📦 Синхронизация зависимостей через uv..."
    uv sync --frozen --extra dev --extra test --extra runtime-http

    echo "🔧 Активация виртуального окружения..."
    source .venv/bin/activate

    # Специфика JAX для разных платформ
    if [[ "$OS" == "macos" ]]; then
        echo "🍎 Установка JAX для macOS (Metal)..."
        uv add jax-metal
    fi

else
    echo "📦 Создание виртуального окружения..."
    python3 -m venv .venv

    echo "🔧 Активация виртуального окружения..."
    source .venv/bin/activate

    echo "📦 Установка зависимостей через pip..."
    pip install -e .[dev,test,runtime-http]

    # Специфика JAX для разных платформ
    if [[ "$OS" == "macos" ]]; then
        echo "🍎 Установка JAX для macOS (Metal)..."
        pip install jax-metal
    elif [[ "$OS" == "linux" ]]; then
        echo "🐧 Проверка NVIDIA GPU..."
        if command -v nvidia-smi &> /dev/null; then
            echo "   NVIDIA GPU обнаружена, устанавливаем JAX с CUDA..."
            pip install -U "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
        else
            echo "   NVIDIA GPU не обнаружена, используем CPU версию JAX"
        fi
    fi
fi

echo ""
echo "🎉 Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Активируйте виртуальное окружение: source .venv/bin/activate"
echo "2. Запустите smoke test: python tools/diagnostics/check_setup.py"
echo "3. Настройте переменные окружения: cp .env.example .env"
echo ""
echo "📚 Документация: cat README.md"
echo "🔧 Доступные команды:"
echo "   - uv run python tools/diagnostics/check_setup.py   # Проверка установки"
echo "   - uv run ruff check .                              # Линтинг кода"
echo "   - uv run ruff format .                             # Форматирование кода"
echo "   - uv run mypy src/                                 # Типизация"
echo "   - uv run pytest                                    # Тесты"
