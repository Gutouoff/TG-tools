# TG-tools · Telegram 小号批量维护工具箱

对**自己拥有的**多个 Telegram 账号做批量日常维护的本地工具：删联系人、删对话（私聊/群/频道）、退群、拉黑 bot、更新 Telegram Desktop 本体、tdata↔session 转换、通行密钥（passkey）管理、账号打包外发。

**主形态 = Web 版**：FastAPI 后端 + Svelte 5（Material 3）前端 + pywebview 壳，PyInstaller 打包成单文件夹绿色程序，双击即用。CLI 保留可用，Tkinter GUI 已归档至 [legacy/](legacy/)。

> ⚠️ 本仓库只含代码，不含任何账号数据。session、tdata、API 凭据等明文登录态等同于账号密码，只保存在本地账号目录，永不入库（见 `.gitignore`），请对存放账号的磁盘做加密（如 BitLocker）。

## 功能特性

- **多账号管理**：账号列表 + 分组 + 搜索 + 头像/资料缓存；**多账号同时在线**（连接池），双击在线账号秒切，无需重连
- **删除类批量任务**：删联系人 / 清理对话（私聊、群、频道）/ 退群 / 拉黑 bot，均带**白名单保护**（白名单外才删；用户可增删，持久化保存）
- **防风控**：五档随机间隔（极快/快速/默认/慢速/极慢）、批间/轮间随机化、FloodWait 自动等待、温和取消（不打断进行中的请求）
- **账号安全页**：两步验证（2FA）设置、通行密钥（passkey）注册/删除（蓝牙 caBLE 扫码）、登录邮箱验证、管理已登录设备
- **资料编辑**：批量/单个修改姓名、简介、用户名、生日、头像
- **打包账号**：把账号（tdata + session + 凭据 + 2fa.txt）打成 **AES-256 加密 zip**，强制设置密码，杜绝明文外发
- **Bot 收件箱**：本地运行一个 TG bot，把账号文件（.session / 凭据 .json / tdata 或 session 的 zip / 2fa.txt）从任意设备转发给它即可自动识别归档进账号列表；加密账号包把密码写在转发说明里；仅允许列表内的用户可推送
- **其他**：Telegram Desktop 本体在线更新、tdata→session 转换导入、代理（system/manual，SOCKS5）、浅色/深色主题、界面中文全部外置可改

## 快速开始

1. 解压发布包（`TG工具箱Web.exe` + `_internal/`）到任意目录
2. 双击 `TG工具箱Web.exe`（首次启动 SmartScreen 拦截时选「更多信息 → 仍要运行」）
3. 程序启动本地服务并打开界面；账号根目录与程序目录同级（`账号根目录/账号名/tdata 或 session`）
4. 双击账号卡片连接；之后所有操作只作用于「当前账号」

### 账号目录格式

```
账号根目录/
├── 账号A/
│   ├── tdata/            # Telegram Desktop 数据（可选）
│   ├── xxx.session       # Telethon 会话（与 tdata 二选一）
│   └── xxx.json          # 凭据: api_id / api_hash / phone / user_id
└── 账号B/
    └── ...
```

## 从源码构建

- Windows + Python 3.14（启动须 `-X utf8`）；`pip install -r requirements.txt`
- 前端：`cd webapp && npm install && npm run build`
- 打包：`python -X utf8 -m PyInstaller TG工具箱Web.spec --noconfirm`（产物在 `dist/TG工具箱Web/`）
- 账号打包功能需系统安装 7-Zip
- CLI 形态：`python -X utf8 tg_tool.py`（在账号根目录=多账号模式；复制进单个账号文件夹=单账号模式）

## 项目结构

```
├── server.py            # FastAPI 后端: token 鉴权、REST/WebSocket API、设置、账号打包
├── web_main.py          # pywebview 壳: 启动本地服务并加载界面
├── tg_engine.py         # 引擎: 后台线程 + asyncio 循环、多账号连接池、任务编排、温和取消
├── tg_tool.py           # 核心业务: 白名单、速度档、tdata 转换、代理、CLI 入口
├── cable.py             # passkey caBLE 完整实现(二维码生成/BLE 扫描/Noise 握手/CTAP)
├── tg_profile.py        # 资料/头像缓存 worker(profiles.json + avatars/)
├── tg_bot.py            # Bot 收件箱: 独立线程/loop 的 TG bot,识别转发的账号文件并归档
├── tl_patch.py          # Telethon 1.44 的新 message 构造体注册(官方更新 layer 后自动失效)
├── tdata2session.py     # opentele-ng tdata 转换
├── webapp/              # Svelte 5 前端源码(App.svelte + api.ts + app.css)
├── legacy/              # 已归档的 Tkinter GUI
└── 界面文本.txt          # 全部界面中文外置(t0xx 编号 key,删除即恢复默认)
```

## 安全与隐私设计

- **数据不出本机**：所有操作走本地账号目录与本地服务；程序自带 token 鉴权，未持 token 的请求一律 401
- **Bot 收件箱白名单**：bot token 只存在本地 settings.json；仅「允许的用户 ID」列表内的人推送的文件才会被接收，其他人发消息只会收到自己的 ID（便于把自己加进列表）
- **删除默认白名单**：内置默认保护名单（本人账号/群/Saved Messages），白名单外才会删除；名单可在界面增删
- **打包强制加密**：账号包必须设置密码（AES-256），不生成明文账号包
- **日志打码**：界面日志对手机号做打码处理

## 免责声明

- 本工具仅供管理**自己拥有**的账号。批量操作违反 Telegram 服务条款可能导致账号被限制或封禁，请自担风险，控制好速度与频率。
- 请勿用于骚扰、垃圾营销或任何违法违规用途。

## 许可证

本项目基于 [GPL-3.0](LICENSE) 许可证发布：

- ✅ 可自由使用、学习、修改、再分发，**也可以商用**；
- ✅ 二次创作后**开源**（同样采用 GPL-3.0）并商用 —— 没问题；
- ❌ **禁止闭源**：任何基于本项目的衍生版本分发时必须完整公开源码并沿用 GPL-3.0；
- 想要商业闭源授权请单独联系作者。

