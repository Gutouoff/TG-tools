# TG 工具箱交接文档（重开会话用）

> 本文档记录项目完整状态、关键机制、卡点与下一步，供新会话无缝继续。
> 最后更新：**2026-11-08，v1.2.3 已发布，前端重构 Phase 1–4 完成、Phase 5 待开始**。旧版基于 v1.2.2 的章节已按当前代码校正。

---

## 一、项目是什么

Telegram 小号批量维护工具箱（删联系人/删对话/退群/加群/拉黑 bot/更新客户端/tdata↔session 转换/passkey/新建账号导入），主形态 Web 版：

- **后端**：FastAPI（`server.py`）+ 引擎（`tg_engine.py`）+ 核心业务与 CLI（`tg_tool.py`）
- **前端**：Svelte 5 + @material/web 2.3（Material 3，Teal 青绿主题），源码 `webapp/src/`
- **壳**：pywebview（`web_main.py`）加载本地 FastAPI；pywebview/.NET 环境异常时自动降级浏览器模式（服务照跑，弹窗提示）
- **打包**：PyInstaller onedir（`TG工具箱Web.spec`），产物 `dist/TG工具箱Web/TG工具箱Web.exe`
- CLI（`python -X utf8 tg_tool.py`，账号目录内）仍可用；Tkinter GUI 已归档 `legacy/`（v1.0.0 起冻结不维护）
- **运行时账号数据**：`D:\Desktop\TG小号\`（不入库、不改目录结构）

## 二、当前状态快照（2026-11-08）

| 项 | 值 |
|---|---|
| 版本 | **v1.2.3**（`tg_tool.py:45` `APP_VERSION`，唯一权威；`/api/ping` 与前端顶栏读它） |
| 分支 | `main` = `origin/main` = v1.2.3 发布提交 `1509748`；`dev` = `82939e4`，领先 main 48 个提交，其中 42 个尚未推到 `origin/dev` |
| tag | v1.2.3 已打并推送，GitHub Release 带资产 TG-tools_v1.2.3.zip（≈30MB） |
| 发布线 | v1.1.0-beta.1→9 → v1.1.0 → v1.1.1 → v1.2.0 → v1.2.1 → v1.2.2 → v1.2.3；notes 归档 `docs/releases/` |
| v1.2.3 内容 | 蓝色主题（#356AE6）+ 设置页分区导航 + 会话区刷新与可达性；配置结构无破坏性变更 |
| 当前工作 | 前端重构 Phase 1–4 已完成：拆 19 个组件、样式迁 `webapp/src/styles/app-ui.css`、文案外置 `webapp/src/texts/zh.ts`、26 条 Playwright 用例全绿；Phase 5 视觉重设计见 `docs/ui-phase5-plan.md` |
| 部署状态 | `D:\Desktop\TG小号\TG工具箱Web\` 仍是 2026-10-23 的 v1.2.3 程序；10-31 构建的新包未覆盖部署 |
| 未完卡点 | ① passkey caBLE 等用户复测（见第七节）② Android M0-D 卡 vivo 后台冻结（见第八节）③ UI Phase 5 未开始 |

## 三、环境

| 项 | 值 |
|---|---|
| 工作目录 | `D:\dsh\tgtools` |
| 部署目录 | `D:\Desktop\TG小号\TG工具箱Web\`（用户运行 exe 处；**E:\Telegram Desktop 是用户主号绝对不碰**） |
| Python | `python`（3.12.10，必须 `-X utf8`）；发版构建用临时 venv 安装依赖，见 `docs/RELEASE_BUILD.md` |
| Node/npm | `webapp/` 下 `npm run build`（Vite） |
| Git 远程 | `https://github.com/Gutouoff/TG-tools.git`（origin） |
| 终端 | MSYS bash（POSIX 语法，原生工具传 `C:/x` 正斜杠路径） |
| 已装依赖 | 见 requirements.txt（pin）：telethon 1.44.0 / opentele-ng 1.4.0 / fastapi 0.141.1 / uvicorn 0.52.4 / pywebview 6.2.1 / websockets 17.1 / qrcode 8.2 / pillow 12.3.0 / cryptography 50.0.1 / cbor2 6.1.4 / bleak 3.0.2 / python-socks 3.0.0 / openpyxl 3.1.5 |

**ROOT（账号根目录）解析规则**（`server.py` 顶部）：frozen 时 SCRIPT_DIR=exe 目录，onedir 下 ROOT=exe 目录的上级（部署态即 `D:\Desktop\TG小号\`）；源码态 ROOT=`tg_tool.SCRIPT_DIR` 的上级（即 `D:\dsh`）。所有账号路径必须过 `_ensure_in_root`（越界 400）。

## 四、标准流程：构建 → 打包 → 部署 → 发布

```powershell
# 1. 前端构建（webapp 目录）——改了 webapp/src/** 后必须先 build 再打包/部署
npm run build

# 2. 打包（tgtools 目录；依赖装在临时 venv 时换成该 venv 的 python）
python -X utf8 -m PyInstaller TG工具箱Web.spec --noconfirm

# 3. 覆盖部署（保留 avatars/profiles 缓存，不删；deploy.bat 同效）
Copy-Item 'D:\dsh\tgtools\dist\TG工具箱Web\*' 'D:\Desktop\TG小号\TG工具箱Web' -Recurse -Force

# 4. 提交 + 发布（bump APP_VERSION → 构建 → git tag v{版本} → 推送 → GitHub Release）
git checkout main; git merge --ff-only dev; git push origin main; git checkout dev
```

- **发布流程已固化为 skill `tgtools-release`**（版本 bump、前端构建、PyInstaller、部署、压缩包、tag、Release 资产上传），发版时直接调用。
- **沙箱注意**：`npm run build` 的 esbuild spawn 与 `git push`（读 Windows 凭据管理器）会 EPERM/Authentication failed，需放开沙箱权限重试。
- **流程铁律**：改了 `webapp/src/**` 忘 build 就打包 = 把旧界面带出去（`webapp/dist` 不入库）。

## 五、代码地图（行数为 2026-11-08 实测）

| 文件 | 行数 | 职责与改动注意 |
|---|---|---|
| `server.py` | 2389 | FastAPI 后端全部 REST/WS API（78 条路由）；鉴权中间件、设置迁移、打包、静态首页注入 token。分组：基础(ping/accounts/ws)、连接(connect/disconnect/switch/online)、任务(tasks/*、speed、whitelist、poll-accounts、join-channels)、聊天资料(dialogs/history/chat.send/me/profile/*/avatar/2fa/email/*/devices)、转换(convert-to-tdata/convert-tdata/refresh-session/refresh-ss-batch)、账号管理(launch-client/open-folder/rename-account/delete-account/groups/*)、**新建账号(add-account/import/qrlogin/*/phonelogin/*)**、系统(update-telegram/settings/pack/export-accounts/passkeys/*) |
| `tg_engine.py` | 2252 | 引擎：线程+私有 asyncio loop、`_pool` 多账号连接池/秒切、任务、温和取消、进度回调；qr_login_start/poll/cancel、phone_login_start/submit/cancel、_write_json_from_me、poll_accounts |
| `tg_tool.py` | 1576 | 核心业务+CLI+`DEFAULT_TEXTS`(t0xx) 界面文本表+白名单(DEFAULT_USER/GROUP_WHITELIST)+代理+`SPEED_PRESETS`+APP_VERSION；`make_json_from_session`/`reconcile_converted_json` 供导入复用 |
| `webapp/src/App.svelte` | 2263 | 主 UI 外壳与业务流程编排（账号/分组/任务/新建账号/移动端）；模板已组件化，业务状态与 `flushSync` 仍在脚本内。改动后必须 `npm run build` |
| `webapp/src/components/` | 19 个 / 1957 | 展示组件：TopBar/AccountCard/FunctionCards/ChatView/SettingsDialog/MobileApp 等；props 与回调由 App 注入 |
| `webapp/src/styles/app-ui.css` | 4996 | 全局界面样式（Phase 2-1 从 App.svelte 迁出）；颜色/尺寸必须引用 app.css 的令牌 |
| `webapp/src/app.css` | 260 | Material 3 颜色、圆角、间距、字号、阴影令牌 + 深色模式（`theme_mode`） |
| `webapp/src/texts/zh.ts` | 446 | 全部界面文案（399 条 key）与卡片显示名；模板禁止硬编码中文 |
| `webapp/src/api.ts` | 421 | API 封装 + TOKEN + connectWS |
| `cable.py` | 660 | passkey caBLE 完整实现（见第七节） |
| `web_main.py` | 121 | pywebview 壳；窗口尺寸记忆 settings.json；降级浏览器模式 |
| `tg_profile.py` | 356 | 资料缓存 worker：profiles.json + avatars/；DEAD 集合跳过死号；PHONE_CODE_MAP 区号表 |
| `tg_log.py` | 212 | 统一日志：分级、按天落盘、环形缓冲、手机号打码 |
| `tl_patch.py` | 283 | Telethon 1.44 新 message 构造体 3ae56482 注册；官方更新 layer 后自动失效，无需维护 |
| `tdata2session.py` | 117 | opentele-ng tdata↔session 独立转换（也被 tg_tool import） |
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
- profiles.json（username/phone/uid/dc/avatar/first/last）+ avatars/ 由 tg_profile worker 维护；运行时还有 settings.json、whitelist.json、groups.json、rename_pending.json（全部 gitignored）。
- **改名遇占用会排队**（v1.2.2）：`/api/rename-account` 撞上 WinError 5/32/33（客户端占着文件夹）时不报错，写进 `rename_pending.json` 待执行；`lifespan` 起的 `_pending_rename_worker` 每 10 秒调 `_pending_run_once` 试一次，成功广播 `state:rename_applied`，前端刷新列表与「待改名」徽标；`GET /api/rename-pending`、`POST /api/rename-pending/run|cancel` 对应「立即执行/取消」。**待执行条目最长留 3 天**。
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

## 八、多设备 App 化规划（M0-A/B/C 已通过，M0-D 卡 vivo 后台冻结）

### 8.1 目标与既定原则
每台设备（Android 优先，电脑保留）都是**完整节点**：能托管账号、执行 Telegram 操作、接收其他设备命令。账号所有权即宿主（session 只在一台设备运行，其他设备只发命令）；**不用租约**；备份文件不允许自动运行（防同 session 双端冲突）；迁移 = 源停号 → 加密传输 → 新宿主接管 → 更新映射；离线设备的账号不显示或标记不可用。技术栈不换（FastAPI + Svelte + pywebview），Android 用 Buildozer/p4a 打包。

### 8.2 技术核实结论（2026-10-01 评估后修订）
- Telethon 1.44.0 的核心代码偏纯 Python，且当前桌面端未安装 cryptg；这只能降低原生扩展风险，**不能证明 Android p4a 构建和运行已经可行**。
- Ed25519 不在 Python 标准库中。设备身份签名、TLS 和 passkey 依赖必须单独选择并验证 p4a recipe；不能再把 Android 方案描述为“零 C 扩展”。`cable.py` 已改为按需加载（缺可选依赖时 passkey 接口明确报错，不再拖垮整个服务），但 Android 首版仍需条件导入或平台拆分。
- 前端已使用 @material/web 2.3（Material 3 官方组件），UI 层可以复用组件和 API 模型，但桌面 pywebview 入口不能直接作为 Android 入口。
- 账号 JSON/profiles.json 中已有 user_id（uid），适合作为候选合并键；目标设备仍必须连接 Telegram 后用 get_me() 校验真实 UID，不能只相信缓存。
- 现有 /api/pack 依赖系统 7z/7za，不能直接用于 Android 迁移；迁移需要独立的可移植加密包格式，包含 KDF、AEAD、版本、文件清单、校验、大小限制和原子提交。
- 现有 /ws 只能复用连接和广播骨架，不能直接作为设备命令通道；设备协议需要新增身份认证、命令权限、request_id、回执、幂等、顺序和断线恢复。
- HTTP HostGuard 不保护 WebSocket scope；LAN 模式必须把本机 UI API 与设备 API 分离监听，并为 /device/* 单独实现 TLS、设备身份和权限校验。

### 8.3 方向性决定
| 决定 | 结论 |
|---|---|
| 平台范围 | **Android only，iOS 明确排除**；先做 APK/内测分发，商店发布另行评估 |
| 网络范围 | **局域网优先**（UDP 广播/mDNS 仅作发现优化）+ 手动输 IP:port 兜底；跨网不自建中继，用户自行走 Tailscale/WireGuard |
| 设备配对加密 | Ed25519 身份密钥和 TLS 传输密钥分开；二维码包含设备 ID、公钥指纹、一次性配对码和过期时间；设备 API 使用 TLS + pin + 应用层签名；密钥轮换、撤销和 Android Keystore 必须纳入实现；应用层 Noise 暂不做 |
| 账号唯一标识 | **Telegram user_id** 作为候选唯一键；目录名/手机号只是本地别名；目标必须以 get_me() 结果确认 |
| 迁移范围 | M0/M1 只支持已有 Telethon .session 的账号；tdata-only 账号暂不承诺 Android 直接接管；迁移必须使用可恢复状态机 |
| 全局映射 | 不引入中心化账号数据库，但每台设备必须持久化配对信任、宿主缓存、迁移日志和 owner epoch；运行时聚合不等于完全无状态 |

### 8.4 设计要点速答
- **进程拓扑**：Android 前台服务进程独占 FastAPI、Engine 和 Telethon clients；Activity/WebView 是控制面，通过本机 HTTP/WebSocket 或 Binder 重新连接服务。不能假设 p4a service 与 WebView 共享 Python 对象。
- **本机与设备 API**：本机 UI API 继续只监听 loopback 并使用本机 token；设备 API 单独监听 /device/*，使用 TLS、设备公钥、命令签名和权限校验，不能放宽现有 /api/* 的 HostGuard。
- **命令协议**：REST 做查询和任务状态恢复，WebSocket 做实时事件；命令必须有 request_id、account_uid、ownership_epoch、时间戳、nonce、签名、回执、幂等和取消语义；宿主离线不排队。
- **账号状态四态**：本机托管 / 远程托管（可下发命令）/ 宿主离线（置灰）/ 仅备份（只能迁移或恢复）。在线状态由缓存 TTL 和健康检查决定，不依赖永久心跳。
- **迁移流程**：源加锁、停止任务并断连 → 生成带 manifest/hash 的可移植 AEAD 加密包 → 传输到目标暂存区 → 解包校验 → 目标用 get_me() 校验 UID 并连接验证 → 提交新的 owner epoch → 双方写迁移日志 → 源文件删除保持显式确认；任一步中断都进入可恢复状态。
- **Android 打包链路**：p4a webview bootstrap 只负责 Android 入口；共享业务代码保持 Python 3.11 语法兼容，但依赖按 Android/桌面分别锁定；允许密码学和平台依赖使用经 p4a 验证的原生扩展；M0 首版不包含 tdata 转换、桌面操作和 7z。
- **Android 保活**：前台服务、常驻通知和正确的 Android 服务声明只是基础条件；必须覆盖通知权限、前台服务类型、Doze、厂商省电、强停、重启和连接恢复。

### 8.5 里程碑与 M0 验证计划
- **M0-A：构建与平台边界**：固定 p4a/Buildozer/Docker、SDK/NDK 和 Python 版本；完成 ARM64 debug APK、Android 私有数据目录、条件依赖和独立入口。
- **M0-B：Telethon 服务生命周期**：服务进程独占 Engine/Telethon，完成已有 .session 的单账号连接、get_me()、只读扫描、断网重连、服务重启和 UI 重连。
- **M0-C：后台与网络**：覆盖熄屏、Doze、Wi-Fi/蜂窝切换、设备重启、划掉应用、强制停止和厂商省电模式；至少完成过夜测试，再评估 24–72 小时稳定性。
- **M0-D：密码学与传输原型**：完成身份密钥、TLS/mTLS 或明确的应用层认证、二维码配对、密钥存储、证书 pin、重放拒绝和设备撤销。
- **M1**：手动 IP 和 mDNS 发现、设备列表与配对。
- **M2**：只读账号聚合和带 ACL 的远程查询。
- **M3**：带 request_id、回执、幂等、取消和断线恢复的安全命令。
- **M4**：可恢复迁移状态机、可移植加密包和 owner epoch。
- **M5**：异常恢复、密钥轮换、UI 重做和内测发布。

**M0 通过条件**：干净 Android 真机能安装并启动 APK；前台服务能独立持有 Telethon 连接；WebView 能重新连接服务；已有 .session 能完成只读操作；断网、熄屏和服务重启后状态可恢复。M0 通过前不进入设备互通开发。

### 8.6 风险清单（修订后）
- **M0-A 构建链已打通并通过真机验证（2026-10-20）**：WSL2 3.0.1 + Ubuntu 26.04.1 + OpenJDK 17 + uv CPython 3.11.17 + Buildozer 1.6.0 下，`android_m0a/` 成功构建 ARM64 debug APK `bin/tgtoolsm0a-0.1.0-arm64-v8a-debug.apk`（21.3 MB，仅 `lib/arm64-v8a/`，13 个原生库），Gradle `BUILD SUCCESSFUL`。已在 vivo V2012A（Android 12 / arm64-v8a）安装并启动，界面显示 `TG-tools Android M0-A / Build entry ready`。环境复现见 `android_m0a/setup_wsl_env.sh`，p4a wheel 直链补丁见 `android_m0a/patch_p4a.sh`。
- **M0-A 已踩过的构建坑**：WSL `E_UNEXPECTED`（需 `wsl --update`）、`skia.googlesource.com` 不可达（libjxl/skcms 子模块）、GitHub TLS 间歇中断、git `transport 'file' not allowed`、libffi 缺 autotools m4 宏、p4a 把 android wheel 直链写进 requirements.txt 导致 pip 拒绝、中断后 venv 内 pip 半升级。处理办法已写入 `android_m0a/README.md`。
- **M0-B1 已通过（2026-10-20）**：`android_m0b/` 把 Telethon 打进 APK，真机返回 `python 3.14.2 / telethon 1.44.0 / http listening 127.0.0.1:8787`，本地 HTTP 服务可经 `adb forward` 从 PC 访问。
- **服务层选型已定（2026-10-20）**：Android 侧不引入 FastAPI/pydantic，改用 Starlette + 231 行兼容垫片 `android_m0b/fastapi_shim.py`。依据：`server.py` 2358 行里**零处直接使用 pydantic**，78 个端点全用 `body: dict`，FastAPI 导入点仅 5 处。垫片验证结果：78 条路由注册、鉴权 401/200、JSON body 注入、查询参数/路径参数、`HTTPException` 404/422、WebSocket 广播全部通过（`test_shim.py` + `test_shim_ws.py`，均 ALL PASS），且**未修改 `server.py` 一行**。详见 `docs/ANDROID_FASTAPI.md`。
- **Android 服务层依赖白名单**：`starlette uvicorn h11 click anyio idna websockets typing-extensions`；禁止引入 `httptools` / `uvloop` / `watchfiles` / `pydantic-core`（C 或 Rust 扩展，Android 无预编译 wheel）。
- **手机端设置改为「列表 → 子页」钻取（2026-10-24 第四轮）**：原先手机端设置是"顶部横滑标签 + 正文"，与主流 App 的交互不一致。改为业界通行的钻取结构：
  - **根页**：标题「设置」+ 关闭；按 `配置 / 工具 / 帮助` 分组，每组一张卡片，行内为「图标 + 标题 + 副标题 + 当前值 + ›」；行高 64dp。
  - 当前值直接回显：通用=常规/调试、外观=浅色/深色、代理=未启用或 `host:port`、加群频道=`N 个`、白名单=`N 项`、关于=`v1.2.3`。
  - **子页**：顶栏变 `‹  + 分区标题 + ✕`，正文复用原有表单（`set-content`），底部「保存设置」吸附。
  - 实现：新增 `mobileSettingsSection`（null=根页），`openSettingsSection()` 同时设 `settingsSection` 与它；`loadSettings()` 每次打开重置回根页；用 `.set-mobile-sub` 类切换根页/子页显隐。
  - 桌面端完全不受影响：`.set-mobile-head` / `.set-mobile-root` 基础规则为 `display: none`，只在 `max-width: 899px` 下启用；桌面仍用左侧导航 + 右侧内容的两栏弹窗。
  - 真机验证：根页分组与回显值正确，点「通用」进入子页、点 `‹` 返回根页均正常。
- **手机端动效（2026-10-24 第三轮）**：按 Material 3 motion token 补齐动效，时长取 short4 200ms / medium1 250ms / medium2 300ms，缓动 `cubic-bezier(0.2,0,0,1)`（standard）与 `cubic-bezier(0.05,0.7,0.1,1)`（emphasized-decelerate）：
  | 场景 | 效果 |
  |---|---|
  | 页签切换 | `{#key mobileTab}` 强制重挂载，整页淡入 + 上移 10px（200ms） |
  | 账号列表 | 逐行错峰入场，每行延迟 24ms |
  | 底栏激活 | 指示器 scaleX 0.4→1 弹出（250ms），标签颜色渐变 |
  | 按压反馈 | 行/按钮 scale(0.975)，120ms |
  | 详情面板 | 底部上滑 18px（300ms）+ 遮罩淡入 |
  | 设置弹窗 | 整屏上滑 280ms |
  | 连接状态点 | 呼吸 2.4s 循环 |
  | 进度条 | 宽度 300ms 平滑推进 |
  同时关闭 Android WebView 默认的蓝色点击高亮（`-webkit-tap-highlight-color: transparent`），改用 M3 状态层，并加 `touch-action: manipulation` 去掉点击延迟。
  **已验证**：构建产物含全部关键帧；真机抓转场中间帧可见内容淡入与指示器中间态，且蓝色高亮已消失。
  已支持 `prefers-reduced-motion: reduce`，系统开启「减弱动态效果」时全部退化为瞬时。
- **手机端 UI 按 Google 规范校准（2026-10-24 第二轮）**：对照 Android 无障碍规范（可点目标 ≥48×48dp）、Material 3 导航栏规范（3–5 个目标、标签常显、激活态用指示器承载）、M3 字体阶梯与色彩角色，修正了第一版手机壳的临时值：
  | 项 | 修正前 | 修正后 |
  |---|---|---|
  | 触控目标 | 关闭/加号 34–36px | 一律 48px；底栏项 min-height 48 |
  | 底栏激活态 | 仅变色 | 图标下 56×28 胶囊指示器（secondary-container） |
  | 字号 | 17 / 14.5 / 12 / 11.5 混用 | title 22 / body 16 / body-medium 14 / label 12 |
  | 色彩 | 硬编码 `#DCE6FF` 等 5 组 | 全部改用 M3 角色 token |
  | 间距 | 6/7/9/11/13 混杂 | 4dp 栅格，屏边 16dp |
  | 列表项高 | ~66px | 双行 72dp；设置行 56dp |
  | 无障碍 | 无焦点样式、无 aria-current | 加 `:focus-visible` 描边与 `aria-current="page"` |
  注：`m3.material.io` 与 `developer.android.com` 正文由 JS 渲染，直接抓取只能拿到空壳；数值依据取自 Android 无障碍文档、Compose NavigationBar 文档与 M3 token 定义。
- **手机端 UI 重做（2026-10-24）**：`webapp/src/App.svelte` 新增**窄屏专用手机壳**（`max-width: 899px`），桌面三栏完全不受影响。手机壳结构：品牌栏（账号数/在线数/新建）→ 搜索 + 分组胶囊 → 账号行（头像、在线点、状态标签、连接/切换）→ 底部四页签（账号 / 当前 / 动态 / 更多）。
  - 「当前」页：账号卡（头像、名称、在线状态、连接/断开/重连/启动客户端）+ 账号管理入口 + 常用操作九宫格。
  - 「动态」页：进度条 + 移动端日志流（按 warn/error 着色）。
  - 「更多」页：设置、外观切换、群组频道、新建账号、运行日志、版本号。
  - 深页（资料/聊天/安全/设备/群组/日志）复用原有右侧面板，通过 `.layout.mobile-panel-open` 全屏呈现，并加手机专用返回栏。
  - **设置弹窗在手机端改为全屏单栏**：新增 `.set-mobile-head`（标题 + 关闭），设置导航变成顶部横向可滚动胶囊，原来 174px 侧栏在手机上会把正文压成竖排文字。
  - 所有尺寸使用 `env(safe-area-inset-*)` 适配刘海与底部手势条；桌面样式与业务逻辑零改动。
  - 真机验证（vivo V2012A / Android 12）：四个页面、设置弹窗、面板返回均正常。
- **Android App 跑起来了（2026-10-24，重要节点）**：新建 `android_app/`，用 **`p4a.bootstrap = webview`** 把桌面版前端原样跑在 Android WebView 里，后端仍是同一个 `server.py`（经 Starlette 垫片）。真机验证：`app.log` 显示 `routes=79`、`ui_token written`、`server listening 127.0.0.1:5000`；界面完整加载 TG小号工具箱（顶栏/分组/搜索/基本信息/聊天/安全）；PC 经 adb forward 验证 `/api/ping` 200、`/` 带 token 200 且注入 `window.__TG_TOKEN__`、`/` 无 token 401、`WS /ws` 连接成功。APK 仅 **11.5 MB**（Kivy 版 23 MB）。构建：Windows 先 `cd webapp && npm run build`，再 WSL 内 `bash android_app/build_apk.sh`。
- **WebView 架构的关键细节**：① 端口必须 5000（p4a 的 `WebViewLoader` 模板 `{{ args.port }}` 实测渲染为 5000，Python 必须监听同端口）；② `server.py` 的 `/` 强制要求 `?token=`，故 Python 把 token 写入私有目录 `ui_token`，再 patch `WebViewLoader` 加 `buildUrl()` 读取拼进 URL（其他 App 读不到私有文件，防护不变）；③ `source.include_exts` 必须放开 html/js/css，否则前端产物被排除；④ 前端要放在构建目录的 `webapp/dist`，因为 `server.py` 从 `BASE/webapp/dist` 读取。
- **M0-D 被 vivo 厂商冻结卡住（2026-10-23 结论更新）**：`android_m0d/` 把服务层搬进独立进程的前台 Service，已确认 `services = tgtools:service.py:foreground:foregroundServiceType=dataSync` 生成 `org.tgtools.tgtoolsm0d.ServiceTgtools`、进程 `:service_tgtools`、`isForeground=true`、服务内真实 `server.py` 起在 8788、PC 经 adb forward 拿到 200。**但退后台约 60 秒后整个进程被 vivo 冻结**（`4:freezer:/frozen`），拉回前台立即解冻。已逐一排除：前台服务、通知通道 IMPORTANCE_LOW（已 patch p4a 并验证 `mImportance=2`）、PARTIAL_WAKE_LOCK、setAutoRestartService、doze 白名单、屏幕常亮（`mWakefulness=Awake`）。执行冻结的是 `com.vivo.abe`，标准机制全部无效。**已穷尽官方特权路径**：`dpm set-active-admin` 注册设备管理员无效；清空账号 + 删除应用分身用户 999 后成功设为 **Device Owner**（`dpm list-owners` 显示 `DeviceOwner,Affiliated`），**冻结依旧**（`4:freezer:/frozen`）。为此给 APK 声明了 `android:testOnly="true"`（安装需 `adb install -t`），验证后用 `dpm remove-active-admin` 撤销，已回到 `no owners`。**结论：厂商冻结与 Android 特权体系完全解耦。** 剩余路径：① 人工加 vivo i管家自启动/后台高耗电白名单复测；② 否则按"仅前台可用"设计产品（服务状态 UI 化、在线状态动态化、常驻需求留在桌面端）。详见 `android_m0d/README.md`。
- **通知通道陷阱**：Android 的 NotificationChannel 一旦创建，重要性**无法**再修改；覆盖安装会保留旧通道。改 `IMPORTANCE` 后必须 `adb uninstall` 再全新安装才能生效（本次踩过，`mImportance` 一直是 0）。
- **M0-D 踩到的坑**：pyjnius 把 Python `str` 传给 `Intent.putExtra` 会匹配 `putExtra(String, CharSequence)` 重载，服务端 `getString()` 返回 null 导致 `onStartCommand` NPE（用 `cast` 也无效，正确做法是用 spec 的 `foreground` 选项）；service 进程 stdout 不进 logcat，必须重定向到私有目录文件并挂 `threading.excepthook` 才能定位"活着但不应答"；`server.start_server()` 绑定失败时仍返回端口号，会掩盖端口冲突。
- **M0-C 已通过（2026-10-20）**：`android_m0c/` 把**真实 `server.py`** 经 Starlette 垫片打进 APK，真机自测 `selftest: PASS no-token=401 with-token=200`、`routes: 77`；PC 经 `adb forward` 外部验证 无 token 401 / 错误 token 401 / 正确 token 200，WebSocket 错误 token 握手 403、正确 token accept。APK 内为 starlette 1.9.0 + uvicorn 0.54.0 + websockets 17.3，**无 pydantic 与任何 C/Rust 扩展**。构建脚本 `android_m0c/build_apk.sh`（复用 recipe 缓存，Gradle 约 2 秒）。注意 `main.py` 里把 token 固定为 `poc-m0c-verify` 仅为 PoC 验证，接入生产前必须删掉。
- **M0-B2 已通过（2026-10-20）**：真机上 Telethon 经 SOCKS5 代理完成真实 MTProto 握手，返回 `mtproto: connected dc=2 server=149.154.167.51 via socks5 192.168.31.97:7897`。代理为 PC 上的 Clash Verge（`verge-mihomo`，7897，允许局域网），APK 内含 `python-socks 3.1.1`。直连 DC 仍超时（网络封锁），故 Android 侧必须把代理作为一等公民。
- **M0-B1 两个硬约束（会影响后续设计）**：
  1. **Telethon 必须在 Kivy 主线程导入**。放在启动期后台线程会抛 `ClassNotFoundException: org.kivy.android.PythonService`（类加载器未就绪）。`tg_engine` 自带 asyncio 线程，首次导入不能裸放在后台线程里。
  2. **直连 Telegram DC 在当前网络不可用**。手机与 PC 同时测 `149.154.167.51:443` / `149.154.175.50:443` 均失败，属网络封锁，不是应用缺陷；M0-B 的连通验证必须配置代理后进行。
- **FastAPI 在 Android 上的关键阻塞**：FastAPI 0.141 需要 pydantic v2 → `pydantic-core` 是 Rust 扩展，PyPI 上没有 Android/arm64 wheel；`pydantic` 1.x 同样只有平台 wheel。要用 FastAPI，必须为 `pydantic-core` 交叉编译 Rust，或改造服务层移除 pydantic 依赖。M0-B1 因此先用 stdlib `http.server` 验证运行时，把问题解耦。
- Telethon/FastAPI/uvicorn/websockets/SQLite/SSL/代理库和密码学依赖尚未完成 ARM64 真机验证；M0-B1 只验证了 Telethon 导入与本地 HTTP。
- Android 前台服务可能被 Doze、厂商省电、用户强停或系统重启影响；必须有服务恢复和 UI 重连设计。
- 当前桌面入口、ROOT 推导、tdata 转换、Explorer、剪贴板、Telegram.exe 更新和 7z 不能直接进入 Android 共享运行时。
- 局域网 mDNS/UDP 可能受多播锁、AP 隔离、VPN、IPv6 和 Tailscale 网卡影响；发现结果必须经过设备身份认证，手动 IP 保留。
- 迁移存在网络分区和源设备重启造成的双宿主风险；需要 transfer_id、owner epoch、fencing 或可恢复人工状态机。
- 账号 session 复制、DC、代理、UID、tdata-only 范围和 Telegram 风控需要真实测试号验证。
- 应用商店合规、前台服务类型和通知权限另行评估；M0 先使用 APK/内测分发。

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
- 前端 E2E：`cd webapp && npx playwright test`（26 条：交互 + 13 张视觉基线 + 深色/手机端 + 文案与运行时错误守卫；自动 build + preview）。有意改视觉后跑 `npm run test:e2e:update`，必须人工看 PNG diff。
- 前端契约守卫：`flushSync` 保持 21 处；`.log`、`.chat-history`、`.ctx`、`details.card` 选择器不能改；分组按钮 padding/高度不能动（见 `docs/UI_REFACTOR_RISKS.md`）。
- 多账号在线/秒切：连两个号 → 双击切号 → 断当前号自动切池内下一个。

## 十一、下一步建议（优先级序）

1. **UI Phase 5 视觉重设计**：按 `docs/ui-phase5-plan.md` 执行。先定色板（沿用 v1.2.3 的 #356AE6，或换方案里的深蓝），再按「令牌 → 密度 → 账号列表 → 功能卡/进度 → 危险弹窗 → 手机端」推进；每个改动单独 build + 26 条全绿 + 单独 commit。
2. **发版**：Phase 5 完成后 bump `APP_VERSION`（新外观建议 1.3.0，纯修复则 1.2.4）→ 构建 → 部署 → tag → GitHub Release；发版前先把 `dev` 推到 `origin/dev` 备份。
3. **passkey caBLE 复测**：等用户按第七节的成功标志验证；走通后清理 `cable.py` 诊断日志。
4. **Android M0-D**：vivo 后台冻结按「仅前台可用」设计，或人工加 i管家白名单复测；Android 实验与文档保留在 `android-m0-local` 分支，不混入桌面发版。
5. **批量任务 fan-out**：排在 UI 与 Android 之后。
6. 改动 `webapp/src/**` 的任何提交前先 `npm run build`（铁律）。
