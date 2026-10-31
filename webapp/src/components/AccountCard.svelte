<script lang="ts">
  import type { Account } from '../api';
  import { t } from '../texts';

  let {
    account,
    isCurrent,
    isOnline,
    hasAvatar,
    avatarSrc,
    avatarBg,
    renameTarget,
    onSelect,
    onConnect,
    onContext,
    onAvatarError,
    onConvert,
  }: {
    account: Account;
    isCurrent: boolean;
    isOnline: boolean;
    hasAvatar: boolean;
    avatarSrc: string;
    avatarBg: string;
    renameTarget: string;
    onSelect: () => void;
    onConnect: () => void;
    onContext: (e: MouseEvent) => void;
    onAvatarError: () => void;
    onConvert: () => void;
  } = $props();
</script>

<li
  class="item"
  class:cur={isCurrent}
  ondblclick={onConnect}
  onclick={onSelect}
  oncontextmenu={onContext}
>
  <div class="avatar-wrap">
    {#if hasAvatar}
      <img class="avatar" src={avatarSrc} alt="" onerror={onAvatarError} />
    {:else}
      <span class="avatar" style="background:{avatarBg}">{account.display?.[0] || account.username?.[0] || account.name[0] || '-'}</span>
    {/if}
    {#if isOnline}
      <span class="online-dot"></span>
    {/if}
  </div>
  <span class="meta">
    <span class="nm">
      {account.display || account.name}
      {#if (account as any).poll_alive === false}<span class="dead-tag" title={t('accountCard.pollTitle', { msg: (account as any).poll_msg || t('accountCard.noConn'), time: (account as any).poll_time ? ` @ ${(account as any).poll_time}` : '' })}>{t('accountCard.dead')}</span>{:else if (account as any).poll_alive === null}<span class="unk-tag" title={t('accountCard.unknownTitle', { msg: (account as any).poll_msg || t('accountCard.unknownMsg'), time: (account as any).poll_time ? ` @ ${(account as any).poll_time}` : '' })}>{t('accountCard.unknown')}</span>{/if}
      {#if account.username}<span class="uname">{account.username}</span>{/if}
    </span>
    <span class="sub">{account.country ? `${account.country} ` : ''}{account.phone ? `+${account.phone}` : account.state}</span>
  </span>
  {#if renameTarget}
    <span
      class="pend-tag"
      title={t('accountCard.renameTitle', { target: renameTarget })}
    >{t('accountCard.renamePending')}</span>
  {/if}
  {#if account.state === 'tdata'}
    <button class="conv" onclick={(e) => { e.stopPropagation(); onConvert(); }}>{t('accountCard.convert')}</button>
  {/if}
</li>
