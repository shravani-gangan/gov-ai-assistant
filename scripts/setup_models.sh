#!/usr/bin/env bash
set -euo pipefail

echo "=== Government AI Assistant: Model Setup ==="

# Pull all required models
MODELS=(
  "mistral:7b-instruct-v0.3-q4_K_M"
  "nous-hermes2:7b-mistral-dpo-q4_K_M"
  "phi3:mini-128k"
  "nomic-embed-text"
)

for model in "${MODELS[@]}"; do
  echo "Pulling: $model"
  ollama pull "$model"
  echo "✓ $model ready"
done

echo ""
echo "=== All models ready ==="
ollama list