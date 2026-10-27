<script lang="ts">
  type CtxMenu = { x: number; y: number; name: string };

  let {
    ctxMenu,
    groups,
    onlineNames,
    renamePending,
    onMove,
    onClose,
    onDisconnect,
    onRename,
    onRunPending,
    onCancelPending,
  }: {
    ctxMenu: CtxMenu;
    groups: Record<string, string[]>;
    onlineNames: Set<string>;
    renamePending: Record<string, string>;
    onMove: (name: string, group: string) => void;
    onClose: () => void;
    onDisconnect: (name: string) => void;
    onRename: (name: string) => void;
    onRunPending: () => void;
    onCancelPending: (name: string) => void;
  } = $props();
</script>

<div class="ctx" style="left:{ctxMenu.x}px;top:{ctxMenu.y}px" onclick={(e) => e.stopPropagation()}>
  <div class="ctx-title">移动分组（可多选）</div>
  {#each Object.keys(groups) as g}
    <label class="ctx-check">
      <input
        class="ctx-check-native"
        type="checkbox"
        checked={(groups[g] || []).includes(ctxMenu.name)}
        onchange={() => onMove(ctxMenu.name, g)}
      />
      <span class="ctx-check-box" class:on={(groups[g] || []).includes(ctxMenu.name)}>
        {#if (groups[g] || []).includes(ctxMenu.name)}✓{/if}
      </span>
      <span>{g}</span>
    </label>
  {/each}
  <button onclick={() => { onMove(ctxMenu.name, 'ungrouped'); onClose(); }}>移出所有分组</button>
  {#if onlineNames.has(ctxMenu.name)}
    <button class="ctx-disconnect" onclick={() => { onDisconnect(ctxMenu.name); onClose(); }}>断开连接（保持其他在线）</button>
  {/if}
  <button onclick={() => { onRename(ctxMenu.name); onClose(); }}>重命名文件夹…</button>
  {#if renamePending[ctxMenu.name]}
    <button onclick={() => { onRunPending(); onClose(); }}>立即执行待重命名 → {renamePending[ctxMenu.name]}</button>
    <button onclick={() => { onCancelPending(ctxMenu.name); onClose(); }}>取消待重命名</button>
  {/if}
</div>
