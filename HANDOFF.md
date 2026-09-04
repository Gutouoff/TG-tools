# TG 工具箱交接文档（重开会话用）

> 本文档记录当前项目的完整状态、关键技术细节、卡点和下一步，供新会话无缝继续。
> 最后更新：main/dev = `27fc7dd`

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
- **纠正**：官方流程里手机 **Telegram 客户端从不参与扫码**（之前文档里「用 TG App 扫」是错的）。正确扫码方 = 手机**系统相机/Google 智能镜头** → Google Play Services（密码管理器）作为通行密钥提供方接手 caBLE。
- 用户实测（系统相机/Google 扫码）：手机弹「连接其他设备」弹窗后瞬间消失,并持续广播 `0000fcf1`（20 字节,head=04322274,hmac 校验不过）→ **QR 被 Google 正确解析**,手机在等电脑接入隧道;是电脑侧解不开 fcf1 广播。
- tdesktop/Chromium 源码都只认 FDE2/FFF9,无 fcf1。tdesktop 常量(secret16/advert20/eid16/hmac 前4字节)与 cable.py 完全一致,实现无偏差。
- 两种可能: ① fcf1 是 Google Play Services 新的 caBLE 广播格式(key 布局/派生变了) ② fcf1 只是伴生信标(Nearby),真正 FDE2 广播未出现(流程中断)。
- **已升级诊断**(cable.py `_detect`)：所有 service-data/厂商数据 UUID 全量抓包(完整 hex+RSSI,去重);任意 UUID 上都先按标准格式验密(命中即连);标准失败自动跑**变体探测**(body 任意偏移/tag 在尾部/hmac 命中即报 `hit:` 前缀含明文 hex)。前端日志前缀: passkey_adv:/passkey_mfg:/passkey_hit:/passkey_diag:。
- **下次复测看什么**：a) 是否出现 fde2/fff9 广播 b) fcf1 完整 hex(去重后只报一次) c) 有无 `[命中]` 行。
- **决定性对照实验**(用户做)：官方 tdesktop 7.1.5 用同一手机绑 passkey。官方也失败 ⇒ Google 换了格式,非我方 bug;官方成功 ⇒ 对照官方 QR 字段找差异。

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
