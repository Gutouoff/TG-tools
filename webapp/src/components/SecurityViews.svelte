<script lang="ts">
  import { t } from '../texts';

  type SecurityView = 'passkey' | '2fa' | 'email' | 'devices';

  let {
    view,
    onBack,
    passkeys,
    pkQrImg,
    onInitPasskey,
    onDeletePasskey,
    has2fa,
    cur2fa = $bindable(''),
    new2fa = $bindable(''),
    onSet2FA,
    boundEmail,
    showEmailForm = $bindable(false),
    emailPresets,
    emailInput = $bindable(''),
    codeInput = $bindable(''),
    onSendEmail,
    onVerifyEmail,
    devices,
    onDeleteDevice,
  }: {
    view: SecurityView;
    onBack: () => void;
    passkeys: any[];
    pkQrImg: string;
    onInitPasskey: () => void;
    onDeletePasskey: (id: string) => void;
    has2fa: boolean;
    cur2fa: string;
    new2fa: string;
    onSet2FA: () => void;
    boundEmail: string;
    showEmailForm: boolean;
    emailPresets: string[];
    emailInput: string;
    codeInput: string;
    onSendEmail: () => void;
    onVerifyEmail: () => void;
    devices: any[];
    onDeleteDevice: (hash: number) => void;
  } = $props();
</script>

{#if view === 'passkey'}
  <div class="sec-head">
    <h3>{t('sec.passkeyTitle')}</h3>
    <button class="back" onclick={onBack}>{t('sec.back')}</button>
  </div>
  <md-filled-button onclick={onInitPasskey}>{t('sec.passkeyAdd')}</md-filled-button>
  {#if pkQrImg}
    <div class="qr-box">
      <img class="qr-img" src={pkQrImg} alt={t('sec.passkeyQrAlt')} />
      <p class="qr-tip">{t('sec.qrPrefix')}<b>{t('sec.qrStrong')}</b>{t('sec.qrSuffix')}<br />{t('sec.qrNote')}</p>
    </div>
  {/if}
  <ul class="sec-list">
    {#each passkeys as pk}
      <li class="sec-item">
        <span>{pk.name || t('sec.unnamed')}</span>
        <button class="danger" onclick={() => onDeletePasskey(pk.id)}>{t('sec.delete')}</button>
      </li>
    {/each}
  </ul>
  {#if !passkeys.length}<p class="empty">{t('sec.noPasskey')}</p>{/if}
{:else if view === '2fa'}
  <div class="sec-head">
    <h3>{t('sec.2faTitle')}</h3>
    <button class="back" onclick={onBack}>{t('sec.back')}</button>
  </div>
  <p>{t('sec.2faStatus', { state: has2fa ? t('sec.2faOn') : t('sec.2faOff') })}</p>
  {#if has2fa}
    <input placeholder={t('sec.curPassword')} bind:value={cur2fa} />
  {/if}
  <input placeholder={t('sec.newPassword')} bind:value={new2fa} />
  <md-filled-button onclick={onSet2FA}>{t('sec.set2fa')}</md-filled-button>
{:else if view === 'email'}
  <div class="sec-head">
    <h3>{t('sec.emailTitle')}</h3>
    <button class="back" onclick={onBack}>{t('sec.back')}</button>
  </div>
  {#if boundEmail && !showEmailForm}
    <div class="bound-box">
      <div class="bound-label">{t('sec.boundEmail')}</div>
      <div class="bound-email">{boundEmail}</div>
    </div>
    <md-outlined-button onclick={() => (showEmailForm = true)}>{t('sec.changeEmail')}</md-outlined-button>
  {:else}
    {#if boundEmail}
      <p class="set-hint">{t('sec.boundHint', { email: boundEmail })}</p>
    {/if}
    {#if emailPresets.length}
      <div class="rename-quick">
        <span class="rename-quick-label">{t('sec.presets')}</span>
        {#each emailPresets as p}
          <button class="rule-chip" onclick={() => (emailInput = p)}>{p}</button>
        {/each}
      </div>
    {/if}
    <input placeholder={t('sec.emailPlaceholder')} bind:value={emailInput} />
    <md-outlined-button onclick={onSendEmail}>{t('sec.sendCode')}</md-outlined-button>
    <input placeholder={t('sec.codePlaceholder')} bind:value={codeInput} />
    <md-filled-button onclick={onVerifyEmail}>{t('sec.verifyEmail')}</md-filled-button>
  {/if}
{:else if view === 'devices'}
  <div class="sec-head">
    <h3>{t('sec.devicesTitle')}</h3>
    <button class="back" onclick={onBack}>{t('sec.back')}</button>
  </div>
  <ul class="sec-list">
    {#each devices as d}
      <li class="sec-item">
        <span>{d.device_model || t('sec.unknownDevice')}{d.current ? t('sec.thisDevice') : ''}</span>
        {#if !d.current}
          <button class="danger" onclick={() => onDeleteDevice(d.hash)}>{t('sec.delete')}</button>
        {/if}
      </li>
    {/each}
  </ul>
  {#if !devices.length}<p class="empty">{t('sec.noDevices')}</p>{/if}
{/if}
