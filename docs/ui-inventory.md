# TG工具箱 前端UI盘点（v1.2.2）

> **盘点时间**：2026-10-27  
> **目的**：为UI重设计做准备，明确现状、边界和风险点  
> **原则**：只读盘点，严禁修改任何现有文件

---

## 1. 技术栈与构建

### 1.1 前端技术栈

| 项目 | 版本 | 说明 |
|------|------|------|
| **Svelte** | 5.20.0 | 使用runes语法（$state, $derived, $props, onclick） |
| **Vite** | 6.2.0 | 开发服务器与构建工具 |
| **TypeScript** | 5.7.0 | 类型定义（仅api.ts使用） |
| **@material/web** | 2.3.0 | Google官方Material 3 Web Components |

**Material 3实现方式**：
- 使用 **@material/web 2.3**（Google官方Web Components库）
- 实际使用组件：`md-filled-button`（17处）、`md-outlined-button`（36处）
- 导入位置：`main.ts`（按需引入6个组件）
- **未使用第三方UI框架**，其余界面元素全部手写HTML+CSS

### 1.2 构建配置（绝对不能动）

| 配置项 | 当前值 | 作用 | 修改后果 |
|--------|--------|------|----------|
| `vite.config.ts` → `build.outDir` | `'dist'` | 构建产物输出目录 | server.py从`BASE/webapp/dist`读取，改了前端加载失败 |
| `vite.config.ts` → `base` | 默认`'/'` | 资源路径前缀 | pywebview加载`http://localhost:port/`，改了路由错乱 |
| `package.json` → `build` script | `vite build` | 构建命令 | 打包前必须`npm run build`，改了spec找不到产物 |

**构建产物去向**：
```
webapp/dist/         ← Vite产物（不入库，.gitignore已挡）
  ├── index.html     ← server.py读取并注入token
  ├── assets/*.js
  └── assets/*.css

→ PyInstaller打包时收集 webapp/dist/** 到 _internal/webapp/dist/
→ server.py在/@app.get('/') 路由中读取 index.html 并注入 window.__TG_TOKEN__
```

**铁律**：改了 `webapp/src/**` 必须 `npm run build` 再打包部署，否则把旧界面带出去。

---

## 2. 文件规模与结构

### 2.1 前端文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `webapp/src/App.svelte` | **8179** | 主界面（巨石单文件） |
| `webapp/src/api.ts` | 421 | API封装、TOKEN、connectWS |
| `webapp/src/app.css` | 198 | Material 3主题变量（浅色/深色） |
| `webapp/src/main.ts` | 17 | 入口、导入Material组件 |

**总计**：8815行前端代码

### 2.2 App.svelte内部结构

| 区块 | 行号范围 | 行数 | 说明 |
|------|----------|------|------|
| **&lt;script&gt;** | 1 - 1861 | 1861 | 全部业务逻辑 |
| **模板** | 1862 - 3184 | 1323 | HTML结构 |
| **&lt;style&gt;** | 3185 - 8179 | 4995 | 全部样式 |

#### &lt;script&gt; 内部逻辑段（行号定位）

| 逻辑段 | 行号区间 | 主要内容 |
|--------|----------|----------|
| 导入与常量 | 1-100 | import、$state变量声明、AVATAR_COLORS |
| 工具函数 | 100-250 | avatarColor, applyFilter, addLog, stampNow |
| 账号操作 | 250-400 | onConnect, doConnectFlow, onSwitch, doDisconnect |
| 任务与转换 | 400-550 | doPollAccounts, doConvertTdata, doRefreshSsBatch |
| 删除账号 | 476-520 | doOpenDeleteAccount, doDeleteAccount（二级确认） |
| Passkey与安全 | 550-800 | 通行密钥注册、2FA设置、设备管理 |
| 分组与白名单 | 800-1000 | 分组CRUD、账号移动、白名单管理 |
| 设置与主题 | 1000-1200 | loadSettings, applyTheme, 主题色预设 |
| 聊天与消息 | 1200-1500 | getDialogs, getHistory, sendChatMsg, 消息接收规则 |
| 新建账号 | 1500-1700 | 拖包导入、扫码登录、手机号登录三流程 |
| WebSocket处理 | 1700-1861 | connectWS回调、日志/进度/状态事件分发 |
| onMount生命周期 | 1834-1887 | 初始加载、恢复在线状态、加载设置 |

#### 模板内部区域（行号定位）

| UI区域 | 行号区间 | 说明 |
|--------|----------|------|
| **桌面顶栏** | 1890-1904 | 标题、连接状态、新建账号/重连/启动/断开/打包/主题切换/设置 |
| **手机端壳** | 1906-2078 | 手机专用UI（header + 四页签底栏） |
| 　├ 手机头部 | 1907-1924 | 品牌标识/账号数/在线数/新建按钮 or 返回+面板标题 |
| 　├ 手机"账号"页 | 1930-1982 | 搜索栏+分组胶囊+账号列表（头像/状态/连接按钮） |
| 　├ 手机"当前"页 | 1983-2036 | 当前账号卡片+九宫格操作 |
| 　├ 手机"动态"页 | 2037-2054 | 进度条+日志流 |
| 　├ 手机"更多"页 | 2055-2069 | 设置/外观/群组/新建/日志/版本 |
| 　└ 手机底栏 | 2070-2076 | 四个页签（账号/当前/动态/更多） |
| **桌面三栏布局** | 2078-2280 | .layout → .left + .splitter + .mid + .splitter + .right |
| 　├ 左栏（账号列表） | 2079-2141 | 分组按钮+搜索框+账号列表（头像/在线点/待改名徽标） |
| 　├ 中栏（功能卡片） | 2142-2277 | 基本信息/聊天/安全/删除/转换/其他设置 6张卡片（details折叠） |
| 　└ 右栏（视图切换） | 2280-2620 | 日志/聊天/资料/安全/设备/群组 6个视图 |
| **右键菜单** | 2144-2174 | 账号右键：连接/断开/改名/分组移动/重连/删除 |
| **分组右键菜单** | 2609-2618 | 改名/断开全部/删除分组 |
| **弹窗区** | 2620-3217 | 所有模态弹窗（见下节） |

#### 弹窗与模态（行号定位）

| 弹窗名称 | 行号 | 变量控制 | 危险程度 | 说明 |
|----------|------|----------|----------|------|
| 分组改名 | 2620-2641 | `groupRenameOpen` | 安全 | 输入框+确认/取消 |
| **新建账号** | 2642-2749 | `addAccOpen` | 安全 | 三标签：拖包/扫码/手机号，含复杂流程 |
| **删除分组** | 2750-2768 | `groupDelOpen` | 中危 | 二级确认，组内账号移回未分组 |
| tdata刷新确认 | 2770-2791 | `t2sOpen` | 安全 | 覆盖刷新session+json |
| session→tdata | 2793-2823 | `convOpen` | 安全 | 覆盖勾选+2FA密码 |
| **删除账号** | 2825-2861 | `delOpen` | **高危** | 红色警告+勾选确认+路径显示 |
| 新建分组 | 2863-2885 | `groupModalOpen` | 安全 | 简单输入框 |
| 账号改名 | 2887-2919 | `renameOpen` | 安全 | 输入框+占用自动排队说明 |
| **设置弹窗** | 2921-3217 | `settingsOpen` | 安全 | 左侧导航7项+右侧表单+底部保存 |
| 　├ 设置导航 | 2986-2996 | `settingsSection` | - | 通用/外观/代理/加群频道/白名单/关于 |
| 　├ 手机设置根页 | 手机端 | `mobileSettingsSection` | - | 列表+钻取子页（v1.2.2新增） |
| 　└ 设置内容区 | 2998-3208 | 多条件渲染 | - | 表单、色彩选择器、白名单编辑 |

---

## 3. 界面清单（按功能分区）

### 3.1 桌面端主界面（三栏布局）

| 区域 | 模板行号 | 主要状态变量 | 可改/需谨慎 | 理由 |
|------|----------|--------------|------------|------|
| **顶栏** | 1890-1904 | `connected`, `connectingLabel`, `appVersion` | 可改 | 纯展示层，逻辑在onclick回调 |
| **左栏·分组** | 2080-2097 | `curGroup`, `groups`, `dragGroup` | 需谨慎 | 拖拽排序涉及onmousedown/onmousemove复杂逻辑 |
| **左栏·搜索** | 2098 | `search`, `onSearch` | 可改 | 仅触发applyFilter |
| **左栏·账号列表** | 2099-2141 | `filtered`, `current`, `onlineNames`, `renamePending` | 可改 | 双击连接、单击选中、右键菜单 |
| **中栏·卡片** | 2175-2277 | `cardOrder`, `cardOpen`, `isCardOpen` | 可改 | details折叠+ontoggle保存状态 |
| **右栏·视图切换** | 2189-2203 | `rightView` | 可改 | 按钮组切换视图 |
| **右栏·日志** | 2282-2291 | `logs[]` | 可改 | 纯展示列表 |
| **右栏·聊天** | 2293-2447 | `dialogs`, `curDialog`, `historyMsgs` | 需谨慎 | 消息滚动、发送、实时推送更新列表 |
| **右栏·资料编辑** | 2449-2476 | `profileData` | 需谨慎 | 表单提交、头像上传 |
| **右栏·安全** | 2478-2545 | `passkeys`, `pk2FA`, `emailVerified` | 需谨慎 | 通行密钥注册含复杂状态机 |
| **右栏·设备管理** | 2547-2520 | `devices[]` | 可改 | 列表+删除按钮 |
| **右栏·群组频道** | 2572-2607 | `joinLinks[]` | 可改 | 列表+增删改 |

### 3.2 手机端专用UI（<900px触发）

| 区域 | 模板行号 | 状态变量 | 说明 |
|------|----------|----------|------|
| 手机头部 | 1907-1924 | `mobilePanelOpen`, `mobileTab` | 品牌标识/账号统计/新建按钮 or 返回栏 |
| 底部四页签 | 2070-2076 | `mobileTab` | 账号/当前/动态/更多 |
| "账号"页 | 1930-1982 | `search`, `curGroup`, `filtered` | 搜索+分组+列表（逐行错峰入场动画） |
| "当前"页 | 1983-2036 | `current`, `onlineNames` | 账号卡+九宫格操作 |
| "动态"页 | 2037-2054 | `progress`, `logs` | 进度条+移动日志流（按warn/error着色） |
| "更多"页 | 2055-2069 | - | 设置/外观/群组/新建/日志入口 |
| 深页面板 | 2280+（复用） | `mobilePanelOpen`, `rightView` | 全屏呈现右栏视图，加返回栏 |

**手机端特点**（v1.2.2）：
- **窄屏专用壳**（`max-width: 899px`），桌面三栏完全不受影响
- **Material 3动效**：页签切换淡入+上移10px（200ms）、列表逐行错峰24ms、底栏指示器scaleX弹出
- **触控优化**：按钮≥48×48dp、关闭蓝色点击高亮、touch-action消除延迟
- **设置改钻取**：根页列表+子页表单，与桌面横向标签不同

### 3.3 弹窗分类（危险程度标注）

| 弹窗 | 控制变量 | 危险操作 | 确认机制 | 样式特征 |
|------|----------|----------|----------|----------|
| **删除账号** | `delOpen` | ✅ 永久删除 | 勾选确认+红色按钮 | `.del-title`, `.danger-btn` |
| **删除分组** | `groupDelOpen` | ⚠️ 组内账号移回未分组 | 二级确认 | `.danger-btn` |
| 删联系人 | 中栏按钮 | ✅ 批量删除 | 白名单保护 | `md-outlined-button` |
| 删对话 | 中栏按钮 | ✅ 批量删除 | 白名单保护 | `md-outlined-button` |
| 退群频道 | 中栏按钮 | ⚠️ 退出群组 | 白名单保护 | `md-outlined-button` |
| 新建账号 | `addAccOpen` | - | 三流程标签页 | `.mode-item`, `.add-acc-*` |
| 设置 | `settingsOpen` | - | 底部保存按钮 | `.set-overlay`, `.set-dialog` |
| 其他 | 各自变量 | - | 简单确认 | 标准弹窗样式 |

---

## 4. 样式现状

### 4.1 设计令牌定义位置

| 令牌类型 | 定义位置 | 令牌数量 | 说明 |
|----------|----------|----------|------|
| **颜色角色** | `app.css:2-67` | 浅色23个 | Material 3标准角色（primary, surface, error等） |
| **深色覆盖** | `app.css:69-120` | 深色23个 | `:root[data-theme='dark']` |
| **圆角** | `app.css:35-39` | 5档 | extra-small 4px → extra-large 24px |
| **语义色** | `app.css:41-52` | 8个 | topbar-color, status-*, hover-overlay, divider等 |
| **组件token** | `app.css:54-66` | 10个 | md-filled-button-*, md-outlined-text-field-* |

**浅色/深色主题实现**：
```css
:root { color-scheme: light; /* 浅色变量 */ }
:root[data-theme='dark'] { color-scheme: dark; /* 深色覆盖 */ }
```
- 切换逻辑：`App.svelte:936-960` `applyTheme()`
- 存储位置：`settings.json` 的 `theme_mode` 字段
- 手动切换：顶栏🌙按钮 或 设置→外观

### 4.2 硬编码问题

| 类型 | 数量 | 主要分布位置 | 示例 |
|------|------|--------------|------|
| **硬编码颜色** | 130处 | `<script>` AVATAR_COLORS + `<style>` 内联色 | `#356AE6`, `rgba(0,0,0,0.25)` |
| **硬编码px** | 375处 | `<style>` 各处尺寸 | `padding: 12px`, `height: 64px` |
| **硬编码中文** | 约300处 | 模板区域所有文字 | 按钮标签、提示文案、表单label |

**硬编码颜色分类**：
1. **头像色盘**（line 81）：8个固定色 `#E17076`, `#7BC862`... → 用于生成未加载头像的占位背景
2. **主题预设**（line 126）：12个 Chrome风格色环 → 用户可选主色
3. **style内联色**：阴影、透明度、渐变 → 大部分可提取为CSS变量

**硬编码px分布**：
- 顶栏高度：64px（line 3223）
- 左/中栏宽度：初始240px/420px（JS控制拖拽调整）
- 按钮高度：32px-48px混用
- 间距：4px-24px不规则跳跃（未统一栅格）

### 4.3 CSS变量使用现状

**已定义但使用率极低**：
- `app.css` 定义了完整的 Material 3 Design Token（46个变量）
- `App.svelte` 的 `<style>` 中仅使用 **9个** `var()` 引用
- 大量样式仍直接写死颜色和尺寸

**实际使用的9个变量**：
```
var(--md-sys-color-primary)
var(--md-sys-color-on-primary)
var(--md-sys-color-surface)
var(--md-sys-color-on-surface)
var(--md-sys-color-outline)
var(--md-sys-color-surface-container-high)
var(--md-sys-shape-corner-large)
var(--scrollbar-thumb)
var(--scrollbar-thumb-hover)
```

**未使用的关键变量**（已定义但被忽略）：
- `--md-sys-color-secondary-container` → 大量地方直接写 `#E0E2EC`
- `--md-sys-shape-corner-medium` → 到处是 `border-radius: 12px`
- `--divider` → 分隔线都是 `border: 1px solid rgba(...)`
- `--state-layer` → 悬停效果各自写 `background: rgba(...)`

### 4.4 字体与图标来源

| 项目 | 来源 | 位置 | 是否本地 |
|------|------|------|----------|
| **字体** | 系统字体栈 | `app.css:131` | ✅ 本地 |
| 　├ 主力 | Segoe UI Variable | Windows 11内置 | - |
| 　├ 备选 | Segoe UI | Windows 7-10 | - |
| 　└ 中文 | Microsoft YaHei UI | Windows通用 | - |
| **图标** | Unicode字符+Emoji | 模板内联 | ✅ 本地 |
| 　├ 导航 | ☰ ✕ ＋ ⚙ ◐ ⇄ ↗ ✓ i | 直接写HTML | - |
| 　├ 手机 | ▦ ◉ ≡ ••• ‹ ⌕ ☷ | 直接写HTML | - |
| 　└ 状态 | ● （在线点） | CSS `::before` | - |

**无CDN依赖**：代码中没有 `fonts.googleapis.com`、`cdnjs`、`material-icons` 等外链。

---

## 5. 界面文本机制

### 5.1 当前实现

| 项目 | 说明 |
|------|------|
| **界面文本.txt** | 171个 `t0xx` key，用于**后端Python**的CLI和日志输出 |
| **前端读取** | **无**（前端所有文字都是硬编码中文） |
| **t0xx在前端的使用** | 0处（grep结果） |

**结论**：
- **界面文本.txt 与前端完全解耦**，只服务于 Python 后端的 `tg_tool.py:DEFAULT_TEXTS`
- 前端所有按钮、标签、提示全部直接写在模板里：`<button>删除账号</button>`
- 如需前端i18n或文案复用，需新建独立机制（如JSON配置文件）

### 5.2 前端文案分布

| 区域 | 硬编码文字数量（估算） | 典型示例 |
|------|----------------------|----------|
| 顶栏按钮 | 8个 | "新建账号", "重新连接", "启动客户端", "断开连接", "打包", "设置" |
| 功能卡片 | 6标题+30按钮 | "基本信息", "删联系人", "删对话", "删机器人", "删频道" |
| 右栏视图 | 6标题+50标签 | "日志", "聊天", "资料编辑", "通行密钥", "两步验证" |
| 弹窗 | 10标题+40提示 | "删除账号", "此操作不可恢复", "我已了解..." |
| 设置项 | 7导航+80标签 | "通用", "外观", "代理", "启用系统代理", "SOCKS5地址" |
| 手机端 | 20额外标签 | "账号", "当前", "动态", "更多", "返回" |

**如需改动文案**：
- 直接在 `App.svelte` 模板区搜索替换
- 无需同步 `界面文本.txt`（它不参与前端渲染）

---

## 6. 动态与状态UI

### 6.1 任务进度（行号定位）

| 状态来源 | 变量 | 视觉位置 | 样式类/元素 |
|----------|------|----------|------------|
| WebSocket `progress` 事件 | `progress.{done,total,label}` | 桌面：右栏顶部进度条（line 2293-2299） | `.prog-wrap`, `.prog-fill` |
| 同上 | 同上 | 手机："动态"页顶部（line 2040-2041） | `.mobile-progress` |
| 显示条件 | `progress.total > 0` | 有任务时显示 | `{#if progress.total}` |
| 取消按钮 | `postTask('/api/tasks/stop')` | 进度条右侧 | `<button>取消</button>` |

### 6.2 账号在线状态（行号定位）

| 状态 | 变量 | 视觉表现 | 位置（行号） |
|------|------|----------|------------|
| **在线** | `onlineNames.has(a.name)` | 绿色小圆点（呼吸动画） | 桌面列表：2115-2117 |
| 同上 | 同上 | 绿色小圆点 | 手机列表：1962 |
| 同上 | 同上 | "在线"标签（绿底） | 手机列表：1968 |
| **离线** | `!onlineNames.has(a.name)` | 无圆点 | - |
| **失效** | `(a as any).poll_alive === false` | "失效"标签（红底） | 手机列表：1968 |
| **连接中** | `connectingLabel !== ''` | 顶栏"● 连接中…" | 1892 |
| **待改名** | `renamePending[a.name]` | 黄色"待改名"徽标 | 2126-2133 |

**在线点样式**（line 3430-3437, 5124-5132）：
```css
.online-dot {
  position: absolute; right: 0; bottom: 0;
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--status-online);  /* #2E7D32 浅色 / #81C784 深色 */
  animation: breathe 2.4s ease-in-out infinite;
}
```

### 6.3 速度档切换（行号定位）

| 档位 | 按钮位置 | 变量 | 后端同步 |
|------|----------|------|----------|
| 极快/快速/默认/慢速/极慢 | 中栏"基本信息"卡（2244-2249） | `speedVal` | `setSpeed(v)` API |
| 视觉 | 5档分段按钮，选中高亮 | `.seg.on` | - |

### 6.4 白名单状态（行号定位）

| 项目 | 数据源 | 显示位置 | 说明 |
|------|--------|----------|------|
| 用户白名单 | `wlUsers[]` | 设置→白名单（3181-3185） | ID列表，每行带"移除"按钮 |
| 群组白名单 | `wlGroups[]` | 设置→白名单（3193-3197） | ID列表，每行带"移除"按钮 |
| 添加操作 | `doAddUser/Group` | 输入框+添加按钮（3176, 3188） | 调用 `addWhitelist*` API |
| 删除操作 | `doRemoveUser/Group` | 每行右侧按钮 | `.danger` 样式 |

### 6.5 消息接收开关（行号定位）

| 状态 | 变量 | 位置 | 视觉 |
|------|------|------|------|
| 开启/关闭 | `recvOn` | 桌面：右栏"聊天"顶部（2323-2338） | 绿点+大按钮 |
| 同上 | 同上 | 手机："当前"页（2199-2213） | 小按钮+规则胶囊 |
| 规则勾选 | `recvRules.{exclude_channels,exclude_groups,exclude_bots}` | 3个胶囊按钮 | `.rule-chip.on` |
| 在线数显示 | `{onlineNames.size} 个` | 按钮内文字 | "消息接收已开启（在线账号 N 个；...）" |

### 6.6 WebSocket日志流（行号定位）

| 事件类型 | 处理位置 | 视觉效果 |
|----------|----------|----------|
| `log` | line 1712-1716 | 追加到 `logs[]`，按level着色（error红/warn黄/info白） |
| `progress` | line 1720-1721 | 更新进度条 `{done}/{total}` |
| `state` | line 1723-1770 | 账号状态变化、在线/离线、改名完成 |
| `passkey_*` | line 1772-1804 | 通行密钥注册流程日志 |
| `recv_message` | line 1805-1825 | 实时消息推送，更新聊天列表/记录 |
| `avatars_done` | line 1827-1831 | 头像缓存完成，刷新列表 |

---

## 7. 风险与建议

### 7.1 最容易误伤业务逻辑的5个位置

| 位置 | 行号 | 风险点 | 为什么危险 |
|------|------|--------|-----------|
| **1. 分组拖拽逻辑** | 1515-1608 | `onGroupMouseDown`, `onWinMouseMove`, `onWinMouseUp` | 全局鼠标事件监听+DOM操作，改样式可能破坏拖拽判定（如改padding影响坐标） |
| **2. WebSocket回调** | 1700-1831 | `connectWS(onMessage)` | 150行复杂分支，status字符串匹配，改日志样式可能破坏条件判断 |
| **3. 新建账号流程** | 1479-1689 | 扫码/手机号登录状态机 | 三个标签页共用状态，异步轮询+flushSync同步，改流程UI易导致状态错乱 |
| **4. 聊天消息滚动** | 1184-1231 | `scrollHistoryBottom()`, `onHistoryScroll` | 自动滚动+上滑加载更多，改消息列表高度/间距会破坏触底检测 |
| **5. 设置保存逻辑** | 1053-1142 | `doSaveSettings()` | 收集7个分区的表单数据，改设置表单结构需同步JS取值路径 |

### 7.2 纯结构拆分建议（零行为变更）

#### 是否建议先拆分？
**强烈建议**。理由：
1. **8179行单文件巨石**，修改任何样式都要滚动上千行，定位困难
2. **业务逻辑与展示层高度耦合**，一个变量被几十处引用，改动牵一发动全身
3. **重设计必然大规模改动结构**，不拆分直接改 = 高风险（测试不全就会漏bug）
4. **拆分是纯机械重构**，可以先做，验证通过后再改样式，分步降低风险

#### 拆分边界建议（按组件职责）

| 新组件 | 对应原行号 | Props输入 | Emits输出 | 说明 |
|--------|-----------|----------|-----------|------|
| `AccountList.svelte` | 2079-2141 | `{accounts, current, onlineNames, search, groups, curGroup}` | `onSelect`, `onConnect`, `onContextMenu` | 左栏账号列表+分组+搜索 |
| `FunctionCards.svelte` | 2175-2277 | `{current, cardOrder, cardOpen, onlineNames}` | `onCardToggle`, `onTask` | 中栏6张功能卡片 |
| `RightPanel.svelte` | 2280-2620 | `{rightView, current, logs, dialogs, ...}` | `onViewChange`, `onAction` | 右栏视图切换器+内容 |
| `　├ ChatView.svelte` | 2293-2447 | `{dialogs, curDialog, historyMsgs}` | `onSelectDialog`, `onSendMsg` | 聊天视图（列表+记录+发送） |
| `　├ ProfileView.svelte` | 2449-2476 | `{profileData}` | `onUpdateProfile`, `onUploadAvatar` | 资料编辑表单 |
| `　├ SecurityView.svelte` | 2478-2545 | `{passkeys, pk2FA, devices}` | `onRegisterPasskey`, `onSet2FA` | 安全功能（通行密钥+2FA+邮箱） |
| `　└ LogView.svelte` | 2282-2291 | `{logs}` | - | 日志列表（纯展示） |
| `MobileShell.svelte` | 1906-2078 | `{mobileTab, accounts, current, progress, logs}` | `onTabChange`, `onConnect` | 手机端四页签壳 |
| `SettingsDialog.svelte` | 2921-3217 | `{settingsOpen, settings}` | `onSave`, `onClose` | 设置弹窗（7导航+表单） |
| `DeleteAccountDialog.svelte` | 2825-2861 | `{delOpen, delTarget}` | `onConfirm`, `onCancel` | 删除账号确认弹窗 |
| `AddAccountDialog.svelte` | 2642-2749 | `{addAccOpen}` | `onComplete`, `onCancel` | 新建账号三流程（拖包/扫码/手机号） |
| `ContextMenu.svelte` | 2144-2174 | `{ctxMenu, groups}` | `onAction` | 右键菜单（账号+分组） |

**拆分原则**：
1. **Props只传必需数据**，避免把整个`$state`对象传下去
2. **事件回调向上冒泡**，子组件不直接调用API（保持纯净）
3. **样式随组件走**，每个`.svelte`带自己的`<style>`（避免全局污染）
4. **保持原有行为**，拆分后E2E测试必须全绿（双击连接、右键菜单、拖拽排序等）

**拆分后App.svelte预期规模**：
- `<script>`：~800行（状态管理+API调用+WebSocket处理）
- 模板：~200行（布局框架+组件占位）
- `<style>`：~500行（全局布局+主题变量）
- **总计**：~1500行（当前的18%）

### 7.3 需要补充的信息/截图

| 项目 | 目的 | 建议操作 |
|------|------|----------|
| **桌面端全屏截图** | 确认当前配色、间距、字号 | 浅色/深色各一张，覆盖左中右三栏 |
| **手机端四页签截图** | 确认移动端布局 | 账号/当前/动态/更多 各一张 |
| **弹窗截图** | 确认模态层样式 | 设置弹窗、删除账号、新建账号（三标签） |
| **状态变化录屏** | 理解动画和过渡 | 账号在线→离线、进度条推进、日志滚动 |
| **Material 3官方规范** | 对齐设计标准 | m3.material.io 的 Button/TextField/Dialog 规格 |
| **用户痛点清单** | 明确改动优先级 | 当前UI哪里不好用？哪些操作繁琐？ |

### 7.4 重设计分步建议

| 阶段 | 目标 | 产物 | 风险 |
|------|------|------|------|
| **Phase 0：盘点** | 摸清现状 | ✅ 本文档 | 无 |
| **Phase 1：纯结构拆分** | 巨石→组件 | 13个子组件 | 低（不改行为） |
| **Phase 2：提取CSS变量** | 消灭硬编码 | design-tokens.css | 低（仅替换值） |
| **Phase 3：统一间距栅格** | 4dp网格 | 修改padding/margin | 中（可能影响布局） |
| **Phase 4：Material 3对齐** | 补全组件 | md-card, md-dialog, md-list | 中（行为可能变） |
| **Phase 5：手机端重做** | 优化移动体验 | 新手势、过渡动画 | 高（大改交互） |

**每个阶段必须**：
1. `npm run build` 通过
2. 单独commit（便于回滚）
3. 冒烟测试：连接账号→执行任务→查看日志→切换主题

---

## 附录：快速定位表

### A. 关键变量速查

| 变量名 | 类型 | 作用 | 定义行号 |
|--------|------|------|----------|
| `accounts` | `Account[]` | 所有账号列表 | 83 |
| `filtered` | `Account[]` | 搜索过滤后的账号 | 84 |
| `current` | `Account \| null` | 当前选中账号 | 87 |
| `connected` | `boolean` | 是否已连接 | 88 |
| `onlineNames` | `Set<string>` | 在线账号名集合 | 816 |
| `logs` | `LogItem[]` | 日志列表 | 91 |
| `progress` | `{done,total,label}` | 任务进度 | 94 |
| `rightView` | `string` | 右栏视图 | 1068 |
| `settingsOpen` | `boolean` | 设置弹窗开关 | 868 |
| `cardOrder` | `string[]` | 功能卡片顺序 | 118 |
| `groups` | `Record<string, string[]>` | 分组→账号名映射 | 1451 |

### B. 危险按钮样式类速查

| 类名 | 使用位置 | 效果 |
|------|----------|------|
| `.danger-btn` | 删除账号/删除分组确认按钮 | 红色填充按钮（Material error色） |
| `.danger` | 白名单移除、设备删除 | 红色文字按钮 |
| `.icon-btn.danger` | 加群条目删除 | 红色图标按钮 |

### C. API端点速查（前端常用）

| API | 方法 | 对应操作 |
|-----|------|----------|
| `/api/connect` | POST | 连接账号 |
| `/api/disconnect` | POST | 断开连接 |
| `/api/switch` | POST | 切换已在线账号 |
| `/api/tasks/delete-contacts` | POST | 删联系人 |
| `/api/tasks/delete-dialogs` | POST | 删对话/退群 |
| `/api/delete-account` | POST | 删除账号 |
| `/api/settings` | GET/POST | 读取/保存设置 |
| `/ws?token=` | WebSocket | 日志/进度/状态推送 |

---

**文档结束** · 生成时间：2026-10-27 22:44  
**下一步**：等待用户确认信息准确性，补充截图/痛点后进入Phase 1（结构拆分）
