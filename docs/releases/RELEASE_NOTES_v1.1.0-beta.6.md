# TG工具箱 v1.1.0-beta.6

> 测试版（beta）。遇到问题请把程序 `logs` 目录最新日志发给开发者。

## 更新内容（相对 beta.5）

### 修复
- **拉取对话/消息报错** `Could not find a matching Constructor ID d49f34c6`：Telegram 服务器启用新版 `channel` 构造体，TL 补丁已跟进（与之前 user 构造体同类问题）
- **导出表格不自动打开、反而多开一个程序窗口**：xlsx 无关联程序时的兜底逻辑误用了程序自身路径；现在改为打开资源管理器并定位到表格文件
- **通行密钥注册报「session 太新」**：这是 Telegram 防盗号保护（新登录的 session 24 小时内不能管理其他授权），现在给出明确中文提示——**先用该号正常挂机一天后再试**，并非故障

## 附件

- `TG-tools_v1.1.0-beta.6.zip`（约 29 MB）：解压后双击 `TG工具箱Web.exe`；首次启动 SmartScreen 拦截时选「更多信息 → 仍要运行」
- beta.4（浏览器模式降级）、beta.5（tdata 转换修复）继续有效
