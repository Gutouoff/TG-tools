# TG-tools · Telegram 小号批量维护工具箱

Python + Telethon 的 Telegram 小号批量维护工具：删联系人、删对话（私聊/群/频道）、退出群组、拉黑 bot、更新 Telegram Desktop 本体、tdata→session 转换、白名单保护、代理支持。CLI 与 GUI（Tkinter）双入口。

> ⚠️ 本仓库**只含代码，不含任何账号数据**。账号 session、tdata、API 凭据全部留在本地账号目录，永不入库（见 `.gitignore`）。

## 架构

```
TG小号/                       ← 账号根目录(本地,不入库)
├── TG工具箱.bat              ← CLI 入口(检测当前目录自动单/多账号)
├── TG工具箱GUI.bat           ← GUI 入口
└── 工具箱/                   ← 运行目录(SCRIPT_DIR)
    ├── tg_tool.py            ← 核心业务:连接/删联系人/删对话/白名单/速度档/tdata转换/CLI交互
    ├── tg_engine.py          ← GUI 引擎:后台线程 asyncio 循环,可取消任务,进度/状态回调
    ├── tg_ui.py              ← Tkinter 主界面:账号列表(头像/用户名/DC/ID)+操作面板+日志
    ├── tg_profile.py         ← 资料缓存:后台串行拉 username/头像/DC,profiles.json 增量落盘
    ├── tl_patch.py           ← Telethon 1.44 猴子补丁:注册新 message 构造体 3ae56482
    ├── tdata2session.py      ← tdata→session 转换(opentele-ng)
    ├── 界面文本.txt           ← 全部界面中文外置(改文件即改UI,删除恢复默认)
    ├── whitelist.json        ← 白名单持久化(用户/群)
    └── settings.json         ← 代理设置(system/none/manual)
```

## 运行环境

- Windows + Python 3.14（`C:\Python314\python.exe`），`-X utf8` 启动
- 依赖：`telethon==1.44.0`（用户 site-packages）、`opentele-ng`、`pysocks`（socks 代理时）、`pillow`（GUI 头像）
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
