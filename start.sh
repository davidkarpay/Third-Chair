#!/bin/bash
# Third Chair - Development Environment Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "========================================"
echo "  Third Chair - Environment Setup"
echo "========================================"
echo

# Check if Ollama is running
echo "[1/3] Checking Ollama service..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "      Ollama is running"
    # Show loaded models
    MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
    if [ -n "$MODELS" ]; then
        echo "      Available models: $MODELS"
    fi
else
    echo "      Ollama is not running. Starting..."
    if command -v snap &> /dev/null && snap list ollama &> /dev/null; then
        sudo snap start ollama
        sleep 2
        echo "      Ollama started via snap"
    elif command -v ollama &> /dev/null; then
        ollama serve &
        sleep 2
        echo "      Ollama started"
    else
        echo "      WARNING: Ollama not found. Install with: sudo snap install ollama"
    fi
fi

# Activate virtual environment
echo
echo "[2/3] Activating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    echo "      Activated: $VENV_DIR"
    echo "      Python: $(python --version)"
else
    echo "      Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    echo "      Installing dependencies..."
    pip install -e "$SCRIPT_DIR" --quiet
    echo "      Virtual environment created and activated"
fi

# Verify third-chair is available
echo
echo "[3/3] Verifying Third Chair installation..."
if command -v third-chair &> /dev/null; then
    echo "      third-chair CLI is available"
else
    echo "      Installing Third Chair..."
    pip install -e "$SCRIPT_DIR" --quiet
    echo "      Installed"
fi

echo
echo "========================================"
echo "  Ready to use Third Chair!"
echo "========================================"
echo
echo "Commands:"
echo "  third-chair --help              Show all commands"
echo "  third-chair process <zip>       Process Axon evidence package"
echo "  third-chair status <case_dir>   Check case status"
echo "  third-chair report <case_dir>   Generate reports"
echo
echo "Data directory: /mnt/d/Third_Chair"
echo

# Keep the shell active with venv
exec "$SHELL"
