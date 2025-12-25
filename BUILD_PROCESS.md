# Build Process - Assets vs Public Directory

## Summary

**CRITICAL:** The build process uses files from the `public/` directory, NOT `assets/`.

## How Vite Build Works

1. **Vite Configuration** (`vite.config.js`):
   - `publicDir: 'public'` - Files in `public/` are copied AS-IS to `dist/`
   - Files in `assets/` are only processed if they're ES modules referenced in HTML

2. **HTML Files Reference:**
   - `index.html` references: `assets/js/main.js` and `assets/css/custom.css`
   - But since these are legacy scripts (not ES modules), Vite can't bundle them
   - **Solution:** They must exist in `public/assets/` to be copied to `dist/assets/`

3. **Build Output:**
   - `public/assets/js/main.js` → `dist/assets/js/main.js` (copied as-is)
   - `public/assets/css/custom.css` → `dist/assets/css/custom.css` (copied as-is)

## Workflow

### When Making Changes to Menu Files:

1. **Edit source files** in `assets/`:
   - `assets/js/main.js`
   - `assets/css/custom.css`
   - `assets/css/main.css`

2. **Sync to public directory:**
   ```powershell
   .\sync-assets-to-public.ps1
   ```
   Or manually:
   ```powershell
   Copy-Item -Path "assets\js\main.js" -Destination "public\assets\js\main.js" -Force
   Copy-Item -Path "assets\css\custom.css" -Destination "public\assets\css\custom.css" -Force
   Copy-Item -Path "assets\css\main.css" -Destination "public\assets\css\main.css" -Force
   ```

3. **Commit and push:**
   ```powershell
   git add assets/ public/
   git commit -m "Update menu functionality"
   git push
   ```

## Current Status

✅ **Both directories are in sync** (verified via file hashes)
✅ **Menu fixes are in both `assets/` and `public/`**
✅ **Build will use files from `public/`**

## Files That Must Stay in Sync

- `assets/js/main.js` ↔ `public/assets/js/main.js`
- `assets/css/custom.css` ↔ `public/assets/css/custom.css`
- `assets/css/main.css` ↔ `public/assets/css/main.css`

## Why This Matters

If you edit `assets/js/main.js` but don't copy it to `public/assets/js/main.js`, your changes won't appear in production because:
- The build copies `public/` to `dist/`
- HTML references `assets/js/main.js` but Vite can't process it (not a module)
- So it must exist in `public/assets/js/main.js` to be copied correctly

