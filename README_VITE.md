# Vite Build Setup - Quick Start

This project has been configured to use Vite for building with content-hashed assets.

## Render Static Site Settings

Update your Render Static Site configuration:

**Build Command:**
```
npm ci && npm run build
```

**Publish Directory:**
```
dist
```

**⚠️ IMPORTANT:** Make sure the publish directory is `dist` (not `.dist` with a leading dot). The build outputs to `dist/` directory.

## What Changed

1. Added `package.json` with Vite dependencies
2. Added `vite.config.js` with proper configuration for static hosting
3. Assets are now content-hashed (e.g., `main-abc123.js`, `main-xyz789.css`)
4. Build output goes to `dist/` directory

## Asset Hashing

All JavaScript and CSS files referenced in HTML are automatically hashed:
- `assets/js/*.js` → `assets/js/[name]-[hash].js`
- `assets/css/*.css` → `assets/css/[name]-[hash].css`

This enables long-term caching (1 year) with automatic cache invalidation when content changes.

## Render Cache Headers

After deploying, configure Render to set cache headers for hashed assets:

**Path:** `/assets/**`
**Header:** `Cache-Control: public, max-age=31536000, immutable`

This tells browsers to cache hashed assets for 1 year. Since the hash changes when content changes, cache invalidation is automatic.

## Local Testing

```bash
# Install dependencies
npm install

# Build for production
npm run build

# Preview the build
npm run preview
```

Check `dist/` directory to verify assets are hashed:
- `dist/assets/js/main-[hash].js`
- `dist/assets/css/main-[hash].css`

## Notes

- Base path is `./` (relative) for compatibility with Render static hosting
- All HTML files are entry points and will be processed
- Static assets in `public/` are copied as-is (not hashed)
- Source assets in `assets/` are processed and hashed

