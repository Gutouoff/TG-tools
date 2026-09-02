<script lang="ts">
  let status = $state('正在连接后端…');
  let ok = $state(false);

  async function ping() {
    try {
      const r = await fetch('/api/ping');
      const d = await r.json();
      ok = true;
      status = `已连接后端 · ${d.app}`;
    } catch (e) {
      ok = false;
      status = '后端连接失败';
    }
  }

  ping();
</script>

<header class="topbar">
  <span class="title">TG小号工具箱</span>
</header>

<main>
  <div class="card">
    <p class="status" class:bad={!ok}>{status}</p>
    <md-filled-button onclick={ping}>重新握手</md-filled-button>
  </div>
</main>

<style>
  .topbar {
    display: flex;
    align-items: center;
    height: 64px;
    padding: 0 24px;
    background: var(--md-sys-color-primary-container);
    color: var(--md-sys-color-on-primary-container);
  }
  .title {
    font-size: 20px;
    font-weight: 600;
  }
  main {
    padding: 24px;
  }
  .card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
    padding: 24px;
    border-radius: var(--md-sys-shape-corner-large);
    background: var(--md-sys-color-surface-container);
  }
  .status {
    margin: 0;
    font-size: 15px;
  }
  .bad {
    color: var(--md-sys-color-error);
  }
</style>
