import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  base: '/hiking/',

  plugins: [
    svelte(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Hiking',
        short_name: 'Hiking',
        description: 'NH 4000-footers and ADK 46 High Peaks — progress and hike log.',
        theme_color: '#3B5D42',
        background_color: '#F7F6F2',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/hiking/',
        scope: '/hiking/',
        icons: [
          {
            // SVG icon with sizes "any" — no raster PNGs generated yet
            // (tracked in STATUS.md); modern install surfaces accept this.
            src: 'favicon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
          },
        ],
      },
    }),
  ],

  server: {
    port: 5176,
    proxy: {
      // BASE_URL is '/hiking/' even in dev, so api.js calls /hiking/api/*.
      // Strip the mount prefix before forwarding to the backend on 5056.
      '/hiking/api': {
        target: 'http://localhost:5056',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/hiking/, ''),
      },
    },
  },

  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
})
