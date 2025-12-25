# Assets vs Public Directory - Build Process Explanation

## How Vite Build Works

### Directory Structure:
- **`assets/`** - Source files (used during development, may be processed by Vite)
- **`public/`** - Static files copied AS-IS to `dist/` during build (NOT processed)

### Build Process:
1. **Vite processes HTML files** in the root directory (`index.html`, `full-reading.html`, etc.)
2. **Files in `public/`** are copied directly to `dist/` without any processing
3. **Files referenced in HTML** from `assets/` may be processed/bundled IF they're ES modules
4. **Legacy scripts** (jQuery, non-module JS) in `public/assets/` are copied as-is

### Important:
- **`public/assets/js/main.js`** is what gets deployed (copied to `dist/assets/js/main.js`)
- **`assets/js/main.js`** is NOT used unless referenced as a module in HTML
- Since `main.js` is a legacy script (not ES module), it MUST be in `public/assets/js/`

## Source of Truth

**For menu-related files:**
- **Source of Truth:** `assets/js/main.js` and `assets/css/custom.css`
- **Deployment Files:** `public/assets/js/main.js` and `public/assets/css/custom.css`
- **Action Required:** Always copy from `assets/` to `public/` after making changes

## Files That Need Syncing

These files must be kept in sync between `assets/` and `public/`:
- `assets/js/main.js` → `public/assets/js/main.js`
- `assets/css/custom.css` → `public/assets/css/custom.css`
- `assets/css/main.css` → `public/assets/css/main.css`

## Sync Script

After making changes to menu files, run:
```powershell
Copy-Item -Path "assets\js\main.js" -Destination "public\assets\js\main.js" -Force
Copy-Item -Path "assets\css\custom.css" -Destination "public\assets\css\custom.css" -Force
Copy-Item -Path "assets\css\main.css" -Destination "public\assets\css\main.css" -Force
```

## Why This Matters

The build process (`npm run build`) uses Vite which:
- Copies `public/` contents to `dist/` as static assets
- Processes ES modules from `assets/` if referenced in HTML
- Legacy scripts (like jQuery-based `main.js`) are NOT processed, so they must be in `public/`

**Result:** Changes to `assets/js/main.js` won't appear in production unless copied to `public/assets/js/main.js`

