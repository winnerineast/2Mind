#!/bin/bash

# === 2mind Server Config (RTX 4090 Edition) ===
MODEL_NAME="Qwen/Qwen2-VL-7B-Instruct"
GPU_UTILIZATION=0.85
MAX_SEQS=10

echo "🚀 Starting 2mind Brain..."
echo "Model: $MODEL_NAME | Hardware: RTX 4090"

# 修正点：vLLM 0.6.3 使用 key=value 格式
python3 -m vllm.entrypoints.openai.api_server \
    --model $MODEL_NAME \
    --trust-remote-code \
    --gpu-memory-utilization $GPU_UTILIZATION \
    --max-model-len 8192 \
    --max-num-seqs $MAX_SEQS \
    --limit-mm-per-prompt image=1 \
    --dtype bfloat16 \
    --host 0.0.0.0 \
    --port 8000