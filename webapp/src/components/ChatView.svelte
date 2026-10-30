<script lang="ts">
  import { t } from '../texts';

  let {
    current,
    isOnline,
    chatUnread,
    dialogs,
    dialogsLoading,
    onRefreshDialogs,
    onBack,
    recvOn,
    recvRules,
    onToggleRecv,
    onRecvRuleChange,
    startChatName = $bindable(''),
    startChatTarget,
    startingChat,
    onStartChat,
    avatarColor,
    onOpenDialog,
    curDialog = $bindable(null),
    historyHasMore,
    historyLoading,
    historyError,
    historyMsgs,
    onLoadHistory,
    chatDraft = $bindable(''),
    sending,
    onSendMsg,
  }: {
    current: any | null;
    isOnline: boolean;
    chatUnread: number;
    dialogs: any[];
    dialogsLoading: boolean;
    onRefreshDialogs: () => void;
    onBack: () => void;
    recvOn: boolean;
    recvRules: Record<string, boolean>;
    onToggleRecv: () => void;
    onRecvRuleChange: (key: string) => void;
    startChatName: string;
    startChatTarget: { kind: string; value: string; label: string };
    startingChat: boolean;
    onStartChat: () => void;
    avatarColor: (name: string) => string;
    onOpenDialog: (d: any) => void;
    curDialog: any | null;
    historyHasMore: boolean;
    historyLoading: boolean;
    historyError: string;
    historyMsgs: any[];
    onLoadHistory: (initial: boolean) => void;
    chatDraft: string;
    sending: boolean;
    onSendMsg: () => void;
  } = $props();
</script>

{#if !curDialog}
  <div class="sec-head">
    <h3>{t('chat.listTitle')}{#if chatUnread} <span class="badge">{chatUnread > 99 ? '99+' : chatUnread}</span>{/if}</h3>
    <span class="head-btns">
      <button class="back" onclick={onBack}>{t('chat.log')}</button>
      <button class="back refresh-btn" disabled={dialogsLoading} aria-busy={dialogsLoading} aria-label={t('chat.refreshLabel')} onclick={onRefreshDialogs}>{dialogsLoading ? t('chat.loading') : t('chat.refresh')}</button>
    </span>
  </div>
  <div class="chat-switch-row">
    <span class="chat-switch-label">
      <span class="status-dot" class:on={recvOn}></span>
      <span class="chat-switch-text">{t('chat.recvNew')}</span>
      <em class="chat-state">{recvOn ? t('chat.listening') : t('chat.stopped')}</em>
    </span>
    <button
      class="toggle"
      class:on={recvOn}
      role="switch"
      aria-label={t('chat.recvNew')}
      aria-checked={recvOn}
      disabled={!isOnline}
      title={!isOnline ? t('chat.connectFirst') : recvOn ? t('chat.stopRecv') : t('chat.startRecv')}
      onclick={onToggleRecv}
    >
      <span class="toggle-thumb"></span>
    </button>
  </div>
  <div class="recv-rules-label">{t('chat.rulesLabel')}</div>
  <div class="recv-rules">
    <button class="rule-chip" class:on={recvRules.exclude_channels} aria-pressed={recvRules.exclude_channels} disabled={!isOnline} onclick={() => onRecvRuleChange('exclude_channels')}>{recvRules.exclude_channels ? '✓ ' : ''}{t('chat.excludeChannels')}</button>
    <button class="rule-chip" class:on={recvRules.exclude_groups} aria-pressed={recvRules.exclude_groups} disabled={!isOnline} onclick={() => onRecvRuleChange('exclude_groups')}>{recvRules.exclude_groups ? '✓ ' : ''}{t('chat.excludeGroups')}</button>
    <button class="rule-chip" class:on={recvRules.exclude_bots} aria-pressed={recvRules.exclude_bots} disabled={!isOnline} onclick={() => onRecvRuleChange('exclude_bots')}>{recvRules.exclude_bots ? '✓ ' : ''}{t('chat.excludeBots')}</button>
  </div>
  <div class="start-chat-row">
    <input
      class="chat-input"
      placeholder={t('chat.startPlaceholder')}
      bind:value={startChatName}
      disabled={!isOnline}
      onkeydown={(e) => { if (e.key === 'Enter') onStartChat(); }}
    />
    <button class="send-btn" disabled={!startChatTarget.value || startingChat || !isOnline} onclick={onStartChat}>
      {startingChat ? t('chat.searching') : t('chat.chat')}
    </button>
  </div>
  {#if startChatTarget.label}
    <div class="start-chat-hint" aria-live="polite">
      {t('chat.recognized')}
      <span class="kind-badge">{startChatTarget.kind === 'id' ? t('chat.kindId') : t('chat.kindUsername')}</span>
      <span class="hint-value">{startChatTarget.label}</span>
    </div>
  {/if}
  {#if !current}
    <p class="empty">{t('chat.selectAccountFirst')}</p>
  {:else if !isOnline}
    <p class="empty">{t('chat.connectToView')}</p>
  {:else if !dialogs.length}
    <p class="empty">{dialogsLoading ? t('chat.loadingDialogs') : t('chat.noDialogs')}</p>
  {/if}
  <ul class="dlg-list">
    {#each dialogs as d (d.id)}
      <li
        class="dlg"
        role="button"
        tabindex="0"
        aria-label={t('chat.openDialog', { name: d.name })}
        onclick={() => onOpenDialog(d)}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenDialog(d); } }}
      >
        <span class="dlg-ava" style="background:{avatarColor(d.name)}">{(d.name || '?')[0]}</span>
        <div class="dlg-body">
          <div class="dlg-row1">
            <span class="dlg-name">{d.name}</span>
            <span class="dlg-time">{d.last_date}</span>
          </div>
          <div class="dlg-row2">
            <span class="dlg-last">{d.last_text || ' '}</span>
            {#if d.unread}<span class="badge">{d.unread > 99 ? '99+' : d.unread}</span>{/if}
          </div>
        </div>
      </li>
    {/each}
  </ul>
{:else}
  <div class="sec-head">
    <h3>{curDialog.name}</h3>
    <span class="head-btns">
      <button class="back" onclick={onBack}>{t('chat.log')}</button>
      <button class="back" onclick={() => (curDialog = null)}>{t('chat.dialogList')}</button>
    </span>
  </div>
  {#if historyHasMore}
    <button class="load-older" disabled={historyLoading} onclick={() => onLoadHistory(false)}>
      {historyLoading ? t('chat.loading') : t('chat.loadOlder')}
    </button>
  {/if}
  <ul class="chat-history">
    {#each historyMsgs as m (m.id)}
      <li class="bbl-row" class:out={m.out}>
        <div class="bbl">
          {#if !m.out && curDialog.type === 'group' && m.sender}<span class="bbl-sender">{m.sender}</span>{/if}
          <div class="bbl-text">{m.text || t('chat.mediaMessage')}<span class="bbl-time">{m.date}{m.out ? ' ✓✓' : ''}</span></div>
        </div>
      </li>
    {/each}
    {#if historyError}
      <li class="empty chat-empty-state" style="color: var(--md-sys-color-error)">
        {t('chat.historyError', { error: historyError })}
        <button class="back" onclick={() => onLoadHistory(true)}>{t('chat.retry')}</button>
      </li>
    {:else if !historyMsgs.length}
      <li class="empty chat-empty-state">{historyLoading ? t('chat.loadingShort') : t('chat.noMessages')}</li>
    {/if}
  </ul>
  <div class="chat-input-row">
    <input
      class="chat-input"
      placeholder={t('chat.inputPlaceholder')}
      bind:value={chatDraft}
      disabled={!isOnline}
      onkeydown={(e) => { if (e.key === 'Enter') onSendMsg(); }}
    />
    <button class="send-btn" disabled={sending || !chatDraft.trim()} onclick={onSendMsg}>
      {sending ? t('chat.sending') : t('chat.send')}
    </button>
  </div>
{/if}
