# TG 工具箱交接文档（重开会话用）

> 本文档记录项目完整状态、关键机制、卡点与下一步，供新会话无缝继续。
> 最后更新：**2026-10-01，v1.2.1（发布提交 c40b053，tag v1.2.1）**。本文档基于全仓库复查整篇重写，替代 v1.1.0 时期旧版。

---

## 一、项目是什么

Telegram 小号批量维护工具箱（删联系人/删对话/退群/加群/拉黑 bot/更新客户端/tdata↔session 转换/passkey/新建账号导入），主形态 Web 版：

- **后端**：FastAPI（`server.py`）+ 引擎（`tg_engine.py`）+ 核心业务与 CLI（`tg_tool.py`）
- **前端**：Svelte 5 + @material/web 2.3（Material 3，Teal 青绿主题），源码 `webapp/src/`
- **壳**：pywebview（`web_main.py`）加载本地 FastAPI；pywebview/.NET 环境异常时自动降级浏览器模式（服务照跑，弹窗提示）
- **打包**：PyInstaller onedir（`TG工具箱Web.spec`），产物 `dist/TG工具箱Web/TG工具箱Web.exe`
- CLI（`python -X utf8 tg_tool.py`，账号目录内）仍可用；Tkinter GUI 已归档 `legacy/`（v1.0.0 起冻结不维护）
- **运行时账号数据**：`D:\Desktop\TG小号\`（不入库、不改目录结构）

## 二、当前状态快照（2026-10-01）

| 项 | 值 |
|---|---|
| 版本 | **v1.2.1**（`tg_tool.py:43` `APP_VERSION`，唯一权威；`/api/ping` 与前端顶栏读它） |
| 分支 | dev = main（v1.2.1 发布提交 c40b053，其后仅文档更新）；本地分支 `new-ui` = a5f97f8（「LocalSend 风 Teal 主题」旧提交，落后 102 提交，纯残留可删） |
| tag | v1.2.1 已打并推送，GitHub Release 带资产 TG-tools_v1.2.1.zip（≈30MB） |
| 发布线 | v1.1.0-beta.1→9 → v1.1.0 → v1.1.1 → v1.2.0 → v1.2.1；notes 归档 `docs/releases/` |
| v1.2.1 内容 | 修复拖入 zip 导入失败（包内账号数据多套一层文件夹时识别不到）+ 同含 session/tdata 的包被误判成 tdata（会多转出一条登录态） |
| v1.2.0 内容 | 新建账号三方式（拖包导入/扫码登录/手机号登录）+ 导入增强 + 加群频道页一体化 + 打包结果进剪贴板 + 安全加固（首页强制 token、Host 白名单）+ 一批修复 |
| 未完卡点 | ① passkey caBLE 等用户复测（见第七节）② 多设备 App 化待启动 M0（见第八节） |

## 三、环境

| 项 | 值 |
|---|---|
| 工作目录 | `D:\dsh\tgtools` |
| 部署目录 | `D:\Desktop\TG小号\TG工具箱Web\`（用户运行 exe 处；**E:\Telegram Desktop 是用户主号绝对不碰**） |
| Python | `C:\Python314\python.exe -X utf8`（必须 `-X utf8`） |
| Node/npm | `webapp/` 下 `npm run build`（Vite） |
| Git 远程 | `https://github.com/Gutouoff/TG-tools.git`（origin） |
| 终端 | MSYS bash（POSIX 语法，原生工具传 `C:/x` 正斜杠路径） |
| 已装依赖 | 见 requirements.txt（pin）：telethon 1.44.0 / opentele-ng 1.4.0 / fastapi 0.141.1 / uvicorn 0.52.4 / pywebview 6.2.1 / websockets 17.1 / qrcode 8.2 / pillow 12.3.0 / cryptography 50.0.1 / cbor2 6.1.4 / bleak 3.0.2 / python-socks 3.0.0 / openpyxl 3.1.5 |

**ROOT（账号根目录）解析规则**（server.py:38-45）：frozen 时 SCRIPT_DIR=exe 目录，onedir 下 ROOT=exe 目录的上级（部署态即 `D:\Desktop\TG小号\`）；源码态 ROOT=`tg_tool.SCRIPT_DIR` 的上级（即 `D:\dsh`）。所有账号路径必须过 `_ensure_in_root`（越界 400）。

## 四、标准流程：构建 → 打包 → 部署 → 发布

```powershell
# 1. 前端构建（webapp 目录）——改了 webapp/src/** 后必须先 build 再打包/部署
npm run build

# 2. 打包（tgtools 目录）
& C:\Python314\python.exe -X utf8 -m PyInstaller TG工具箱Web.spec --noconfirm

# 3. 覆盖部署（保留 avatars/profiles 缓存，不删；deploy.bat 同效）
Copy-Item 'D:\dsh\tgtools\dist\TG工具箱Web\*' 'D:\Desktop\TG小号\TG工具箱Web' -Recurse -Force

# 4. 提交 + 发布（bump APP_VERSION → 构建 → git tag v{版本} → 推送 → GitHub Release）
git checkout main; git merge --ff-only dev; git push origin main; git checkout dev
```

- **发布流程已固化为 skill `tgtools-release`**（版本 bump、前端构建、PyInstaller、部署、压缩包、tag、Release 资产上传），发版时直接调用。
- **沙箱注意**：`npm run build` 的 esbuild spawn 与 `git push`（读 Windows 凭据管理器）会 EPERM/Authentication failed，需放开沙箱权限重试。
- **流程铁律**：改了 `webapp/src/**` 忘 build 就打包 = 把旧界面带出去（`webapp/dist` 不入库）。

## 五、代码地图（行数为 2026-10-01 实测）

| 文件 | 行数 | 职责与改动注意 |
|---|---|---|
| `server.py` | 2176 | FastAPI 后端全部 REST/WS API；鉴权中间件、设置迁移、打包、静态首页注入 token。50+ 路由分组：基础(ping/accounts/ws)、连接(connect/disconnect/switch/online)、任务(tasks/*、speed、whitelist、poll-accounts、join-channels)、聊天资料(dialogs/history/chat.send/me/profile/*/avatar/2fa/email/*/devices)、转换(convert-to-tdata/convert-tdata/refresh-session/refresh-ss-batch)、账号管理(launch-client/open-folder/rename-account/delete-account/groups/*)、**新建账号(add-account/import/qrlogin/*/phonelogin/*)**、系统(update-telegram/settings/pack/export-accounts/passkeys/*) |
| `tg_engine.py` | 2264 | 引擎：线程+私有 asyncio loop、`_pool` 多账号连接池/秒切、任务、温和取消、进度回调；v1.2.0 新增 qr_login_start/poll/cancel、phone_login_start/submit/cancel、_write_json_from_me、poll_accounts |
| `tg_tool.py` | 1583 | 核心业务+CLI+`DEFAULT_TEXTS`(t0xx) 界面文本表+白名单(DEFAULT_USER/GROUP_WHITELIST)+代理+`SPEED_PRESETS`+APP_VERSION；`make_json_from_session`/`reconcile_converted_json` 供导入复用 |
| `webapp/src/App.svelte` | 4487 | 主 UI 全部：账号卡/分组/功能卡/弹窗/新建账号三流程/加群页/安全页。改动后必须 `npm run build` |
| `webapp/src/api.ts` | 373 | API 封装 + TOKEN + connectWS |
| `webapp/src/app.css` | 128 | Material 3 Teal 主题变量 + 深色模式（theme_mode 切换） |
| `cable.py` | 660 | passkey caBLE 完整实现（见第七节） |
| `web_main.py` | 121 | pywebview 壳；窗口尺寸记忆 settings.json；降级浏览器模式 |
| `tg_profile.py` | 363 | 资料缓存 worker：profiles.json + avatars/；DEAD 集合跳过死号；PHONE_CODE_MAP 区号表 |
| `tl_patch.py` | 283 | Telethon 1.44 新 message 构造体 3ae56482 注册；官方更新 layer 后自动失效，无需维护 |
| `tdata2session.py` | 119 | opentele-ng tdata↔session 独立转换（也被 tg_tool import） |
| `legacy/` | — | tg_ui.py（Tkinter，冻结）+ tdesktop 参考源码 reference/ |
| `docs/releases/` | — | 各版本 release notes |
| `界面文本.txt` | — | 全部界面中文外置；**运行目录那份才是活的，仓库这份是模板**；新增文案 = tg_tool.py DEFAULT_TEXTS 加 t0xx key + 此文件同步 |

## 六、关键机制（新会话必读）

### 6.1 鉴权与安全模型
- `TOKEN = secrets.token_urlsafe(32)` **每次启动随机生成，不落盘**；web_main 用 URL query 传给前端，前端从 `window.__TG_TOKEN__`（后端注入 index.html）或 URL query 读。
- 纯 ASGI 中间件 `_AuthMiddleware`（server.py:60）：**不走 BaseHTTPMiddleware**（会吞真实异常成 "No response returned"）；职责 = token 鉴权 + Host 白名单（仅 localhost/127.0.0.1，防 DNS rebinding）+ 异常兜底转 JSON（真实异常穿透到这层拿得到原因；SystemExit 等 BaseException 继续上抛）。
- `GET /` 也要 token（防本机恶意进程扫端口白拿控制权）；`/api/*` 查 `X-TG-Token`；**唯一例外** `/api/avatar-image` 放行 query token（`<img>` 带不了 header）。
- `_ensure_in_root` 路径校验；zip 解压三重防护（单文件/总量 1GB 上限、条目数上限、`commonpath` 路径越界校验）。
- 打包 `/api/pack`：**无 pack_password 必须拒绝**，7z AES-256（需系统装 7z），密码存 settings.json；产物复制进剪贴板后挪 `%TEMP%/tgpack`（超一天自动清理，不留在账号根目录）。
- 日志统一经 `_emit` 打码手机号（引擎日志不走 tg_tool.log，补一层 `_mask_phone_text`）。
- FastAPI 关闭 docs/redoc。

### 6.2 引擎模型
- `Engine`：私有线程 + asyncio loop，跨线程一律 `Engine._submit(coro, timeout)`（或 `asyncio.run_coroutine_threadsafe`）。
- 回调 on_log/on_progress/on_state/on_message 默认在**引擎线程**执行；Web 侧经 `_emit` → `run_coroutine_threadsafe(_ws_broadcast(...))` 广播到 WebSocket。
- **连接池 `_pool`**：账号名 → {client, me, info, dir}；connect 入池不踢旧连接；已在线再 connect = 秒切（`switch`）；`disconnect(name)` 只断指定、None=断当前（断后池里还有账号自动切过去）；`online_accounts()`；shutdown 清全池。
- **任务只作用「当前账号」**（self._client）；`stop_task` 温和取消（协程内 `_check_cancel` 检查取消标志）。批量 fan-out 到多账号是后续方向。
- 模块级可变量 `DIALOG_DELAY`/`CONTACT_*_DELAY` 被 `set_speed` 运行时改；SPEED_PRESETS 五档参数是用户钦定的精确值，**别改数字**。

### 6.3 账号数据模型
- 一个账号 = ROOT 下一个文件夹：`{名}.session` + `{名}.json`（凭据：phone/session_file/app_id/app_hash/device/sdk/app_version/user_id/first_name/last_name/username）+ 可选 `Telegram.exe` + tdata/。
- 目录名只是**本地别名**；json 里的 `user_id`（uid）已落盘且 profiles.json 也缓存——跨设备/跨列表的唯一标识用它。
- profiles.json（username/phone/uid/dc/avatar/first/last）+ avatars/ 由 tg_profile worker 维护；运行时还有 settings.json、whitelist.json、groups.json（全部 gitignored）。
- **绝不提交账号数据**：session/tdata/json/profiles/avatars/logs/backups/whitelist 全被 .gitignore 挡住；新增运行时产物同步更新 .gitignore。

### 6.4 新建账号三流程（v1.2.0 核心新增）
1. **拖包导入**（`/api/add-account` 顶栏拖放 + `/api/import` zip）：收 base64 文件列表 → 临时目录落盘（**文件名只去路径分隔符、不过 _clean_name——它会把扩展名的点清掉**）→ zip 自动解压（安全校验）→ `_find_account` 定位（平铺或一级子目录）→ tdata 自动转 session → 文件夹名 = session 文件名（tdata 包沿用 zip 名）→ **仅 session 时立即 `make_json_from_session` 补建凭据 json**（不等首次连接）→ 自动放 Telegram.exe。
2. **扫码登录**（`/api/qrlogin/start|poll|cancel`）：临时 client（公开桌面端凭据 app_id 2040 + 写死在 tg_engine.py 的 app_hash）在 `.qrlogin/` 划痕目录建 `qr_xxx.session` → 生成 `tg://login` 二维码（约 30 秒有效期）→ 前端轮询 `qr.wait()`（5s 超时循环返回 waiting/success/expired）→ 成功 `_qr_login_finalize`：按手机号建目录、disconnect 落盘、session+json 移入、复制客户端；取消则清理临时会话。划痕目录 `.qrlogin/` 在程序根下（*.session 已 gitignore）。
3. **手机号登录**（`/api/phonelogin/start|submit`）：start 发验证码 → submit 两步提交（验证码，开了 2FA 的号再带 password）→ 成功同样自动建号（session+json+客户端）。前端 async 赋值用 `flushSync` 驱动条件渲染（Svelte 5 坑，见第九节）。

### 6.5 设置体系（改设置必读）
- `DEFAULT_SETTINGS`（server.py ~1840）+ `_load_settings` 合并迁移：新设置项**必须加进 DEFAULT_SETTINGS**（否则被白名单过滤丢弃）。
- 已有迁移逻辑可参照：card_order 自动补新卡片（老 settings 缺新卡会让新功能不显示）、join_links 旧字符串→结构化条目、proxy dict 兼容字段。
- 主题 Teal 青绿：主色 #009688、顶栏 #00796B、浅青背景；`theme_mode` 控制深浅。

### 6.6 防风控纪律（铁律）
- 批量操作必须带随机间隔（速度五档）；后台串行任务每号间隔 1s；**FloodWait 自动等待不许删**。
- 删除逻辑只有白名单不删：用户 {5434838648, 6775358409, 238879089}、群 2284618069、Saved Messages；改默认白名单 = 改 tg_tool.py 的 DEFAULT_USER/GROUP_WHITELIST（界面可增删，持久化 whitelist.json）。
- bat 文件纪律：UTF-8 无 BOM + `chcp 65001` + 绝对路径 + 任何退出路径 pause。

## 七、passkey caBLE 状态（等用户复测）

`cable.py` 对照 tdesktop webauthn/ 源码完整移植，**核心密码学与协议逐字节对齐官方且单测通过**（QR CBOR 文本串修复、Noise 协议名 32 字节零填充、padding 粒度 32、CTAP 命令字节等已全修）。进展到：手机正常弹连接界面并广播 fff9，电脑侧 EID 解密成功 → 隧道 websocket → 握手首消息已发出；**当前卡在握手结果等用户复测**（成功标志：日志出现「安全握手…」「等待手机确认注册…」）。

- 官方参考源码在 `legacy/reference/`（tdesktop 7.1.5 webauthn/ 四个 cpp）。
- 诊断基建 `cable.py _detect` 保留：全 UUID 抓包、验密、变体探测；debug 日志（passkey_adv/mfg/diag）需 settings.json `log_level=debug` 才下发。
- 走通后清理 cable.py 诊断日志。

## 八、多设备 App 化规划（2026-10-01 已定案，待启动 M0）

### 8.1 目标与既定原则
每台设备（Android 优先，电脑保留）都是**完整节点**：能托管账号、执行 Telegram 操作、接收其他设备命令。账号所有权即宿主（session 只在一台设备运行，其他设备只发命令）；**不用租约**；备份文件不允许自动运行（防同 session 双端冲突）；迁移 = 源停号 → 加密传输 → 新宿主接管 → 更新映射；离线设备的账号不显示或标记不可用。技术栈不换（FastAPI + Svelte + pywebview），Android 用 Buildozer/p4a 打包。

### 8.2 技术核实结论（2026-10-01 已验证的事实）
- **Telegram 库 = Telethon 1.44.0，纯 Python**（非 TDLib）；本项目**从未安装 cryptg**，桌面端现在就跑在纯 Python AES（pyaes）上 → 「C 扩展 Android 编译」风险基本消除。
- 前端**已在用 @material/web 2.3**（Material 3 官方组件）→ 不需要 Quaff/SMUI/Smelte 选型，UI 重做 = 响应式改造 + LocalSend 风卡片。
- 账号 json/profiles.json **已存 user_id（uid）** → 跨设备合并键现成。
- `/api/pack` 的 7z AES-256 加密包逻辑可直接复用为迁移传输格式；WS 广播基建（/ws + _ws_broadcast）可直接复用为设备间命令通道。
- server.py:76 Host 白名单只放行 localhost —— 局域网模式需改为对端设备身份校验。

### 8.3 方向性决定
| 决定 | 结论 |
|---|---|
| 平台范围 | **Android only，iOS 明确排除**（Python 后台长驻不可行） |
| 网络范围 | **局域网优先**（UDP 广播/mDNS 发现 + 直连）+ 手动输 IP:port 兜底；跨网不自建中继，用户自行走 Tailscale/WireGuard |
| 设备配对加密 | 每设备首次运行生成 **Ed25519 身份密钥对**（身份=公钥，改名换 IP 不变）；QR 配对（设备名+IP:port+公钥指纹+一次性配对码）；通信走 TLS 自签证书 **pin 对方公钥**；每条命令带时间戳+nonce 签名防重放；**应用层 Noise 先不做**（协议头留版本位） |
| 账号唯一标识 | **Telegram user_id**（uid 已落盘）；目录名/手机号只是本地别名 |
| 迁移范围 | **不限电脑之间，手机也可作宿主**；Android 存 App 私有目录，session 格式与桌面同（同 Telethon 版本）天然兼容 |
| 全局映射 | **不引入全局存储**：每设备只持久化自己托管的账号，全局视图 = 本机 + 在线设备运行时聚合；无全局状态即无同步冲突 |

### 8.4 设计要点速答
- **命令协议**：REST 做查询、WebSocket 做命令与进度；**离线不排队**（宿主离线即不可用，与无租约一致），重试由发起方做。
- **账号状态四态**：本机托管 / 远程托管（可下发命令）/ 宿主离线（置灰）/ 仅备份（只能迁移或恢复）。
- **迁移流程**：源停号断连+停任务 → 复用 pack 打 AES-256 加密包（迁移密码交互输入）→ 传输 → 目标解包写入 → 目标验证连接 → 更新双方记录 → **最后一步才删源文件**（任何中断源都在，删除是显式确认）。
- **Android 打包链路**：必需依赖全纯 Python（FastAPI/uvicorn/websockets/qrcode 纯版 uvicorn、pillow 有 p4a recipe）；**裁掉 passkey（cryptography/cbor2/bleak）与 tdata 导入（opentele）后零 C 扩展**；Android 端不用 pywebview（后端质量存疑），用 p4a webview bootstrap 指向本地 FastAPI；构建环境 = WSL2 + buildozer + Android SDK/NDK（Windows 不能原生跑）；**共享后端代码保持 Python 3.11+ 兼容**（桌面 3.14，p4a recipe 通常只到 3.11/3.12）。
- **Android 保活**：前台服务（p4a service bootstrap + 常驻通知 + FOREGROUND_SERVICE 权限）。

### 8.5 里程碑与 M0 验证计划
M0 技术验证 → M1 设备发现与配对 → M2 列表互通与命令路由 → M3 账号迁移 → M4 移动端打包与保活 → M5 UI 重做与发布。

**M0 三件事**：① WSL2 装 buildozer + SDK/NDK（主要成本在此）；② 最小 demo：webview bootstrap + FastAPI/uvicorn + Telethon 用测试号 Dexpornuxiuo 登录并跑一次扫描（不真删）；③ 前台服务保活：熄屏 10 分钟连接不断。三项过了再进 M1。

### 8.6 风险清单（修订后）
- ~~TDLib 不可行~~（消除：用的是 Telethon）；~~C 扩展编译失败~~（降级：裁剪后零 C 扩展）。
- 新增：p4a 构建链在 WSL2 的版本匹配折腾度（M0 主要成本）；Python 3.14 与 p4a Python 的兼容窗口。
- 保留：Android 后台限制断长连接（前台服务缓解）；Telegram 风控（新设备登录提示，迁移/移动端登录用测试号渐进验证）；局域网监听安全（Ed25519+TLS pin 方案覆盖）；双端 session 冲突（备份不自动运行 + 单宿主原则覆盖）。

## 九、历史坑清单（踩过的别再踩）

1. **Svelte 5 async 赋值不重渲染**：`$state` 在 await 后赋值，`{#each}`/`{#if}` 不更新，必须 `flushSync` 包裹（手机号登录两步切换就是）。
2. **WebView2 缓存旧前端**：`/` 与 `/assets` 要加 no-cache 头。
3. **纯 ASGI 中间件**：BaseHTTPMiddleware 吞真实异常，别改回去。
4. **64 位 ctypes 句柄截断**：GlobalAlloc/SetClipboardData 必须声明 restype/argtypes。
5. **_clean_name 会清扩展名的点**：add-account 落盘文件名只去路径分隔符。
6. **opentele 数据文件**：打包必须 collect_data_files('opentele')（devices.json），缺了报 Errno 2；PIL 不全量收集（省 13MB，二维码走纯 zlib PNG）。
7. **zip 解压安全**：路径越界 commonpath 校验 + 大小/条目数上限，别删。
8. **冷启动 /api/online 500**：online_accounts 缺 on_done 参数已修——引擎带 on_done 的方法注意默认参数。
9. **部署覆盖不删**：保留 avatars/profiles 缓存（deploy.bat 覆盖式）。
10. **uvicorn 只装纯版**：uvicorn[standard] 带 C 扩展（httptools/uvloop），桌面 PyInstaller 白 bloated，Android 直接装不上。
11. **token 不落盘**：settings.json/日志/URL 之外不新增暴露点（约定）。
12. **zip 内账号数据多套一层文件夹**：拖入（`/api/add-account`）比「导入」按钮多解压一层（`临时目录/zip名/…`），`_find_account` 原只看两层 → 报「未识别到账号数据（需要 .session、tdata 或其压缩包）」；v1.2.1 起逐层往下找（3 层，跳过 `__MACOSX`）。另有：**同时含 session+tdata 的包必须按 session 判**，判成 tdata 会在导入时多触发一次转换、凭空多出一条登录态。
13. **工作区文件权限**：`D:\dsh\tgtools` 及其 `.git`/`build` 子目录缺当前用户写权限时，受限模式下 git 建不了 `.git/index.lock`、PyInstaller 删不掉 `build\TG工具箱Web\base_library.zip`（都是 Permission denied，且没有 sandbox 标记）；用 `diagnose-windows-sandbox-acl` skill 修该路径权限，或放开沙箱重跑那条命令即可。

## 十、测试

- 测试账号：`D:\Desktop\TG小号\Dexpornuxiuo`（用户授权随便删）。
- 死号（连接失败正常）：18296957526、Racoro、xxxCeay。
- CLI 回归：`printf '\n0\n' | python -X utf8 tg_tool.py`（账号目录内）。
- Web 后端冒烟：起服务后无 token 访问 /api/* 应 401、带 X-TG-Token 应 200；`/api/pack` 无 pack_password 必须拒绝；路径越界必须 400。
- 前端构建：`cd webapp && npm run build`。
- 多账号在线/秒切：连两个号 → 双击切号 → 断当前号自动切池内下一个。

## 十一、下一步建议（优先级序）

1. **passkey 复测**（唯一阻塞在用户侧）：用户用手机系统相机扫码，观察日志是否过握手；通过后清理 cable.py 诊断日志。
2. **多设备 M0 技术验证**（第八节 8.5）：WSL2 buildozer 环境 → 最小 demo → 保活验证。
3. 批量任务 fan-out：多账号已同时在线，可让删除等任务支持「对所有在线账号执行」。
4. 清理 `new-ui` 残留分支（已确认是旧主题提交，无独有内容）。
5. 改动 `webapp/src/**` 的任何提交前先 `npm run build`（铁律）。
