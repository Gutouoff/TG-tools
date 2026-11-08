# 前端文案机制（Phase 4）

> 目标：组件里不再出现硬编码中文；所有界面文案集中在 `webapp/src/texts/zh.ts`。

## 结构

```
webapp/src/texts/
  zh.ts     // 唯一文案源：扁平 key -> 文案，另含 cardLabels（卡片 id -> 显示名）
  index.ts  // t(key, params) 与 cardLabel(id)
```

用法：

```svelte
<script lang="ts">
  import { t } from '../texts';
</script>

<button>{t('common.cancel')}</button>
<p>{t('chat.historyError', { error: historyError })}</p>
```

- 占位符统一写成 `{name}`，由 `t(key, { name })` 做字符串替换；
- 带 `<b>` / `<br />` 的句子拆成 `prefix / strong / suffix` 多个 key，在模板里拼接，保证加粗位置不变；
- key 命名：`模块.语义`，公共词放 `common.*`。

## 卡片 id 与显示名

`FunctionCards` 的卡片名（基本信息/聊天/安全/删除/转换/其他设置）同时是：

- `settings.card_order` 的持久化值；
- `cardOpen`（折叠状态）的键；
- `<details data-card>` 与 `isOpen()/onToggle()` 的参数。

所以**不能直接改这些字符串**。`zh.ts` 里导出 `cardLabels` 与 `cardLabel(id)`，模板只把显示名换成 `cardLabel(id)`，id 本身保持中文原值不变。

## 图标

手机端动作列表里的「人 / 聊 / 盾 / 端」等是**图标字形**，不是文案，保留在模板里；语义由旁边的 `strong/small` 文本承担。剩余 `aria-label` 已全部外置。

## 新增文案的流程

1. 在 `zh.ts` 加 key（同一模块内按语义命名）；
2. 组件里用 `t('模块.key')`，需要参数就写 `{param}`；
3. `cd webapp && npm run build`；
4. `npm run test:e2e` 必须 26 条全绿（纯文案迁移截图不应变化）；
5. 单独 commit。

## 当前状态

- 19 个组件 + `App.svelte` 外壳已全部外置，`App.svelte` 模板中文行数为 0；
- 文案守卫在 `e2e/texts.spec.ts`：检查 `t()` 的 key 都存在于 `zh.ts`，且组件模板没有硬编码中文（图标字形除外）；
- 组件模板只剩图标字形；
- 动态文案（后端返回的日志、账号名、错误信息）不在本机制内，仍按原样透传。
