<script lang="ts">
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
      <span>删除分组</span>
      <button class="back set-close rename-x" title="关闭" onclick={onClose}>✕</button>
    </div>
    <p class="set-hint">
      删除分组「<b>{target}</b>」？组内账号不受影响，将归入「未分组」。
    </p>
    <div class="rename-btns">
      <md-outlined-button onclick={onClose}>取消</md-outlined-button>
      <md-filled-button class="danger-btn" disabled={deleting} onclick={onConfirm}>
        {deleting ? '删除中…' : '删除'}
      </md-filled-button>
    </div>
  </div>
</div>
