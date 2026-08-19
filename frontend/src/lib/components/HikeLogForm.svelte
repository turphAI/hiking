<script>
  import { createHike, updateHike, getWeather } from '../api.js'

  // `peak` supplies trailhead coords for the weather auto-fill. `hike`, when
  // present, puts the form in edit mode (pre-filled, PUT on save).
  let { peak, hike = null, onSaved, onCancel } = $props()

  let date = $state(hike?.date ?? new Date().toISOString().slice(0, 10))
  let weather = $state(hike?.weather ?? '')
  let notes = $state(hike?.notes ?? '')
  let weatherTouched = $state(false) // once the user edits weather, stop auto-overwriting it
  let weatherLoading = $state(false)
  let saving = $state(false)
  let error = $state(null)

  let hasTrailhead = $derived(peak?.trailhead_lat != null && peak?.trailhead_lon != null)

  async function fillWeather() {
    if (!hasTrailhead || !date || weatherTouched) return
    weatherLoading = true
    const result = await getWeather(peak.trailhead_lat, peak.trailhead_lon, date)
    weatherLoading = false
    if (result?.ok && result.summary) {
      weather = result.summary
    }
  }

  // Fetch on mount (edit mode leaves the saved value alone) and whenever the
  // date changes, as long as the user hasn't hand-edited the field.
  $effect(() => {
    date
    if (!hike) fillWeather()
  })

  async function save() {
    saving = true
    error = null
    try {
      const body = { date, weather: weather || null, notes: notes || null }
      if (hike) {
        await updateHike(hike.id, body)
      } else {
        await createHike({ peak_id: peak.id, ...body })
      }
      onSaved()
    } catch (e) {
      error = e.message
    } finally {
      saving = false
    }
  }
</script>

<form class="hike-form" onsubmit={(e) => { e.preventDefault(); save() }}>
  <div class="field">
    <label class="field-label" for="hike-date">Date</label>
    <input id="hike-date" class="input" type="date" bind:value={date} required />
  </div>

  <div class="field">
    <label class="field-label" for="hike-weather">Weather</label>
    <input
      id="hike-weather"
      class="input"
      type="text"
      bind:value={weather}
      oninput={() => (weatherTouched = true)}
      placeholder={hasTrailhead ? (weatherLoading ? 'Fetching…' : 'e.g. 45–58°F, partly cloudy') : 'No trailhead coordinates to look up weather'}
    />
    {#if hasTrailhead}
      <span class="field-hint">Pre-filled from Open-Meteo — edit freely.</span>
    {/if}
  </div>

  <div class="field">
    <label class="field-label" for="hike-notes">Notes</label>
    <textarea id="hike-notes" class="input textarea" bind:value={notes} rows="4"></textarea>
  </div>

  {#if error}
    <p class="form-error">{error}</p>
  {/if}

  <div class="form-actions">
    <button type="button" class="btn-secondary" onclick={onCancel} disabled={saving}>Cancel</button>
    <button type="submit" class="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
  </div>
</form>

<style>
  .hike-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .form-actions {
    display: flex;
    gap: var(--space-2);
  }

  .form-error {
    color: #B33A3A;
    font-family: var(--font-display);
    font-size: 13px;
  }
</style>
