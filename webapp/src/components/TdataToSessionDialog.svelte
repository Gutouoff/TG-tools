<script lang="ts">
  import { t } from '../texts';

  let {
    accountName,
    converting,
    onClose,
    onConfirm,
  }: {
    accountName: string;
    converting: boolean;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>{t('t2s.title')}</span>
      <button class="back set-close rename-x" title={t('common.close')} onclick={onClose}>✕</button>
    </div>
    <p class="set-hint">
      {t('t2s.hintPrefix')}<b>{accountName}</b>{t('t2s.hintMid')}<b>tdata</b>{t('t2s.hintSuffix')}
    </p>
    <p class="set-hint" style="color: var(--md-sys-color-error)">
      {t('t2s.warn')}
    </p>
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>{t('common.cancel')}</md-outlined-button>
      <md-filled-button disabled={converting} onclick={onConfirm}>
        {converting ? t('t2s.refreshing') : t('t2s.confirm')}
      </md-filled-button>
    </div>
  </div>
</div>
