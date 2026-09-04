# AGENTS.md — 协同开发须知（给参与本项目的 AI agent）

## 项目是什么

Telegram 小号批量维护工具箱（删联系人/删对话/退群/拉黑bot/更新本体/tdata转换/passkey）。
**主形态 = Web 版**：FastAPI 后端（server.py）+ Svelte 5 前端（webapp/）+ pywebview 壳（web_main.py），PyInstaller 打包（TG工具箱Web.spec）部署到 `D:\Desktop\TG小号\TG工具箱Web\`。
CLI（tg_tool.py）与 Tkinter GUI（tg_ui.py，**遗留维护，不再是主形态**）仍可用。运行时账号数据在 `D:\Desktop\TG小号\`（**不入库、不改动账号目录结构**）。

## 铁律

1. **绝不提交账号数据**：session、tdata、json 凭据、profiles.json、avatars、logs、backups、whitelist.json 都被 .gitignore 挡住。新增运行时产物时同步更新 .gitignore。
2. **E:\Telegram Desktop 是用户主号，绝对不碰。**
3. **删除逻辑只有白名单不删**：用户 {5434838648, 6775358409, 238879089}、群 2284618069、Saved Messages。改白名单默认值 = 改 tg_tool.py 的 DEFAULT_USER_WHITELIST/GROUP_WHITELIST（界面上可增删，持久化 whitelist.json）。
4. **telethon client 单循环纪律**：一个 client 全生命周期在同一个 asyncio loop（GUI 里是 Engine 的私有 loop）。跨线程提交用 `Engine._submit` / `asyncio.run_coroutine_threadsafe`。
5. **bat 文件纪律**：UTF-8 无 BOM + `chcp 65001` + 绝对路径 + 任何退出路径 pause。编辑 bat 后必须重新保存为 UTF-8 无 BOM。
6. **防风控**：所有批量操作必须带随机间隔（速度五档）；后台串行任务每号间隔 1s；FloodWait 自动等待不许删。

## 代码地图

| 文件 | 职责 | 改动注意 |
|---|---|---|
| `server.py` | FastAPI 后端：token 鉴权、账号/连接池/任务/打包/设置/安全 API、WebSocket 广播、静态首页注入 token | 所有 /api 需 `X-TG-Token` 头（仅 avatar-image 放行 query token）；路径一律过 `_ensure_in_root`；日志经 `_emit` 打码手机号后广播；打包强制 AES-256（需 7z），密码存 settings.json |
| `web_main.py` | pywebview 壳 | 启动 FastAPI 后加载 `http://localhost:{port}/?token=`（用 localhost 是为 WebAuthn rp.id） |
| `webapp/src/` | Svelte 5 前端（App.svelte 主界面 + api.ts 封装 + app.css 主题） | 改完必须 `cd webapp && npm run build` 再打包部署（webapp/dist 不入库）；token 从 `window.__TG_TOKEN__`（后端注入 index.html）或 URL query 读 |
| `cable.py` | passkey caBLE（蓝牙扫码登录）完整实现 | 依赖 bleak/cbor2/cryptography；诊断日志待 passkey 走通后清理（见 HANDOFF.md 卡点） |
| `tg_tool.py` | 核心业务+CLI 交互+界面文本表 DEFAULT_TEXTS+白名单+代理 | 它是库（GUI/Web 都 import 它）也是 CLI 入口；模块级可变量 DIALOG_DELAY/CONTACT_*_DELAY 被 Engine.set_speed 运行时改 |
| `tg_engine.py` | 引擎：线程+asyncio 循环、**多账号连接池(_pool)/秒切**、任务、温和取消、进度回调 | 所有 on_log/on_progress/on_state 回调默认在引擎线程执行,UI 侧必须 root.after 投递;任务只作用于"当前账号" |
| `tg_ui.py` | Tkinter 界面（遗留维护） | 引擎新特性（连接池等）不保证同步到它;界面文案走 T()/界面文本.txt |
| `tg_profile.py` | 资料缓存 worker | DEAD 集合=已知死号直接跳过;PHONE_CODE_MAP 区号→国家 |
| `tl_patch.py` | Telethon 1.44 新 message 构造体 3ae56482 注册 | Telethon 官方更新 layer 后此补丁自动被覆盖,无需维护 |
| `tdata2session.py` | opentele-ng tdata 转换 | 独立脚本,也被 tg_tool import |
| `HANDOFF.md` | 交接文档（活文档,并行会话维护） | 提交时随手更新;其自述版本号易与 HEAD 漂移 |
| `requirements.txt` | 依赖 pin 清单 | 新增/升级依赖必须同步此文件和 TG工具箱Web.spec 的 hiddenimports |
| `界面文本.txt` | 全部界面中文外置 | 运行目录的这份才是活的;仓库这份是模板 |

## 测试

- 测试账号：`D:\Desktop\TG小号\Dexpornuxiuo`（用户授权随便删）
- 死号（连接失败正常）：18296957526、Racoro、xxxCeay
- GUI 冒烟：构建 App → 搜索过滤 → 弹窗构建,不真删
- CLI 回归：`printf '\n0\n' | python -X utf8 tg_tool.py`（账号目录内）
- Web 后端冒烟：`server.start_server()` 起服务后,无 token 访问 /api/* 应 401,带 `X-TG-Token` 应 200;`/api/pack` 无 pack_password 必须拒绝;路径越界必须 400
- 前端构建：`cd webapp && npm run build`（沙箱内 esbuild 可能 EPERM,需放开权限重试）
- Python：`C:\Python314\python.exe` + `-X utf8`,终端是 MSYS bash（POSIX 语法,原生工具传 `C:/x` 正斜杠路径）

## 约定

- 界面文本书面语（「请选择」「未找到」），全角标点
- 确认输入是 `y`（不分大小写）
- 速度档参数是用户钦定的精确值,别改数字
- 新增界面文案：tg_tool.py DEFAULT_TEXTS 加 key（t0xx 序号）+ 界面文本.txt 同步
- 打包账号必须设 pack_password（AES-256 加密 zip）,禁止生成明文账号包
- token 是唯一访问控制,绝不落盘（settings.json/日志/URL 之外不新增暴露点）
