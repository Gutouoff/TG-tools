<script lang="ts">
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
      <span>新建账号</span>
      <button class="back set-close rename-x" title="关闭" onclick={() => onClose()}>✕</button>
    </div>
    <div class="mode-seg addacc-tabs">
      <button class="mode-item" class:on={tab === 'files'} onclick={() => (tab = 'files')}>拖入文件</button>
      <button class="mode-item" class:on={tab === 'qr'} onclick={onStartQr}>扫码登录</button>
      <button class="mode-item" class:on={tab === 'phone'} onclick={() => (tab = 'phone')}>手机号登录</button>
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
        <div>拖入文件创建账号</div>
        <small>.session / .json / 2fa.txt / .zip（tdata 或 session+json 打包）</small>
        <small>zip 将自动解压；tdata 将自动转换为 session</small>
      </div>
      {#if files.length}
        <ul class="addacc-list">
          {#each files as f, i}
            <li class="sec-item">
              <span>{f.name}</span>
              <button class="icon-btn" title="移除" onclick={() => onRemoveFile(i)}>✕</button>
            </li>
          {/each}
        </ul>
      {/if}
      <div class="rename-btns">
        <md-outlined-button onclick={() => onClose()}>取消</md-outlined-button>
        <md-filled-button disabled={!files.length || busy} onclick={onConfirm}>
          {busy ? '创建中…' : '创建账号'}
        </md-filled-button>
      </div>
    {:else if tab === 'phone'}
      <div class="phonelogin-box">
        {#if phoneStage === 'phone'}
          <div class="set-row set-row-col">
            <span class="set-label">手机号码（含国家区号，如 6281234567890）</span>
            <input class="set-input" inputmode="numeric" placeholder="6281234567890"
              bind:value={phoneInput} onkeydown={(e) => { if (e.key === 'Enter') onPhoneStart(); }} />
          </div>
          {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
          <div class="rename-btns">
            <md-filled-button disabled={!phoneInput.trim() || phoneBusy} onclick={onPhoneStart}>
              {phoneBusy ? '发送中…' : '发送验证码'}
            </md-filled-button>
          </div>
        {:else if phoneStage === 'code'}
          <p class="set-hint">验证码已发送至 +{phoneInput}，请查收短信或 Telegram 官方消息</p>
          <div class="set-row set-row-col">
            <span class="set-label">验证码</span>
            <input class="set-input" inputmode="numeric" placeholder="登录验证码"
              bind:value={phoneCode} onkeydown={(e) => { if (e.key === 'Enter') onPhoneSubmit(); }} />
          </div>
          {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
          <div class="rename-btns">
            <md-outlined-button onclick={onPhoneReset}>重填手机号</md-outlined-button>
            <md-filled-button disabled={!phoneCode.trim() || phoneBusy} onclick={onPhoneSubmit}>
              {phoneBusy ? '验证中…' : '登录'}
            </md-filled-button>
          </div>
        {:else if phoneStage === 'password'}
          <p class="set-hint">该账号开启了两步验证，请输入 2FA 密码</p>
          <div class="set-row set-row-col">
            <span class="set-label">两步验证密码</span>
            <input class="set-input" type="password" autocomplete="new-password" placeholder="2FA 密码"
              bind:value={phonePwd} onkeydown={(e) => { if (e.key === 'Enter') onPhoneSubmit(); }} />
          </div>
          {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
          <div class="rename-btns">
            <md-filled-button disabled={!phonePwd || phoneBusy} onclick={onPhoneSubmit}>
              {phoneBusy ? '验证中…' : '登录'}
            </md-filled-button>
          </div>
        {/if}
      </div>
    {:else}
      <div class="qrlogin-box">
        {#if qrImg}
          <img class="qr-img" src={`data:image/png;base64,${qrImg}`} alt="登录二维码" />
          <p class="qr-tip">手机 Telegram → 设置 → 设备 → <b>链接桌面设备</b>，扫描此二维码</p>
          <p class="qr-tip qr-status">
            {#if qrStatus === 'waiting'}等待扫码确认…（{qrRemain}s 后过期）{/if}
            {#if qrStatus === 'expired'}二维码已过期，请关闭后重试{/if}
            {#if qrStatus === 'error'}{qrErr}{/if}
          </p>
        {:else if qrStatus === 'loading'}
          <p class="empty">正在生成二维码…</p>
        {:else}
          <p class="empty">{qrErr || '点击「扫码登录」标签页生成二维码'}</p>
        {/if}
      </div>
      <div class="rename-btns">
        <md-outlined-button onclick={() => onClose(true)}>取消登录</md-outlined-button>
      </div>
    {/if}
  </div>
</div>
