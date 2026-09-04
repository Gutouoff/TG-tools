# legacy/ — 已归档的历史版本

本目录存放**已冻结、不再维护**的旧版入口，仅作历史保留。功能以 Web 版（`web_main.py` / `server.py`）为准。

| 文件 | 说明 |
|---|---|
| `tg_ui.py` | Tkinter 老版 GUI（v1.0.0 前的主界面）。引擎已演进为多账号连接池等新架构，本文件不保证可用 |
| `TG工具箱GUI.spec` | Tkinter 版 PyInstaller 打包配置（入口原为根目录 `tg_ui.py`，归档后路径已失效，需自行调整） |
| `TG工具箱GUI.bat` | Tkinter 版启动器（按部署目录布局 `工具箱\tg_ui.py` 查找，同样需自行调整） |

如确需运行：把 `tg_ui.py` 临时复制回项目根目录（`import tg_tool` 按根目录解析），并安装 `ttkbootstrap`。
