<script>
  import { getPeaks } from '../lib/api.js'

  let { range = $bindable('NH'), onSelectPeak } = $props()

  let peaks = $state([])
  let loading = $state(true)
  let error = $state(null)

  async function load() {
    loading = true
    error = null
    try {
      peaks = (await getPeaks(range)) ?? []
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  $effect(() => {
    range // dependency
    load()
  })

  // Group completion counts, derived from the flat peak list — no extra
  // endpoint needed since each peak already carries group_id/group_name.
  let groupCounts = $derived.by(() => {
    const counts = {}
    for (const p of peaks) {
      if (!p.group_id) continue
      counts[p.group_id] ??= { name: p.group_name, total: 0, done: 0 }
      counts[p.group_id].total += 1
      if (p.completed) counts[p.group_id].done += 1
    }
    return counts
  })
</script>

<div class="list-view">
  <header class="header">
    <h1>Peaks</h1>
    <div class="segmented" role="tablist" aria-label="Peak range">
      <button class:active={range === 'NH'} onclick={() => (range = 'NH')}>NH 48</button>
      <button class:active={range === 'ADK'} onclick={() => (range = 'ADK')}>ADK 46</button>
    </div>
  </header>

  {#if loading}
    <p class="status-text">Loading…</p>
  {:else if error}
    <p class="status-text error">Couldn't load peaks: {error}</p>
  {:else if peaks.length === 0}
    <p class="status-text">No peaks seeded for this range yet.</p>
  {:else}
    <ul class="peak-list">
      {#each peaks as peak (peak.id)}
        <li>
          <button class="peak-card" onclick={() => onSelectPeak(peak.id)}>
            <div class="peak-card-main">
              <span class="peak-order">{peak.order_index + 1}</span>
              <div class="peak-card-text">
                <span class="peak-name">{peak.name}</span>
                <span class="peak-meta">
                  {peak.elevation_ft ? `${peak.elevation_ft.toLocaleString()} ft` : ''}
                  {#if peak.group_name}
                    · {peak.group_name}
                    {#if groupCounts[peak.group_id]}
                      ({groupCounts[peak.group_id].done}/{groupCounts[peak.group_id].total} done)
                    {/if}
                  {/if}
                </span>
              </div>
            </div>
            {#if peak.completed}
              <span class="badge-done">Done</span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .list-view {
    padding: var(--space-4);
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .header .segmented {
    width: auto;
  }

  .status-text {
    color: var(--color-muted);
    font-family: var(--font-display);
    padding: var(--space-6) 0;
  }

  .status-text.error {
    color: #B33A3A;
  }

  .peak-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .peak-card {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    cursor: pointer;
    text-align: left;
    -webkit-tap-highlight-color: transparent;
  }

  .peak-card-main {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-width: 0;
  }

  .peak-order {
    flex: 0 0 auto;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-full);
    background: var(--color-accent-hover-light);
    color: var(--color-accent);
    font-family: var(--font-display);
    font-size: 13px;
    font-weight: 600;
  }

  .peak-card-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .peak-name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 16px;
    color: var(--color-text);
  }

  .peak-meta {
    font-family: var(--font-display);
    font-size: 13px;
    color: var(--color-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .badge-done {
    flex: 0 0 auto;
    font-family: var(--font-display);
    font-size: 12px;
    font-weight: 600;
    color: var(--color-done);
    background: var(--color-done-bg);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
  }
</style>
