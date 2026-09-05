# TG工具箱 v1.1.0-beta.4

> 测试版（beta）。遇到问题请把程序 `logs` 目录最新日志发给开发者。

## 更新内容（相对 beta.3）

### 重要修复：启动白屏报错
- 部分电脑双击 exe 后报 `Failed to resolve Python.Runtime.Loader.Initialize`（缺 .NET Framework 4.8，或下载的 zip 被 Windows「锁定」）——现在**窗口模式启动失败会自动降级为浏览器模式**：弹提示后自动用默认浏览器打开界面，服务照常运行，任何机器都能用
- beta.3 遇到此报错的测试者：优先尝试右键 zip → 属性 → 勾选「解除锁定」后重新解压；或安装 [.NET Framework 4.8](https://dotnet.microsoft.com/zh-cn/download/dotnet-framework/net48) 恢复窗口模式

### 新功能
- **导出表格**：一键导出 `账号总表.xlsx`（用户名 / ID / 手机号 / 邮箱 / 通行密钥 / 2FA / 注册时间 / 国家 / 状态），自动用系统程序打开；注册时间由账号最早会话消息估算

## 附件

- `TG-tools_v1.1.0-beta.4.zip`（约 29 MB）：解压后双击 `TG工具箱Web.exe`；首次启动 SmartScreen 拦截时选「更多信息 → 仍要运行」
