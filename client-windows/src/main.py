import time
import base64
import hashlib
from io import BytesIO
import os

import mss
import mss.tools
from PIL import Image
from openai import OpenAI
from colorama import init, Fore, Style

# === 配置区域 ===
# WSL2 的 vLLM 地址 (localhost 端口转发通常是自动的)
VLLM_API_URL = "http://localhost:8000/v1"
API_KEY = "EMPTY"
MODEL_NAME = "Qwen/Qwen2-VL-7B-Instruct"

# 行为配置
CHECK_INTERVAL = 0.5  # 每次检查间隔(秒)
STABILITY_COUNT = 4  # 需要连续检查多少次无变化才触发 (4 * 0.5 = 2秒)
RESIZE_DIM = 1024  # 图片最大边长 (太大会导致推理变慢)

# 初始化
init(autoreset=True)
client = OpenAI(base_url=VLLM_API_URL, api_key=API_KEY)


def capture_screen():
    """使用 mss 极速截屏"""
    with mss.mss() as sct:
        # 截取第一个显示器 (通常是主屏)
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return img


def compress_image(image):
    """缩放并转为 Base64"""
    # 保持比例缩放
    image.thumbnail((RESIZE_DIM, RESIZE_DIM))
    buffered = BytesIO()
    image.save(buffered, format="JPEG", quality=60)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def get_screen_hash(image):
    """计算屏幕指纹，用于检测变化"""
    # 为了性能，我们将图片缩小后再计算 hash
    small = image.resize((64, 64), Image.Resampling.NEAREST)
    return hashlib.md5(small.tobytes()).hexdigest()


def ask_brain(b64_img):
    """发送给 WSL2 的 vLLM"""
    print(f"\n{Fore.YELLOW}🧠 Thinking... (Sending to vLLM)", end="\r")

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text",
                         "text": "你是一个专业的桌面助手。请分析我当前的屏幕内容。如果我在写代码，请检查潜在的 bug 或优化点。如果我在阅读，请总结要点。如果只是桌面，请忽略。请用简短的中文回答（50字以内）。"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                        },
                    ],
                }
            ],
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"{Fore.RED}Error: {e}"


def main():
    print(f"{Fore.CYAN}{Style.BRIGHT}>>> 2mind Observer Started")
    print(f"{Fore.CYAN}Target Brain: {VLLM_API_URL}")
    print(f"{Fore.CYAN}Waiting for screen to stabilize ({STABILITY_COUNT * CHECK_INTERVAL}s)...")

    last_hash = None
    stable_counter = 0

    try:
        while True:
            start_time = time.time()

            # 1. 抓取与检测
            current_img = capture_screen()
            current_hash = get_screen_hash(current_img)

            if current_hash != last_hash:
                # 屏幕变化中... 重置计数器
                stable_counter = 0
                last_hash = current_hash
                # print(".", end="", flush=True) # 调试用：显示心跳
            else:
                # 屏幕静止
                stable_counter += 1

            # 2. 触发逻辑
            if stable_counter == STABILITY_COUNT:
                print(f"\n{Fore.GREEN}[!] Screen Stable. Capturing context...")

                # 准备图片
                b64 = compress_image(current_img)

                # 调用大脑
                result = ask_brain(b64)

                # 输出结果
                print("-" * 40)
                print(f"{Fore.WHITE}{result}")
                print("-" * 40)

                # 避免重复触发，增加计数器直到下一次屏幕变动
                stable_counter += 1

            # 保持循环频率
            elapsed = time.time() - start_time
            sleep_time = max(0, CHECK_INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Observer stopped.")


if __name__ == "__main__":
    main()