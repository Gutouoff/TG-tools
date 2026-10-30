<script lang="ts">
  import { t } from '../texts';

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
  <h3>{t('join.title')}</h3>
  <button class="back" onclick={onBack}>{t('join.back')}</button>
</div>
<div class="join-toolbar">
  <md-outlined-button onclick={onAdd}>{t('join.add')}</md-outlined-button>
</div>
{#each ['group', 'channel'] as cat}
  <div class="join-cat">{cat === 'group' ? t('join.group') : t('join.channel')}</div>
  <ul class="sec-list">
    {#each entries as e, i (i)}
      {#if e.type === cat}
        <li class="sec-item join-item">
          {#if editIdx === i}
            <!-- 行内编辑: 类型+备注+链接,确定/取消 -->
            <div class="join-edit">
              <div class="join-edit-row">
                <select class="set-select join-type" bind:value={e.type}>
                  <option value="group">{t('join.typeGroup')}</option>
                  <option value="channel">{t('join.typeChannel')}</option>
                </select>
                <input class="set-input join-name" bind:value={e.name} placeholder={t('join.namePlaceholder')} />
              </div>
              <input class="set-input join-link" bind:value={e.link} placeholder={t('join.linkPlaceholder')} />
              <div class="join-edit-btns">
                <md-outlined-button onclick={onCancelEdit}>{t('join.cancel')}</md-outlined-button>
                <md-filled-button onclick={() => onSaveEdit(i)}>{t('join.save')}</md-filled-button>
              </div>
            </div>
          {:else}
            <span class="join-item-meta">
              <b>{e.name || t('join.unnamed')}</b>
              <small>{e.link}</small>
            </span>
            <span class="join-item-ops">
              <button class="back" onclick={() => onJoin(e)}>{t('join.join')}</button>
              <button class="icon-btn" title={t('join.edit')} onclick={() => (editIdx = i)}>✎</button>
              <button class="icon-btn danger" title={t('join.delete')} onclick={() => onDelete(i)}>✕</button>
            </span>
          {/if}
        </li>
      {/if}
    {/each}
    {#if !entries.some((e) => e.type === cat)}
      <li class="empty">{t('join.empty', { cat: cat === 'group' ? t('join.group') : t('join.channel') })}</li>
    {/if}
  </ul>
{/each}
{#if entries.length}
  <md-outlined-button class="full-row" onclick={onJoinAll}>{t('join.joinAll')}</md-outlined-button>
{/if}
