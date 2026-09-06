# TG工具箱 v1.1.0-beta.9

> 测试版（beta）。遇到问题请把程序 `logs` 目录最新日志发给开发者。

## 更新内容（相对 beta.8）

### 彻底修复：转换报 `Unexpected token 'I', "Internal S"...`

根因链（两层叠加）：
1. 转换流程的账号异常（`SystemExit`）是 BaseException，FastAPI 常规异常处理器接不住 → 返回纯文本 `Internal Server Error`；
2. 前端对纯文本响应调 `JSON.parse` → 二次报错 `Unexpected token`。

修复：
- 服务器：请求中间件兜底**任何**未捕获异常（含 SystemExit 等极端情况），全部返回带具体异常类型与信息的 JSON（已本地实测）；
- 前端：`apiFetch` 对非 JSON / 非法 JSON 响应统一兜底重包成 JSON（含 HTTP 状态码与响应片段）——**今后所有错误都会显示可读原因，不会再出现 JSON 解析二次异常**。

### 其他
- 启动日志显示程序版本号（`程序版本: vX.Y.Z`），报问题时请带上此版本号，便于确认运行的是哪个构建。

## 附件

- `TG-tools_v1.1.0-beta.9.zip`（约 30 MB）：解压后双击 `TG工具箱Web.exe`；首次启动 SmartScreen 拦截时选「更多信息 → 仍要运行」
- 此前修复继续有效：启动白屏自动降浏览器模式（beta.4）、tdata 转换缺文件（beta.5）、channel 构造体补丁（beta.6）、转换缺 json 自愈（beta.7/8）
