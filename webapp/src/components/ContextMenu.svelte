<script lang="ts">
  import { t } from '../texts';

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
  <div class="ctx-title">{t('ctx.moveGroup')}</div>
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
  <button onclick={() => { onMove(ctxMenu.name, 'ungrouped'); onClose(); }}>{t('ctx.removeAll')}</button>
  {#if onlineNames.has(ctxMenu.name)}
    <button class="ctx-disconnect" onclick={() => { onDisconnect(ctxMenu.name); onClose(); }}>{t('ctx.disconnect')}</button>
  {/if}
  <button onclick={() => { onRename(ctxMenu.name); onClose(); }}>{t('ctx.rename')}</button>
  {#if renamePending[ctxMenu.name]}
    <button onclick={() => { onRunPending(); onClose(); }}>{t('ctx.runPending', { target: renamePending[ctxMenu.name] })}</button>
    <button onclick={() => { onCancelPending(ctxMenu.name); onClose(); }}>{t('ctx.cancelPending')}</button>
  {/if}
</div>
