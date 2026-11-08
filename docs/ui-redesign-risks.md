# TG工具箱 UI重设计风险深度分析

> **分析时间**：2026-10-28 00:30  
> **基于版本**：v1.2.2  
> **分析方法**：代码静态分析 + 模式匹配 + 依赖追踪  
> **结论先行**：**中高风险项目**，需分阶段实施，强制测试覆盖

> **状态：历史分析（2026-11-08）**。基于 v1.2.2 单文件结构；Phase 1–4 完成后部分行号已失效，现行契约以 [UI_REFACTOR_RISKS.md](UI_REFACTOR_RISKS.md) 为准。

---

## 执行摘要

### 风险等级：⚠️ **中高风险**

| 维度 | 评级 | 理由 |
|------|------|------|
| **代码复杂度** | 🔴 极高 | 7517行单文件巨石，业务逻辑与UI强耦合 |
| **副作用密度** | 🟠 高 | 21处flushSync、11处定时器、6处DOM直接操作 |
| **交互复杂性** | 🟠 高 | 分组拖拽、右键菜单、聊天滚动含精细DOM操作 |
| **状态依赖** | 🟡 中高 | 32处双向绑定、19处条件类名、167个事件处理器 |
| **测试覆盖** | 🔴 无 | 无单元测试、E2E测试，改动全凭手工验证 |

### 核心风险点（按危险程度排序）

1. **分组拖拽逻辑**（94行）：全局鼠标事件监听 + 坐标计算 + 防抖点击
2. **Svelte 5 flushSync依赖**（21处）：异步后强制同步渲染，去掉会导致UI不更新
3. **聊天消息滚动**（3处自动滚动）：依赖固定类名 `.chat-history` / `.log`
4. **右键菜单定位**：getBoundingClientRect + 边界检测翻转
5. **卡片折叠状态持久化**：querySelector遍历 + localStorage同步

---

## 1. 副作用与DOM依赖清单

### 1.1 DOM直接操作（5处）

| 位置 | 代码 | 目的 | 风险 | 缓解措施 |
|------|------|------|------|----------|
| **219-220** | `document.querySelector('.log')?.scrollTop = scrollHeight` | 日志自动滚动到底 | 🟠 改类名`.log`失效 | 改用 Svelte `bind:this` + `$effect` |
| **1008-1009** | 同上（日志加载后滚动） | 同上 | 🟠 同上 | 同上 |
| **1137-1138** | `document.querySelector('.chat-history')` | 聊天记录滚动 | 🟠 改类名失效 | 改用 `bind:this` |
| **1627-1629** | `document.querySelector('.ctx')?.getBoundingClientRect()` | 右键菜单边界检测 | 🟡 改类名失效 | 改用 Svelte 动作（action） |
| **1856-1859** | `document.querySelectorAll('details.card')` 遍历恢复 `open` | 卡片折叠状态恢复 | 🟡 改HTML结构需同步 | 改用 `{#each}` + `bind:open` |

**建议**：所有 `querySelector` 替换为 Svelte 的 `bind:this={element}` + `$effect()`，消除字符串选择器依赖。

### 1.2 强制同步渲染（flushSync 21处）

| 使用场景 | 出现次数 | 为什么必须同步 | 风险 |
|----------|----------|----------------|------|
| **异步API返回后更新状态** | 15处 | Svelte 5 的 `$state` 在 `await` 后赋值不触发重渲染 | 🔴 去掉会导致UI冻结 |
| **手机号登录流程切换** | 3处 | 两步验证切换需立即渲染输入框，否则 `{#if}` 条件不生效 | 🔴 去掉流程卡住 |
| **在线状态批量更新** | 2处 | `Set` 更新后需立即反映到列表 | 🟠 去掉在线点延迟显示 |
| **卡片折叠恢复** | 1处 | `details.open` 需在DOM渲染后同步 | 🟡 去掉折叠状态不准 |

**核心依赖行**（删除会炸）：
```javascript
// Line 627-640: 手机号登录两步切换（验证码 → 密码）
await phoneLoginStart(phone);
flushSync(() => { phoneLoginStep = 'code'; });  // 必须同步，否则输入框不出现
// ... 输入验证码后
await phoneLoginSubmit(session, code);
if (需要密码) {
  flushSync(() => { phoneLoginStep = 'password'; });  // 同步切换到密码输入
}
```

**陷阱**：改手机号登录UI布局时，必须保留 `flushSync`，否则 `{#if phoneLoginStep === 'code'}` 不触发渲染。

### 1.3 定时器与异步（11处）

| 类型 | 位置 | 用途 | 风险 |
|------|------|------|------|
| **防抖** | 197-200 | 搜索框输入300ms防抖 | 🟢 安全（纯性能优化） |
| **自动滚动** | 219, 1008, 1137 | `setTimeout(() => scroll(), 0)` 等待DOM渲染 | 🟠 改为 `$effect` 更安全 |
| **拖拽防误触** | 1560 | 拖拽结束后250ms吞掉 `click` 事件 | 🟠 改拖拽逻辑需保留 |
| **扫码登录轮询** | 575, 590 | 1.5s/3s轮询 QR 状态 | 🟡 改UI不影响，但别删 `clearTimeout` |

**关键副作用**：
```javascript
// Line 1558-1560: 拖拽排序后短暂禁用点击
suppressGroupClick = true;
setTimeout(() => (suppressGroupClick = false), 250);
```
**作用**：松手瞬间鼠标下的按钮会收到 `click` 事件，导致误切分组。必须短暂吞掉 `click`。

---

## 2. 复杂交互深度分析

### 2.1 分组拖拽排序（1517-1579，94行）

#### 实现原理
```
1. mousedown → 记录 pressGroup + 坐标
2. mousemove → 超5px判定拖动，进入 dragGroup 状态
3. mousemove 持续 → elementFromPoint 命中检测，dragGroupOver 高亮
4. mouseup → 交换顺序，调用 API
5. 延迟250ms → 解除 suppressGroupClick 防误触
```

#### 风险点（按严重性排序）

| 风险 | 说明 | 触发条件 | 后果 |
|------|------|----------|------|
| 🔴 **全局事件泄漏** | `<svelte:window onmousemove={onGroupMouseMove} onmouseup={onGroupMouseUp}>` | 组件卸载时未清理 | 内存泄漏 + 报错 |
| 🔴 **坐标计算失效** | `elementFromPoint(e.clientX, e.clientY)` 依赖鼠标坐标 | 改按钮 `padding`/`margin` | 命中检测错位，拖到其他按钮不高亮 |
| 🟠 **data属性依赖** | `btn?.getAttribute('data-group')` | 改 HTML 结构去掉 `data-group` | 拖拽完全失效 |
| 🟠 **样式耦合** | `.grp.drag-over` 高亮样式 | 改类名或去掉样式 | 用户看不到拖拽目标 |
| 🟡 **防抖时序** | `suppressGroupClick` 250ms | 改动画时长 | 拖拽后立即点击误触发 |

#### 改动禁区

**绝对不能动的部分**：
1. `<svelte:window onmousemove onmouseup>` 全局监听（line 2080）
2. `data-group` 属性（line 2089）
3. `suppressGroupClick` 机制（line 1558-1560）
4. 5px 拖拽阈值判定（line 1538）

**可以改的部分**：
- `.grp` 按钮的颜色、圆角、字体（不影响坐标）
- `.drag-over` 高亮样式（只要保留视觉区分）
- 拖拽动画（opacity、transform，不影响命中检测）

**测试要求**：
- 拖动 A 到 B → 顺序变为 BA
- 拖动后立即点击 C → 不应切换分组（防误触生效）
- 拖动到 "全部/未分组" → 不高亮，松手无效（line 1548）

### 2.2 右键菜单定位（1622-1675）

#### 实现原理
```javascript
// Line 1627-1640: 边界检测 + 翻转
const el = document.querySelector('.ctx');
const r = el.getBoundingClientRect();
const rightOverflow = e.clientX + r.width > window.innerWidth;
const bottomOverflow = e.clientY + r.height > window.innerHeight;
ctxMenu = {
  x: rightOverflow ? e.clientX - r.width : e.clientX,
  y: bottomOverflow ? e.clientY - r.height : e.clientY,
  // ...
};
```

#### 风险点

| 风险 | 说明 | 缓解 |
|------|------|------|
| 🟠 **类名依赖** | `.ctx` 选择器写死 | 改用 Svelte `use:action` 动态测量 |
| 🟡 **尺寸假设** | 假设菜单在显示后才测量 | 实际可行，但改菜单高度需重测 |
| 🟡 **滚动偏移** | 未考虑页面滚动（window.scrollY） | 当前UI无滚动，未来需补 |

**改动建议**：
- 菜单宽度/高度可改，自动重新计算翻转
- 菜单内容（按钮文字、图标）随意改
- **禁止**：去掉边界检测逻辑（会导致菜单被裁剪）

### 2.3 聊天消息自动滚动（3处）

#### 位置与触发时机

| 位置 | 触发时机 | 代码 |
|------|----------|------|
| 219-220 | 每条日志添加后 | `if (rightView === 'log') setTimeout(() => el.scrollTop = el.scrollHeight)` |
| 1008-1009 | 历史日志加载后 | 同上 |
| 1137-1138 | 聊天记录加载/新消息 | `querySelector('.chat-history')` |

#### 风险分析

**高风险**（🔴）：
- **类名硬编码**：`.log` / `.chat-history` 改了立即失效
- **条件检查**：`if (rightView === 'log')` 假设视图切换变量名不变
- **异步时序**：`setTimeout(..., 0)` 依赖浏览器下一帧渲染

**示例故障**：
```svelte
<!-- 原代码：正常工作 -->
<div class="log">...</div>

<!-- 改成这样：滚动失效 -->
<div class="log-container">...</div>  <!-- 类名变了，querySelector 找不到 -->
```

**正确改法**：
```svelte
<script>
  let logElement = $state<HTMLDivElement>();
  
  function addLog(line: string) {
    logs.push({ ts: stampNow(), msg: line });
    $effect(() => {
      if (logElement) logElement.scrollTop = logElement.scrollHeight;
    });
  }
</script>

<div class="任意类名" bind:this={logElement}>
  {#each logs as log}...{/each}
</div>
```

### 2.4 卡片折叠状态持久化（103-115, 1878-1884）

#### 实现流程
```
1. onMount → 从 settings.json 恢复 cardOpen = {基本信息: true, ...}
2. flushSync 立即渲染
3. querySelectorAll('details.card') 遍历所有卡片
4. 手动设置每个 details.open = cardOpen[name]
5. 用户点击折叠 → ontoggle 事件 → 保存到 settings.json
```

#### 为什么这么复杂？

**Svelte 5 的坑**：
```svelte
<!-- 预期：cardOpen 变化后 details 自动同步 open -->
<details open={cardOpen['基本信息']}></details>

<!-- 实际：flushSync 后 open 属性不一定更新（Svelte 5 bug） -->
<!-- 所以必须手动 querySelectorAll 强制同步 -->
```

#### 风险点

| 风险 | 说明 | 影响 |
|------|------|------|
| 🟠 **HTML结构假设** | `details.card` 选择器 + `data-card` 属性 | 改标签或属性名失效 |
| 🟠 **事件监听** | `ontoggle={(e) => onCardToggle(name, e.currentTarget.open)}` | 改为其他折叠组件需重写 |
| 🟡 **性能** | 每次恢复遍历所有 `<details>` | 6个卡片可接受，超20个需优化 |

**安全改法**：
```svelte
<!-- 方案1：不改 details，只改样式 -->
<details class="新样式名" data-card="基本信息" ...>

<!-- 方案2：换成自定义折叠组件 -->
<CollapsibleCard name="基本信息" bind:open={cardOpen['基本信息']}>
  <!-- 内容 -->
</CollapsibleCard>
```

---

## 3. 状态与绑定依赖图

### 3.1 双向绑定清单（32处）

| 类型 | 数量 | 示例 | 风险 |
|------|------|------|------|
| **输入框** | 18 | `bind:value={search}`, `bind:value={phoneInput}` | 🟢 安全（标准表单） |
| **复选框** | 2 | `bind:checked={convOverwrite}`, `bind:confirm={delConfirm}` | 🟢 安全 |
| **自定义状态** | 12 | `bind:cur2fa`, `bind:showEmailForm`, `bind:section` | 🟡 改组件 props 需同步 |

**关键依赖**（改了会炸）：
```svelte
<!-- Line 2202-2214: 聊天视图的6个绑定 -->
<ChatView
  bind:startChatName      <!-- 新会话输入框 -->
  bind:curDialog          <!-- 当前打开的对话 -->
  bind:chatDraft          <!-- 草稿输入框 -->
  bind:dialogList={dialogs}
  bind:history={historyMsgs}
  bind:recvState={recvOn}
/>
```

**风险**：拆分组件时这些 `bind:` 全部要搬到新组件的 `$props`，漏一个就报错。

### 3.2 条件类名（19处）

| 模式 | 示例 | 作用 | 风险 |
|------|------|------|------|
| `class:on` | `class:on={connected}` | 开关状态视觉反馈 | 🟢 安全（只改样式） |
| `class:active` | `class:active={curGroup === g}` | 选中态高亮 | 🟢 安全 |
| `class:online` | `class:online={onlineNames.has(a.name)}` | 在线状态小圆点 | 🟢 安全 |
| `class:drag-over` | `class:drag-over={dragGroupOver === g}` | 拖拽目标高亮 | 🟠 改了拖拽视觉丢失 |

**安全原则**：条件类名只控制样式，改类名本身不影响逻辑（CSS 里定义对应样式即可）。

### 3.3 事件处理器分布（167处）

| 事件类型 | 数量 | 风险 |
|----------|------|------|
| `onclick` | 120 | 🟢 安全（标准点击） |
| `oninput` | 10 | 🟢 安全（输入框） |
| `onkeydown` | 8 | 🟡 回车提交，改布局需保留 |
| `oncontextmenu` | 3 | 🟠 右键菜单，改了失效 |
| `ondblclick` | 2 | 🟡 双击连接账号，改布局需保留 |
| `ondragover/ondrop` | 2 | 🟠 拖入文件，改新建账号流程需保留 |
| `onmousedown/onmousemove/onmouseup` | 5 | 🔴 拖拽分组，禁止动 |
| `ontoggle` | 6 | 🟡 卡片折叠，改 `<details>` 需同步 |

---

## 4. 关键业务流程风险矩阵

### 4.1 新建账号三流程（1479-1749，270行）

#### 流程1：拖包导入

**依赖链**：
```
ondragover → 阻止默认 → 高亮拖入区
ondrop → 读取 files → base64编码 → /api/add-account
→ 后端解压/识别 → 返回 path → 刷新账号列表
```

**风险点**：
- 🟠 `ondragover`/`ondrop` 事件：改新建账号弹窗布局需保留
- 🟢 拖入区高亮样式：可随意改
- 🔴 base64编码逻辑：不能动（后端期望这个格式）

#### 流程2：扫码登录

**状态机**：
```
start → 显示二维码 → 轮询(waiting) → success → 完成
      ↘ expired → 提示重新开始
      ↘ 取消 → 清理临时会话
```

**风险点**：
- 🔴 `qrTimer` 轮询定时器：改UI不能删定时器逻辑
- 🟠 二维码 `<img src="data:image/png;base64,{pkQrImg}">` ：保留 `bind:value`
- 🟡 状态文案（"等待扫码" / "已扫码" / "已过期"）：可改文字，不能改状态值

#### 流程3：手机号登录

**最复杂状态机**（含 flushSync 陷阱）：
```
step='input' → 输入手机号 → start
  ↓ flushSync 强制渲染
step='code' → 输入验证码 → submit
  ↓ 如需2FA
  ↓ flushSync 强制渲染
step='password' → 输入密码 → submit → 完成
```

**风险点**：
- 🔴 **flushSync 同步渲染**（line 629, 634, 639）：删了UI不更新
- 🔴 **条件渲染** `{#if phoneLoginStep === 'code'}` ：改布局需保留
- 🟠 **输入框绑定** `bind:value={phoneCode}` / `bind:value={phonePwd}` ：拆组件需搬到 props
- 🟡 **回车提交** `onkeydown={(e) => { if (e.key === 'Enter') ... }}` ：改表单样式需保留

**陷阱示例**：
```svelte
<!-- 错误改法：去掉 flushSync -->
async function doPhoneLoginStart() {
  await phoneLoginStart(phone);
  phoneLoginStep = 'code';  // ❌ Svelte 5 不会立即渲染
}
<!-- 结果：用户看到的还是手机号输入框，验证码框不出现 -->

<!-- 正确改法：保留 flushSync -->
async function doPhoneLoginStart() {
  await phoneLoginStart(phone);
  flushSync(() => { phoneLoginStep = 'code'; });  // ✅ 强制同步
}
```

### 4.2 聊天消息实时推送（1805-1825）

#### 实现原理
```
WebSocket 'recv_message' 事件
→ 判断 rightView === 'chat'
→ 如果在会话列表 → 未读+1，对话置顶
→ 如果在聊天记录 && 是当前对话 → 追加消息 + 自动滚动
→ 如果不在聊天视图 → chatUnread 全局计数+1
```

**风险点**：
| 风险 | 说明 | 后果 |
|------|------|------|
| 🔴 `rightView` 变量名 | 改了视图切换逻辑失效 | 消息不更新 |
| 🟠 `curDialog` 当前对话判定 | 改了可能推送错对话 | 消息串台 |
| 🟠 `scrollHistoryBottom()` 调用 | 改了新消息不自动滚动 | 用户看不到 |
| 🟡 `chatUnread` 计数 | 改了未读徽标不准 | 小问题 |

**测试要求**：
1. 打开聊天列表 → 收到消息 → 对应对话未读+1，跳到顶部
2. 打开某个聊天记录 → 收到该对话消息 → 实时追加，自动滚动
3. 在其他视图（日志/资料） → 收到消息 → 聊天图标显示未读数

---

## 5. 手机端专用风险（v1.2.2新增）

### 5.1 响应式断点（max-width: 899px）

**实现方式**：
```css
/* 桌面端（默认）：三栏布局 */
.layout { display: flex; }
.mobile-app { display: none; }

/* 手机端：切换为单栏+底栏 */
@media (max-width: 899px) {
  .layout { display: none; }
  .mobile-app { display: flex; }
}
```

**风险点**：
| 风险 | 说明 | 影响 |
|------|------|------|
| 🔴 **断点硬编码** | `899px` 写死 | 改了可能同时显示两套UI |
| 🟠 **两套模板共存** | 桌面(2078-2280) + 手机(1906-2078) | 改功能需改两处 |
| 🟡 **状态共享** | `current`, `logs`, `progress` 两套UI共用 | 状态不一致风险 |

### 5.2 Material 3动效（17处动画）

**关键动画**：
```css
/* Line 7419-7427: 页面切换淡入+上移 */
@keyframes m-page-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Line 7501-7506: 在线点呼吸 */
@keyframes m-conn-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(..., 40%); }
  50% { box-shadow: 0 0 0 5px rgba(..., 0%); }
}
```

**风险点**：
| 风险 | 说明 | 后果 |
|------|------|------|
| 🟢 **纯视觉动画** | 不影响布局和交互 | 随意改时长/缓动 |
| 🟡 **transform依赖** | `translateY` 假设元素无其他transform | 冲突会叠加 |
| 🟡 **无障碍** | `prefers-reduced-motion: reduce` 已支持 | 系统关闭动效时自动禁用 |

**安全改动**：
- 改时长（200ms → 300ms）
- 改缓动函数（cubic-bezier）
- 改位移距离（10px → 20px）
- 改透明度范围

**禁止改动**：
- 去掉 `@media (prefers-reduced-motion)` 适配
- 改 `animation` 属性名（CSS引用会失效）

### 5.3 触控优化

**关键实现**：
```css
/* Line 7404-7410: 去掉点击延迟 + 蓝色高亮 */
.mobile-app button {
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

/* Line 7426-7431: 按压反馈 */
.mobile-account-row:active {
  transform: scale(0.975);
  transition: transform 120ms cubic-bezier(0.2, 0, 0, 1);
}
```

**风险点**：
| 风险 | 说明 | 影响 |
|------|------|------|
| 🟢 **纯优化** | 不影响功能 | 去掉只是体验变差 |
| 🟡 **scale变换** | 假设按钮无其他transform | 改布局时检查冲突 |

---

## 6. 分阶段实施建议（降低风险）

### Phase 0：环境准备（必须先做）

| 任务 | 目的 | 产物 |
|------|------|------|
| **建立测试基线** | 记录当前所有功能的正确行为 | 测试清单.xlsx（50+项） |
| **搭建E2E测试** | Playwright/Cypress 覆盖关键路径 | `tests/` 目录 + CI配置 |
| **截图对比** | Percy/Chromatic 视觉回归测试 | 30+页面截图基线 |
| **风险点标注** | 代码中标注"⚠️ 改动需谨慎" | 注释 + README |

**不做Phase 0直接改 = 盲飞**，改完全凭手工点点点，漏bug是必然。

### Phase 1：纯结构拆分（零行为变更）

**目标**：8179行 → 13个子组件，功能完全不变

**拆分顺序**（按依赖关系）：

1. **LogView.svelte**（最简单，无交互） → 50行
2. **ProfileView.svelte**（纯表单） → 120行
3. **ChatView.svelte**（含滚动，需bind:this） → 200行
4. **SecurityView.svelte**（passkey复杂，单独隔离） → 180行
5. **SettingsDialog.svelte**（7导航+表单） → 300行
6. **AccountList.svelte**（含右键菜单） → 250行
7. **FunctionCards.svelte**（6张卡片） → 200行
8. **ContextMenu.svelte**（右键菜单定位逻辑） → 80行
9. **DeleteAccountDialog.svelte**（高危操作单独组件） → 60行
10. **AddAccountDialog.svelte**（三流程，最复杂） → 350行
11. **MobileShell.svelte**（四页签） → 300行
12. **GroupManagement.svelte**（拖拽逻辑，最危险） → 150行
13. **RightPanel.svelte**（视图切换容器） → 100行

**每个组件拆完必须**：
- ✅ `npm run build` 成功
- ✅ E2E测试全绿
- ✅ 截图对比无差异
- ✅ 独立commit（便于回滚）

**预计时间**：20小时（平均每组件1.5小时）

### Phase 2：提取CSS变量（低风险）

**目标**：消灭130处硬编码颜色、375处硬编码px

**步骤**：
1. 在 `app.css` 新增变量：
   ```css
   --spacing-xs: 4px;
   --spacing-sm: 8px;
   --spacing-md: 12px;
   --spacing-lg: 16px;
   --spacing-xl: 24px;
   ```
2. 全局替换：`padding: 12px` → `padding: var(--spacing-md)`
3. 验证：截图对比确认视觉无差异

**预计时间**：8小时

### Phase 3：统一间距栅格（中风险）

**目标**：4dp网格，消除 `5px`, `7px`, `11px` 等不规则值

**风险**：
- 🟠 改 `padding` 可能影响拖拽坐标计算
- 🟠 改 `height` 可能影响滚动检测

**缓解**：
- 每改一个组件立即跑E2E
- 拖拽、滚动相关的尺寸最后改

**预计时间**：12小时

### Phase 4：Material 3组件补全（中风险）

**目标**：引入 `md-card`, `md-dialog`, `md-list`

**风险**：
- 🟠 `md-dialog` 行为可能与自定义弹窗不同
- 🟡 `md-list` 滚动行为需验证

**缓解**：
- 先在非关键区域试用（如"关于"页）
- 关键弹窗（删除账号）保持自定义

**预计时间**：16小时

### Phase 5：手机端交互优化（高风险）

**目标**：新手势、过渡动画、下拉刷新

**风险**：
- 🔴 手势识别可能与现有事件冲突
- 🟠 动画可能影响性能

**缓解**：
- 在 `<900px` 独立分支开发
- Feature Flag 控制上线

**预计时间**：24小时

---

## 7. 强制测试覆盖要求

### 7.1 E2E测试清单（最低要求）

#### 关键路径（18项，必须100%通过）

| 编号 | 测试用例 | 验证点 |
|------|----------|--------|
| E01 | 启动应用 | 顶栏显示版本号 |
| E02 | 双击账号卡片 | 连接成功，顶栏变绿 |
| E03 | 分组拖拽排序 | A拖到B后面，顺序变为BA |
| E04 | 拖拽后立即点击 | 不切换分组（防误触生效） |
| E05 | 账号右键菜单 | 菜单在鼠标位置，不被裁剪 |
| E06 | 卡片折叠 | 刷新后状态保持 |
| E07 | 搜索账号 | 输入关键词，列表过滤 |
| E08 | 删除联系人 | 进度条推进，日志滚动 |
| E09 | 聊天消息接收 | 新消息追加，自动滚动 |
| E10 | 新建账号-拖包 | 拖入zip，账号列表更新 |
| E11 | 新建账号-扫码 | 二维码显示，轮询生效 |
| E12 | 新建账号-手机号 | 验证码→密码两步切换 |
| E13 | 删除账号确认 | 勾选框未勾选，按钮禁用 |
| E14 | 设置保存 | 修改主题，刷新后保持 |
| E15 | 手机端-底栏切换 | 四个页签切换正常 |
| E16 | 手机端-深页返回 | 点返回回到列表 |
| E17 | 浅色/深色切换 | 颜色立即切换，无闪烁 |
| E18 | WebSocket重连 | 断网重连后日志继续接收 |

#### 视觉回归（截图对比，30+页面）

- 桌面端：浅色/深色各15张
- 手机端：浅色/深色各15张
- 关键弹窗：5张

**工具推荐**：
- E2E：Playwright（官方Svelte支持）
- 视觉：Percy（GitHub集成） 或 Chromatic（Storybook）

### 7.2 手工测试清单（改动后必做）

| 分类 | 项目 | 验证点 |
|------|------|--------|
| **拖拽** | 分组排序 | 顺序正确，防误触生效 |
| **滚动** | 日志/聊天自动滚动 | 新内容可见，不卡顿 |
| **右键** | 账号/分组菜单 | 定位准确，不被裁剪 |
| **输入** | 所有表单 | 回车提交，ESC取消 |
| **弹窗** | 删除确认 | 勾选才能点，路径正确 |
| **手机** | 四页签 + 深页 | 切换流畅，返回正常 |
| **动画** | 页面切换 | 时长合理，无卡顿 |
| **主题** | 浅色/深色 | 所有颜色适配，对比度够 |

---

## 8. 应急回滚预案

### 8.1 回滚触发条件

**立即回滚**（生产环境遇到）：
- 🔴 关键功能失效（连接账号、删除操作、新建账号）
- 🔴 数据丢失风险（账号列表清空、设置重置）
- 🔴 严重性能问题（界面卡死、内存泄漏）

**计划回滚**（测试环境发现）：
- 🟠 E2E测试通过率 < 90%
- 🟠 视觉回归超过10处差异
- 🟠 关键bug无法在24小时内修复

### 8.2 回滚机制

**代码层面**：
```bash
# 每个Phase打tag
git tag ui-redesign-phase1-complete
git tag ui-redesign-phase2-complete

# 回滚到上一个稳定版本
git reset --hard ui-redesign-phase1-complete
npm run build
# 重新打包部署
```

**用户层面**：
- 保留旧版本exe备份
- settings.json 向后兼容（新字段有默认值）
- profiles.json 不改结构

### 8.3 灰度发布

**策略**：
1. **内部测试**（Phase 1-3）：开发者自己用1周
2. **Beta测试**（Phase 4）：发给3-5个用户，收集反馈
3. **金丝雀发布**（Phase 5）：正式版带"实验性功能"开关
4. **全量发布**：Beta稳定2周后

---

## 9. 总结与行动建议

### 9.1 风险评估结论

**整体风险等级：⚠️ 中高风险**

- ✅ **技术可行**：Svelte 5架构良好，拆分和重构都可行
- ⚠️ **复杂度高**：8179行单文件，94行拖拽逻辑，21处flushSync陷阱
- ❌ **测试缺失**：无自动化测试，改动全凭手工验证，风险极高

### 9.2 强烈建议

**必须先做**（否则不要开始）：
1. ✅ 建立E2E测试（Playwright，覆盖18项关键路径）
2. ✅ 截图基线（Percy/Chromatic，30+页面）
3. ✅ 手工测试清单（打印出来，每次改动过一遍）

**分阶段实施**：
- Phase 0（环境）→ Phase 1（拆分）→ Phase 2（变量）→ Phase 3（栅格）→ Phase 4（组件）→ Phase 5（手机）
- 每个Phase独立验证，通过后再进下一个
- 预留20%时间处理意外bug

**禁止操作**：
- ❌ 不建测试直接改
- ❌ 同时改多个Phase
- ❌ 改完不验证就commit
- ❌ 跳过视觉回归测试

### 9.3 投入估算

| Phase | 开发 | 测试 | 总计 | 风险 |
|-------|------|------|------|------|
| Phase 0（环境） | 8h | 4h | 12h | 低 |
| Phase 1（拆分） | 20h | 10h | 30h | 低 |
| Phase 2（变量） | 8h | 4h | 12h | 低 |
| Phase 3（栅格） | 12h | 6h | 18h | 中 |
| Phase 4（组件） | 16h | 8h | 24h | 中 |
| Phase 5（手机） | 24h | 12h | 36h | 高 |
| **总计** | **88h** | **44h** | **132h** | - |

**约16.5个工作日**（按8小时/天），实际建议预留**20个工作日**（含缓冲）。

### 9.4 最终建议

**如果你问："要不要做UI重设计？"**

答案：**要做，但必须分阶段，强制测试覆盖**。

**如果你问："能不能不建测试直接改？"**

答案：**不能。7517行单文件巨石 + 21处flushSync陷阱 + 无测试 = 改一处炸一片**。

**如果你问："最快多久能上线？"**

答案：**最快4周（Phase 0-3，低风险改动）；完整重设计需6-8周**。

---

**文档结束** · 生成时间：2026-10-28 00:30  
**下一步**：与团队评审，决定是否启动Phase 0（环境准备）
