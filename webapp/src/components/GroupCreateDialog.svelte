<script lang="ts">
  import { t } from '../texts';

  let {
    value = $bindable(''),
    creating,
    onClose,
    onConfirm,
  }: {
    value: string;
    creating: boolean;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>{t('group.createTitle')}</span>
      <button class="back set-close rename-x" title={t('common.close')} onclick={onClose}>✕</button>
    </div>
    <input
      class="rename-input"
      bind:value
      onkeydown={(e) => { if (e.key === 'Enter') onConfirm(); }}
      placeholder={t('group.createPlaceholder')}
      maxlength="30"
    />
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>{t('common.cancel')}</md-outlined-button>
      <md-filled-button disabled={creating || !value.trim()} onclick={onConfirm}>
        {creating ? t('common.processing') : t('common.confirm')}
      </md-filled-button>
    </div>
  </div>
</div>
