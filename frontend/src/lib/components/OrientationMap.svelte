<script>
  // Orientation-only map: "where is this, roughly" — not turn-by-turn (that's
  // the separate maps:// button). Leaflet + OSM tiles, no API key.
  import { onMount, onDestroy } from 'svelte'
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
  import markerIcon from 'leaflet/dist/images/marker-icon.png'
  import markerShadow from 'leaflet/dist/images/marker-shadow.png'

  let { lat, lon, label = '' } = $props()

  let container = $state()
  let map

  // Vite-bundled marker assets don't resolve via Leaflet's default relative
  // paths — point the default icon at the imported URLs directly.
  delete L.Icon.Default.prototype._getIconUrl
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: markerIcon2x,
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
  })

  onMount(() => {
    if (lat == null || lon == null) return
    map = L.map(container, {
      zoomControl: true,
      scrollWheelZoom: false, // avoid trapping page-scroll on mobile
    }).setView([lat, lon], 13)

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 17,
    }).addTo(map)

    L.marker([lat, lon]).addTo(map).bindPopup(label || 'Trailhead')
  })

  onDestroy(() => {
    map?.remove()
  })
</script>

{#if lat == null || lon == null}
  <div class="map-placeholder">No coordinates yet for this trailhead.</div>
{:else}
  <div class="map-container" bind:this={container}></div>
{/if}

<style>
  .map-container {
    width: 100%;
    height: 200px;
    border-radius: var(--radius-lg);
    overflow: hidden;
    border: 1px solid var(--color-border);
  }

  .map-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 120px;
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-lg);
    color: var(--color-muted);
    font-family: var(--font-display);
    font-size: 13px;
  }
</style>
