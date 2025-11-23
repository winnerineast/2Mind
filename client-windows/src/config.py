# Network
VLLM_API_URL = "http://localhost:8000/v1"
API_KEY = "EMPTY" # vLLM 本地运行通常不需要 Key

# Model
MODEL_NAME = "Qwen/Qwen2-VL-7B-Instruct"

# Behavior
SCREEN_CHECK_INTERVAL = 0.5  # 每 0.5 秒检查一次屏幕变化
STABILITY_THRESHOLD = 4      # 连续 4 次检查无变化（即静止2秒）才触发 AI
IMAGE_RESIZE_DIM = 1024      # 发送给 AI 的图片最大边长 (太大了慢，太小了看不清)