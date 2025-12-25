# Render MIME Type Configuration

## Issue
JavaScript files are being served with `text/plain` MIME type instead of `application/javascript`, causing browsers to refuse execution.

## Solution

If files are still showing MIME type errors after copying to `public/assets/`, you may need to configure Render to serve JavaScript files with the correct content-type.

### Option 1: Render HTTP Headers (Recommended)

In Render Static Site settings, add HTTP response headers:

**Request Path:** `/assets/js/*.js`
**Header Name:** `Content-Type`
**Header Value:** `application/javascript; charset=utf-8`

**Request Path:** `/assets/css/*.css`
**Header Name:** `Content-Type`
**Header Value:** `text/css; charset=utf-8`

### Option 2: Verify File Structure

After build, verify that files exist in `dist/assets/js/`:
- `dist/assets/js/jquery.min.js`
- `dist/assets/js/calculator.js`
- etc.

If files don't exist, the build isn't copying from `public/` correctly.

### Option 3: Check Build Output

The build should show files being copied. If you see errors about missing files, Vite might not be copying from `public/` directory.

## Current Setup

Files are now in:
- `public/assets/js/*` - Will be copied to `dist/assets/js/*`
- `public/assets/css/*` - Will be copied to `dist/assets/css/*`
- `public/assets/webfonts/*` - Will be copied to `dist/assets/webfonts/*`

These should be served correctly by Render, but if MIME types are wrong, use Option 1 above.

