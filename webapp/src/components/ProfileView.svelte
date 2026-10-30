<script lang="ts">
  import type { Account } from '../api';
  import { t } from '../texts';

  let {
    current,
    avatarFailed,
    avatarUrl,
    avatarColor,
    onAvatarError,
    firstName = $bindable(''),
    lastName = $bindable(''),
    username = $bindable(''),
    about = $bindable(''),
    month = $bindable(''),
    day = $bindable(''),
    year = $bindable(''),
    onUploadAvatar,
    onSaveProfile,
    onBack,
  }: {
    current: Account | null;
    avatarFailed: Set<string>;
    avatarUrl: (a: Account) => string;
    avatarColor: (name: string) => string;
    onAvatarError: (name: string) => void;
    firstName: string;
    lastName: string;
    username: string;
    about: string;
    month: string;
    day: string;
    year: string;
    onUploadAvatar: (e: Event) => void;
    onSaveProfile: () => void;
    onBack: () => void;
  } = $props();

  let aboutEl = $state<HTMLTextAreaElement>();

  // 简介自动增高: 打开资料/内容变化时都调整
  $effect(() => {
    const el = aboutEl;
    const _content = about;   // 建立依赖: 内容变化时重新调高
    if (el) {
      el.style.height = 'auto';
      el.style.height = el.scrollHeight + 'px';
    }
  });
</script>

<div class="sec-head">
  <h3>{t('profile.title')}</h3>
  <button class="back" onclick={onBack}>{t('profile.back')}</button>
</div>
<div class="bi">
  {#if current?.avatar && !avatarFailed.has(current.name)}
    <img class="avatar big" src={avatarUrl(current)} alt="" onerror={() => onAvatarError(current?.name || '')} />
  {:else}
    <span class="avatar big" style="background:{avatarColor(current?.name || '-')}">{current?.display?.[0] || current?.name?.[0] || '-'}</span>
  {/if}
  <div class="bi-meta">
    <div class="bi-name">{current?.display || current?.name || t('profile.noAccount')}</div>
    <div class="bi-sub">@{current?.username || '-'}</div>
  </div>
</div>
<div class="form">
  <label>{t('profile.firstName')}</label>
  <input bind:value={firstName} />
  <label>{t('profile.lastName')}</label>
  <input bind:value={lastName} />
  <label>{t('profile.username')}</label>
  <input bind:value={username} />
  <label>{t('profile.about')}</label>
  <textarea
    bind:value={about}
    bind:this={aboutEl}
    rows="1"
  ></textarea>
  <label>{t('profile.birthday')}</label>
  <div class="row3">
    <input placeholder={t('profile.month')} bind:value={month} />
    <input placeholder={t('profile.day')} bind:value={day} />
    <input placeholder={t('profile.year')} bind:value={year} />
  </div>
  <label>{t('profile.avatar')}</label>
  <input type="file" accept="image/*" onchange={onUploadAvatar} />
  <md-filled-button onclick={onSaveProfile}>{t('profile.save')}</md-filled-button>
</div>
