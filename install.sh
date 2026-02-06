#!/bin/bash
# Self-Improving Agent - Quick Install Script
# Usage: curl -fsSL https://raw.githubusercontent.com/self-improving-agent/main/install.sh | bash

set -e

REPO_URL="https://github.com/xmaks82/self-improving-agent.git"
INSTALL_DIR="$HOME/self-improving-agent"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         Self-Improving AI Agent - Installation               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check requirements
command -v docker >/dev/null 2>&1 || { echo "❌ Docker required. Install: https://docs.docker.com/get-docker/"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v "docker compose" >/dev/null 2>&1 || { echo "❌ Docker Compose required"; exit 1; }

echo "✓ Docker found"

# Clone or update repo
if [ -d "$INSTALL_DIR" ]; then
    echo "→ Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "→ Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Setup environment
if [ ! -f .env ]; then
    echo ""
    echo "→ Setting up environment..."
    cp .env.example .env

    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Enter API keys (press Enter to skip optional ones)          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    read -p "GROQ_API_KEY (FREE, recommended - https://console.groq.com/): " GROQ_KEY
    if [ -n "$GROQ_KEY" ]; then
        sed -i "s/GROQ_API_KEY=.*/GROQ_API_KEY=$GROQ_KEY/" .env
    fi

    read -p "SAMBANOVA_API_KEY (FREE, fastest - https://cloud.sambanova.ai/): " SAMBANOVA_KEY
    if [ -n "$SAMBANOVA_KEY" ]; then
        sed -i "s/SAMBANOVA_API_KEY=.*/SAMBANOVA_API_KEY=$SAMBANOVA_KEY/" .env
    fi

    read -p "ANTHROPIC_API_KEY (paid, for improvements - https://console.anthropic.com/): " ANTHROPIC_KEY
    if [ -n "$ANTHROPIC_KEY" ]; then
        sed -i "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$ANTHROPIC_KEY/" .env
    fi
fi

# Build and run
echo ""
echo "→ Building Docker image..."
docker compose build

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Installation Complete!                     ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Start agent:    cd $INSTALL_DIR && docker compose run agent ║"
echo "║  Stop agent:     docker compose down                         ║"
echo "║  View logs:      docker compose logs -f                      ║"
echo "║  Edit config:    nano .env                                   ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
