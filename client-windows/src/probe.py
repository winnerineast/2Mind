import cv2
from colorama import init, Fore, Style

init(autoreset=True)


def list_ports():
    """
    扫描可用的摄像头索引。
    """
    print(f"{Fore.CYAN}>>> 正在扫描摄像头设备 (0-5)...")

    # 在 Windows 上通常尝试这两个后端
    backends = [
        (cv2.CAP_DSHOW, "DirectShow"),
        (cv2.CAP_MSMF, "Media Foundation"),
        (cv2.CAP_ANY, "Default/Auto")
    ]

    available_cameras = []

    for index in range(5):  # 扫描前5个端口
        print(f"{Fore.YELLOW}Checking Index {index}...", end=" ")

        working_config = None

        # 对每个端口尝试不同的驱动后端
        for backend_id, backend_name in backends:
            cap = cv2.VideoCapture(index, backend_id)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    working_config = backend_name
                    cap.release()
                    break  # 只要有一个后端能通，就算这个端口是活的
                cap.release()

        if working_config:
            print(f"{Fore.GREEN}[FOUND] (Backend: {working_config})")
            available_cameras.append(index)
        else:
            print(f"{Fore.RED}[Failed]")

    print("-" * 30)
    if not available_cameras:
        print(f"{Fore.RED}❌ 未检测到任何可用摄像头！请检查 USB 连接或隐私设置。")
    else:
        print(f"{Fore.GREEN}✅ 可用摄像头索引: {available_cameras}")
        print(f"请在 main.py 中使用这些数字。")


if __name__ == "__main__":
    list_ports()