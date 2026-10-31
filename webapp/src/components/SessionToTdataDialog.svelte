<script lang="ts">
  import { t } from '../texts';

  let {
    accountName,
    overwrite = $bindable(false),
    twofa = $bindable(''),
    converting,
    onClose,
    onConfirm,
  }: {
    accountName: string;
    overwrite: boolean;
    twofa: string;
    converting: boolean;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>{t('conv.title')}</span>
      <button class="back set-close rename-x" title={t('common.close')} onclick={onClose}>✕</button>
    </div>
    <p class="set-hint">
      {t('conv.hintPrefix')}<b>{accountName}</b>{t('conv.hintMid')}<b>tdata</b>{t('conv.hintSuffix')}
    </p>
    <p class="set-hint" style="color: var(--md-sys-color-error)">
      {t('conv.warn')}
    </p>
    <label class="del-check">
      <input type="checkbox" bind:checked={overwrite} />
      <span>{t('conv.overwrite')}</span>
    </label>
    <div class="set-row" style="margin-top:8px">
      <span class="set-label">{t('conv.twofaLabel')}</span>
      <input class="set-input" type="password" autocomplete="new-password"
        bind:value={twofa} placeholder={t('conv.twofaPlaceholder')} />
    </div>
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>{t('common.cancel')}</md-outlined-button>
      <md-filled-button disabled={converting} onclick={onConfirm}>
        {converting ? t('card.converting') : t('conv.confirm')}
      </md-filled-button>
    </div>
  </div>
</div>
