<script lang="ts">
  import { t } from '../texts';

  let {
    tab = $bindable('files'),
    dragging = $bindable(false),
    files,
    busy,
    qrImg,
    qrStatus,
    qrRemain,
    qrErr,
    phoneStage,
    phoneInput = $bindable(''),
    phoneCode = $bindable(''),
    phonePwd = $bindable(''),
    phoneErr,
    phoneBusy,
    onClose,
    onStartQr,
    onRemoveFile,
    onConfirm,
    onDragOver,
    onDragLeave,
    onDrop,
    onPhoneStart,
    onPhoneSubmit,
    onPhoneReset,
  }: {
    tab: string;
    dragging: boolean;
    files: Array<{ name: string; data: string }>;
    busy: boolean;
    qrImg: string;
    qrStatus: string;
    qrRemain: number;
    qrErr: string;
    phoneStage: string;
    phoneInput: string;
    phoneCode: string;
    phonePwd: string;
    phoneErr: string;
    phoneBusy: boolean;
    onClose: (cancelQr?: boolean) => void;
    onStartQr: () => void;
    onRemoveFile: (i: number) => void;
    onConfirm: () => void;
    onDragOver: (e: DragEvent) => void;
    onDragLeave: () => void;
    onDrop: (e: DragEvent) => void;
    onPhoneStart: () => void;
    onPhoneSubmit: () => void;
    onPhoneReset: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={() => onClose()}>
  <div class="modal rename-modal addacc-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>{t('add.title')}</span>
      <button class="back set-close rename-x" title={t('common.close')} onclick={() => onClose()}>✕</button>
    </div>
    <div class="mode-seg addacc-tabs">
      <button class="mode-item" class:on={tab === 'files'} onclick={() => (tab = 'files')}>{t('add.tabFiles')}</button>
      <button class="mode-item" class:on={tab === 'qr'} onclick={onStartQr}>{t('add.tabQr')}</button>
      <button class="mode-item" class:on={tab === 'phone'} onclick={() => (tab = 'phone')}>{t('add.tabPhone')}</button>
    </div>
    {#if tab === 'files'}
      <div
        class="addacc-drop"
        class:over={dragging}
        ondragover={onDragOver}
        ondragleave={onDragLeave}
        ondrop={onDrop}
      >
        <div class="addacc-drop-icon">⬇</div>
        <div>{t('add.dropTitle')}</div>
        <small>{t('add.dropFormats')}</small>
        <small>{t('add.dropHint')}</small>
      </div>
      {#if files.length}
        <ul class="addacc-list">
          {#each files as f, i}
            <li class="sec-item">
              <span>{f.name}</span>
              <button class="icon-btn" title={t('add.remove')} onclick={() => onRemoveFile(i)}>✕</button>
            </li>
          {/each}
        </ul>
      {/if}
      <div class="rename-btns">
        <md-outlined-button onclick={() => onClose()}>{t('common.cancel')}</md-outlined-button>
        <md-filled-button disabled={!files.length || busy} onclick={onConfirm}>
          {busy ? t('add.creating') : t('add.create')}
        </md-filled-button>
      </div>
    {:else if tab === 'phone'}
      <div class="phonelogin-box">
        {#if phoneStage === 'phone'}
          <div class="set-row set-row-col">
            <span class="set-label">{t('add.phoneLabel')}</span>
            <input class="set-input" inputmode="numeric" placeholder="6281234567890"
              bind:value={phoneInput} onkeydown={(e) => { if (e.key === 'Enter') onPhoneStart(); }} />
          </div>
          {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
          <div class="rename-btns">
            <md-filled-button disabled={!phoneInput.trim() || phoneBusy} onclick={onPhoneStart}>
              {phoneBusy ? t('add.sending') : t('add.sendCode')}
            </md-filled-button>
          </div>
        {:else if phoneStage === 'code'}
          <p class="set-hint">{t('add.codeSent', { phone: phoneInput })}</p>
          <div class="set-row set-row-col">
            <span class="set-label">{t('add.codeLabel')}</span>
            <input class="set-input" inputmode="numeric" placeholder={t('add.codePlaceholder')}
              bind:value={phoneCode} onkeydown={(e) => { if (e.key === 'Enter') onPhoneSubmit(); }} />
          </div>
          {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
          <div class="rename-btns">
            <md-outlined-button onclick={onPhoneReset}>{t('add.refillPhone')}</md-outlined-button>
            <md-filled-button disabled={!phoneCode.trim() || phoneBusy} onclick={onPhoneSubmit}>
              {phoneBusy ? t('add.verifying') : t('add.login')}
            </md-filled-button>
          </div>
        {:else if phoneStage === 'password'}
          <p class="set-hint">{t('add.2faHint')}</p>
          <div class="set-row set-row-col">
            <span class="set-label">{t('add.2faLabel')}</span>
            <input class="set-input" type="password" autocomplete="new-password" placeholder={t('add.2faPlaceholder')}
              bind:value={phonePwd} onkeydown={(e) => { if (e.key === 'Enter') onPhoneSubmit(); }} />
          </div>
          {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
          <div class="rename-btns">
            <md-filled-button disabled={!phonePwd || phoneBusy} onclick={onPhoneSubmit}>
              {phoneBusy ? t('add.verifying') : t('add.login')}
            </md-filled-button>
          </div>
        {/if}
      </div>
    {:else}
      <div class="qrlogin-box">
        {#if qrImg}
          <img class="qr-img" src={`data:image/png;base64,${qrImg}`} alt={t('add.qrAlt')} />
          <p class="qr-tip">{t('add.qrTip')}<b>{t('add.qrTipStrong')}</b>{t('add.qrTipSuffix')}</p>
          <p class="qr-tip qr-status">
            {#if qrStatus === 'waiting'}{t('add.qrWaiting', { seconds: qrRemain })}{/if}
            {#if qrStatus === 'expired'}{t('add.qrExpired')}{/if}
            {#if qrStatus === 'error'}{qrErr}{/if}
          </p>
        {:else if qrStatus === 'loading'}
          <p class="empty">{t('add.qrLoading')}</p>
        {:else}
          <p class="empty">{qrErr || t('add.qrIdle')}</p>
        {/if}
      </div>
      <div class="rename-btns">
        <md-outlined-button onclick={() => onClose(true)}>{t('add.cancelLogin')}</md-outlined-button>
      </div>
    {/if}
  </div>
</div>
