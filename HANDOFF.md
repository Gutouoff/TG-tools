# TG 工具箱交接文档（重开会话用）

> 本文档记录当前项目的完整状态、关键技术细节、卡点和下一步，供新会话无缝继续。
> 最后更新：dev = v1.3.0-beta.1（**Bot 收件箱**新功能，见「六c」）；此前 main/dev = v1.1.0 正式版（143cddd+，v1.2.0 新建账号已发）

---

## 一、项目是什么

Telegram 小号批量管理工具箱，Web 版架构：
- **后端**：FastAPI（`server.py`）+ 引擎（`tg_engine.py`）+ 核心业务（`tg_tool.py`）
- **前端**：Svelte 5 + @material/web（Material 3），源码在 `webapp/`
- **壳**：pywebview（`web_main.py`）加载本地 FastAPI 服务
- **打包**：PyInstaller onedir（`TG工具箱Web.spec`）

## 二、环境

| 项 | 值 |
|---|---|
| 工作目录 | `D:\dsh\tgtools` |
| 部署目录 | `D:\Desktop\TG小号\TG工具箱Web\`（用户运行 exe 的地方）|
| Python | `C:\Python314\python.exe -X utf8`（必须加 `-X utf8`）|
| Node/npm | `webapp/` 目录下 `npm run build` |
| Git 远程 | `https://github.com/Gutouoff/TG-tools.git`（origin）|
| Git 分支 | `main`（权威，已推送）；`dev`（开发）|
| 已装依赖 | telethon 1.44、fastapi、uvicorn、pywebview、websockets、qrcode、cryptography、cbor2、bleak（+winrt）|

## 三、构建 → 打包 → 部署 → 推送 标准流程

```powershell
# 1. 前端构建（webapp 目录）
npm run build

# 2. 打包（tgtools 目录）
& C:\Python314\python.exe -X utf8 -m PyInstaller TG工具箱Web.spec --noconfirm

# 3. 覆盖部署（保留 avatars/profiles 缓存，不删）
Copy-Item 'D:\dsh\tgtools\dist\TG工具箱Web\*' 'D:\Desktop\TG小号\TG工具箱Web' -Recurse -Force

# 4. 提交 + 推送（main）
git add -A
git commit -m "xxx"
git checkout main; git merge --ff-only dev; git push origin main; git checkout dev
```

**沙箱注意**（重要）：

> ⚠️ **流程铁律**：改了 `webapp/src/**` 后必须先 `npm run build` 再提交/打包/部署——`webapp/dist` 不入库，部署产物用的是构建时刻的前端，漏 build 会把旧界面带出去。
- `npm run build` 里的 esbuild `spawn` 会触发 EPERM，需要 `sandbox_permissions: danger-full-access` 重试。
- `git push` 读 Windows 凭据管理器也会报 Authentication failed，同样要 `danger-full-access`。
- 若 approval policy 是 `never` 且 file policy 是 `danger-full-access`，则不用设 `sandbox_permissions`，直接跑。

## 四、关键文件地图

| 文件 | 职责 |
|---|---|
| `server.py` | FastAPI 后端（~1080 行）：token 鉴权、账号/连接/任务/pack/settings/安全 API |
| `web_main.py` | pywebview 壳，加载 `http://localhost:{port}/?token=`（注意是 localhost，为 WebAuthn rp.id）|
| `tg_engine.py` | 引擎：线程 + asyncio loop、连接、任务、进度回调；passkey 相关方法在 ~810 行 |
| `tg_profile.py` | 资料/头像缓存 worker（`AVATAR_DIR`、`refresh_one`、`avatar_path` 返回 .jpg）|
| `tg_tool.py` | 核心业务 + 白名单 + 界面文本 + 代理 |
| `cable.py` | **caBLE（passkey 蓝牙）完整实现**（本会话新增，重点）|
| `tg_bot.py` | **Bot 收件箱**（v1.3.0-beta.1 新增）：本地 TG bot，识别转发的账号文件并归档 |
| `webapp/src/App.svelte` | 主 UI（~1515 行）：账号卡、功能卡片、设置弹窗、passkey 页 |
| `webapp/src/api.ts` | API 封装 + TOKEN + connectWS |
| `webapp/src/app.css` | Material 3 主题（Teal 青绿）+ 深色模式 |
| `TG工具箱Web.spec` | 打包配置（hiddenimports 已含 cryptography/cbor2/bleak/winrt）|
| `deploy.bat` | 手动部署脚本（覆盖部署保留缓存）|

## 五、主题（已完成）

- 浅色 = Teal 青绿：主色 `#009688`、背景 `#F7FAF9`、卡片 `#FFFFFF`、顶栏 `#00796B`
- 深色 = 顶栏 🌙 切换，`data-theme='dark'` 变量集在 app.css
- 后端 `DEFAULT_SETTINGS`（server.py ~798 行）和 settings.json 都已更新为 Teal
- settings.json 里 `theme_mode` 控制浅/深色

## 六、卡片折叠记忆（已修复 2026-09-04）

- 根因：浏览器对初始 `open` 属性异步派发 `toggle` 事件,此时 cardOpen 还是默认值,onCardToggle 把默认状态写回 settings.json 覆盖保存值。
- 修复：`cardOpenRestored` 标志（恢复完成前忽略 toggle）+ 恢复后按 `data-card` 属性直接同步 DOM open。

## 六b、多账号同时在线（2026-09-04 新增）

- 引擎 `Engine._pool`：账号名 → {client, me, info, dir}。`connect` 不再踢旧连接而是入池；已在线再 connect = 秒切不重连。
- 新引擎方法：`switch(name)`（秒切）、`disconnect(name)`（只断指定,None=断当前,断后池里还有账号则自动切过去）、`online_accounts()`、`shutdown` 清空全池。
- 新接口：`POST /api/switch` {name}、`GET /api/online`、`POST /api/disconnect` 可带 {name}；`/api/connect` 响应多带 `online` 列表。
- 前端：头像橘点=连接池在线;双击在线账号=秒切;账号右键菜单有「断开连接（保持其他在线）」;页面刷新后 `GET /api/online` 恢复徽标;WS 新增 `switched`/带账号名的 `disconnected` 事件处理。
- 注意：所有任务仍只作用于「当前账号」（self._client）,批量 fan-out 到多账号是后续方向。

## 六c、Bot 收件箱（v1.3.0-beta.1 新增）

- **形态**：`tg_bot.py` 的 `BotInbox`——独立线程 + 独立 asyncio loop（与引擎同款的 client 单循环纪律），Telethon `MemorySession` + `client.start(bot_token=...)`，代理沿用 `tg_tool.resolve_proxy()`，bot 客户端用 Telegram Desktop 公开凭据（2040/b18441…，与 tdata 转换一致）。
- **配置**：settings.json 新增 `bot_token` / `bot_allowed_ids`（int 列表，_load_settings 归一化）/ `bot_on`（启动自启，在 server lifespan 里拉起）。token 与 pack_password 同级明文存本地。
- **安全**：仅 `bot_allowed_ids` 内的用户可推送；列表外用户发消息只回他的 ID（1 小时冷却防刷屏），便于 onboarding。**坑**：Telethon NewMessage 收发都触发，handler 必须排 `msg.out`，否则 bot 对自己的回复再回复（自我循环）。
- **合并逻辑**：同一用户 4s 安静窗口内的连续转发合并成一批；每批里**每个 zip 单独成一个账号**，散文件（session/json/2fa.txt）合并成一个账号；支持类型白名单 .session/.session-journal/.json/.zip/.txt，单文件上限 512MB。
- **归档共用**：server.py 把原 `/api/add-account` 的步骤 2-6 抽成 `async _ingest_account_dir(tmp, passwords)`（拖放导入与 bot 共用），并新增 `_extract_zip`：**zipfile 打不开的包按 7z AES 加密包处理**，候选密码 = 转发说明文字 + settings.pack_password，需系统装 7-Zip。
- **接口**：`GET /api/bot`、`POST /api/bot/start`（wait_ready 45s 内回连接结果）、`POST /api/bot/stop`；保存 settings 时 `bot_allowed_ids` 热更新不用重启；WS 事件 `state:bot`（状态变更）与 `state:bot_imported`（前端据此刷新账号列表）。
- **前端**：设置弹窗新增「🤖 Bot收件箱」页（token/允许 ID/自启/启停按钮/状态）。
- **测试**：归档逻辑单测（散文件/重名 _2/仅 session 自愈打桩/tdata zip/加密 zip 无 7z/zip slip/无关文件）+ API 冒烟（401、bot 状态、未配 token 拒启动、settings bot 键读写）全过；真 bot 联调需用户提供 token 实测。

## 七、passkey caBLE（重点，未完全走通）

### 已完成
`cable.py` 完整移植了 Telegram 官方（tdesktop）的 caBLE 流程，**核心密码学全部单测通过**：

1. QR 生成：`FIDO:/` + BytesToDigits(CBOR map {0:压缩公钥,1:secret16,2:域名数,3:时间戳,4:false,5:"mc"})
2. Noise NKpsk0 握手（协议名 `Noise_KNpsk0_P256_AESGCM_SHA256`，prologue=1）
3. Crypter（AES-GCM + 16 字节对齐 padding，nonce 前 4 字节大端 counter）
4. DecryptAdvert（AES-256-ECB 解密 16 字节 EID + HMAC-SHA256 前 4 字节校验）
5. CTAP makeCredential 请求/响应（CBOR）
6. 完整流程 `register_via_cable`：QR → BLE 扫描(bleak) → tunnel websocket → 握手 → CTAP → 返回 credential
7. 后端集成：`/api/passkeys/init` 启动后台 caBLE 流程 + 返回二维码图片；完成后 `RegisterPasskey` 提交
8. 前端：显示二维码 + WebSocket 实时进度（passkey_scanning/connecting/handshake/awaiting/done/error）

### 关键常量（cable.py）
```python
TUNNEL_DOMAINS = ["cable.ua5v.com", "cable.auth.com"]
# DerivedValueType: EidKey=1, TunnelId=2, Psk=3（HKDF info 用 4 字节小端）
# eid_key = HKDF(secret, salt={}, info=b'\x01\x00\x00\x00', 64)
# psk = HKDF(secret, salt=eid(16字节), info=b'\x03\x00\x00\x00', 32)
# tunnel_id = HKDF(secret, salt={}, info=b'\x02\x00\x00\x00', 16)
# EID 结构: [0]=0, [1:11]=nonce, [11:14]=routing_id, [14:16]=domain(小端)
# 广播 UUID: 0xFDE2(Google旧), 0xFFF9(FIDO caBLE)
# tunnel URL: wss://{domain}/cable/connect/{routing_hex}/{tunnel_hex}, 子协议 fido.cable
# RegisterPasskey: id=raw_id=base64url(credentialId), client_data=clientDataJSON(origin=https://telegram.org),
#   attestation = CBOR{fmt:"none", attStmt:{}, authData}
```

### 当前卡点（2026-09-04 更新）
- **纠正**：官方流程里手机 **Telegram 客户端从不参与扫码**。正确扫码方 = 手机**系统相机/Google 智能镜头** → Google Play Services（密码管理器）接手 caBLE。
- **抓包结论**（升级诊断后实测）：`fcf1` 广播 RSSI 仅 -96dBm 且内容每次会话都变 ⇒ 是**环境里其他 Android 设备的常驻 Google 信标**,不是本仪式广播;`c0a80107…` 开头的厂商数据 = 局域网 IoT 设备(192.168.1.7)。**手机真正的 fde2 广播从未出现** ⇒ Google 在手机上解析 QR 后立刻放弃(「连接其他设备」弹窗秒没)。
- **已找到并修复根因**：cable.py `encode_qr_contents` 的 CBOR 字段 5（"mc"/"ga"）用 `bytes` 编码成了**字节字符串**(0x42),官方 tdesktop `CborValue(std::string)` 是**文本字符串**(0x62)——`a105426d63` vs `a105626d63`。Play Services 严格解析直接拒绝 ⇒ 弹窗秒退。已改为 str 并通过往返单测（字段类型/长度全部对齐官方）。
- 其余字段核对过：pubkey 33B 压缩、secret 16B、domains=2、时间戳 int、false,与 tdesktop EncodeQRContents 完全一致;域名表 cable.ua5v.com/cable.auth.com 一致;tdesktop DecryptAdvert 与 cable.py decrypt_advert 字节级一致。
- 诊断基建保留(cable.py `_detect`)：全 UUID/厂商数据抓包(完整 hex+RSSI)、任意 UUID 验密、变体探测(`hit:` 前缀)。
- **进展 2（QR 修复已验证生效）**：部署 CBOR 文本串修复后,手机正常弹出连接界面并广播 fff9(20 字节,hmac 命中!),电脑侧 EID 解密成功进入「蓝牙连接中…」→ 隧道 websocket → 发送握手首消息。
- **进展 3（握手失败=手机端「连接失败」,已修两处）**：① `Noise.__init__` 协议名未零填充到 32 字节(tdesktop `_chainingKey.fill(0)` + memcpy,31 字节名字尾补 0x00),我们 _ck/_h 少一个 0x00 导致整条握手哈希/HKDF/AAD 全错;② `K_PADDING_GRANULARITY` 写成了 16,tdesktop/Chromium 均为 **32**。两处已修+部署。psk/tunnelId 派生、握手消息结构(prologue={1}→identity→psk→e→e/ee/se)、CTAP 封装(0x01 前缀)均已逐字节核对与官方一致。
- **下一步**：用户重测。若握手通过,日志应出现「安全握手…」「等待手机确认注册…」;若仍「连接失败」,抓 ws.recv() 原始响应 hex 分析。

### 官方源码位置（已解压到工作目录，.gitignore 已忽略，勿提交）
- `D:\dsh\tgtools\tdesktop-7.1.5-full\Telegram\SourceFiles\webauthn\` —— caBLE 的 C++ 实现
  - `cable_core.cpp`（QR/CBOR/Noise/DecryptAdvert/CTAP）
  - `cable_scanner_win.cpp`（WinRT BLE 扫描）
  - `cable_tunnel.cpp`（websocket）
  - `cable_ceremony.cpp`（完整流程编排）
  - `cable_box.cpp`（UI）
- Chromium 源码（web 查）：`device/fido/cable/`，`v2_handshake.cc`、`fido_ble_uuids.cc`、`v2_authenticator.cc`

## 八、账号/白名单安全（铁律）

- **绝不提交账号数据**：session/tdata/profiles.json/avatars/logs/whitelist.json 已被 .gitignore 挡住
- **E:\Telegram Desktop 是用户主号，绝对不碰**
- 白名单保护：用户 {5434838648, 6775358409, 238879089}、群 2284618069、Saved Messages
- 测试账号 `D:\Desktop\TG小号\Dexpornuxiuo`（可随便删）；死号 18296957526、Racoro、xxxCeay

## 九、其他已修复的历史坑（避免重踩）

1. **Svelte 5 async 赋值不重渲染**：`$state` 在 async 回调/await 后赋值，`{#each}`/`{#if}` 不更新。必须 `flushSync(() => {...})` 包裹。`rightView` 切换用 `setView()` 助手。
2. **WebView2 缓存旧前端**：`/` 和 `/assets` 要加 no-cache 头。
3. **token 鉴权**：前端从 `window.__TG_TOKEN__` 或 `location.search` 读 token，加到 `X-TG-Token` 头 + WS `?token=`。
4. **头像目录**：`avatar-image` 要允许读 exe avatars 目录 + 旧工具箱 `D:\Desktop\TG小号\工具箱\avatars\`（历史 png 缓存）。
5. **部署用覆盖不删**：保留 avatars/profiles 缓存（deploy.bat 已改为覆盖式）。
6. **WebAuthn rp.id**：程序 URL 已改 `localhost`（不是 127.0.0.1），因 WebAuthn 不认 IP。但此方案（navigator.credentials.create）已废弃，改用 caBLE。

## 十、下一步（新会话建议顺序）

1. **让用户用 Telegram App 扫码验证 passkey**（当前卡点的唯一出路）。二维码下方已加引导文案。若日志出现 `[通行密钥] 蓝牙连接中…` 说明 EID 解密通了，继续看后续握手/注册。
2. 若 passkey 走通，清理 `cable.py` 里的诊断日志（passkey_adv/diag/decrypt_fail）。
3. 批量任务 fan-out：多账号已同时在线,可让删除等任务支持「对所有在线账号执行」。
4. 卡片折叠记忆已修复（待用户确认）。

## 十一、passkey 后端接口（供前端对接参考）

- `POST /api/passkeys/init` → 返回 `{ok, qr, img}`（qr 是 FIDO:/ 文本，img 是 base64 PNG）
- `POST /api/passkeys/register` → 接收 `{id, raw_id, client_data, attestation}`，调 RegisterPasskey
- WebSocket 推送 `{type:'state', status:'passkey_scanning/connecting/handshake/awaiting/done/error', data}`

---

**给新会话的一句话总结**：项目在 main/dev = `eff382b` 附近;多账号同时在线(连接池+秒切)与卡片折叠记忆已实现;passkey caBLE 卡在 Google Play Services 用私有 `fcf1` 广播(手机 QR 解析成功但电脑侧解不开),已升级全量抓包+变体探测诊断,等用户复测;决定性对照=官方 tdesktop 同机绑 passkey。
