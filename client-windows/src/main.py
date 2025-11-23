import time
import base64
import sys
import hashlib
from io import BytesIO

import mss
import mss.tools
from PIL import Image
from openai import OpenAI
from colorama import init, Fore, Style

import config

# 初始化颜色输出
init(autoreset=True)

class MindObserver:
    def __init__(self):
        self.client = OpenAI(base_url=config.VLLM_API_URL, api_key=config.API_KEY)
        self.last_hash = None
        self.stable_count = 0
        print(f"{Fore.CYAN}[System] 2mind Observer Initialized.")
        print(f"{Fore.CYAN}[System] Connected to Brain at: {config.VLLM_API_URL}")

    def capture_screen(self):
        """截取主屏幕并返回 PIL Image"""
        with mss.mss() as sct:
            monitor = sct.monitors[1] # 1 是主屏幕
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            # 缩放以加快传输和推理
            img.thumbnail((config.IMAGE_RESIZE_DIM, config.IMAGE_RESIZE_DIM))
            return img

    def get_image_hash(self, img):
        """计算图片哈希值用于检测变化"""
        return hashlib.md5(img.tobytes()).hexdigest()

    def image_to_base64(self, img):
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=60)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def ask_brain(self, b64_img):
        """发送视觉请求给 vLLM"""
        print(f"{Fore.YELLOW}🧠 Thinking...", end="\r")
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful desktop assistant. Keep your answers brief (under 30 words) and actionable."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze my screen. What am I doing and what should I verify next?"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                        ],
                    }
                ],
                max_tokens=100,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"{Fore.RED}Connection Error: {e}"

    def run(self):
        print(f"{Fore.GREEN}>>> Observer Started. Waiting for screen stability...")

        while True:
            try:
                current_img = self.capture_screen()
                current_hash = self.get_image_hash(current_img)

                if current_hash != self.last_hash:
                    # 屏幕在动
                    self.last_hash = current_hash
                    self.stable_count = 0
                    # sys.stdout.write(".")
                    # sys.stdout.flush()
                else:
                    # 屏幕静止
                    self.stable_count += 1

                # 触发条件：屏幕静止达到阈值
                if self.stable_count == config.STABILITY_THRESHOLD:
                    print(f"\n{Fore.GREEN}[Event] Screen Stable. Capturing Context...")
                    b64 = self.image_to_base64(current_img)
                    suggestion = self.ask_brain(b64)

                    print(f"{Fore.WHITE}{Style.BRIGHT}----------------------------------------")
                    print(f"{Fore.MAGENTA}🤖 AI: {suggestion}")
                    print(f"{Fore.WHITE}{Style.BRIGHT}----------------------------------------")

                    # 增加计数防止死循环触发，直到下一次屏幕变动
                    self.stable_count += 1

                time.sleep(config.SCREEN_CHECK_INTERVAL)

            except KeyboardInterrupt:
                print(f"\n{Fore.RED}Stopping Observer.")
                break

if __name__ == "__main__":
    app = MindObserver()
    app.run()