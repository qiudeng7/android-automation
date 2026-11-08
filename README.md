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


## redroid

真机测试完 firerpa 之后，我发现抓包和进程逆向都需要 root，又只能折返到 linux 下的隔离安卓环境思路，redroid 相比其他思路显然更优质，它最轻量化，和宿主机共享内核，并且 gpu 加速也直接共享宿主机的 mesa 驱动。

在 redroid 下我成功跑通了 firerpa quickstart，并且也实现了网络抓包。

唯一的问题是，redroid 运行的安卓是 x86 架构的，于是我转而使用我的 MacBook 去运行安卓。

## mac 模拟安卓

mac 模拟安卓也有很多思路，我最后选择了[谷歌官方模拟器](https://developer.android.com/studio?hl=zh-cn)

安卓版本选择 16，系统选 AOSP(Android Open Source)，因为这个可以 root。

启动之后可以成功 abd root 进去:
```bash
~/Library/Android/sdk/platform-tools/adb -e root
~/Library/Android/sdk/platform-tools/adb -e shell id
```

这样 mac 模拟安卓就算成功了

## 小红书抓包测试

在测试环境按照之前的方式安装 firerpa，然后还需要安装一些需要测试的社交平台，由于我们用的是 AOSP 无法使用各种第三方的软件商店，可以通过 Aurora store 下载常用软件，aurora 是一个 Google play 的第三方客户端，我们可以手动下载一下然后安装小红书来测试抓包。

### 安装 FIRERPA

以下命令在仓库目录运行，要求终端能直接使用 `adb`，且模拟器已启动。首次安装下载 ARM64 服务端，校验后解压到设备 `/data`：

```bash
adb -s emulator-5554 root
adb -s emulator-5554 wait-for-device
adb -s emulator-5554 shell id

mkdir -p .temp/downloads
curl -fL --retry 2 \
  https://github.com/firerpa/lamda/releases/download/v10.9/lamda-server-arm64-v8a.tar.gz \
  -o .temp/downloads/lamda-server-arm64-v8a.tar.gz
echo '88957c04f6cae2e2cc56aaece92cec4074ad72092bc05f1e26e4095de7dedeca  .temp/downloads/lamda-server-arm64-v8a.tar.gz' | shasum -a 256 -c -

adb -s emulator-5554 push .temp/downloads/lamda-server-arm64-v8a.tar.gz /data/local/tmp/
adb -s emulator-5554 shell tar -C /data -xzf /data/local/tmp/lamda-server-arm64-v8a.tar.gz
adb -s emulator-5554 shell sh /data/server/bin/launch.sh
adb -s emulator-5554 forward tcp:65000 tcp:65000
```



### 用 Aurora 下载小红书

通过 [Aurora Store 发布页](https://f-droid.org/en/packages/com.aurora.store/) 安装 Aurora 4.8.4，然后在软件内安装小红书，可以直接用匿名用户安装。


### 首页推荐抓包

先启动模拟器和 firerpa，打开小红书，首次使用时手动同意隐私协议，保持未登录状态。确认可以在首页看到推荐内容之后，就可以开始测试了。

相关代码放在 `xhs-quickstart/`，在仓库目录里安装依赖，然后运行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r xhs-quickstart/requirements.txt
.venv/bin/python xhs-quickstart/main.py
```

运行之后，脚本会配置抓包环境，重新启动小红书并点击首页，等首页推荐返回后，把这一批笔记保存下来。这里用 mitmproxy 作为手机访问网络时的中间代理，通过 firerpa 安装测试证书来解密 HTTPS，再用 `adb reverse` 把安卓里的代理端口转发到 Mac。结束时会恢复代理设置并卸载本次安装的证书。

代码也都放在这个目录里：`main.py` 负责操作小红书和整理结果，`capture.py` 负责启动、清理抓包环境，`homefeed_addon.py` 负责从请求里取出首页推荐。

每次运行的结果会放在 `xhs-quickstart/runs/` 下，按时间分目录，终端也会打印本次的完整路径。仓库里保留了一份[抓包示例](xhs-quickstart/runs/example/)，不用运行代码也可以直接在 GitHub 上看[推荐笔记](xhs-quickstart/runs/example/recommendations.json)和[首页截图](xhs-quickstart/runs/example/02-homefeed-captured.jpg)。这次抓到了 19 条去重后的笔记，示例里的临时 token 和 URL 查询参数已去掉，其余运行结果由 `runs/.gitignore` 忽略。

一个运行目录里主要有这些产物：

- `recommendations.json`：从首页推荐响应里取出的笔记，按 ID 去重。这是接口返回的一批数据，不只是屏幕上同时能看到的几张卡片。
- `homefeed.jsonl`：首页推荐和频道分类的完整 JSON 响应，每行对应一个请求，包含请求地址、HTTP 状态和响应正文。
- `summary.json`：这次运行是否成功、抓到了多少条笔记，以及对应的笔记 ID。
- `01-guest-home.jpg`、`02-homefeed-captured.jpg`：进入首页和抓到推荐后的截图，同名 XML 文件是当时的控件树。
- `flows.mitm`、`flows.jsonl`、`mitmproxy.log`：完整抓包及代理日志。`flows.mitm` 可以用 mitmweb 打开，`flows.jsonl` 则是请求头、响应头和正文的文本导出。
- `ca/`、`proxy-before.json`：本次使用的测试证书和运行前的代理设置，供脚本配置和清理环境使用。

