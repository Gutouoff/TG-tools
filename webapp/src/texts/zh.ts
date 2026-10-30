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

  'common.close': '关闭',
  'common.cancel': '取消',
  'common.confirm': '确定',
  'common.delete': '删除',
  'common.deleting': '删除中…',
  'common.processing': '处理中…',

  'group.renameTitle': '分组重命名',
  'group.renamePlaceholder': '输入新的分组名称',
  'group.createTitle': '新建分组',
  'group.createPlaceholder': '输入分组名称',
  'group.deleteTitle': '删除分组',
  'group.deleteHintPrefix': '删除分组「',
  'group.deleteHintSuffix': '」？组内账号不受影响，将归入「未分组」。',

  'account.deleteTitle': '删除账号',
  'account.deleteWarnPrefix': '此操作',
  'account.deleteWarnStrong': '不可恢复',
  'account.deleteWarnSuffix': '。将永久删除该账号的 session、tdata、登录凭据等全部文件，删除后只能重新登录。',
  'account.label': '账号',
  'account.uid': 'UID',
  'account.deleteFolder': '将被删除的文件夹',
  'account.deleteConfirm': '我已了解该操作不可恢复，确认删除该账号的全部文件',
  'account.deleteForever': '永久删除',
} as const;

export type TextKey = keyof typeof zh;
