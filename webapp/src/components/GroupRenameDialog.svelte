<script lang="ts">
  let {
    value = $bindable(''),
    onClose,
    onConfirm,
  }: {
    value: string;
    onClose: () => void;
    onConfirm: () => void;
  } = $props();
</script>

<div class="modal-mask" onclick={onClose}>
  <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
    <div class="rename-head">
      <span>分组重命名</span>
      <button class="back set-close rename-x" title="关闭" onclick={onClose}>✕</button>
    </div>
    <input
      class="rename-input"
      bind:value
      onkeydown={(e) => { if (e.key === 'Enter') onConfirm(); }}
      placeholder="输入新的分组名称"
      maxlength="30"
    />
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>取消</md-outlined-button>
      <md-filled-button disabled={!value.trim()} onclick={onConfirm}>确定</md-filled-button>
    </div>
  </div>
</div>
