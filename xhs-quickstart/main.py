"""Capture rednote home recommendations as a guest with FIRERPA and MITM.

Usage: .venv/bin/python xhs-quickstart/main.py [--accept-privacy]
Requires an installed com.xingin.xhs and a running root FIRERPA server.
Does not log in, publish, like, follow, or send messages.
"""

import argparse
import json
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from lamda.client import Device

from capture import adb, capture, export_flows

HERE = Path(__file__).resolve().parent
PACKAGE = "com.xingin.xhs"


def snapshot(device, output, name):
    xml = device.dump_window_hierarchy().getvalue()
    (output / f"{name}.xml").write_bytes(xml)
    device.screenshot(80).save(str(output / f"{name}.jpg"))
    return ET.fromstring(xml)


def dismiss_notifications(device):
    device(resourceId="com.android.permissioncontroller:id/permission_deny_button").click_exists()


def read_homefeed(output):
    path = output / "homefeed.jsonl"
    if not path.exists():
        return []
    # A reader may observe the final line while mitmproxy is still writing it.
    records = []
    for line in path.read_text().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def feed_notes(record):
    if urlsplit(record["url"]).path.endswith("/categories"):
        return []
    body = record.get("body")
    if record["status"] != 200 or not isinstance(body, dict) or body.get("success") is not True:
        return []
    data = body.get("data")
    return data if isinstance(data, list) else []


def run_ui(device, serial, output, accept_privacy, timeout):
    print("未登录启动小红书，抓取首页推荐", flush=True)
    adb(serial, "shell", "am", "force-stop", PACKAGE)
    adb(serial, "shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
    agree = device(resourceId=f"{PACKAGE}:id/agreeBtn")
    if agree.wait_for_exists(1500):
        snapshot(device, output, "00-privacy")
        if not accept_privacy:
            raise RuntimeError("首次运行请阅读隐私协议后使用 --accept-privacy，或在设备中手动确认。")
        agree.click()
    time.sleep(1)
    dismiss_notifications(device)
    home = device(resourceId=f"{PACKAGE}:id/index_home")
    if not home.wait_for_exists(60000):
        snapshot(device, output, "error-home")
        raise RuntimeError("首页没有出现，请查看 error-home 截图。")
    home.click()
    if not device(resourceId=f"{PACKAGE}:id/goToLogin").wait_for_exists(5000):
        snapshot(device, output, "error-guest-state")
        raise RuntimeError("未检测到首页游客登录提示，无法确认未登录状态；不会自动退出已有账号。")
    snapshot(device, output, "01-guest-home")
    print("已确认首页游客状态，等待推荐列表响应", flush=True)
    deadline = time.monotonic() + timeout
    while not any(feed_notes(record) for record in read_homefeed(output)):
        if time.monotonic() >= deadline:
            snapshot(device, output, "error-feed-timeout")
            raise TimeoutError("未收到包含推荐笔记的首页响应，请检查 homefeed.jsonl 和 mitmproxy.log。")
        time.sleep(0.5)
    snapshot(device, output, "02-homefeed-captured")
    return {"home_clicked": True, "guest_indicator_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--port", type=int, default=65000)
    parser.add_argument("--timeout", type=int, default=45, help="等待首页推荐响应的秒数")
    parser.add_argument("--accept-privacy", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    output = HERE / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S-%f-xhs")
    output.mkdir(parents=True)
    print("运行结果：", output, flush=True)
    adb(args.serial, "forward", f"tcp:{args.port}", "tcp:65000")
    device = Device("127.0.0.1", port=args.port)
    summary = {"package": PACKAGE, "serial": args.serial, "routing": "system"}
    summary["app_version"] = adb(
        args.serial, "shell", "dumpsys package com.xingin.xhs | grep -m 1 versionName="
    )
    try:
        with capture(device, args.serial, output, addon=HERE / "homefeed_addon.py"):
            summary["ui"] = run_ui(device, args.serial, output, args.accept_privacy, args.timeout)
            time.sleep(3)
    except (Exception, KeyboardInterrupt) as error:
        summary["error"] = str(error)
    finally:
        flow_path = output / "flows.mitm"
        if flow_path.exists():
            export_flows(flow_path)
            records = [json.loads(line) for line in flow_path.with_suffix(".jsonl").read_text().splitlines()]
            business = [r for r in records if (
                urlsplit(r["url"]).hostname or ""
            ).endswith(".xiaohongshu.com")]
            summary["http"] = {
                "total_flows": len(records),
                "xhs_flows": len(business),
                "statuses": dict(Counter(str(r["status"]) for r in business)),
                "successful_https_responses": sum(
                    r["url"].startswith("https://") and r["status"] == 200 for r in business
                ),
                "endpoints": sorted({
                    f'{r["method"]} {urlsplit(r["url"]).netloc}{urlsplit(r["url"]).path}'
                    for r in business
                }),
            }
        feed_records = read_homefeed(output)
        notes = {}
        for record in feed_records:
            for note in feed_notes(record):
                if isinstance(note, dict) and note.get("id"):
                    notes.setdefault(note["id"], note)
        (output / "recommendations.json").write_text(
            json.dumps(list(notes.values()), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", errors="backslashreplace",
        )
        summary["homefeed"] = {
            "response_statuses": [r["status"] for r in feed_records if not urlsplit(r["url"]).path.endswith("/categories")],
            "category_response_statuses": [r["status"] for r in feed_records if urlsplit(r["url"]).path.endswith("/categories")],
            "note_count": len(notes),
            "note_ids": list(notes),
        }
        summary["passed"] = bool(
            "error" not in summary and "ui" in summary and notes
        )
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
