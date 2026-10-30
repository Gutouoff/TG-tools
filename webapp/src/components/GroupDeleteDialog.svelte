<script lang="ts">
  import { t } from '../texts';

  let {
    target,
    deleting,
    onClose,
    onConfirm,
  }: {
    target: string;
    deleting: boolean;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>{t('group.deleteTitle')}</span>
      <button class="back set-close rename-x" title={t('common.close')} onclick={onClose}>✕</button>
    </div>
    <p class="set-hint">
      {t('group.deleteHintPrefix')}<b>{target}</b>{t('group.deleteHintSuffix')}
    </p>
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>{t('common.cancel')}</md-outlined-button>
      <md-filled-button class="danger-btn" disabled={deleting} onclick={onConfirm}>
        {deleting ? t('common.deleting') : t('common.delete')}
      </md-filled-button>
    </div>
  </div>
</div>
