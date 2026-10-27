<script lang="ts">
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
    <h3>通行密钥</h3>
    <button class="back" onclick={onBack}>日志</button>
  </div>
  <md-filled-button onclick={onInitPasskey}>＋ 添加通行密钥</md-filled-button>
  {#if pkQrImg}
    <div class="qr-box">
      <img class="qr-img" src={pkQrImg} alt="通行密钥二维码" />
      <p class="qr-tip">请使用<b>手机系统相机或 Google 智能镜头</b>扫描<br />（由手机密码管理器完成通行密钥注册；Telegram 客户端不参与扫码）</p>
    </div>
  {/if}
  <ul class="sec-list">
    {#each passkeys as pk}
      <li class="sec-item">
        <span>{pk.name || '（未命名）'}</span>
        <button class="danger" onclick={() => onDeletePasskey(pk.id)}>删除</button>
      </li>
    {/each}
  </ul>
  {#if !passkeys.length}<p class="empty">暂无通行密钥</p>{/if}
{:else if view === '2fa'}
  <div class="sec-head">
    <h3>两步验证</h3>
    <button class="back" onclick={onBack}>日志</button>
  </div>
  <p>当前状态：{has2fa ? '已开启' : '未开启'}</p>
  {#if has2fa}
    <input placeholder="当前密码" bind:value={cur2fa} />
  {/if}
  <input placeholder="新密码" bind:value={new2fa} />
  <md-filled-button onclick={onSet2FA}>设置或修改</md-filled-button>
{:else if view === 'email'}
  <div class="sec-head">
    <h3>邮箱登录</h3>
    <button class="back" onclick={onBack}>日志</button>
  </div>
  {#if boundEmail && !showEmailForm}
    <div class="bound-box">
      <div class="bound-label">已绑定邮箱</div>
      <div class="bound-email">{boundEmail}</div>
    </div>
    <md-outlined-button onclick={() => (showEmailForm = true)}>换绑邮箱</md-outlined-button>
  {:else}
    {#if boundEmail}
      <p class="set-hint">当前绑定：{boundEmail}。填写新邮箱即可完成换绑。</p>
    {/if}
    {#if emailPresets.length}
      <div class="rename-quick">
        <span class="rename-quick-label">预选邮箱：</span>
        {#each emailPresets as p}
          <button class="rule-chip" onclick={() => (emailInput = p)}>{p}</button>
        {/each}
      </div>
    {/if}
    <input placeholder="邮箱地址" bind:value={emailInput} />
    <md-outlined-button onclick={onSendEmail}>发送验证码</md-outlined-button>
    <input placeholder="验证码" bind:value={codeInput} />
    <md-filled-button onclick={onVerifyEmail}>验证绑定</md-filled-button>
  {/if}
{:else if view === 'devices'}
  <div class="sec-head">
    <h3>登录设备</h3>
    <button class="back" onclick={onBack}>日志</button>
  </div>
  <ul class="sec-list">
    {#each devices as d}
      <li class="sec-item">
        <span>{d.device_model || '未知设备'}{d.current ? '（本设备）' : ''}</span>
        {#if !d.current}
          <button class="danger" onclick={() => onDeleteDevice(d.hash)}>删除</button>
        {/if}
      </li>
    {/each}
  </ul>
  {#if !devices.length}<p class="empty">暂无设备</p>{/if}
{/if}
