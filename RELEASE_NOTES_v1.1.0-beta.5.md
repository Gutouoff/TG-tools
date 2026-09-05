# TG工具箱 v1.1.0-beta.5

> 测试版（beta）。遇到问题请把程序 `logs` 目录最新日志发给开发者。

## 更新内容（相对 beta.4）

### 修复：tdata 账号转换/登录报错
- 全新环境对仅 tdata 登录态的账号连接时（或点「转换」），报
  `[Errno 2] No such file or directory: ..._internal\opentele\devices.json`
- 原因：打包时遗漏了 opentele 库的数据文件（devices.json），本机因历史目录残留未暴露，全新解压必现
- 已修复：打包配置补收 opentele 数据文件，tdata 自动转换恢复正常

## 附件

- `TG-tools_v1.1.0-beta.5.zip`（约 29 MB）：解压后双击 `TG工具箱Web.exe`；首次启动 SmartScreen 拦截时选「更多信息 → 仍要运行」
- beta.4 的启动白屏修复（浏览器模式自动降级）继续有效
