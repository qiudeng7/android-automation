"""FIRERPA 基础接口试跑：只读信息 + 少量无副作用的交互。

准备：python3 -m venv .venv && .venv/bin/pip install lamda
用法：.venv/bin/python quickstart.py [设备IP]，默认 100.127.0.1（redmi-k70 的 Tailscale 地址）。
截图和界面布局保存到 .temp/。
"""

import sys
import time
from pathlib import Path

from lamda.client import Device, Keys

host = sys.argv[1] if len(sys.argv) > 1 else "100.127.0.1"
out = Path(__file__).parent / ".temp"
out.mkdir(exist_ok=True)

d = Device(host)

print("== 服务信息")
print(d.server_info())

print("== 设备信息")
print(d.device_info())

# Shizuku 启动时这里应是 shell 身份
print("== 执行命令 id")
print(d.execute_script("id").stdout.decode().strip())

print("== 屏幕")
if not d.is_screen_on():
    d.wake_up()
print("亮屏:", d.is_screen_on(), "锁屏:", d.is_screen_locked())

d.show_toast("Hello from quickstart.py")

print("== 打开设置，再回到桌面")
settings = d.application("com.android.settings")
settings.start()
time.sleep(2)
print("设置在前台:", settings.is_foreground())

d.screenshot(60).save(str(out / "settings.jpg"))  # 返回的是 JPEG
(out / "settings.xml").write_bytes(d.dump_window_hierarchy().getvalue())
print("截图和布局已保存到", out)

d.press_key(Keys.KEY_HOME)
print("当前前台应用:", d.current_application().applicationId)
