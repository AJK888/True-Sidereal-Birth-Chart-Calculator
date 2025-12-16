import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // Enable content hashing for cache busting
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        'full-reading': resolve(__dirname, 'full-reading.html'),
        'examples/index': resolve(__dirname, 'examples/index.html'),
        'examples/elon-musk': resolve(__dirname, 'examples/elon-musk.html'),
        'examples/barack-obama': resolve(__dirname, 'examples/barack-obama.html'),
      },
      output: {
        // Ensure content hashing for all assets
        entryFileNames: 'assets/js/[name]-[hash].js',
        chunkFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.');
          const ext = info[info.length - 1];
          // Images go to images/ directory
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext)) {
            return 'images/[name]-[hash].[ext]';
          }
          // Fonts go to assets/webfonts/
          if (/woff2?|eot|ttf|otf/i.test(ext)) {
            return 'assets/webfonts/[name]-[hash].[ext]';
          }
          // CSS goes to assets/css/
          if (ext === 'css') {
            return 'assets/css/[name]-[hash].[ext]';
          }
          // Other assets go to assets/
          return 'assets/[name]-[hash].[ext]';
        },
      },
    },
    // Generate manifest for asset mapping (optional, for advanced use cases)
    manifest: false,
    // Copy legacy scripts as-is (they're not ES modules)
    copyPublicDir: true,
  },
  publicDir: 'public',
  // Legacy scripts should be copied, not bundled
  // Vite will copy them from public/ or keep them as external references
});

