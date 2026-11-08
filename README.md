# android-automation

探索安卓自动化。

## 调研

### 自动化原理

总体来讲，安卓自动化围绕几个安卓官方提供的接口展开。

第一个是 ADB(Android Debug Bridge)：本来是为开发者调试应用和设备而设计的，但它开放了一套非常直接的命令接口：

- adb shell：打开一个 Unix shell，可以直接执行 shell 权限的命令
- adb shell input tap x y：向系统注入一次坐标点击事件，不依赖任何应用进程或 View 树，属于最底层的硬件事件模拟。
- adb shell input swipe：模拟滑动、拖拽等手势轨迹。
- adb shell input text：向当前获得焦点的输入框直接注入文本内容。
- adb shell uiautomator dump：将当前前台窗口的 UI 控件层级导出为 XML 文件，从中可以读取每个节点的 class、text、- resource-id、bounds、clickable 等属性。
- adb shell screencap：截取当前屏幕画面，输出为 PNG 格式。
- adb shell am / adb shell pm：分别与 Activity Manager 和 Package Manager 交互，用于启动界面、强制停止应用、查询包信息等。


在 adb 环境下开发者通过 Shell 用户登录，开发者可以获得一些比普通用户更高一些的权限（不过仍然低于root）

第二个是无障碍服务 AccessibilityService：本来是为辅助功能设计的，但它开放了一套非常有意思的接口：

- getRootInActiveWindow()：获取当前窗口的 UI 控件树。
- AccessibilityNodeInfo：遍历控件，获取文本、ID、位置、可点击状态等。
- performAction(ACTION_CLICK)：对控件执行点击。
- performAction(ACTION_SET_TEXT)：设置输入框内容。
- dispatchGesture()：模拟点击、滑动等手势。

有一些方案是围绕无障碍服务来构建的。


第三个是 UIAutomator，这是 Google 官方提供的跨应用 UI 测试框架，它和 ADB、无障碍服务位于不同的抽象层：ADB 是命令级的 Shell 接口，无障碍服务是应用进程内的系统服务，而 UI Automator 是基于插桩（instrumentation）的测试框架，运行在设备上的测试进程中，通过系统的无障碍层去“看见”并操作任意应用的界面。

UI Automator 的 API 围绕四个核心概念展开：

- `UiDevice`：代表设备本身。可以通过 UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()) 获取实例，用于执行设备级操作：按 Home / Back / Menu 键、旋转屏幕、打开通知栏、截屏、获取屏幕尺寸，也可以用它来查找 UI 元素。

- `UiObject2`：代表屏幕上的一个 UI 元素。由 UiDevice.findObject(BySelector) 返回，封装了该元素的属性（文本、resource-id、class、可点击状态等）和动作（click()、setText()、scroll()、swipe() 等）。

- `BySelector` / `By`：元素查找的“选择器”。By 是构建 BySelector 的简洁入口，支持按 resource-id（By.res(...)）、文本（By.text(...)）、类名、content-desc 等条件匹配元素。

- `Until` ：等待条件。用于 device.wait(Until.hasObject(...)) 或 clickAndWait(Until.newWindow(), timeout) 等场景，让脚本在元素出现、窗口切换等事件发生前阻塞等待，而不是硬编码 sleep。

一个典型调用链是：UiDevice → findObject(By.xxx(...)) → UiObject2.click() / setText()，整个过程不依赖无障碍服务的手动开关，也不需要知道你测试的应用内部是如何实现的。

### 自动化应用层

应用层的自动化框架主要解决一个问题：如何将底层 Android 控制能力封装成开发者容易使用的自动化接口，并提供任务执行、调度和通信机制。

#### Appium

Appium 是一个跨平台自动化测试框架，采用典型的 Client-Server 架构。

-   **Appium Server**：运行在 PC / Linux 上，负责接收客户端请求、管理设备和分发自动化命令。
-   **Driver**：负责适配不同平台和自动化技术，例如 Android 上的 UiAutomator2 Driver。
-   **设备端服务**：Driver 通常通过 ADB 在 Android 设备上安装并启动对应的自动化服务，实际 UI 操作由设备端执行。
-   **客户端 SDK**：提供 JavaScript、Python、Java 等语言的调用接口，通过
    WebDriver 协议（Selenium用的那个）与 Server 通信。

其核心思想是将自动化逻辑放在外部，通过标准化协议远程控制设备，而不是要求开发者在
Android 内部编写自动化脚本。

#### JS 方案（Hamibot、AutoX.js）

这类方案采用脚本驱动模式，将 JavaScript Runtime 和 Android
自动化能力集成在 Android 应用内部。

-   **JS Runtime**：在 Android 设备上运行 JavaScript 脚本。
-   **自动化 API**：将
    AccessibilityService、手势模拟、控件查询等能力封装成 JavaScript
    接口。
-   **任务执行**：通过加载、执行 JS 脚本完成自动化任务。

例如：

``` javascript
auto.waitFor();

launchApp("微信");

text("通讯录").findOne().click();

sleep(1000);
```

其核心思想是直接派发 JavaScript
脚本到设备执行，自动化逻辑与设备控制能力处于同一个运行环境中。

Hamibot
进一步提供了服务端管理能力，可以远程管理设备、派发脚本和查看执行结果。


#### FIRERPA

FIRERPA 采用常驻服务 + RPC 的架构思路。

-   **Android Agent**：在设备上运行服务，负责提供自动化执行能力。
-   **自动化接口**：将 Android 的控件查询、点击、滑动、截图等能力封装成可调用的接口。
-   **RPC通信**：外部控制端通过通信协议向设备发送操作请求，并获取执行结果。
-   **任务编排**：自动化逻辑可以放在外部，由控制端组织多个设备操作。

与 JS Runtime 方案不同，它不要求把完整的自动化逻辑作为脚本发送到设备，而是将设备抽象成一个可以远程调用的自动化执行端。

其核心思想是将设备控制能力服务化，使设备执行层与自动化编排层解耦。

#### Shizuku

Shizuku 本身不是自动化框架，而是一个为 Android 应用提供更高权限系统 API 访问能力的桥接工具。

普通 Android 应用运行在各自独立的 UID 和权限沙箱中，通常无法直接调用许多需要 `shell` 身份或特权权限的系统接口。

Shizuku 通过在设备上启动一个独立的服务进程，并让授权应用通过 Binder 与其通信，使应用能够借助该服务执行部分原本无法直接执行的系统 API 调用。

-   **服务端进程**：Shizuku Server 通常通过 ADB shell 身份启动；在具备
    root 环境时，也可以通过 root 方式启动。
-   **Binder 通信**：应用集成 Shizuku API，通过 Binder 与 Shizuku Server
    通信，请求执行受支持的系统 API。
-   **权限边界**：通过 ADB 启动时，调用能力主要受 `shell` UID
    本身权限限制，并不等于获得 root；具体能否调用某个 API，还取决于
    Android 版本、目标 API 的权限要求及系统实现。
-   **应用集成**：开发者可以在自己的 Android 应用中集成
    Shizuku，将部分系统操作交给 Shizuku 执行，而不必自行实现一套 ADB
    通信或提权机制。

对于自动化系统而言，Shizuku
更适合作为设备控制层的能力补充：例如访问部分系统服务、执行 shell
身份允许的操作等。它并不直接提供完整的 UI
自动化能力，也不负责任务编排；控件树查询、点击和手势等能力仍需要结合
AccessibilityService、UiAutomator 或其他机制实现。

### 自动化应用层工具对比

| 方案 | 定位 | 任务派发 / 调用方式 | 主要特点 |
|---|---|---|---|
| Appium | 自动化测试框架 | RPC / WebDriver 命令 | 标准化、跨平台，自动化逻辑通常运行在外部 |
| Hamibot / AutoX.js | 脚本自动化框架 | 派发 JS 脚本 | 自动化逻辑在设备内部运行，脚本表达灵活 |
| FIRERPA | 设备自动化服务 | RPC 命令 | 将设备能力服务化，便于外部编排 |


### 安卓隔离环境

由于我的开发方式一般是远程连接 homeserver （headless linux）进行开发，所以我倾向于在 linux 中运行一个安卓系统，未来如果需要规模化运行使用 linux 下的虚拟方案也会更方便管理。

我考虑了几种方案包括 Cuttlefish、docker-Android 但是都弃用了，这里就不写了，主要原因是软件渲染太卡了，最后决定真机测试。


## quickstart firerpa

综合考量下来觉得 firerpa 最好，理由如下：

1. firerpa 本质是一个运维级的安卓控制节点，接口面更广。
2. 如果规模化管理，firerpa 的运维功能会很有用。
3. 有 web 管理界面，有远程桌面而且支持 webRTC，开发体验较好。

下面以小米 HyperOS 、无 root 为例上手 firerpa，并且让 homeserver 开发环境上的 Agent 也能访问firerpa，主要参考 https://device-farm.com/docs/zh/quick-start。

先在手机上安装 [firerpa.apk](https://device-farm.com/assets/apk/firerpa.apk) 和 [shizuku.apk](https://device-farm.com/assets/apk/shizuku-v13.6.0.r1086.2650830c-release.apk)

shizuku 的作用是给 firerpa 提供 shell 权限，本质上我们需要帮 shizuku 连接上 adb，后续 shizuku 就会一直在 adb 中以 shell 用户运行来提供服务，按照 shizuku 内置的说明做即可，只有两点要注意：

1. 要先打开开发者模式才能打开无线调试，hyperos打开开发者模式的方式是「我的设备 => 全部参数与信息」 找到OS版本，多点几下即可进入开发者模式。
2. 在无线调试界面，打开配对码弹框之后，不要关闭弹框，直接下拉然后长按 shizuku 的通知，把配对码输入进去即可，这样shizuku就可以客户端的身份连接上adb，然后左脚蹬右脚启动一个 shell 身份的 shizuku 守护服务。

启动 shizuku 之后由于我们是 homeserver 环境，还需要处理一下 tailscale，让 homeserver 和手机都加入同一个tailscale网络，可以直接参考[这篇博客](https://github.com/qiudeng7/blog/blob/main/2026.08/2-networking-service-providers-in-china.md) 此处不再赘述。

然后现在就可以打开 firerpa 启动服务了，他会直接把服务暴露到所有的网络上，包括浏览器后台和mcp服务器，在应用内可以复制 tailscale 的地址。

然后我们可以测试一下用仓库内的 python 脚本访问 firerpa：

```bash
python3 -m venv .venv && .venv/bin/pip install lamda
.venv/bin/python quickstart.py [设备IP，默认100.127.0.1]
```

firerpa 的全部接口可以参考[官方文档](https://device-farm.com/docs/zh/quick-start)

## quickstart redroid

由于抓包和进程逆向都需要 root，又只能折返到linux下的隔离安卓环境思路，这次用 redroid，它最轻量化，和宿主机共享内核，并且 gpu 加速也直接共享宿主机的 mesa 驱动。

启动 redroid 之前，我这边注意到有内核模块需要挂载，如果重启的话要重挂，可能每个人情况不一样，让 AI 修。

```bash
sudo modprobe -a \
  iptable_filter iptable_nat iptable_mangle \
  ip6table_filter ip6table_nat ip6table_mangle \
  xt_TPROXY xt_owner xt_mark
```

`docker compose up redroid -d` 启动 redroid，相关配置在 compose 里有注释说明；

然后连接adb 

```bash
adb connect localhost:5555
adb -s localhost:5555 shell getprop sys.boot_completed
adb -s localhost:5555 shell id
```

### 2. 安装并启动 root FireRPA

首次安装使用 FireRPA v10.9 的 **x86_64 服务端**；已安装或容器重启后，只执行最后一条启动命令。

```bash
mkdir -p .temp
curl -fL --retry 3 \
  https://github.com/firerpa/lamda/releases/download/v10.9/lamda-server-x86_64.tar.gz \
  -o .temp/lamda-server-x86_64.tar.gz &&
docker compose cp .temp/lamda-server-x86_64.tar.gz redroid:/data/local/tmp/lamda-server-x86_64.tar.gz &&
docker compose exec -T redroid sh -c \
  'mkdir -p /data/server && tar -xzf /data/local/tmp/lamda-server-x86_64.tar.gz -C /data/server' &&
docker compose exec -T redroid sh /data/server/bin/launch.sh
```

看到 `llllaamDaa started` 后打开 [FireRPA 控制台](http://100.127.0.7:65000/)；`already running` 表示已启动。数据保存在命名卷中，不要用 `docker compose down -v` 删除它。

### 3. 准备宿主机抓包工具

使用官方仓库中的 [startmitm.py](<lamda/tools/startmitm.py>)：它安装测试 CA，并通过容器内的 iptables 把指定 App 流量转给宿主机 mitmproxy，不占 Android 的 VPN 槽位。

如果本地还没有 `lamda` 目录，克隆后切到本次使用的提交；已经有该目录则跳过这两条，不要覆盖本地修改：

```bash
git clone https://github.com/firerpa/lamda.git lamda
git -C lamda checkout a980a38130ba00711311e509e3009301e8ff705a
```

安装客户端及抓包依赖（本次使用 lamda 10.9、mitmproxy 12.3.1）：

```bash
python3 -m venv .venv
.venv/bin/pip install 'lamda==10.9' 'mitmproxy==12.3.1' -r lamda/tools/requirements.txt
mkdir -p .temp/home
```

### 4. 只抓测试浏览器的流量

先记录 Android 当前的 IPv6 开关，供结束时恢复。下面的抓包脚本会把它改成 `1`，但脚本退出时不会自动恢复：

```bash
docker compose exec -T redroid \
  cat /proc/sys/net/ipv6/conf/all/disable_ipv6 > .temp/redroid-ipv6-before.txt
```

在终端 A 启动抓包并保持运行；不要同时运行多个抓包实例：

```bash
HOME="$PWD/.temp/home" PROXYPORT=38080 \
.venv/bin/python lamda/tools/startmitm.py \
  100.127.0.7:org.chromium.webview_shell \
  --device-side-out-interface eth0 \
  --listen-host 100.127.0.7 \
  --web-port 38081 --no-web-open-browser \
  --save-stream-file "$PWD/.temp/redroid-flows.mitm"
```

- `org.chromium.webview_shell` 是 Redroid 自带的测试浏览器包名，本节用它完成最小验证。以后抓其他已安装的 App 时，替换此包名，并在该 App 内操作以触发请求；下面的 WebView 启动命令和 httpbin 响应断言仅用于测试浏览器。不要省略包名变成全局抓包。
- `eth0` 是 Redroid 的网卡。`38080` 是代理端口，必须能从容器访问；`38081` 是 mitmweb 页面端口，只监听宿主机回环地址。
- `HOME` 只对这条命令生效，让 CA 和私钥保存在项目的 `.temp/home/.mitmproxy/`，不写入用户主目录。不要提交或分享其中的私钥、抓包文件。

等待终端显示 SOCKS 代理和 Web server 已监听。若从另一台电脑看抓包界面，在那台电脑执行：

```bash
ssh -N -L 38081:127.0.0.1:38081 qiudeng@100.127.0.7
```

然后在电脑浏览器打开抓包终端输出的 `http://127.0.0.1:38081/?token=...` 完整链接，token 使用本次启动生成的值。

在宿主机终端 B 重开测试浏览器，让它发起新的 HTTPS 连接：

```bash
adb -s 100.127.0.7:5555 shell am force-stop org.chromium.webview_shell
adb -s 100.127.0.7:5555 shell am start \
  -a android.intent.action.VIEW \
  -d 'https://httpbin.org/get?redroid_capture=verified' \
  -n org.chromium.webview_shell/.WebViewBrowserActivity
```

在 mitmweb 找到 `/get?redroid_capture=verified` 请求，确认状态码 `200`，响应 JSON 中有 `args.redroid_capture = "verified"`。本次已实际读到请求头和响应正文，证明 HTTPS 被解密，而不只是代理进程启动成功。SOCKS 模式下列表中的目标主机可能显示 IP，按请求路径或 `Host: httpbin.org` 查找即可。

### 5. 停止抓包与恢复

在终端 A 按 `Ctrl+C`，等待进程退出。正常退出会卸载本次 CA 并停止 gproxy；异常退出可能跳过清理。下面这段用于确保代理停止、CA 卸载，并恢复刚才记录的 IPv6 开关：

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from lamda.client import Device

d = Device("100.127.0.7")
ipv6_before = int(Path(".temp/redroid-ipv6-before.txt").read_text().strip())
if ipv6_before not in (0, 1):
    raise ValueError("IPv6 开关记录必须是 0 或 1")

try:
    d.stop_gproxy()
finally:
    try:
        d.uninstall_ca_certificate(".temp/home/.mitmproxy/mitmproxy-ca-cert.pem")
    finally:
        result = d.execute_script(
            f"echo {ipv6_before} > /proc/sys/net/ipv6/conf/all/disable_ipv6"
        )
        if result.exitstatus != 0:
            raise RuntimeError(result.stderr.decode())

print("gproxy_running:", d.is_gproxy_running())  # 应为 False
PY
```

抓包文件留在 [.temp/redroid-flows.mitm](<.temp/redroid-flows.mitm>)，退出后也可以用命令查看解密后的内容：

```bash
HOME="$PWD/.temp/home" .venv/bin/mitmdump \
  -nr .temp/redroid-flows.mitm --flow-detail 4 '~u redroid_capture=verified'
```

只停安卓环境时执行 `docker compose down`（不带 `-v`），保留 App 和 FireRPA 数据，下次从启动容器、启动 FireRPA 两步继续。

### 已知问题

- 报 `iptables core tables (FILTER/MANGLE) are not supported`，或 gproxy 看似运行但一直没有请求：先检查宿主机是否加载了第 1 步的全部模块，尤其 `iptable_filter` 和 `ip6table_filter`。不要只看 `is_gproxy_running()` 的布尔值判断成功。
- 当前组合的 UI 层级读取正常，但 FireRPA 截图接口报空 Bitmap 异常，尚未解决；这不影响上面已验证的 HTTPS 抓包流程。

