# Phase 0：前端回归基线（Playwright E2E + 本地截图对比）

> 目的：在动任何样式之前先有「可重复的 UI 基线」，避免重设计把功能/布局改坏。
> 当前覆盖：5 条交互冒烟 + 8 张视觉快照，共 13 条用例；`npm run test:e2e` 全绿。

## 为什么是本地截图，而不是 Percy

Percy 需要云端 token 与网络，本项目运行在离线 Windows 环境。这里用 Playwright 自带的
`toHaveScreenshot()` 做**逐像素对比**，基线 PNG 入库（`webapp/e2e/*-snapshots/`），
效果等价于 Percy 的视觉回归，且没有外部依赖。以后若接入 Percy，只需加 `PERCY_TOKEN`
并在 CI 里追加 `percy exec`，现有断言可复用。

## 怎么跑

```bat
cd webapp
npm run test:e2e          :: 跑全部（构建 + preview + 13 条用例 + 截图比对）
npm run test:e2e:update   :: 有意改动视觉后，重新生成基线（会覆盖 PNG，务必看 diff）
```

首次需要安装浏览器（已装过可跳过）：

```bat
set PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
npx playwright install chromium
```

## 测试构成

| 文件 | 内容 |
|---|---|
| `e2e/fixtures.ts` | 固定数据（3 个账号、设置、会话、日志）+ `/api/**` 拦截 + 确定性注入 |
| `e2e/smoke.spec.ts` | 主界面渲染、设置弹窗切分区、右键菜单开关、删除账号二次确认、会话列表刷新、发起聊天识别提示 |
| `e2e/visual.spec.ts` | 8 张基线：主界面、设置-通用、设置-外观、右键菜单、删除弹窗、会话列表、加群频道、资料编辑 |

## 确定性措施（很重要）

- 所有 `/api/**` 被 `page.route` 拦截，返回固定 JSON，不依赖后端；
- `WebSocket` 替换为不触发事件的替身，避免连接状态/日志随环境变化；
- `Date` 固定为 `2026-10-28 10:00:00 +08:00`，日志时间戳不漂移；
- 注入 CSS 禁用所有动画/过渡/光标闪烁，隐藏滚动条；
- 视口固定 1400×900、`deviceScaleFactor=1`、浅色主题；
- 每张截图前把鼠标移出（0,0），避免 hover 态。

基线文件名带 `-win32` 后缀，是 Playwright 的平台标识；换 Linux CI 需要单独生成一套基线。

## 基线更新纪律

1. 只有**确认是预期的视觉变化**才允许 `npm run test:e2e:update`；
2. 更新后必须人工看一遍 `git diff --stat` 与变更的 PNG，确认没有意外区域变色/位移；
3. 每个 Phase 的提交必须包含「测试全绿」的说明；
4. 交互类改动（flushSync、拖拽、登录流程）不能只靠截图，需按
   [UI_REFACTOR_RISKS.md](UI_REFACTOR_RISKS.md) 做人工点检。

## 已知边界

- 数据是 mock 的：能覆盖布局/状态渲染，覆盖不了真实 Telethon 连接、任务进度、WS 推送；
- 弹窗类视觉用例是「先点开再截图」，比只截默认视图可靠，但仍未覆盖所有危险操作；
- 真实后端冒烟（`server.py` + 真账号）仍需在装有 fastapi/telethon 的机器上单独做。
