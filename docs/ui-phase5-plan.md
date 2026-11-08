# UI 重构实施计划（Phase 5：外观重设计）

> **状态**：待执行。Phase 1–4（组件化、令牌化、文案外置、测试基线）已完成。
> **基线**：`dev` @ `82939e4`（2026-10-31，v1.2.3 + 前端重构 48 个提交）。
> **目标**：只改视觉、布局与样式，不改任何功能、接口、数据结构与持久化值。
> **关联**：[AGENTS.md](../AGENTS.md)、[UI_REFACTOR_RISKS.md](UI_REFACTOR_RISKS.md)、[PHASE0_TESTING.md](PHASE0_TESTING.md)、[UI_TEXTS.md](UI_TEXTS.md)、[UI_STYLE.md](UI_STYLE.md)。
> **历史文档**：[ui-redesign-plan.md](ui-redesign-plan.md) 与 [ui-redesign-risks.md](ui-redesign-risks.md) 基于 v1.2.2 单文件结构，仅作设计参考，任务分解以本文件为准。

---

## 0. 一页结论

1. **不整体换品牌色**。浅色主色、底色、顶栏色由 `settings.json` 在运行时注入，纯 CSS 改不动；换主色必须改后端默认值与前端 `applyTheme()` 逻辑，超出「只改外观」的任务边界。
2. **重做的是「层级 + 密度 + 状态 + 危险操作 + 深色模式」**，不是换一套配色。主色仍是 v1.2.3 的 `#356AE6`，深色主题可以整体重做。
3. **预计 8–10 个工作日**，拆成 9 个可独立回滚的提交；每个提交必须 `npm run build` 通过 + 26 条 E2E 全绿。
4. **版本建议 1.3.0**（外观级新版本），先出 `1.3.0-beta.1` 给测试者；版本号 bump 属于发版动作，不在本 UI 任务约束内。
5. 需要先拍板 6 个决策（第 2 节），其中 **D1 主色** 是唯一会改变工作量的分叉点。

---

## 1. 基线（2026-11-08 实测）

### 1.1 代码与测试

| 项 | 当前值 |
|---|---|
| `APP_VERSION` | `1.2.3`（`tg_tool.py:45`） |
| `App.svelte` | 2263 行（外壳 + 业务状态/流程编排） |
| 组件 | 19 个，共 1957 行（`webapp/src/components/`） |
| `app-ui.css` | 4996 行（全局样式） |
| `app.css` | 260 行（颜色/圆角/间距/字号/阴影令牌） |
| `texts/zh.ts` | 446 行 / 399 条文案 key |
| `api.ts` | 421 行（只读） |
| 构建 | `npm run build` ✅ 217 模块，335KB JS / 92KB CSS |
| E2E | `npx playwright test` ✅ 26/26，13 张视觉基线 |
| 已知告警 | `AddAccountDialog.svelte:157` 的 `md-outlined-button` 点击缺 ARIA role |

### 1.2 已完成的准备（Phase 1–4）

- 巨石拆分为 19 个组件；样式集中到 `app-ui.css`；文案全部走 `t()`。
- 圆角/字号/间距/阴影已令牌化（`--radius-*`、`--text-*`、`--space-*`、`--shadow-*`）。
- Playwright 基线覆盖主界面、设置、右键菜单、删除弹窗、会话、加群、资料、新建账号、手机端与深色模式。
- 高风险契约已固定：`flushSync` 21 处、5 个 DOM 选择器、分组拖拽几何、手机号登录状态机。

### 1.3 硬约束（会直接决定方案）

| 约束 | 影响 |
|---|---|
| **浅色主题色由 settings 注入** | `applyTheme()` 把 `theme_seed / theme_bg / theme_topbar` 写成行内变量，优先级高于 `app.css`。不改 `server.py` 的 `DEFAULT_SETTINGS` 和 `applyTheme()`，就改不了浅色主色、底色、顶栏色的默认值。 |
| **深色主题完全走 CSS** | 深色模式会移除行内变量，`app.css` 的 `:root[data-theme='dark']` 可整体重做。 |
| **`flushSync` 21 处** | 不能删、不能挪、不能换 `tick()`；涉及连接、手机号登录、右键菜单、聊天滚动。 |
| **5 个 DOM 选择器** | `.log`、`.chat-history`、`.ctx`、`details.card`、`.item` 的类名/层级是运行时契约。 |
| **分组拖拽几何** | `.grp` 的 padding/高度/外边距/圆角参与命中计算，不能改。 |
| **文案 key 与卡片 id** | `zh.ts` 的 399 条 key 与 `card_order` 的中文卡片 id 都是持久化/测试契约，不能改名。 |
| **接口与数据结构** | `api.ts`、`server.py`、`tg_engine.py`、`tg_tool.py` 全部只读。 |
| **字体与图标** | 只能用系统字体栈与 Unicode 字形；禁止 CDN、外链、内嵌字体。 |

### 1.4 顺手要还的技术债

| 项 | 位置 | 处理 |
|---|---|---|
| 危险按钮写死红色 | `app-ui.css` 的 `--md-filled-button-container-color: #B3261E` 等 | 改引用 `var(--md-sys-color-error)` |
| 纯白文字写死 | `#FFFFFF` / `#fff` 多处（主色按钮、头像） | 能走 `on-primary` / `on-error` 的走令牌；头像色盘保留 |
| 手机动作图标色盘写死 | `.mobile-action-icon.blue/mint/...` | 抽成 `--accent-*` 令牌或统一走容器色 |
| 状态色分散 | `--status-online` / `--status-warning` / `--status-success` | 补齐 `--status-error` / `--status-info` / `--status-neutral`，统一命名 |
| a11y 告警 | 全前端 76 条（构建不阻断；多为弹窗遮罩点击与 `md-*` 自定义元素） | Phase 5.8 统一评估：遮罩加 role/键盘关闭，`md-*` 用 `svelte-ignore` 或组件封装 |

---

## 2. 设计决策（执行前拍板）

| ID | 决策 | 选项 | 建议 | 影响 |
|---|---|---|---|---|
| **D1** | 主色与品牌 | A. 保留 `#356AE6`；B. 换旧方案深蓝 `#0D47A1`；C. 做成可选预设 | **A** | B/C 需要改 `server.py` 默认值与 `applyTheme()` 迁移，超出纯外观约束，应单独立项 |
| **D2** | 信息密度 | A. 局部收紧（日志/设置/卡片内边距）；B. 全局 -20% | **A** | 账号行已约 64px，接近 M3 标准；全局压缩会牺牲可点性并让全部基线失效 |
| **D3** | 默认主题 | A. 浅色默认；B. 跟随系统；C. 深色默认 | **A** | 跟随系统要新增逻辑（只读脚本），本期不做 |
| **D4** | 字体/图标 | A. 系统字体栈 + Unicode；B. 内嵌字体/图标 | **A** | B 增加包体且需要授权文件，收益低 |
| **D5** | 形状/阴影 | A. 保留现有圆角，统一 elevation；B. 整体换大圆角 | **A** | B 会让弹窗/卡片比例失衡，且改动面过大 |
| **D6** | 版本 | A. `1.3.0`（先 beta.1）；B. `1.2.4` | **A** | 外观级改版按 Y 版本走；纯修复才用 Z |

> 若 D1 选 B：必须新增一条「主题迁移」任务，改 `server.py` 的 `DEFAULT_SETTINGS` 与 `App.svelte` 的 `applyTheme()`，并补 settings 迁移测试；这会突破本任务「root *.py 只读 / script 业务逻辑只读」的约束，需要单独授权。

---

## 3. 设计目标（可验收）

### 3.1 视觉层级

- 三级表面清晰：页面底 → 卡片/面板 → 弹窗/浮层；靠背景明度 + 1px 边框 + 阴影区分，不靠重色块。
- 顶栏、左栏、中栏、右栏的边界稳定；滚动区域不出现双重边框。
- 卡片标题行统一高度与图标位置；展开/收起状态有明确指示。
- 危险操作（删除账号、删除分组、移出白名单）保持红色系 + 二次确认，不因改版弱化。

### 3.2 状态可读

- 在线 / 离线 / 失效 / 状态未知 / 待改名：颜色 + 文字/形状双编码，不能只靠颜色。
- 运行中 / 已取消 / FloodWait 等待：沿用现有日志与状态事件，不新增业务状态字段；只改视觉呈现。
- 深色与浅色下同一状态必须一眼可区分。

### 3.3 无障碍

- 正文对比度 ≥ 4.5:1，大字 ≥ 3:1；聚焦环在深浅色下都可见。
- 可点目标 ≥ 32px（桌面）/ 48px（手机）。
- 保留 `prefers-reduced-motion: reduce` 下的瞬时退化。

### 3.4 响应式

- 桌面断点 > 899px；手机 ≤ 899px，沿用现有断点，不新增断点。
- 手机端保留四个页签、设置钻取、面板返回、`env(safe-area-inset-*)`。

---

## 4. 实施阶段

> 每个阶段独立 commit；提交前必须 build + 26 条 E2E 全绿。截图变化只能来自本阶段声明的区域。

### Phase 5.0 准备与冻结（0.5 天）

- 从 `dev` 切分支 `ui-phase5`。
- 跑一次全量测试，记录 26 条通过；记录主界面/设置/删除弹窗三张基线的 hash。
- 记录基线：`npm run build` 通过（76 条 a11y 告警为既有基线，Phase 5.8 统一处理，本阶段不新增）。
- 产出对比目录约定：`webapp/test-results/ui-phase5/`（已 gitignore），每阶段留改前/改后截图。

**验收**：`npm run build` 通过（告警数与基线一致）；26 条全绿；分支干净。
**提交**：`Phase 5-0: 从 dev 切 ui-phase5 并确认基线`

### Phase 5.1 令牌层（1 天）

**文件**：`webapp/src/app.css`

**动作**：
- 补齐语义状态色：`--status-error`、`--status-info`、`--status-neutral`（沿用现有 `--status-online/success/warning` 命名）。
- 增加 elevation 语义：`--elevation-0..4`，内部映射到现有 `--shadow-*`，不直接替换旧变量。
- 增加动效令牌：`--motion-fast/base/slow`、`--motion-ease-standard/emphasized`。
- 增加密度令牌：`--row-height-account`、`--row-height-setting`、`--control-height`。
- 把危险按钮、纯白文字、手机动作图标色盘改为引用令牌（附录 A）。
- 不改变任何现有令牌的数值。

**验收**：build 通过；26 条全绿；13 张基线零 diff；浅色/深色都无颜色跳变。
**提交**：`Phase 5-1: 补齐状态/层级/动效/密度令牌并收敛硬编码颜色（零视觉变化）`

### Phase 5.2 表面与层级（1 天）

**文件**：`app.css`、`app-ui.css`

**动作**：
- 浅色：调整 `surface-container-low/high/highest` 的层级差；卡片、面板、弹窗改用对应层级 + 1px `outline-variant`。
- 深色：重做 `surface-container-*` 与边界，避免纯黑上叠纯黑；弹窗加 scrim 与 elevation。
- 统一顶栏下边界、面板分隔线、列表 hover/选中状态层。
- 滚动条、focus ring 跟随新层级。

**验收**：截图 diff 仅出现在背景/边界/阴影区域；深浅色对比度达标；无布局位移。
**提交**：`Phase 5-2: 重做表面层级与 elevation（浅色/深色）`

### Phase 5.3 排版与密度（1 天）

**文件**：`app-ui.css`

**动作**：
- 明确字阶角色：页面标题 / 分区标题 / 正文 / 次要 / 说明，全部走 `--text-*`。
- 收紧日志行距与内边距（不改 `.log` 类名与结构）。
- 收紧设置表单、卡片内容、列表副标题的纵向间距。
- 账号行保持 ≥ 60px 可点高度，头像 48px 不变；**不改 `.grp` 的 padding/高度/外边距**。

**验收**：同屏日志行数增加；账号列表行数与点击区域不退化；分组拖拽与单击切换正常；基线更新需人工确认。
**提交**：`Phase 5-3: 统一字阶与局部密度（日志/设置/卡片）`

### Phase 5.4 账号列表与状态（1 天）

**文件**：`components/AccountCard.svelte`（只改 class/结构，不改 props 与事件）、`app-ui.css`

**动作**：
- 选中态：左侧 3px 主色条 + 状态层背景，替代整块 `primary-container`。
- 在线点：右下 10–12px 绿点，2.4s 呼吸；`prefers-reduced-motion` 下静止。
- 失效/状态未知/待改名：统一为小标签，颜色 + 文字双编码；`title` 提示保留。
- tdata 转换按钮与账号行 hover 的层级关系理顺。
- 头像占位色盘保留（数据色，不是主题色）。

**验收**：3 个 fixture 账号（在线/失效/未知+待改名）渲染正确；双击连接、右键菜单、拖拽排序不变；更新主界面基线并逐像素检查。
**提交**：`Phase 5-4: 重做账号列表选中态与状态标识`

### Phase 5.5 功能卡与进度（1.5 天）

**文件**：`components/FunctionCards.svelte`、`App.svelte` 的进度标记（只改模板 class/包裹，不改脚本）、`app-ui.css`

**动作**：
- 卡片标题行统一高度、字号、展开图标；`details[open]` 的边界与阴影统一。
- 卡片内容区 padding 走密度令牌；按钮组换行规则保持。
- 进度条：高度、圆角、底色、填充色统一；`width` 过渡保留 300ms。
- 只美化现有状态，不新增「运行中/完成」业务字段。

**验收**：6 张卡展开/收起正常，`card_order` 与 `cardOpen` 持久化不变；进度推进动画正常；截图基线更新。
**提交**：`Phase 5-5: 重做功能卡与进度条视觉`

### Phase 5.6 弹窗与危险操作（1 天）

**文件**：`components/DeleteAccountDialog.svelte`、`GroupDeleteDialog.svelte`、`GroupRenameDialog.svelte`、`SettingsDialog.svelte`、`app-ui.css`

**动作**：
- 弹窗统一 header/body/footer、圆角、elevation、scrim；移动端全屏规则保留。
- 危险按钮：`error` 填充、hover 加深、disabled 0.38、聚焦环可见；二次确认勾选逻辑不动。
- 删除账号弹窗的路径展示用等宽字体 + 容器底色；警告区左侧 4px 红条。
- 设置弹窗导航选中态、分区标题、保存栏吸附统一。

**验收**：勾选前禁用/勾选后可用；删除分组红色样式；键盘 Tab 可达；深浅色对比度达标。
**提交**：`Phase 5-6: 统一弹窗与危险操作视觉`

### Phase 5.7 手机端（1.5 天）

**文件**：`components/MobileApp.svelte`、`app-ui.css` 的 `max-width: 899px` 段

**动作**：
- 底栏：图标 + 标签常显，激活态用 56×28 胶囊指示器；触控目标 ≥ 48px。
- 账号行：双行 72dp，在线点/状态标签与桌面一致。
- 当前页账号卡、动作九宫格、动态页日志、更多页列表统一间距。
- 设置根页/子页、面板返回栏、safe-area 全部保留。
- 页签切换与详情面板动效沿用现有 `{#key}` 与过渡，不改状态逻辑。

**验收**：四个页签、设置根/子页、面板返回正常；390×844 两张基线更新；真机（WebView2/Android WebView）点检。
**提交**：`Phase 5-7: 校准手机端视觉与触控目标`

### Phase 5.8 收尾与基线（1 天）

**动作**：
- 全界面走查：a11y、对比度、focus-visible、reduced-motion。
- 处理既有 a11y 告警：弹窗遮罩补 role/键盘关闭；`md-*` 交互统一用 `svelte-ignore` 注释；目标清零，至少不新增。
- 更新 13 张视觉基线（`npm run test:e2e:update`），逐张看 diff。
- 全量 26 条 + build；补一条「深色主界面」走查（如已有则复用）。
- 更新 `HANDOFF.md`、`UI_TEXTS.md`（如新增文案）、`ui-inventory.md`（历史标注）。
- 人工回归：分组拖拽、手机号登录、删除账号、聊天滚动、主题切换。

**验收**：26 条全绿；build 无新增告警；文档与现状一致。
**提交**：`Phase 5-8: 更新视觉基线并完成无障碍收尾`

---

## 5. 依赖与排期

```
5.0 准备
  └─ 5.1 令牌
       └─ 5.2 表面/层级
            └─ 5.3 排版/密度
                 ├─ 5.4 账号列表
                 ├─ 5.5 功能卡/进度
                 └─ 5.6 弹窗/危险操作
                      └─ 5.7 手机端
                           └─ 5.8 收尾/基线
```

| 阶段 | 预估 | 可并行 |
|---|---|---|
| 5.0 | 0.5 天 | 否 |
| 5.1 | 1 天 | 否 |
| 5.2 | 1 天 | 否 |
| 5.3 | 1 天 | 否 |
| 5.4 / 5.5 / 5.6 | 各 1–1.5 天 | 可三人并行（不同文件） |
| 5.7 | 1.5 天 | 依赖 5.3–5.6 |
| 5.8 | 1 天 | 否 |
| **合计** | **8–10 个工作日** | |

---

## 6. 质量门禁（每个提交）

```bash
cd webapp
npm run build          # 必须通过；告警不能新增
npx playwright test    # 26 条全绿；视觉用例允许按阶段更新基线
```

契约检查（任一不满足即回退）：

```bash
grep -c flushSync webapp/src/App.svelte            # 21
grep -n 'class="log"' webapp/src/components/LogView.svelte
grep -n 'class="chat-history"' webapp/src/components/ChatView.svelte
grep -n 'class="ctx"' webapp/src/components/ContextMenu.svelte
grep -n 'details class="card"' webapp/src/components/FunctionCards.svelte
grep -n 'onGroupMouseDown' webapp/src/App.svelte     # 仍在
```

人工回归（每阶段至少做一次，5.8 全量）：

- 分组拖拽排序 + 单击切换分组；
- 手机号登录三步（输入手机号 → 验证码 → 2FA）；
- 删除账号弹窗勾选前禁用/勾选后可用；
- 聊天消息发送与自动滚动；
- 深浅色切换、窗口缩放跨 899px；
- 手机端四页签 + 设置根/子页 + 面板返回。

---

## 7. 分支、提交与发版

| 项 | 约定 |
|---|---|
| 分支 | 从 `dev` 切 `ui-phase5`，完成后再合回 `dev` |
| 提交粒度 | 一个 Phase 一个 commit；a11y 修复单独一个 commit |
| 提交信息 | `Phase 5-N: <改动摘要>（无行为变化）` |
| 基线更新 | 只在该 Phase 声明的视觉区域；更新后必须人工看 PNG diff |
| 预发布 | 5.1–5.6 完成后出 `1.3.0-beta.1` 给测试者；5.7–5.8 后发 `1.3.0` |
| 版本 bump | 由发版流程改 `tg_tool.py` 的 `APP_VERSION`；不在 UI 任务内顺手改 |
| 发版 | build → PyInstaller → 部署 → tag `v1.3.0` → GitHub Release（按 `docs/RELEASE_BUILD.md`） |
| 回滚 | 单 Phase 可 `git revert`；基线 PNG 与代码同一提交，不会出现半套视觉 |

---

## 8. 风险与回滚

| 风险 | 触发点 | 防控 |
|---|---|---|
| **主题注入冲突** | 想换浅色主色/底色/顶栏色 | D1 选 A；否则单开「主题迁移」任务，改 backend + `applyTheme()` 并补测试 |
| **截图基线大面积失效** | 改令牌/密度/表面 | 每阶段只更新预期区域的基线；`maxDiffPixels: 0` 下逐张确认 |
| **拖拽命中失效** | 动 `.grp` 的 padding/高度/圆角 | 明确禁止；回归时实际拖一次分组 |
| **UI 冻结/弹窗不出** | 移动或删除 `flushSync` | 契约 grep 21；不在组件拆分中搬动登录状态机 |
| **聊天/日志滚动失效** | 改 `.log` / `.chat-history` 类名或层级 | 契约 grep；打开日志/聊天确认滚到底 |
| **深色对比度不足** | 只用背景明度做层级 | 每阶段检查 4.5:1；深色下单独走查 |
| **自定义元素无障碍** | `md-*` 组件加点击 | 加 role/tabindex，或 `svelte-ignore` + 键盘回归 |
| **字体差异** | `Segoe UI Variable` 在旧系统缺失 | 字体栈已含 `Segoe UI` / `Microsoft YaHei UI`，不新增字体 |
| **改动越界** | 顺手改脚本/接口/文案 key | 每个 commit 前 `git diff` 只允许 `app.css`、`app-ui.css`、组件模板/style、文档 |

---

## 9. Definition of Done

- [ ] 9 个 Phase 提交全部完成，每个提交 build 通过、26 条 E2E 全绿。
- [ ] 13 张视觉基线已更新并逐张人工确认。
- [ ] `flushSync` 仍为 21，5 个选择器与拖拽逻辑未变。
- [ ] 深浅色对比度达标，focus-visible 可见，reduced-motion 生效。
- [ ] 既有 76 条 a11y 告警已清零，或至少不新增（Phase 5.8 记录处理结果）。
- [ ] 删除/退群/白名单移除仍保持红色警示与二次确认。
- [ ] 手机端四页签、设置钻取、面板返回、safe-area 正常。
- [ ] `HANDOFF.md`、`UI_TEXTS.md`、`ui-inventory.md` 与现状一致。
- [ ] 没有修改 `server.py`、`tg_engine.py`、`tg_tool.py`、`api.ts`、`界面文本.txt` 的既有 key、vite 配置。

---

## 10. 明确不做

- 不改任何后端接口、数据结构、settings 字段、profiles 缓存。
- 不新增业务功能、不改任务流程、不改白名单逻辑。
- 不改文案 key、卡片 id、`card_order` 持久化值。
- 不引入新的 UI 框架、CSS 预处理器、图标库、CDN 或内嵌字体。
- 不重写 `flushSync`、拖拽、手机号登录状态机（属于行为重构，另立任务）。
- 不把 Android/移动端打包改动混入本期。

---

## 附录 A：令牌清单（Phase 5.1 目标）

| 类别 | 现有 | 新增/调整 |
|---|---|---|
| 主色角色 | `--md-sys-color-primary/on-primary/container/on-container` | 保持；浅色主色由 settings 注入 |
| 表面 | `--md-sys-color-surface*`、`--topbar-color`、`--divider` | 调层级差；顶栏色保持 settings 注入 |
| 状态 | `--status-online`、`--status-success`、`--status-warning` | 补 `--status-error`、`--status-info`、`--status-neutral` |
| 语义 | `--hover-overlay`、`--state-layer`、`--focus-ring` | 统一透明度与聚焦环 |
| 圆角 | `--radius-xs..7xl`、`--radius-pill/circle` | 保持 |
| 字号 | `--text-2xs..8xl` | 补角色别名：`--type-title/section/body/caption` |
| 间距 | `--space-2..24` | 补 `--row-height-account`、`--row-height-setting`、`--control-height` |
| 阴影 | `--shadow-*` | 补 `--elevation-0..4` 作为语义别名 |
| 动效 | 无统一令牌 | 补 `--motion-fast/base/slow`、`--motion-ease-standard/emphasized` |
| 强调色 | 手机动作图标写死 | 抽 `--accent-blue/mint/violet/amber/slate` |

---

## 附录 B：手工回归清单（5.8 全量）

1. 双击账号连接 → 顶栏状态变绿；再双击另一账号秒切。
2. 断开当前账号 → 自动切到池内下一个。
3. 执行删联系人/删对话 → 进度推进、日志实时滚动。
4. 取消任务 → 状态变「已取消」，不中断进行中的请求。
5. 分组拖拽排序 → 顺序保存；单击分组 → 过滤生效。
6. 右键账号 → 菜单出现在鼠标附近；点击空白关闭。
7. 删除账号 → 勾选前按钮禁用，勾选后可点；取消不删文件。
8. 手机号登录 → 验证码步骤、2FA 步骤都能继续。
9. 设置 → 六个分区切换、保存、深浅色切换。
10. 手机端（≤899px）→ 四页签、当前页、动态页日志、更多页、设置钻取、面板返回。
11. 缩放窗口跨 899px → 桌面三栏与手机壳互切，不残留布局。
12. 系统开启「减弱动态效果」→ 动画退化为瞬时，功能不受影响。
