<script>
  import ListView from './routes/ListView.svelte'
  import DetailView from './routes/DetailView.svelte'

  // No tab bar — just two views. `range` persists across a detail visit so
  // returning to the list keeps the NH/ADK toggle where you left it.
  let view = $state('list') // 'list' | 'detail'
  let range = $state('NH') // 'NH' | 'ADK'
  let selectedPeakId = $state(null)

  function openPeak(id) {
    selectedPeakId = id
    view = 'detail'
  }

  function backToList() {
    view = 'list'
    selectedPeakId = null
  }
</script>

<div class="app-shell">
  <main class="route-content">
    {#if view === 'list'}
      <ListView bind:range onSelectPeak={openPeak} />
    {:else if view === 'detail'}
      <DetailView peakId={selectedPeakId} onBack={backToList} />
    {/if}
  </main>
</div>

<style>
  .app-shell {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
  }

  .route-content {
    flex: 1 1 auto;
    overflow-y: auto;
    padding-bottom: calc(var(--safe-area-bottom) + var(--space-6));
  }
</style>
