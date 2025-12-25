import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // Enable content hashing for cache busting
    // Code splitting for better performance
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
        // Code splitting: separate chunks for better caching
        chunkFileNames: 'assets/js/chunks/[name]-[hash].js',
        manualChunks: (id) => {
          // Split vendor libraries into separate chunks
          if (id.includes('node_modules')) {
            if (id.includes('jquery')) {
              return 'vendor-jquery';
            }
            return 'vendor';
          }
          // Split large modules
          if (id.includes('calculator.js')) {
            return 'calculator';
          }
          if (id.includes('chart') || id.includes('wheel')) {
            return 'chart-rendering';
          }
        },
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
  // Legacy scripts and CSS in public/assets/ will be copied as-is to dist/assets/
  // These files are not processed/bundled - they're static assets
});

