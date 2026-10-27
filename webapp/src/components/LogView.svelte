<script lang="ts">
  import type { LogItem } from '../api';

  let {
    logs,
    progress,
    showBack = false,
    onBack,
  }: {
    logs: LogItem[];
    progress: { done: number; total: number; label: string };
    showBack?: boolean;
    onBack?: () => void;
  } = $props();
</script>

<div class="sec-head">
  <h3>日志</h3>
  {#if showBack}
    <button class="back" onclick={() => onBack?.()}>返回</button>
  {/if}
</div>
<div class="prog">
  <span>{progress.label || '无任务'}</span>
  <span>{progress.total ? `${progress.done}/${progress.total}` : ''}</span>
</div>
{#if progress.total}
  <div class="prog-bar">
    <div class="prog-fill" style="width:{Math.min(100, Math.round((progress.done / progress.total) * 100))}%"></div>
  </div>
{/if}
{#if !logs.length}
  <p class="empty">暂无日志</p>
{/if}
<ul class="log">
  {#each logs as e, i (e.ts + '|' + i)}
    <li class="log-line" class:lv-warn={e.level === 'warn'} class:lv-error={e.level === 'error'}>
      <span class="log-ts">{e.ts ? e.ts.slice(11) : ''}</span>
      <span class="log-msg">{e.msg}</span>
    </li>
  {/each}
</ul>
