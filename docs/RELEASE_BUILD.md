# 发版构建记录（Windows / PyInstaller）

> 2026-10-31 在本机（Python 3.12.10，无既有环境）从零验证通过：
> 依赖安装 → PyInstaller 打包 → exe 启动 → 监听端口 → 未授权请求被拒。

## 结论

- 本机可以用 **临时 venv + Python 3.12** 完成打包，不必依赖原来那台 3.14 机器；
- 产物 `dist/TG工具箱Web/TG工具箱Web.exe` 11.2 MB，整目录 **50.6 MB**；
- exe 启动后正常拉起 FastAPI，监听 `127.0.0.1:<随机端口>`，`/api/*` 无 token 返回 **401**。

## 一次性环境准备

系统 `pip.ini` 已损坏（带 BOM 且把 `\n` 当字面量），pip 会报
`Configuration file could not be loaded`。用独立配置文件绕过：

```powershell
$ini = Join-Path $env:TEMP 'pip-release.ini'
"[global]`nindex-url = https://pypi.org/simple`ntimeout = 60" | Set-Content -Encoding ASCII $ini
$env:PIP_CONFIG_FILE = $ini

$venv = Join-Path $env:TEMP 'tgtools-release-venv'
python -m venv $venv
& "$venv\Scripts\python.exe" -m pip install -q -r requirements.txt pyinstaller
```

依赖全部为 `requirements.txt` 里的 pin 版本，Python 3.12 可安装、可导入
（fastapi / uvicorn / telethon / pywebview / PyInstaller 6.22.3）。

## 打包

```powershell
cd D:\dsh\tgtools
cd webapp; npm run build; cd ..
& "$venv\Scripts\python.exe" -m PyInstaller 'TG工具箱Web.spec' --noconfirm
```

约 30 秒完成，产物在 `dist\TG工具箱Web\`。

## 冒烟（不打开界面也能查）

```powershell
$p = Start-Process 'dist\TG工具箱Web\TG工具箱Web.exe' -PassThru
# 等 1~2 秒，查监听端口
Get-NetTCPConnection -OwningProcess $p.Id -State Listen
# 无 token 访问 /api/accounts 应为 401
```

`/` 根路径在没有 token 时同样返回 401，这是预期行为：真实入口由 `web_main.py`
拼接 `?token=<运行时 token>` 后加载，token 不落盘，无法从外部读取。

## 发版前仍需确认

1. `APP_VERSION` 版本号（当前 1.2.3，建议 1.2.4）；
2. 发布说明（`docs/releases/`）与 tag；
3. 真机人工点检：连接账号、聊天、设置保存、危险操作确认，以及
   [UI_REFACTOR_RISKS.md](UI_REFACTOR_RISKS.md) 里的拖拽/手机号登录；
4. 7z 打包脚本与 GitHub Release 资产命名沿用历史流程（`TG-tools_vX.Y.Z.zip`）。
