<script lang="ts">
  import { t } from '../texts';

  let {
    value = $bindable(''),
    renaming,
    quickOpts,
    quickVal,
    onApplyQuick,
    onClose,
    onConfirm,
  }: {
    value: string;
    renaming: boolean;
    quickOpts: Array<[string, string]>;
    quickVal: (key: string) => string | false;
    onApplyQuick: (key: string, label: string) => void;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>{t('rename.title')}</span>
      <button class="back set-close rename-x" title={t('common.close')} onclick={onClose}>✕</button>
    </div>
    <input
      class="rename-input"
      bind:value
      onkeydown={(e) => { if (e.key === 'Enter') onConfirm(); }}
      placeholder={t('rename.placeholder')}
      maxlength="60"
    />
    {#if quickOpts.length}
      <div class="rename-quick">
        <span class="rename-quick-label">{t('rename.quick')}</span>
        {#each quickOpts as [k, label]}
          {#if quickVal(k)}
            <button class="rule-chip" title={quickVal(k) || ''} onclick={() => onApplyQuick(k, label)}>{label}</button>
          {/if}
        {/each}
      </div>
    {/if}
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>{t('common.cancel')}</md-outlined-button>
      <md-filled-button disabled={renaming || !value.trim()} onclick={onConfirm}>
        {renaming ? t('common.processing') : t('common.confirm')}
      </md-filled-button>
    </div>
  </div>
</div>
