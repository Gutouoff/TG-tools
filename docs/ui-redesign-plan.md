# TG工具箱 UI重设计方案（保持M3结构）

> **方案时间**：2026-10-28  
> **设计目标**：保留Material 3框架，优化信息密度、批量操作流程、风险操作视觉区分  
> **约束条件**：仅改样式与布局，保持所有业务逻辑和交互不变  
> **基线版本**：v1.2.2（7517行单文件巨石）

> **状态：历史草案（2026-11-08 起由 [ui-phase5-plan.md](ui-phase5-plan.md) 接替）**。Phase 1–4 已按另一条路径完成（19 个组件 + `app.css` 令牌 + `zh.ts` 文案）；本文的 T1/T2 任务分解与色板不再直接适用，保留作设计参考。

---

## 1. 设计原则

### 5条核心原则

| 原则 | 说明 | 应用场景 |
|------|------|----------|
| **高密度信息承载** | 在M3的宽松间距基础上，收紧20%的padding/margin，充分利用屏幕空间，减少滚动次数 | 账号列表、功能卡片、日志面板 |
| **批量操作一致性** | 所有批量任务UI（删除、转换、打包）共用统一的进度/确认模式，降低认知成本 | 任务面板、进度条、确认弹窗 |
| **风险操作视觉升级** | 危险操作（删除账号/分组、拉黑bot）必须视觉突出，但不过度吸引；采用"2级确认+路径提示"模式 | 删除类弹窗、白名单移除 |
| **深色优先、浅色适配** | 以深色为主题基准设计，充分利用深色的高对比度优势；浅色作为备选（保留但非重点） | 颜色令牌、组件状态层 |
| **动效支持冗余取消** | 关键操作（新建账号、登录流程）的状态切换必须有"返回上一步"的视觉提示，动效时长200ms以内 | 新建账号三流程、手机号登录 |

---

## 2. 设计令牌体系

### 2.1 颜色系统（Material 3基础上调整）

#### 浅色主题（Light）

```css
/* 原色角色 - 保持M3标准，但加强对比 */
--md-sys-color-primary: #0D47A1;              /* 更深的蓝（替代#356AE6），增强视觉层级 */
--md-sys-color-on-primary: #FFFFFF;
--md-sys-color-primary-container: #E3F2FD;    /* 保持浅蓝背景 */
--md-sys-color-on-primary-container: #0D47A1;

/* 次色 - 强化实用性 */
--md-sys-color-secondary: #455A64;            /* 更沉的灰，用于次要操作 */
--md-sys-color-on-secondary: #FFFFFF;
--md-sys-color-secondary-container: #ECEFF1;

/* 三级色 - 用于特殊强调 */
--md-sys-color-tertiary: #F57C00;             /* 橙色，用于"运行中"状态 */
--md-sys-color-on-tertiary: #FFFFFF;
--md-sys-color-tertiary-container: #FFE0B2;

/* 表面色 */
--md-sys-color-surface: #FAFAFA;              /* 极浅灰，减少纯白刺激 */
--md-sys-color-surface-dim: #E0E0E0;
--md-sys-color-surface-bright: #F5F5F5;
--md-sys-color-surface-container-lowest: #FFFFFF;
--md-sys-color-surface-container-low: #F5F5F5;
--md-sys-color-surface-container: #EEEEEE;
--md-sys-color-surface-container-high: #E8E8E8;
--md-sys-color-surface-container-highest: #E0E0E0;
--md-sys-color-surface-variant: #E0E0E0;

/* 文字层 */
--md-sys-color-on-surface: #1A1A1A;
--md-sys-color-on-surface-variant: #616161;
--md-sys-color-outline: #9E9E9E;
--md-sys-color-outline-variant: #BDBDBD;

/* 错误 */
--md-sys-color-error: #D32F2F;                /* 鲜红，危险操作专用 */
--md-sys-color-on-error: #FFFFFF;
--md-sys-color-error-container: #FFEBEE;
--md-sys-color-on-error-container: #B71C1C;

/* 语义色（新增） */
--md-sys-color-success: #2E7D32;              /* 绿：账号在线、任务完成 */
--md-sys-color-warning: #F57F17;              /* 黄：待改名、FloodWait */
--md-sys-color-info: #0277BD;                 /* 浅蓝：信息提示 */
```

#### 深色主题（Dark）

```css
:root[data-theme='dark'] {
  /* 原色角色 - 深色下提亮以保持可读性 */
  --md-sys-color-primary: #90CAF9;            /* 浅蓝，保持M3标准 */
  --md-sys-color-on-primary: #000B4D;
  --md-sys-color-primary-container: #1A237E;
  --md-sys-color-on-primary-container: #E3F2FD;

  /* 次色 */
  --md-sys-color-secondary: #B0BEC5;          /* 浅灰 */
  --md-sys-color-on-secondary: #1C1C1C;
  --md-sys-color-secondary-container: #37474F;

  /* 三级色 */
  --md-sys-color-tertiary: #FFB74D;           /* 浅橙，"运行中"状态 */
  --md-sys-color-on-tertiary: #332200;
  --md-sys-color-tertiary-container: #E65100;

  /* 表面色 */
  --md-sys-color-surface: #121212;            /* 纯黑，OLED友好 */
  --md-sys-color-surface-dim: #0F0F0F;
  --md-sys-color-surface-bright: #282828;
  --md-sys-color-surface-container-lowest: #0D0D0D;
  --md-sys-color-surface-container-low: #1A1A1A;
  --md-sys-color-surface-container: #262626;
  --md-sys-color-surface-container-high: #313131;
  --md-sys-color-surface-container-highest: #3C3C3C;
  --md-sys-color-surface-variant: #313131;

  /* 文字层 */
  --md-sys-color-on-surface: #F5F5F5;
  --md-sys-color-on-surface-variant: #BDBDBD;
  --md-sys-color-outline: #757575;
  --md-sys-color-outline-variant: #616161;

  /* 错误 */
  --md-sys-color-error: #FF6B6B;              /* 更鲜的红，危险操作 */
  --md-sys-color-on-error: #1A0000;
  --md-sys-color-error-container: #C62828;
  --md-sys-color-on-error-container: #FFEBEE;

  /* 语义色 */
  --md-sys-color-success: #81C784;            /* 浅绿 */
  --md-sys-color-warning: #FFD54F;            /* 浅黄 */
  --md-sys-color-info: #64B5F6;               /* 浅蓝 */
}
```

### 2.2 圆角系统（保持M3）

```css
--md-sys-shape-corner-extra-small: 4px;
--md-sys-shape-corner-small: 8px;
--md-sys-shape-corner-medium: 12px;
--md-sys-shape-corner-large: 16px;
--md-sys-shape-corner-extra-large: 28px;
```

### 2.3 间距系统（优化密度）

```css
/* 基础栅格：4dp */
--spacing-xs: 4px;                /* 极小间距（icon间距、细节） */
--spacing-sm: 8px;                /* 小间距（行内元素、列表项内间距） */
--spacing-md: 12px;               /* 标准间距（卡片内容、按钮padding） */
--spacing-lg: 16px;               /* 大间距（卡片间距、区块padding） */
--spacing-xl: 24px;               /* 超大间距（主要区块） */
--spacing-2xl: 32px;              /* 页面级间距 */

/* 高密度调整（相比M3减少20%） */
--spacing-compact-xs: 2px;        /* 极小 */
--spacing-compact-sm: 6px;        /* 小 */
--spacing-compact-md: 10px;       /* 标准 */
--spacing-compact-lg: 14px;       /* 大 */
--spacing-compact-xl: 20px;       /* 超大 */
```

**应用规则**：
- 账号列表、日志面板、设置表单：用`compact-*`系列
- 功能卡片、弹窗：用标准`spacing-*`系列
- 桌面顶栏、左栏分组：用标准系列

### 2.4 字阶与字体

```css
/* 字体栈：保持系统字体，支持本地打包 */
--font-family-base: 'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
--font-family-mono: 'Fira Code', 'Consolas', monospace;

/* 字阶（M3规范） */
--md-sys-typescale-display-large: 57px / 64px / 500;
--md-sys-typescale-display-medium: 45px / 52px / 500;
--md-sys-typescale-display-small: 36px / 44px / 400;

--md-sys-typescale-headline-large: 32px / 40px / 600;      /* 页面标题 */
--md-sys-typescale-headline-medium: 28px / 36px / 500;     /* 卡片标题 */
--md-sys-typescale-headline-small: 24px / 32px / 600;      /* 弹窗标题 */

--md-sys-typescale-title-large: 22px / 28px / 500;         /* 顶栏标题 */
--md-sys-typescale-title-medium: 16px / 24px / 500;        /* 卡片小标题 */
--md-sys-typescale-title-small: 14px / 20px / 500;         /* 列表项标题 */

--md-sys-typescale-body-large: 16px / 24px / 400;          /* 正文（大） */
--md-sys-typescale-body-medium: 14px / 20px / 500;         /* 正文（中） */
--md-sys-typescale-body-small: 12px / 16px / 400;          /* 正文（小，日志用） */

--md-sys-typescale-label-large: 14px / 20px / 500;         /* 标签（大） */
--md-sys-typescale-label-medium: 12px / 16px / 500;        /* 标签（中） */
--md-sys-typescale-label-small: 11px / 16px / 500;         /* 标签（小） */
```

**字体许可**：
- Segoe UI：Windows系统字体，Microsoft授权，所有Windows版本内置
- Microsoft YaHei UI：Windows中文字体，Microsoft授权，所有中文Windows版本内置
- 无需外链，完全本地打包支持

### 2.5 阴影系统（深色优化）

```css
/* M3标准elevation映射到shadow */
--md-sys-shadow-none: none;
--md-sys-shadow-level1: 0 1px 2px rgba(0, 0, 0, 0.3),
                        0 1px 3px rgba(0, 0, 0, 0.12);      /* 卡片、按钮 */
--md-sys-shadow-level2: 0 3px 6px rgba(0, 0, 0, 0.3),
                        0 3px 6px rgba(0, 0, 0, 0.15);      /* 弹窗、下拉菜单 */
--md-sys-shadow-level3: 0 10px 20px rgba(0, 0, 0, 0.3),
                        0 6px 12px rgba(0, 0, 0, 0.18);     /* 模态叠加 */
--md-sys-shadow-level4: 0 15px 30px rgba(0, 0, 0, 0.3),
                        0 10px 18px rgba(0, 0, 0, 0.2);     /* 通知、浮动操作 */

/* 深色模式调整：增加半透明黑的比例 */
:root[data-theme='dark'] {
  --md-sys-shadow-level1: 0 1px 2px rgba(0, 0, 0, 0.6);
  --md-sys-shadow-level2: 0 3px 6px rgba(0, 0, 0, 0.7);
  --md-sys-shadow-level3: 0 10px 20px rgba(0, 0, 0, 0.8);
  --md-sys-shadow-level4: 0 15px 30px rgba(0, 0, 0, 0.9);
}
```

### 2.6 动效时长（快节奏批量操作优化）

```css
/* 时长预设 */
--motion-duration-short1: 50ms;               /* 极快：反馈颜色变化 */
--motion-duration-short2: 100ms;              /* 快：简单平移、缩放 */
--motion-duration-short3: 150ms;              /* 中快：复合动画 */
--motion-duration-medium1: 200ms;             /* 中：标准过渡（推荐） */
--motion-duration-medium2: 250ms;             /* 中慢：复杂状态切换 */
--motion-duration-long: 300ms;                /* 慢：模态层、全屏切换 */
--motion-duration-extra-long: 500ms;          /* 极慢：不推荐使用 */

/* 缓动函数 */
--motion-easing-standard: cubic-bezier(0.2, 0, 0, 1);        /* 标准 */
--motion-easing-emphasized: cubic-bezier(0.05, 0.7, 0.1, 1); /* 强调（弹出） */
--motion-easing-decelerate: cubic-bezier(0, 0, 0.2, 1);       /* 减速（进入） */
--motion-easing-accelerate: cubic-bezier(0.8, 0, 1, 0.2);     /* 加速（离开） */
```

**应用**：
- 列表项hover：50ms标准缓动
- 弹窗出现/消失：200ms强调缓动
- 状态切换（在线→离线）：150ms标准缓动
- 进度条推进：100ms线性

---

## 3. 关键组件规范

### 3.1 账号卡片与列表

#### 桌面版（左栏，行高优化）

**当前状态**：
- 行高约66-72px（含padding和avatar）
- avatar 48x48px + 文字标签

**重设计后**：
```
[Avatar]  账号名 @username
48x48     [在线点/失效标签] [待改名徽标]
          phone: +86xxx...
          
高度：64px（4dp栅格对齐，减少margin）
间距：
  - avatar左边距：8px
  - avatar右边距：12px
  - 右侧标签/徽标：4px间距
  - 底部行间距：4px
```

**状态规范**：
| 状态 | 外观 | 颜色 |
|------|------|------|
| 默认 | surface-container-low背景，无框 | `--md-sys-color-surface-container-low` |
| 悬停 | 背景变亮，状态层叠加 | `background: --surface + state-layer` |
| 选中（current） | 左边3px蓝条，背景变亮 | `border-left: 3px --primary` |
| 在线 | 右下绿点（10x10px），呼吸动画2.4s | `--success`，`animation: pulse 2.4s` |
| 离线 | 无点 | - |
| 失效 | "失效"红标签（8x16px） | `background: --error` |
| 待改名 | 右上黄标签"待改名"（编辑中） | `background: --warning` |

**密度规则**：
- **标准密度**（默认）：行高64px，用`spacing-md`
- **紧凑密度**（可选设置）：行高56px，用`spacing-compact-md`

#### 手机版（列表，流式布局）

```
搜索栏（height 44px）
分组胶囊（8px gap，overflow-x auto）
---
账号行（高度56px，4dp栅格）
[Avatar] 账号名        [在线点]
         @username
         [状态标签]
         
Tap激活区：整行可点，下拉连接按钮
```

### 3.2 功能卡片（中栏）

**当前结构**：`<details class="card" open=...>`内6张卡片折叠

**重设计优化**：

```
卡片框架
├─ 标题行（28px高）
│  ├─ 卡片名（title-medium, 16px）
│  ├─ 展开/收起图标
│  └─ 可选：状态徽标（如"运行中"）
├─ 分隔线（1px, --outline-variant）
└─ 内容区（动态高度）
   ├─ 按钮组（flex wrap）
   ├─ 表单（spacing-compact-md）
   └─ 状态行

卡片尺寸：全宽，margin: 8px 0
标题padding：12px（上下10px + 文字间距）
内容padding：12px（compact-lg）
```

**状态规范**：
| 状态 | 样式 |
|------|------|
| 默认 | surface-container背景，border-radius-lg |
| 展开 | 底部阴影level1，边框 outline-variant 1px |
| 收起 | 无阴影，title行保留 |
| 运行中 | 标题右侧"运行中"徽标，tertiary色 |
| 完成 | 标题右侧"✓"绿标 |
| 错误 | 标题变红，error色 |

### 3.3 分组与搜索栏

#### 分组胶囊

```css
/* 分组按钮布局 */
.groups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;                    /* 减少默认8px到6px */
  padding: 8px 0;              /* 上下紧贴 */
  margin-bottom: 8px;
  overflow-x: auto;            /* 手机端支持横滑 */
}

.grp {
  padding: 6px 12px;           /* 减少上下from 8px */
  height: 32px;
  border-radius: corner-medium;
  font-size: label-medium;
  border: 1px solid outline-variant;
}

.grp.on {
  background: primary-container;
  border-color: primary;
  color: primary;
}

.grp.drag-over {
  outline: 2px dashed primary;
  outline-offset: -2px;
}
```

#### 搜索栏

```css
.search {
  width: 100%;
  height: 40px;                 /* 规范M3搜索框高度 */
  padding: 8px 12px;
  border: 1px solid outline;
  border-radius: corner-medium;
  background: surface;
  font-size: body-medium;
  transition: border-color 100ms, box-shadow 100ms;
}

.search:focus {
  outline: none;
  border-color: primary;
  box-shadow: 0 0 0 2px rgba(primary, 0.12);
}
```

### 3.4 任务面板（进度展示）

```html
<!-- 结构 -->
<div class="progress-panel">
  <div class="progress-header">
    <span class="progress-label">删除联系人</span>
    <span class="progress-count">23/150</span>
  </div>
  <div class="progress-bar-wrap">
    <div class="progress-bar" style="width: 15%"></div>
  </div>
  <button class="progress-cancel">取消</button>
</div>
```

```css
.progress-panel {
  display: flex;
  flex-direction: column;
  gap: spacing-sm;
  padding: spacing-md;
  background: surface-container;
  border-radius: corner-medium;
  border-left: 4px solid tertiary;  /* 运行中的橙色左边框 */
}

.progress-bar {
  height: 6px;
  background: tertiary;
  border-radius: corner-extra-small;
  transition: width 100ms standard;
}

.progress-cancel {
  align-self: flex-end;
  padding: 8px 16px;
  height: 36px;
  border-radius: corner-medium;
  background: surface-container-high;
  border: none;
  cursor: pointer;
  font-size: label-large;
}
```

**状态**：
| 状态 | 左边框 | 进度条色 | 取消按钮 |
|------|--------|----------|----------|
| 运行中 | 橙(tertiary) | tertiary | 活跃 |
| 完成 | 绿(success) | success | 禁用 |
| 错误 | 红(error) | error | 活跃 |
| 已取消 | 灰(outline) | outline-variant | 禁用 |

### 3.5 日志面板

```css
.log {
  flex: 1;
  overflow-y: auto;
  padding: spacing-md;
  background: surface;
  font-family: var(--font-family-mono);
  font-size: body-small;        /* 12px */
  line-height: 1.6;
  gap: 2px;                      /* 日志行极小间距 */
}

.log-item {
  padding: 4px 0;               /* 极小垂直间距 */
  display: flex;
  gap: spacing-xs;
}

.log-item.error {
  color: error;
}

.log-item.warn {
  color: warning;
}

.log-item.info {
  color: on-surface-variant;
}

.log-timestamp {
  color: outline-variant;
  flex-shrink: 0;
  width: 80px;                  /* 固定宽度对齐 */
}
```

### 3.6 速度档选择

```html
<div class="speed-selector">
  <div class="speed-label">删除速度</div>
  <div class="speed-buttons">
    <button class="speed-btn">极快</button>
    <button class="speed-btn">快速</button>
    <button class="speed-btn active">默认</button>
    <button class="speed-btn">慢速</button>
    <button class="speed-btn">极慢</button>
  </div>
</div>
```

```css
.speed-buttons {
  display: flex;
  gap: 4px;
  margin-top: spacing-sm;
}

.speed-btn {
  flex: 1;
  padding: 8px 0;
  height: 36px;
  border: 1px solid outline-variant;
  border-radius: corner-medium;
  background: surface-container-low;
  cursor: pointer;
  font-size: label-medium;
  transition: all 100ms standard;
}

.speed-btn:hover {
  background: surface-container;
  border-color: primary;
}

.speed-btn.active {
  background: primary-container;
  border-color: primary;
  color: primary;
  font-weight: 600;
}
```

### 3.7 白名单管理

```html
<div class="whitelist-section">
  <div class="whitelist-header">
    <input class="whitelist-input" placeholder="用户ID / 群组ID" />
    <button class="whitelist-add">添加</button>
  </div>
  <ul class="whitelist-list">
    <li class="whitelist-item">
      <span>5434838648</span>
      <button class="whitelist-remove">移除</button>
    </li>
  </ul>
</div>
```

```css
.whitelist-input {
  flex: 1;
  height: 40px;
  padding: 8px 12px;
  border: 1px solid outline;
  border-radius: corner-medium;
  font-size: body-medium;
  background: surface;
}

.whitelist-list {
  margin-top: spacing-md;
  list-style: none;
  padding: 0;
  gap: spacing-xs;
  display: flex;
  flex-direction: column;
}

.whitelist-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: spacing-sm spacing-md;
  background: surface-container-low;
  border-radius: corner-small;
  font-size: body-medium;
}

.whitelist-remove {
  padding: 4px 12px;
  height: 28px;
  background: none;
  border: 1px solid error;
  color: error;
  border-radius: corner-small;
  cursor: pointer;
  font-size: label-small;
  transition: all 100ms standard;
}

.whitelist-remove:hover {
  background: error;
  color: on-error;
}
```

### 3.8 危险操作按钮（删除/退群）

```css
/* 高危操作按钮规范 */
.danger-btn {
  padding: 10px 24px;
  height: 44px;
  border-radius: corner-medium;
  background: error;
  color: on-error;
  border: none;
  font-size: label-large;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--md-sys-shadow-level1);
  transition: all 150ms emphasized;
}

.danger-btn:hover {
  box-shadow: var(--md-sys-shadow-level2);
  background: color-mix(in srgb, error 90%, black 10%);  /* 加深 */
}

.danger-btn:active {
  transform: scale(0.98);
}

.danger-btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

/* 中危按钮（删除分组） */
.warning-btn {
  background: warning;
  color: on-surface;
}

.warning-btn:hover {
  background: color-mix(in srgb, warning 85%, black 15%);
}
```

### 3.9 弹窗（高危操作确认）

```html
<!-- 删除账号弹窗结构 -->
<div class="dialog-overlay">
  <div class="dialog-content">
    <div class="dialog-header">
      <h2>删除账号</h2>
      <button class="dialog-close">✕</button>
    </div>
    
    <div class="dialog-body">
      <div class="dialog-warning">
        此操作<strong>不可恢复</strong>。将永久删除该账号的 session、tdata、登录凭据等全部文件。
      </div>
      
      <div class="dialog-path">
        <span class="label">将被删除的文件夹</span>
        <code>D:\Desktop\TG小号\Dexpornuxiuo</code>
      </div>
      
      <label class="dialog-checkbox">
        <input type="checkbox" />
        我已了解该操作不可恢复，确认删除该账号的全部文件
      </label>
    </div>
    
    <div class="dialog-footer">
      <button class="btn-secondary">取消</button>
      <button class="danger-btn" disabled>永久删除</button>
    </div>
  </div>
</div>
```

```css
.dialog-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);  /* 深色背景提升焦点 */
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fade-in 200ms emphasized;
}

.dialog-content {
  background: surface;
  border-radius: corner-extra-large;
  box-shadow: var(--md-sys-shadow-level4);
  max-width: 480px;
  width: 90%;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: spacing-lg;
  border-bottom: 1px solid outline-variant;
}

.dialog-header h2 {
  margin: 0;
  font-size: headline-small;
  color: on-surface;
}

.dialog-close {
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 20px;
  color: on-surface-variant;
  transition: color 100ms standard;
}

.dialog-close:hover {
  color: on-surface;
}

.dialog-body {
  padding: spacing-lg;
  display: flex;
  flex-direction: column;
  gap: spacing-md;
}

.dialog-warning {
  padding: spacing-md;
  background: color-mix(in srgb, error 12%, surface);
  border-left: 4px solid error;
  border-radius: corner-small;
  font-size: body-medium;
  color: on-surface;
}

.dialog-warning strong {
  color: error;
}

.dialog-path {
  display: flex;
  flex-direction: column;
  gap: spacing-xs;
}

.dialog-path .label {
  font-size: label-medium;
  color: on-surface-variant;
}

.dialog-path code {
  padding: spacing-sm;
  background: surface-container;
  border-radius: corner-small;
  font-family: var(--font-family-mono);
  font-size: body-small;
  color: on-surface;
  word-break: break-all;
}

.dialog-checkbox {
  display: flex;
  align-items: flex-start;
  gap: spacing-sm;
  font-size: body-medium;
  cursor: pointer;
}

.dialog-checkbox input {
  margin-top: 4px;
  cursor: pointer;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: spacing-md;
  padding: spacing-lg;
  background: surface-container-low;
  border-top: 1px solid outline-variant;
}

.btn-secondary {
  padding: 10px 24px;
  height: 40px;
  border: 1px solid outline;
  background: surface;
  border-radius: corner-medium;
  cursor: pointer;
  font-size: label-large;
  transition: all 100ms standard;
}

.btn-secondary:hover {
  background: surface-container;
}
```

### 3.10 通知与状态提示

```css
/* 浮动提示（异步反馈） */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: spacing-md spacing-lg;
  background: surface-container-high;
  color: on-surface;
  border-radius: corner-medium;
  box-shadow: var(--md-sys-shadow-level2);
  font-size: body-medium;
  max-width: 400px;
  animation: slide-up 200ms emphasized;
  z-index: 2000;
}

.toast.success {
  border-left: 4px solid success;
}

.toast.error {
  border-left: 4px solid error;
  color: error;
}

.toast.warning {
  border-left: 4px solid warning;
}

@keyframes slide-up {
  from {
    transform: translateX(-50%) translateY(100px);
    opacity: 0;
  }
  to {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
  }
}
```

---

## 4. 实施路线

### 4.1 先拆分还是先改样式？

**强烈建议先做纯结构拆分**，理由：

1. **降低改动复杂度**：7517行单文件改样式 = 翻上千行找位置
2. **团队协作**：拆分后Sonnet可并行处理12+子组件
3. **回滚可控**：每个子组件独立commit，改错了只需回滚该组件
4. **测试聚焦**：拆分验证通过后改样式，只需测样式，不测逻辑

**拆分工作量**：~20-30小时（含验证）  
**样式改动工作量**：~40-50小时（12+个子组件并行）

### 4.2 任务分解（15个独立任务）

#### **第一阶段：准备（2任务）**

| 任务ID | 任务名 | 改动范围 | 禁止触碰 | 验收标准 | 建议模型 |
|--------|--------|---------|---------|----------|---------|
| **T1** | 提取CSS变量到`design-tokens.css` | 新建`webapp/src/design-tokens.css`，定义本文档第2章全部令牌 | 不改`app.css`，保持原有变量兼容 | `npm run build`通过；design-tokens.css包含46+变量，命名符合规范 | Haiku |
| **T2** | 创建子组件框架（纯结构） | 新建13个子组件文件（见4.2表），各组件暂时只有`<script>`和占位符 | 不涉及样式，不改App.svelte业务逻辑 | 13个文件创建成功，导入不报错，build通过 | Haiku |

#### **第二阶段：结构拆分（8任务）**

| 任务ID | 任务名 | 改动范围 | 禁止触碰 | 验收标准 | 建议模型 |
|--------|--------|---------|---------|----------|---------|
| **T3** | 拆分`LogView.svelte` | 从App.svelte的日志部分（2282-2291行）拆出 | `logs[]`数组定义、WebSocket逻辑 | 构建通过，日志显示不变，自动滚动生效 | Haiku |
| **T4** | 拆分`ChatView.svelte` | 聊天区块（2293-2447行） | WebSocket消息推送逻辑、会话API调用 | 构建通过，发送消息、消息滚动正常 | Sonnet |
| **T5** | 拆分`ProfileView.svelte` | 资料编辑（2449-2476行） | 头像上传API、表单验证 | 构建通过，表单提交、头像上传功能正常 | Sonnet |
| **T6** | 拆分`SecurityView.svelte` | 安全功能（2478-2545行） | passkey状态机、2FA逻辑、设备删除 | 构建通过，通行密钥界面、2FA按钮功能正常 | Sonnet |
| **T7** | 拆分`AccountList.svelte` | 左栏列表（2079-2141行） | 拖拽排序逻辑、右键菜单显示位置计算 | 构建通过，列表显示、双击连接、右键菜单生效 | Sonnet |
| **T8** | 拆分`FunctionCards.svelte` | 中栏卡片（2175-2277行） | 卡片折叠状态持久化、`onCardToggle`逻辑 | 构建通过，6张卡片折叠展开、状态保存正常 | Sonnet |
| **T9** | 拆分`SettingsDialog.svelte` | 设置弹窗（2921-3217行） | 设置读写API、7导航项状态管理 | 构建通过，设置开关、保存按钮、手机钻取功能正常 | Sonnet |
| **T10** | 拆分`DeleteAccountDialog.svelte` | 删除账号弹窗（2825-2861行） | 二级确认勾选逻辑、账号删除API | 构建通过，勾选框、删除按钮禁用/启用逻辑正常 | Haiku |

#### **第三阶段：样式重设计（5任务）**

| 任务ID | 任务名 | 改动范围 | 禁止触碰 | 验收标准 | 建议模型 |
|--------|--------|---------|---------|----------|---------|
| **T11** | 更新颜色令牌到深色优先 | `design-tokens.css`的颜色变量更新为第2章规范；`app.css`的`:root`和`:root[data-theme='dark']`更新 | 不改颜色值在代码中的应用位置 | `npm run build`通过；浅色/深色模式切换正常，对比度≥4.5:1 | Haiku |
| **T12** | 优化信息密度（紧凑间距） | 全部组件的`padding/margin`应用本文档第2.3章的`spacing-*`和`spacing-compact-*` | 不改flex/grid布局、不改元素高宽 | 构建通过；账号列表行高减少5%；日志行距减少；设置表单紧凑；目视对比 | Sonnet |
| **T13** | 更新账号列表样式 | `AccountList.svelte`应用3.1规范（64px行高、状态层、在线点呼吸）；手机版调整到56px | 不改列表绑定、过滤、拖拽逻辑 | 构建通过；列表项颜色正确，在线点动画生效，hover状态正确 | Sonnet |
| **T14** | 更新功能卡片样式 | `FunctionCards.svelte`应用3.2规范（阴影、分隔线、padding） | 不改卡片折叠逻辑 | 构建通过；卡片外观符合规范，展开/收起流畅 | Haiku |
| **T15** | 更新弹窗与危险按钮样式 | 全部弹窗应用3.9规范；`DeleteAccountDialog`、删除分组按钮应用3.8规范 | 不改确认逻辑、API调用 | 构建通过；删除弹窗、危险按钮红色视觉突出；目视检查危险操作三层确认链 | Sonnet |

### 4.3 执行顺序与依赖关系

```
T1(design-tokens)
  ↓
T2(component framework)
  ↓
┌─ T3(LogView) ──────────┐
├─ T4(ChatView) ────────┬┤
├─ T5(ProfileView) ────┬┤
├─ T6(SecurityView) ──┬┤
├─ T7(AccountList) ───┤├─ T11(color tokens)
├─ T8(FunctionCards) ─┤├─ T12(density)
├─ T9(SettingsDialog) ┤├─ T13(list style)
└─ T10(DeleteDialog) ──┤├─ T14(card style)
                       └┤─ T15(button & dialog)
                         ↓
                     构建通过、冒烟测试
```

**并行关键**：
- T3-T10可全部并行（各自独立修改不同区块）
- T11-T12必须在T3-T10完成后（应用新变量）
- T13-T15可与T11-T12并行，但要在新变量定义后

**预计总耗时**：60-70小时（假设3人团队并行T3-T10，8-10天完成）

### 4.4 每个任务的验收标准详解

#### 构建验收（所有任务必须）
```bash
cd webapp && npm run build
# 输出：build: dist/ 成功，无error警告
```

#### E2E冒烟测试（所有任务必须）
```
1. 连接账号（双击列表项）→ 顶栏变绿 ✓
2. 执行删除任务 → 进度条推进、日志实时更新 ✓
3. 查看日志 → 日志自动滚动、error/warn着色 ✓
4. 切换主题（顶栏🌙） → 颜色立即切换 ✓
5. 弹窗操作 → 删除弹窗、设置弹窗正常显示 ✓
```

#### 结构拆分任务特有（T3-T10）
```
1. 新组件导入App.svelte无报错 ✓
2. 子组件的props/emits定义符合4.2表 ✓
3. 功能完全不变（冒烟测试通过） ✓
4. 新组件文件行数 < 原App.svelte对应块行数的110% ✓
  （允许略微增加是因为组件声明和prop接收）
```

#### 样式任务特有（T11-T15）
```
1. 目视对比：新样式符合本文档规范图示 ✓
2. 覆盖率：涉及区块的所有元素应用了新令牌/间距 ✓
3. 深浅主题：两套主题对比度≥4.5:1（无障碍标准） ✓
4. 动效：状态切换流畅（无抖动、卡顿） ✓
5. 响应式：桌面(>900px)和手机(<900px)布局都正常 ✓
```

---

## 5. 风险与防护

### 5.1 最可能误伤业务逻辑的5个位置

| 位置 | 出现在 | 风险 | 防护措施 |
|------|--------|------|---------|
| **分组拖拽逻辑** | `AccountList.svelte`(1505-1567行) | 改padding会破坏坐标计算 | `git diff`检查：不允许修改`.grp`的padding/margin值；补充grep: `grep -n "padding.*group\|margin.*group" AccountList.svelte` |
| **WebSocket消息推送** | `ChatView.svelte`(1805-1825行) | 改日志样式可能影响条件匹配 | 日志行不修改条件判断(`if rightView`等)，grep: `grep -n "rightView\|curDialog" ChatView.svelte` 不能减少 |
| **手机号登录flushSync** | 新建账号三流程(627-640行) | 删flushSync导致UI不更新 | 禁止删除`flushSync`，grep: `grep -c "flushSync" AddAccountDialog.svelte` 结果不能 < 原始 |
| **卡片折叠状态** | `FunctionCards.svelte`(1856-1859行) | 去掉`querySelectorAll`导致折叠状态丢失 | 不改`details.card`选择器，grep: `grep "details.card" FunctionCards.svelte` 必须存在 |
| **聊天消息自动滚动** | `ChatView.svelte`(1137-1138行) | 改`.chat-history`类名或删`scrollTop`赋值导致新消息看不到 | 类名保持，grep: `grep "chat-history\|scrollTop" ChatView.svelte` 必须存在 |

### 5.2 Git检查规则

**在每个任务commit前自动运行**：

```bash
# 禁止检查：不允许修改这些关键行
git diff HEAD -- webapp/src/ | grep -E "^\-.*querySelect|^\-.*flushSync|^\-.*onMouseDown|^\-.*elementFromPoint" && echo "ERROR: 禁止删除关键逻辑" || echo "PASS"

# 变量检查：确保state变量没有被意外删除
for var in "accounts" "filtered" "current" "connected" "onlineNames" "logs" "progress" "cardOpen"; do
  grep -q "$var" webapp/src/App.svelte || echo "WARNING: $var not found in App.svelte"
done

# CSS变量覆盖率：检查是否有硬编码颜色仍未转为变量
grep -o "#[0-9A-F]\{6\}" webapp/src/App.svelte | wc -l > /tmp/color_count.txt
# 目标：新数字 < 原始数字 * 30%
```

### 5.3 浅色与深色主题验证清单

#### 浅色主题验收
- [ ] 背景颜色 = `--md-sys-color-surface`（#FAFAFA），不是纯白
- [ ] 文字颜色 = `--md-sys-color-on-surface`（#1A1A1A），不是纯黑
- [ ] 按钮默认 = `--md-sys-color-surface-container`，hover时变亮
- [ ] 在线点 = `--md-sys-color-success`（#2E7D32），绿色
- [ ] 删除按钮 = `--md-sys-color-error`（#D32F2F），鲜红
- [ ] 对比度测试工具（如WAVE）：所有文本对比度≥4.5:1

#### 深色主题验收
- [ ] 背景颜色 = `--md-sys-color-surface`（#121212），OLED黑
- [ ] 文字颜色 = `--md-sys-color-on-surface`（#F5F5F5），几乎白
- [ ] 按钮默认 = `--md-sys-color-surface-container`，深灰
- [ ] 在线点 = `--md-sys-color-success`（#81C784），浅绿（深色适配）
- [ ] 删除按钮 = `--md-sys-color-error`（#FF6B6B），浅红（深色适配）
- [ ] 同样对比度测试≥4.5:1

#### 打包后绿色版验证
```bash
# 1. PyInstaller打包
python -X utf8 -m PyInstaller TG工具箱Web.spec --noconfirm

# 2. 启动打包后的exe
./dist/TG工具箱Web/TG工具箱Web.exe

# 3. 冒烟测试
# - 切换浅色/深色 → 颜色正确切换
# - 连接账号 → 状态显示正常
# - 删除确认弹窗 → 红色按钮显眼
# - 日志滚动 → 流畅无卡顿
```

---

## 6. Sonnet任务提示词模板

### 6.1 通用模板（所有结构拆分任务）

```
你是资深前端工程师。根据以下要求拆分Svelte组件：

【基础约束】
- 遵守 CLAUDE.md 第2、3节（Svelte 5 runes语法、业务逻辑与UI分离、无CDN依赖）
- 保持所有业务逻辑不变，只做结构拆分
- 使用Svelte 5的 $state、$props、事件回调，不用Svelte 4语法
- 新组件必须在 webapp/src/ 目录，命名 `{ComponentName}.svelte`

【拆分目标】
源文件：webapp/src/App.svelte
源行号：{START_LINE} - {END_LINE}
新组件：{COMPONENT_NAME}.svelte

【组件接口】
Props接收（来自App.svelte的$state变量）：
{PROPS_LIST}

事件发射（回调到App.svelte）：
{EVENTS_LIST}

禁止修改的业务逻辑段：
{FORBIDDEN_LOGIC}

【验收标准】
✓ npm run build 通过
✓ 新组件导入App.svelte无报错
✓ 冒烟测试通过（见第4.4章）
✓ git diff 不包含关键逻辑的删除

请从 webapp/src/App.svelte 的指定行号范围提取代码到新组件，
确保Props绑定、事件通信、样式class保持原样，
然后更新 App.svelte 的相应位置为组件标签。
```

### 6.2 样式改动任务模板

```
你是UI设计师兼前端工程师。根据设计规范改造组件样式：

【基础约束】
- 遵守 docs/ui-redesign-plan.md 第2、3章的设计令牌与组件规范
- 所有颜色、间距、圆角、阴影必须使用CSS变量
- 保持所有业务逻辑、事件监听、状态管理不变
- 组件响应式必须支持桌面(>900px)和手机(<900px)

【改动目标】
组件文件：{COMPONENT_FILE}
改动范围：{STYLE_AREA}（如"账号列表行样式、在线点动画"）
参考规范：docs/ui-redesign-plan.md 第 {SPEC_SECTION} 章

【设计规范要点】
- 颜色令牌：design-tokens.css（已定义）或 app.css 中的 --md-sys-* 变量
- 间距规则：标准密度用 spacing-*；紧凑区域用 spacing-compact-*
- 动效时长：{MOTION_DURATION}（如"200ms standard"）
- 深色模式：必须测试 :root[data-theme='dark'] 的颜色适配

【具体改动】
当前CSS问题：
{CURRENT_ISSUES}

目标样式：
{TARGET_STYLE}

【验收标准】
✓ npm run build 通过
✓ 浅色/深色主题对比度≥4.5:1
✓ 目视对比：新样式符合规范
✓ 动效流畅（无抖动、卡顿）
✓ 响应式正常（桌面/手机都可用）

请提取组件的 <style> 块，应用新令牌和规范，
保持 <script> 和模板结构完全不变。
```

### 6.3 令牌定义任务模板

```
你是前端架构师。创建Material 3设计令牌CSS文件：

【基础约束】
- 文件位置：webapp/src/design-tokens.css
- 格式：纯CSS变量（:root 作用域），无SCSS/LESS
- 命名规范：--md-sys-* 或 --spacing-* 等（遵循M3）
- 必须支持浅色(:root)和深色(:root[data-theme='dark'])

【令牌定义】
根据 docs/ui-redesign-plan.md 第2章，定义以下令牌组：

1. 颜色系统（第2.1章）
   - 浅色主题：47个变量
   - 深色主题：47个变量（在 :root[data-theme='dark'] 中）
   
2. 圆角系统（第2.2章）
   - 5档圆角：4px → 28px
   
3. 间距系统（第2.3章）
   - 标准间距：5个级别
   - 紧凑间距：5个级别
   
4. 字阶系统（第2.4章）
   - 7种字体大小分类
   - 行高与字重配置
   
5. 阴影系统（第2.5章）
   - 4个elevation级别
   - 浅色与深色版本
   
6. 动效系统（第2.6章）
   - 6个时长预设
   - 4个缓动函数

【验收标准】
✓ npm run build 通过（导入无语法错误）
✓ 所有变量名符合命名规范，无拼写错误
✓ 浅色值和深色值对应且有合理的对比度差异
✓ 颜色值都是十六进制，阴影和缓动都是有效的CSS语法

请完整输出 design-tokens.css 文件，
包含所有令牌定义和必要的注释说明。
```

---

## 7. 待确认事项

根据ui-inventory.md标注的"未确认"内容：

| 项目 | 当前状态 | 需要确认 |
|------|----------|---------|
| **Material Web组件版本** | @material/web 2.3.0 | 是否继续使用仅这13处用法，其他区域保持手写？ |
| **手机端深色主题** | v1.2.2已支持 | 深色主题是否作为默认推荐，还是保持浅色优先？ |
| **打包后的FontFamily** | 系统字体栈（Segoe UI） | Windows 7/10上Segoe UI Variable是否一定可用？备选字体是否需要内嵌ttf？ |
| **图标方案** | Unicode/Emoji | 现有的●、✓、☰等符号是否继续使用，还是考虑Material Icons的SVG方案？ |
| **手机端底栏高度** | 56dp（Material标准） | 与顶栏64px的比例是否合适？ |
| **进度条样式** | 左边框+填充条 | 是否考虑用M3的LinearProgressIndicator组件替代手写div？ |

---

## 8. 时间与资源预估

### 工作量分解

| 阶段 | 任务数 | 人天 | 并行度 | 总耗时 |
|------|--------|------|--------|--------|
| 准备 | 2 | 2 | 1 | 2天 |
| 结构拆分 | 8 | 24 | 8 | 3天 |
| 样式重设计 | 5 | 20 | 5 | 4天 |
| 验证与调试 | - | 8 | 1 | 1天 |
| **总计** | **15** | **54** | - | **10-12天** |

### 团队配置建议

- **1名Sonnet运维**（T1-T2, T11-T15）：8人天
- **2名Sonnet开发**（T3-T10并行）：16人天×2 = 32人天
- **1名QA冒烟**（每个任务后）：8人天
- **总投入**：50-56人小时，按8h/人天 = 6.25-7人天

### 关键路径

```
Day 1-2: T1(4h) + T2(4h)
  ↓
Day 3-5: T3-T10并行(12h×8 = 96h/3人 ≈ 32h = 4day)
  ↓
Day 6-9: T11-T15并行(16h×5 = 80h/5人 ≈ 16h = 2day)
  ↓
Day 10: 集成验证(8h)
```

---

## 9. 后续维护建议

### 不需要维护的部分

- **design-tokens.css**：定义后基本不改，除非M3官方更新color-tone
- **组件框架**：拆分后保持稳定，除非改业务流程

### 需要维护的部分

| 项目 | 维护频率 | 责任人 |
|------|----------|--------|
| 颜色令牌对比度 | 每次改配色 | UI设计师 |
| 动效时长 | 每次优化交互 | 前端工程师 |
| 响应式断点(900px) | 如果改手机端UI | 前端工程师 |
| 组件规范文档 | 每个大版本 | 技术负责人 |

---

**文档结束** · 设计方案版本 v1.0 · 2026-10-28  
**下一步**：待你确认第7章"待确认事项"后，即可开始任务T1（提取令牌）。
