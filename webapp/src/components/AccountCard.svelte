<script lang="ts">
  import type { Account } from '../api';

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
      {#if (account as any).poll_alive === false}<span class="dead-tag" title={`轮询：${(account as any).poll_msg || '无法连接'}${(account as any).poll_time ? ` @ ${(account as any).poll_time}` : ''}`}>失效</span>{:else if (account as any).poll_alive === null}<span class="unk-tag" title={`轮询：${(account as any).poll_msg || '状态未知'}${(account as any).poll_time ? ` @ ${(account as any).poll_time}` : ''} —— 状态未知，可重试或重新登录`}>?</span>{/if}
      {#if account.username}<span class="uname">{account.username}</span>{/if}
    </span>
    <span class="sub">{account.country ? `${account.country} ` : ''}{account.phone ? `+${account.phone}` : account.state}</span>
  </span>
  {#if renameTarget}
    <span
      class="pend-tag"
      title={`待执行重命名 → ${renameTarget}（该账号客户端关闭后自动重命名；右键可立即执行或取消）`}
    >待重命名</span>
  {/if}
  {#if account.state === 'tdata'}
    <button class="conv" onclick={(e) => { e.stopPropagation(); onConvert(); }}>转换</button>
  {/if}
</li>
