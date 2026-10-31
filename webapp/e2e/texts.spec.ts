import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../src/', import.meta.url));

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return entry.name.endsWith('.svelte') ? [full] : [];
  });
}

test('文案 key 全部存在于 zh.ts，且模板无硬编码中文', () => {
  const zh = fs.readFileSync(path.join(SRC, 'texts/zh.ts'), 'utf8');
  const keys = new Set([...zh.matchAll(/'([a-zA-Z0-9.]+)':/g)].map((m) => m[1]));

  const missing: string[] = [];
  const hardcoded: string[] = [];

  for (const file of walk(SRC)) {
    const rel = path.relative(SRC, file).replace(/\\/g, '/');
    // 只检查实际参与构建的界面文件；src 根目录存在并行会话的未跟踪草稿，不纳入
    if (!(rel === 'App.svelte' || rel.startsWith('components/'))) continue;
    const src = fs.readFileSync(file, 'utf8');

    for (const m of src.matchAll(/\bt\(\s*'([^']+)'/g)) {
      if (!keys.has(m[1])) missing.push(`${rel}: ${m[1]}`);
    }

    // 模板文本节点里的中文：图标字形（人聊盾端删清包刷设群≡）之外都算硬编码
    for (const m of src.matchAll(/>([^<>{}\n]*[\u4e00-\u9fa5][^<>{}\n]*)</g)) {
      const text = m[1].trim();
      if (text && !/^[人聊盾端删清包刷设群≡]+$/.test(text)) hardcoded.push(`${rel}: ${text}`);
    }
  }

  expect(missing, `zh.ts 缺少这些 key：\n${missing.join('\n')}`).toEqual([]);
  expect(hardcoded, `模板里仍有硬编码中文：\n${hardcoded.join('\n')}`).toEqual([]);
});
