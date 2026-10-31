import { zh, type TextKey } from './zh';

/**
 * 取界面文案。
 * t('topbar.settings')
 * t('ctx.runPending', { target: '新名字' })
 */
export function t(key: TextKey, params?: Record<string, string | number>): string {
  let text: string = zh[key];
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

export { cardLabel } from './zh';
