<script lang="ts">
  import type { Account } from '../api';

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
  <h3>编辑资料</h3>
  <button class="back" onclick={onBack}>日志</button>
</div>
<div class="bi">
  {#if current?.avatar && !avatarFailed.has(current.name)}
    <img class="avatar big" src={avatarUrl(current)} alt="" onerror={() => onAvatarError(current?.name || '')} />
  {:else}
    <span class="avatar big" style="background:{avatarColor(current?.name || '-')}">{current?.display?.[0] || current?.name?.[0] || '-'}</span>
  {/if}
  <div class="bi-meta">
    <div class="bi-name">{current?.display || current?.name || '未选择账号'}</div>
    <div class="bi-sub">@{current?.username || '-'}</div>
  </div>
</div>
<div class="form">
  <label>名字</label>
  <input bind:value={firstName} />
  <label>姓氏</label>
  <input bind:value={lastName} />
  <label>用户名（不带 @）</label>
  <input bind:value={username} />
  <label>简介</label>
  <textarea
    bind:value={about}
    bind:this={aboutEl}
    rows="1"
  ></textarea>
  <label>生日（月 / 日 / 年）</label>
  <div class="row3">
    <input placeholder="月" bind:value={month} />
    <input placeholder="日" bind:value={day} />
    <input placeholder="年" bind:value={year} />
  </div>
  <label>头像</label>
  <input type="file" accept="image/*" onchange={onUploadAvatar} />
  <md-filled-button onclick={onSaveProfile}>保存</md-filled-button>
</div>
