<script lang="ts">
  import type { Account } from '../api';

  let {
    target,
    confirm = $bindable(false),
    deleting,
    onClose,
    onConfirm,
  }: {
    target: Account;
    confirm: boolean;
    deleting: boolean;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal del-modal" onclick={(e) => e.stopPropagation()}>
    <div class="del-icon">
      <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true">
        <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
      </svg>
    </div>
    <div class="del-title">删除账号</div>
    <p class="del-sub">此操作<b>不可恢复</b>。将永久删除该账号的 session、tdata、登录凭据等全部文件，删除后只能重新登录。</p>
    <div class="set-group">
      <div class="set-row">
        <span class="set-label">账号</span>
        <span class="del-val">{target.display || target.name}</span>
      </div>
      {#if target.uid}<div class="set-row">
        <span class="set-label">UID</span>
        <span class="del-val mono">{target.uid}</span>
      </div>{/if}
      <div class="set-row set-row-col">
        <span class="set-label">将被删除的文件夹</span>
        <code class="del-path">{target.path}</code>
      </div>
    </div>
    <label class="del-check">
      <input type="checkbox" bind:checked={confirm} />
      <span>我已了解该操作不可恢复，确认删除该账号的全部文件</span>
    </label>
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>取消</md-outlined-button>
      <md-filled-button class="danger-btn" disabled={deleting || !confirm} onclick={onConfirm}>
        {deleting ? '删除中…' : '永久删除'}
      </md-filled-button>
    </div>
  </div>
</div>
