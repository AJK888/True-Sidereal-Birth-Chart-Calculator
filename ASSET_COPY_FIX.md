# Asset Copy Fix

## Issue
JavaScript and CSS files were returning 404 errors because Vite wasn't copying them to the build output.

## Solution
Legacy JavaScript and CSS files have been copied to `public/assets/` directory so Vite will copy them as static assets during build.

## Files Copied
- `assets/js/*` → `public/assets/js/*` (all JavaScript files)
- `assets/css/*` → `public/assets/css/*` (all CSS files)  
- `assets/webfonts/*` → `public/assets/webfonts/*` (all font files)

## How It Works
1. Files in `public/` are copied to `dist/` as-is during build
2. HTML files reference `assets/js/...` which maps to `dist/assets/js/...` after build
3. These files are served as static assets (not processed/bundled)

## MIME Type Issue
If you still see MIME type errors (`text/plain` instead of `application/javascript`), this is a server configuration issue. Render should serve `.js` files with the correct content-type, but you may need to configure it in Render's settings.

## Verification
After rebuilding, check that:
- `dist/assets/js/` contains all JavaScript files
- `dist/assets/css/` contains all CSS files
- Files are accessible at the correct paths

