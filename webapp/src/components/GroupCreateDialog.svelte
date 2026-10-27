<script lang="ts">
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
      <span>新建分组</span>
      <button class="back set-close rename-x" title="关闭" onclick={onClose}>✕</button>
    </div>
    <input
      class="rename-input"
      bind:value
      onkeydown={(e) => { if (e.key === 'Enter') onConfirm(); }}
      placeholder="输入分组名称"
      maxlength="30"
    />
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>取消</md-outlined-button>
      <md-filled-button disabled={creating || !value.trim()} onclick={onConfirm}>
        {creating ? '处理中…' : '确定'}
      </md-filled-button>
    </div>
  </div>
</div>
