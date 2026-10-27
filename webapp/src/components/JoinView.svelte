<script lang="ts">
  type JoinEntry = { name: string; link: string; type: string };

  let {
    entries,
    editIdx = $bindable(-1),
    onAdd,
    onCancelEdit,
    onSaveEdit,
    onJoin,
    onDelete,
    onJoinAll,
    onBack,
  }: {
    entries: JoinEntry[];
    editIdx: number;
    onAdd: () => void;
    onCancelEdit: () => void;
    onSaveEdit: (i: number) => void;
    onJoin: (e: JoinEntry) => void;
    onDelete: (i: number) => void;
    onJoinAll: () => void;
    onBack: () => void;
  } = $props();
</script>

<div class="sec-head">
  <h3>加群频道</h3>
  <button class="back" onclick={onBack}>日志</button>
</div>
<div class="join-toolbar">
  <md-outlined-button onclick={onAdd}>＋ 添加链接</md-outlined-button>
</div>
{#each [['group', '群'], ['channel', '频道']] as [cat, catLabel]}
  <div class="join-cat">{catLabel}</div>
  <ul class="sec-list">
    {#each entries as e, i (i)}
      {#if e.type === cat}
        <li class="sec-item join-item">
          {#if editIdx === i}
            <!-- 行内编辑: 类型+备注+链接,确定/取消 -->
            <div class="join-edit">
              <div class="join-edit-row">
                <select class="set-select join-type" bind:value={e.type}>
                  <option value="group">群</option>
                  <option value="channel">频道</option>
                </select>
                <input class="set-input join-name" bind:value={e.name} placeholder="备注名" />
              </div>
              <input class="set-input join-link" bind:value={e.link} placeholder="https://t.me/xxx 或 @xxx 或邀请链接" />
              <div class="join-edit-btns">
                <md-outlined-button onclick={onCancelEdit}>取消</md-outlined-button>
                <md-filled-button onclick={() => onSaveEdit(i)}>保存</md-filled-button>
              </div>
            </div>
          {:else}
            <span class="join-item-meta">
              <b>{e.name || '(未命名)'}</b>
              <small>{e.link}</small>
            </span>
            <span class="join-item-ops">
              <button class="back" onclick={() => onJoin(e)}>加入</button>
              <button class="icon-btn" title="编辑" onclick={() => (editIdx = i)}>✎</button>
              <button class="icon-btn danger" title="删除" onclick={() => onDelete(i)}>✕</button>
            </span>
          {/if}
        </li>
      {/if}
    {/each}
    {#if !entries.some((e) => e.type === cat)}
      <li class="empty">暂无{catLabel}链接，请点击上方「添加链接」</li>
    {/if}
  </ul>
{/each}
{#if entries.length}
  <md-outlined-button class="full-row" onclick={onJoinAll}>全部加入（当前账号）</md-outlined-button>
{/if}
