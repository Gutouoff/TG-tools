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

## 部署目录现状（2026-10-31 只读检查）

`D:\Desktop\TG小号\TG工具箱Web\` 共 **326.5 MB**，不能整目录覆盖或清空：

| 项 | 大小 | 说明 |
|---|---|---|
| `Telegram.exe` | 208.7 MB | 用户自己的客户端，**绝对不能动** |
| `_internal\` | 104.2 MB | 旧版程序依赖，部署时整目录替换 |
| `TG工具箱Web.exe` | 12.1 MB | 旧版主程序（2026-10-23） |
| `avatars\` | 1.4 MB | 头像缓存，保留 |
| `backups\` / `logs\` / `.qrlogin\` | <1 MB | 运行数据，保留 |
| `settings.json` / `profiles.json` / `groups.json` / `whitelist.json` / `poll_results.json` | <1 MB | 用户配置与缓存，保留 |
| `界面文本.txt` / `更新说明.txt` | <1 MB | 界面文本可能被用户改过，**不要覆盖** |

新构建的 `_internal` 约 39 MB（已排除 numpy/pandas/scipy/matplotlib），比旧版 104 MB 小很多，替换后目录会瘦身。

## 部署步骤（只换程序，保留数据）

```powershell
$app = 'D:\Desktop\TG小号\TG工具箱Web'
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
# 1. 退出正在运行的程序（确认托盘/窗口已关闭）
# 2. 备份旧程序
New-Item -ItemType Directory "$app\backups\release-$stamp" -Force | Out-Null
Copy-Item "$app\TG工具箱Web.exe" "$app\backups\release-$stamp\"
Copy-Item "$app\_internal" "$app\backups\release-$stamp\_internal" -Recurse
# 3. 替换 exe 与 _internal
Copy-Item 'dist\TG工具箱Web\TG工具箱Web.exe' $app -Force
Remove-Item "$app\_internal" -Recurse -Force
Copy-Item 'dist\TG工具箱Web\_internal' $app -Recurse
# 4. 启动并冒烟：能开窗口、能连账号、设置能保存
```

## 回滚

把 `backups\release-<stamp>\` 里的 `TG工具箱Web.exe` 和 `_internal` 复制回 `$app` 即可；
用户数据（settings/profiles/avatars/logs）全程未被触碰。

## 发版前仍需确认


1. `APP_VERSION` 版本号（当前 1.2.3，建议 1.2.4）；
2. 发布说明（`docs/releases/`）与 tag；
3. 真机人工点检：连接账号、聊天、设置保存、危险操作确认，以及
   [UI_REFACTOR_RISKS.md](UI_REFACTOR_RISKS.md) 里的拖拽/手机号登录；
4. 7z 打包脚本与 GitHub Release 资产命名沿用历史流程（`TG-tools_vX.Y.Z.zip`）。
