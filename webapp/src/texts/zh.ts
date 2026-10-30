/**
 * 界面文案（简体中文）。
 * 规则：组件里不再直接写死中文，统一从这里取；新增文案先加 key 再用。
 * 带占位符的用 {name} 形式，由 t(key, params) 替换。
 */
export const zh = {
  'app.title': 'TG小号工具箱',

  'topbar.connected': '● 已连接',
  'topbar.disconnected': '● 未连接',
  'topbar.newAccount': '新建账号',
  'topbar.reconnect': '重新连接',
  'topbar.launchClient': '启动客户端',
  'topbar.launchClientHint': '启动当前账号的 Telegram 客户端；右键账号卡片可打开文件夹',
  'topbar.disconnect': '断开连接',
  'topbar.pack': '打包',
  'topbar.themeToLight': '切换到浅色',
  'topbar.themeToDark': '切换到深色',
  'topbar.settings': '设置',

  'log.title': '日志',
  'log.back': '返回',
  'log.noTask': '无任务',
  'log.empty': '暂无日志',

  'ctx.moveGroup': '移动分组（可多选）',
  'ctx.removeAll': '移出所有分组',
  'ctx.disconnect': '断开连接（保持其他在线）',
  'ctx.rename': '重命名文件夹…',
  'ctx.runPending': '立即执行待重命名 → {target}',
  'ctx.cancelPending': '取消待重命名',
} as const;

export type TextKey = keyof typeof zh;
