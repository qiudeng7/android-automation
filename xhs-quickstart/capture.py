"""MITM capture with FIRERPA certificate management and an ADB connection.

Run with the repository virtualenv. The context manager removes its proxy,
test CA, and ADB reverse mapping on exit. The Android system proxy is
device-wide. Capture files contain sensitive data. Apps which ignore Android's
proxy require another route.
"""

import json
import shutil
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from mitmproxy import http, io
from mitmproxy.certs import CertStore


def adb(serial, *args):
    executable = shutil.which("adb") or str(
        Path.home() / "Library/Android/sdk/platform-tools/adb"
    )
    return subprocess.run(
        [executable, "-s", serial, *args], check=True, capture_output=True, text=True,
        timeout=60, close_fds=False,
    ).stdout.strip()


def export_flows(path):
    """Export decrypted HTTP transactions; preserve complete originals in .mitm."""
    count = 0
    with path.open("rb") as source, path.with_suffix(".jsonl").open("w") as out:
        for flow in io.FlowReader(source).stream():
            if not isinstance(flow, http.HTTPFlow):
                continue
            record = {
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "request_headers": list(flow.request.headers.items(multi=True)),
                "request_body": flow.request.get_text(strict=False),
                "status": flow.response.status_code if flow.response else None,
                "response_headers": list(flow.response.headers.items(multi=True))
                if flow.response else [],
                "response_body": flow.response.get_text(strict=False)
                if flow.response else None,
                "error": str(flow.error) if flow.error else None,
            }
            # Binary bodies may decode to surrogate escapes; keep JSON valid.
            out.write(json.dumps(record, ensure_ascii=True) + "\n")
            if flow.response:
                count += 1
    return count


@contextmanager
def capture(device, serial, output, addon=None):
    if device.is_gproxy_running():
        raise RuntimeError("已有 FIRERPA 代理在运行，请先停止它再抓包。")
    output.mkdir(parents=True, exist_ok=True)
    ca_dir = output / "ca"
    ca_dir.mkdir()
    CertStore.from_store(ca_dir, "mitmproxy", 2048)
    cert = str(ca_dir / "mitmproxy-ca-cert.pem")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    flow_path = output / "flows.mitm"
    log = (output / "mitmproxy.log").open("w")
    process = None
    reversed_port = installed = False
    system_proxy_before = None
    try:
        command = [
            str(Path(sys.executable).with_name("mitmdump")),
            "--mode", "regular",
            "--listen-host", "127.0.0.1",
            "--listen-port", str(port), "--set", f"confdir={ca_dir}",
            "-w", str(flow_path),
        ]
        if addon is not None:
            command.extend(["-s", str(addon), "--set", f"homefeed_output={output / 'homefeed.jsonl'}"])
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, close_fds=False)
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError("mitmdump 启动失败，请查看 mitmproxy.log")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("mitmdump 未开始监听")
                time.sleep(0.2)
        adb(serial, "reverse", f"tcp:{port}", f"tcp:{port}")
        reversed_port = True
        installed = True  # Also remove a certificate after a partial install.
        device.install_ca_certificate(cert)
        system_proxy_before = adb(serial, "shell", "settings", "get", "global", "http_proxy")
        (output / "proxy-before.json").write_text(
            json.dumps({"http_proxy": system_proxy_before}) + "\n"
        )
        adb(serial, "shell", "settings", "put", "global", "http_proxy", f"127.0.0.1:{port}")
        yield flow_path
    finally:
        # Attempt every cleanup even if another cleanup operation fails.
        errors = []
        for enabled, operation in [
            (system_proxy_before is not None, lambda: adb(
                serial, "shell", "settings",
                "delete" if system_proxy_before == "null" else "put",
                "global", "http_proxy",
                *([] if system_proxy_before == "null" else [system_proxy_before]),
            )),
            (installed, lambda: device.uninstall_ca_certificate(cert)),
            (reversed_port, lambda: adb(serial, "reverse", "--remove", f"tcp:{port}")),
        ]:
            if enabled:
                try:
                    operation()
                except Exception as error:
                    errors.append(str(error))
        if process and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                errors.append("mitmdump 未正常退出，抓包文件可能不完整")
        log.close()
        if errors:
            raise RuntimeError("清理未完成：" + "; ".join(errors))
