# TG-tools · Telegram 小号批量维护工具箱

Python + Telethon 的 Telegram 小号批量维护工具：删联系人、删对话（私聊/群/频道）、退出群组、拉黑 bot、更新 Telegram Desktop 本体、tdata→session 转换、passkey（蓝牙 caBLE）、多账号同时在线、白名单保护、代理支持。**主形态 = Web 版**（FastAPI + Svelte 5 + pywebview）；CLI 保留，Tkinter GUI 已归档至 [legacy/](legacy/)。

> ⚠️ 本仓库**只含代码，不含任何账号数据**。账号 session、tdata、API 凭据全部留在本地账号目录，永不入库（见 `.gitignore`）。

> 🔒 `*.session`、`tdata/`、`*.json`（含 api_id/api_hash）、`2fa.txt` 均为**明文登录态**，等同于账号密码，务必对存放账号的磁盘做加密（如 BitLocker）。

## 架构

```
TG工具箱Web/                  ← 部署目录(PyInstaller onedir, 主形态)
├── TG工具箱Web.exe           ← pywebview 壳(web_main.py)
│   ├── server.py             ← FastAPI 后端: token 鉴权 + REST/WebSocket API
│   ├── tg_engine.py          ← 引擎: 多账号连接池/秒切/任务/温和取消
│   ├── tg_tool.py            ← 核心业务: 白名单/速度档/tdata转换/代理
│   ├── cable.py              ← passkey caBLE(蓝牙扫码)
│   ├── tg_profile.py         ← 资料/头像缓存(profiles.json + avatars/)
│   └── webapp/dist/          ← Svelte 5 构建产物(npm run build 生成)
└── avatars/ profiles.json    ← 运行缓存(部署时保留)

工具箱/                       ← 旧 CLI 运行目录（Tkinter GUI 已归档至 legacy/）
    ├── tg_tool.py / tg_engine.py ...
    └── 界面文本.txt           ← 全部界面中文外置(改文件即改UI,删除恢复默认)
```

## 运行环境

- Windows + Python 3.14（`C:\Python314\python.exe`），`-X utf8` 启动
- 依赖：`pip install -r requirements.txt`（telethon 1.44 / fastapi / uvicorn / pywebview / websockets / qrcode / pillow / cryptography / cbor2 / bleak / opentele-ng / python-socks；版本已 pin）
- 前端：Node/npm，`webapp/` 目录 `npm install && npm run build`（改 `webapp/src/**` 后必须重新 build 再打包部署）
- 打包账号功能需要系统安装 7-Zip（AES-256 加密）
- bat 必须存 **UTF-8 无 BOM**（中文路径 + `chcp 65001`，GBK 字节会乱码）

## 使用

1. 账号目录结构：每个账号一个文件夹，内含 `*.json`（app_id/app_hash/phone/session_file 等）+ `*.session` 或 `tdata/`
2. CLI：双击 `TG工具箱.bat`（在账号根目录=多账号模式；把 bat 复制进单个账号文件夹=单账号模式）
3. GUI：双击 `TG工具箱GUI.bat`
4. 删除逻辑：**白名单外全删**。用户白名单（默认 5434838648/6775358409/238879089）+ 群白名单（默认 2284618069）+ Saved Messages 永久保护
5. 速度五档（对话间隔）：极快 0.2~0.4s / 快速 0.4~0.6s / 默认 0.9~1.4s / 慢速 1.3~1.6s / 极慢 1.9~2.2s，联系人批/轮间隔按档位等比缩放

## 关键实现备忘

- **telethon 全生命周期单协程纪律**：一个 client 的所有操作都在同一个 asyncio 循环里（GUI 引擎线程的私有循环），绝不跨循环使用
- **tl_patch.py**：Telegram 服务器 schema 更新 message 构造体（7600b9d3→3ae56482），Telethon 1.44 未跟进,启动时自动注册新构造体,Telethon 升级后自动失效
- **温和取消**：停止任务不打断进行中的 API 请求,当前动作完成后中止（防半途废 session）
- **防风控**：FloodWait 自动等待;删对话批间/轮间随机间隔;后台资料刷新串行每号 1s 且跳过当前已连接账号（防 session 并发冲突）
- **GUI 线程模型**：Tk mainloop（主线程）+ Engine 后台线程（asyncio run_forever）+ profile worker 线程;所有回调经 `root.after(0,...)` 投递

## 开发

- 修改界面文字 → 编辑 `界面文本.txt`（编号 `t001`-style keys，等号右边，`{0}` 占位符保留）
- 跑测试用账号 `D:\Desktop\TG小号\Dexpornuxiuo`（授权随便测）；`18296957526`/`Racoro`/`xxxCeay` 是死号，连接失败属正常
- 代理设置：`工具箱\settings.json` 的 `proxy` 字段，`{"mode":"system"|"none"|"manual","scheme":"socks5","host":...,"port":...}`
