<script>
  import { getPeak } from '../lib/api.js'
  import OrientationMap from '../lib/components/OrientationMap.svelte'
  import HikeLogForm from '../lib/components/HikeLogForm.svelte'

  let { peakId, onBack } = $props()

  let peak = $state(null)
  let loading = $state(true)
  let error = $state(null)
  let formMode = $state(null) // null | 'add' | {hikeId}

  async function load() {
    loading = true
    error = null
    try {
      peak = await getPeak(peakId)
      if (!peak) error = 'not_found'
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  $effect(() => {
    peakId
    load()
  })

  function onHikeSaved() {
    formMode = null
    load()
  }

  const mapsUrl = (lat, lon) => `maps://?daddr=${lat},${lon}`
</script>

<div class="detail-view">
  <button class="back-btn" onclick={onBack}>&larr; Back to list</button>

  {#if loading}
    <p class="status-text">Loading…</p>
  {:else if error}
    <p class="status-text error">Couldn't load this peak: {error}</p>
  {:else if peak}
    <header class="peak-header">
      <h1>{peak.name}</h1>
      <p class="peak-subtitle">{peak.range === 'NH' ? 'NH 4000-footers' : 'ADK 46 High Peaks'}</p>
    </header>

    <section class="meta-grid">
      <div class="meta-item">
        <span class="meta-label">Elevation</span>
        <span class="meta-value">{peak.elevation_ft ? `${peak.elevation_ft.toLocaleString()} ft` : '—'}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Round-trip length</span>
        <span class="meta-value">{peak.trail_length_mi ? `${peak.trail_length_mi} mi` : '—'}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Elevation gain</span>
        <span class="meta-value">{peak.elevation_gain_ft ? `${peak.elevation_gain_ft.toLocaleString()} ft` : '—'}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Paper map</span>
        <span class="meta-value">{peak.paper_map_ref ?? '—'}</span>
      </div>
    </section>

    {#if peak.group_name}
      <p class="group-note">Part of a group: <strong>{peak.group_name}</strong> — tracked here for reference; each peak's completion still stands on its own.</p>
    {/if}

    <section class="trailhead-section">
      <h2>Trailhead</h2>
      <p class="trailhead-name">{peak.trailhead_name ?? 'Not recorded yet'}</p>
      <OrientationMap lat={peak.trailhead_lat} lon={peak.trailhead_lon} label={peak.trailhead_name} />
      {#if peak.trailhead_lat != null && peak.trailhead_lon != null}
        <a class="btn-secondary maps-link" href={mapsUrl(peak.trailhead_lat, peak.trailhead_lon)}>
          Open in Maps for directions
        </a>
      {/if}
    </section>

    <section class="log-section">
      <div class="log-header">
        <h2>Hike log</h2>
        {#if formMode !== 'add'}
          <button class="btn-secondary add-btn" onclick={() => (formMode = 'add')}>+ Add hike</button>
        {/if}
      </div>

      {#if formMode === 'add'}
        <HikeLogForm {peak} onSaved={onHikeSaved} onCancel={() => (formMode = null)} />
      {/if}

      {#if peak.hikes.length === 0 && formMode !== 'add'}
        <p class="status-text">No hikes logged yet.</p>
      {:else}
        <ul class="hike-list">
          {#each peak.hikes as hike (hike.id)}
            <li class="hike-item">
              {#if formMode?.hikeId === hike.id}
                <HikeLogForm {peak} {hike} onSaved={onHikeSaved} onCancel={() => (formMode = null)} />
              {:else}
                <div class="hike-row">
                  <div>
                    <span class="hike-date">{hike.date}</span>
                    {#if hike.weather}<span class="hike-weather"> · {hike.weather}</span>{/if}
                    {#if hike.notes}<p class="hike-notes">{hike.notes}</p>{/if}
                  </div>
                  <button class="edit-btn" onclick={() => (formMode = { hikeId: hike.id })}>Edit</button>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  {/if}
</div>

<style>
  .detail-view {
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .back-btn {
    align-self: flex-start;
    background: none;
    border: none;
    color: var(--color-accent);
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    padding: 0;
  }

  .status-text {
    color: var(--color-muted);
    font-family: var(--font-display);
  }

  .status-text.error {
    color: #B33A3A;
  }

  .peak-header h1 {
    font-size: 24px;
  }

  .peak-subtitle {
    color: var(--color-muted);
    font-family: var(--font-display);
    font-size: 13px;
    margin-top: var(--space-1);
  }

  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
  }

  .meta-item {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .meta-label {
    font-family: var(--font-display);
    font-size: 12px;
    color: var(--color-muted);
  }

  .meta-value {
    font-family: var(--font-display);
    font-size: 15px;
    font-weight: 600;
  }

  .group-note {
    font-family: var(--font-display);
    font-size: 13px;
    color: var(--color-secondary);
  }

  .trailhead-section, .log-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .trailhead-name {
    font-family: var(--font-display);
    font-size: 14px;
    color: var(--color-secondary);
  }

  .maps-link {
    display: block;
    text-align: center;
    text-decoration: none;
  }

  .log-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .add-btn {
    width: auto;
    padding: 0 var(--space-4);
    min-height: 36px;
  }

  .hike-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .hike-item {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3);
  }

  .hike-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .hike-date {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 14px;
  }

  .hike-weather {
    font-family: var(--font-display);
    font-size: 13px;
    color: var(--color-muted);
  }

  .hike-notes {
    margin-top: var(--space-1);
    font-size: 14px;
    color: var(--color-text);
  }

  .edit-btn {
    flex: 0 0 auto;
    background: none;
    border: none;
    color: var(--color-accent);
    font-family: var(--font-display);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }
</style>
