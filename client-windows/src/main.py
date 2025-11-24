import time
import base64
import hashlib
from io import BytesIO
import argparse
import sys

import mss
import mss.tools
import cv2
import numpy as np
from PIL import Image
from openai import OpenAI
from colorama import init, Fore, Style

# === 配置区域 ===
VLLM_API_URL = "http://localhost:8000/v1"
API_KEY = "EMPTY"
MODEL_NAME = "Qwen/Qwen2-VL-7B-Instruct"

# 行为配置
CHECK_INTERVAL = 0.5  # 采样间隔
STABILITY_COUNT = 3  # 稳定次数阈值
CAMERA_DIFF_THRESHOLD = 10.0  # 摄像头判定静止的阈值 (调大一点更宽松)

init(autoreset=True)


def debug(msg, color=Fore.MAGENTA, end="\n"):
    """强制刷新的调试打印"""
    print(f"{color}{msg}{Style.RESET_ALL}", end=end, flush=True)


class VisionSensor:
    def __init__(self, mode="screen", camera_index=0):
        self.mode = mode
        self.camera_index = camera_index
        self.cap = None

        if self.mode == "camera":
            debug(f"\n[Init] Start initializing Camera #{camera_index}...")

            # 策略：优先 DirectShow (也就是 probe.py 成功的那个)
            # 这里的关键是不设置任何分辨率，完全使用默认值，以此保证最大兼容性
            debug(f"[Init] Trying backend: cv2.CAP_DSHOW...")
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

            if not self.cap.isOpened():
                debug(f"[Init] DSHOW failed! Trying cv2.CAP_MSMF...", Fore.YELLOW)
                self.cap = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)

            if not self.cap.isOpened():
                debug(f"[Init] MSMF failed! Trying Auto...", Fore.YELLOW)
                self.cap = cv2.VideoCapture(camera_index)

            if not self.cap.isOpened():
                raise RuntimeError(f"❌ Fatal: Could not open camera #{camera_index}")

            debug(f"[Init] Camera Opened! Reading warmup frame...", Fore.CYAN)
            ret, _ = self.cap.read()
            if not ret:
                debug(f"[Init] Warmup read failed!", Fore.RED)
            else:
                debug(f"[Init] Warmup read success.", Fore.GREEN)

    def capture(self):
        if self.mode == "screen":
            return self._capture_screen()
        elif self.mode == "camera":
            return self._capture_camera()

    def _capture_screen(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    def _capture_camera(self):
        if not self.cap: return None

        # === 关键调试点 ===
        # R = Requesting (正在请求硬件)
        # G = Got (硬件返回数据)
        # 如果你只看到 R 后面没东西，就是卡死在驱动层了
        debug("R", Fore.BLACK, end="")

        ret, frame = self.cap.read()

        if not ret:
            debug("X", Fore.RED, end="")  # X = 失败
            # 尝试重连
            # debug("\n[Error] Lost stream, reopening...", Fore.RED)
            # self.cap.open(self.camera_index)
            return None

        debug("G", Fore.BLACK, end="")

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_frame)

    def release(self):
        if self.cap: self.cap.release()


class MindObserver:
    def __init__(self, sensor_mode="screen", camera_index=0):
        self.client = OpenAI(base_url=VLLM_API_URL, api_key=API_KEY)
        self.sensor = VisionSensor(mode=sensor_mode, camera_index=camera_index)
        self.last_frame_array = None
        self.last_hash = None

    def compress_image(self, image):
        # 缩小图片以加快传输
        image.thumbnail((1024, 1024))
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=60)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def is_stable(self, current_img):
        if self.sensor.mode == "screen":
            small = current_img.resize((64, 64), Image.Resampling.NEAREST)
            current_hash = hashlib.md5(small.tobytes()).hexdigest()
            is_same = (current_hash == self.last_hash)
            self.last_hash = current_hash
            if not is_same: debug(".", Fore.CYAN, end="")
            return is_same
        else:
            # 摄像头模式：计算像素差
            current_array = np.array(current_img.resize((256, 256)))
            if self.last_frame_array is None:
                self.last_frame_array = current_array
                return False

            diff = cv2.absdiff(current_array, self.last_frame_array)
            mean_diff = np.mean(diff)
            self.last_frame_array = current_array

            # 打印实时差异值
            color = Fore.GREEN if mean_diff < CAMERA_DIFF_THRESHOLD else Fore.YELLOW
            debug(f"[{mean_diff:.1f}]", color, end="")

            return mean_diff < CAMERA_DIFF_THRESHOLD

    def ask_brain(self, b64_img):
        debug("\n🧠 Thinking... ", Fore.YELLOW)
        try:
            prompt = "分析这个画面。"
            if self.sensor.mode == "camera":
                prompt = "这是摄像头实时画面。你看到了什么？简短描述。"

            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                    ]}
                ],
                max_tokens=100,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {e}"

    def run(self):
        print(f"{Fore.CYAN}>>> Observer Started [{self.sensor.mode.upper()}]")
        stable_counter = 0

        try:
            while True:
                # === Windows OpenCV 必须加这句，否则 DirectShow 会卡死 ===
                if self.sensor.mode == "camera":
                    cv2.waitKey(1)

                start = time.time()
                img = self.sensor.capture()

                if img is None:
                    time.sleep(0.1)
                    continue

                # 检测静止
                if self.is_stable(img):
                    stable_counter += 1
                else:
                    stable_counter = 0

                # 触发
                if stable_counter == STABILITY_COUNT:
                    print(f"\n{Fore.GREEN}[!] Stable. Analyzing...")
                    result = self.ask_brain(self.compress_image(img))
                    print(f"\n{Fore.WHITE}{Style.BRIGHT}{result}\n{'-' * 20}")
                    stable_counter += 1

                elapsed = time.time() - start
                time.sleep(max(0, CHECK_INTERVAL - elapsed))

        except KeyboardInterrupt:
            print(f"\n{Fore.RED}Stopped.")
            self.sensor.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="screen", choices=["screen", "camera"])
    parser.add_argument("--cam-index", type=int, default=0)
    args = parser.parse_args()

    try:
        MindObserver(sensor_mode=args.mode, camera_index=args.cam_index).run()
    except Exception as e:
        print(f"\n{Fore.RED}Fatal Error: {e}")