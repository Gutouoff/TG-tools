<script lang="ts">
  import type { Account } from '../api';
  import { t, cardLabel } from '../texts';

  let {
    cardOrder,
    isOpen,
    onToggle,
    current,
    avatarFailed,
    avatarUrl,
    avatarColor,
    onAvatarError,
    onEditProfile,
    recvOn,
    canRecv,
    chatUnread,
    onToggleRecv,
    onOpenChatList,
    on2FA,
    onPasskeys,
    onEmail,
    onDevices,
    onDeleteContacts,
    onDeleteDialogs,
    speedVal,
    speedSeg,
    onSpeed,
    converting,
    onOpenTdataToSs,
    onOpenConvertTdata,
    onRefreshSs,
    onUpdateTelegram,
    onRefreshInfo,
    onPollAccounts,
    onJoinChannels,
    exporting,
    onExport,
    onDeleteAccount,
  }: {
    cardOrder: string[];
    isOpen: (name: string, def: boolean) => boolean;
    onToggle: (name: string, open: boolean) => void;
    current: Account | null;
    avatarFailed: Set<string>;
    avatarUrl: (a: Account) => string;
    avatarColor: (name: string) => string;
    onAvatarError: (name: string) => void;
    onEditProfile: () => void;
    recvOn: boolean;
    canRecv: boolean;
    chatUnread: number;
    onToggleRecv: () => void;
    onOpenChatList: () => void;
    on2FA: () => void;
    onPasskeys: () => void;
    onEmail: () => void;
    onDevices: () => void;
    onDeleteContacts: () => void;
    onDeleteDialogs: (choice: string) => void;
    speedVal: number;
    speedSeg: Array<[string, number]>;
    onSpeed: (v: number) => void;
    converting: boolean;
    onOpenTdataToSs: () => void;
    onOpenConvertTdata: () => void;
    onRefreshSs: () => void;
    onUpdateTelegram: () => void;
    onRefreshInfo: () => void;
    onPollAccounts: () => void;
    onJoinChannels: () => void;
    exporting: boolean;
    onExport: () => void;
    onDeleteAccount: () => void;
  } = $props();
</script>

{#each cardOrder as c (c)}
  {#if c === '基本信息'}
    <details class="card" data-card="基本信息" open={isOpen('基本信息', true)} ontoggle={(e) => onToggle('基本信息', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{cardLabel('基本信息')}</summary>
      <div class="bi">
        {#if current?.avatar && !avatarFailed.has(current.name)}
          <img class="avatar big" src={avatarUrl(current)} alt="" onerror={() => onAvatarError(current?.name || '')} />
        {:else}
          <span class="avatar big" style="background:{avatarColor(current?.name || '-')}">
            {current?.display?.[0] || current?.name?.[0] || '-'}
          </span>
        {/if}
        <div class="bi-meta">
          <div class="bi-name">{current?.display || current?.name || t('card.noAccount')}</div>
          <div class="bi-sub">@{current?.username || current?.phone || '-'}</div>
        </div>
        <button class="edit-btn" onclick={onEditProfile}>{t('card.edit')}</button>
      </div>
    </details>
  {:else if c === '聊天'}
    <details class="card" data-card="聊天" open={isOpen('聊天', true)} ontoggle={(e) => onToggle('聊天', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{cardLabel('聊天')}</summary>
      <div class="chat-ctl">
        <div class="chat-switch-row">
          <span class="chat-switch-label">
            <span class="status-dot" class:on={recvOn}></span>
            <span class="chat-switch-text">{t('card.recvNew')}</span>
            <em class="chat-state">{recvOn ? t('card.listening') : t('card.stopped')}</em>
          </span>
          <button
            class="toggle"
            class:on={recvOn}
            role="switch"
            aria-label={t('card.recvNew')}
            aria-checked={recvOn}
            disabled={!canRecv}
            title={!canRecv ? t('card.connectFirst') : recvOn ? t('card.stopRecv') : t('card.startRecv')}
            onclick={onToggleRecv}
          >
            <span class="toggle-thumb"></span>
          </button>
        </div>
        <div class="chat-entries">
          <button class="chat-entry" onclick={onOpenChatList}>
            {t('card.messageList')}
            {#if chatUnread}<span class="badge">{chatUnread > 99 ? '99+' : chatUnread}</span>{/if}
          </button>
        </div>
      </div>
    </details>
  {:else if c === '安全'}
    <details class="card" data-card="安全" open={isOpen('安全', false)} ontoggle={(e) => onToggle('安全', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{cardLabel('安全')}</summary>
      <div class="grid">
        <md-outlined-button onclick={on2FA}>{t('card.2fa')}</md-outlined-button>
        <md-outlined-button onclick={onPasskeys}>{t('card.passkey')}</md-outlined-button>
        <md-outlined-button onclick={onEmail}>{t('card.email')}</md-outlined-button>
        <md-outlined-button onclick={onDevices}>{t('card.devices')}</md-outlined-button>
      </div>
    </details>
  {:else if c === '删除'}
    <details class="card" data-card="删除" open={isOpen('删除', true)} ontoggle={(e) => onToggle('删除', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{cardLabel('删除')}</summary>
      <div class="grid">
        <md-outlined-button onclick={onDeleteContacts}>{t('card.delContacts')}</md-outlined-button>
        <md-outlined-button onclick={() => onDeleteDialogs('users')}>{t('card.delDialogs')}</md-outlined-button>
        <md-outlined-button onclick={() => onDeleteDialogs('bots')}>{t('card.delBots')}</md-outlined-button>
        <md-outlined-button onclick={() => onDeleteDialogs('groups')}>{t('card.delChannels')}</md-outlined-button>
      </div>
      <div class="speed-row">
        <span class="speed-label">{t('card.speed')}</span>
        <div class="speed-seg">
          {#each speedSeg as [label, v]}
            <button class="seg" class:on={speedVal === v} onclick={() => onSpeed(v)}>{label}</button>
          {/each}
        </div>
      </div>
    </details>
  {:else if c === '转换'}
    <details class="card" data-card="转换" open={isOpen('转换', false)} ontoggle={(e) => onToggle('转换', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{cardLabel('转换')}</summary>
      <div class="conv-group">
        <md-outlined-button class="full-row" onclick={onOpenTdataToSs}>{t('card.tdataToSs')}</md-outlined-button>
        <md-outlined-button class="full-row" onclick={onOpenConvertTdata} disabled={converting}>{converting ? t('card.converting') : t('card.ssToTdata')}</md-outlined-button>
        <md-outlined-button onclick={onRefreshSs}>{t('card.refreshSs')}</md-outlined-button>
      </div>
    </details>
  {:else if c === '其他设置'}
    <details class="card" data-card="其他设置" open={isOpen('其他设置', false)} ontoggle={(e) => onToggle('其他设置', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{cardLabel('其他设置')}</summary>
      <div class="grid">
        <md-outlined-button onclick={onUpdateTelegram}>{t('card.updateClient')}</md-outlined-button>
        <md-outlined-button onclick={onRefreshInfo}>{t('card.refreshInfo')}</md-outlined-button>
        <md-outlined-button onclick={onPollAccounts}>{t('card.poll')}</md-outlined-button>
        <md-outlined-button onclick={onJoinChannels}>{t('card.joinChannels')}</md-outlined-button>
        <md-outlined-button onclick={onExport} disabled={exporting}>{exporting ? t('card.exporting') : t('card.export')}</md-outlined-button>
        <md-outlined-button class="danger-btn" onclick={onDeleteAccount}>{t('card.deleteAccount')}</md-outlined-button>
      </div>
    </details>
  {/if}
{/each}
