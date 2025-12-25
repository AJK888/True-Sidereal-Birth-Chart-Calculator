# PWA Features Documentation

## Overview

The Synthesis Astrology website now includes Progressive Web App (PWA) features, allowing users to install the app on their devices and use it offline.

---

## Features Implemented

### 1. Service Worker (`sw.js`)

**Location:** `/sw.js`

**Features:**
- **Offline Support:** Caches critical assets for offline access
- **Cache Strategy:** 
  - Static assets: Cached on install
  - Dynamic content: Network-first with cache fallback
  - API requests: Always use network (not cached)
- **Automatic Updates:** Checks for new versions and updates cache

**Cached Assets:**
- HTML files
- CSS files
- JavaScript modules
- Images
- Fonts

**Cache Names:**
- `synthesis-astrology-v1` - Static assets
- `synthesis-astrology-runtime-v1` - Runtime cached content

### 2. Web App Manifest (`manifest.json`)

**Location:** `/manifest.json`

**Configuration:**
- **App Name:** "Synthesis Astrology"
- **Short Name:** "Synthesis"
- **Display Mode:** Standalone (feels like native app)
- **Theme Color:** `#9f7aea` (purple)
- **Background Color:** `#242943` (dark blue)
- **Icons:** Uses star-background.jpg (192x192 and 512x512)

**Installation:**
- Users can install via browser prompt
- Appears in app drawer/home screen
- Launches in standalone mode (no browser UI)

### 3. Install Prompt Handler (`pwa-install.js`)

**Location:** `assets/js/pwa-install.js`

**Features:**
- Detects when app can be installed
- Shows install button when appropriate
- Handles installation flow
- Tracks installation status

**Usage:**
```javascript
// Check installation status
const status = pwaInstall.getStatus();
console.log(status.isInstalled); // true/false
console.log(status.canInstall); // true/false
```

### 4. Meta Tags

**Added to `index.html`:**
- Theme color
- Apple mobile web app capable
- Apple status bar style
- Manifest link

---

## User Experience

### Installation Flow

1. **User visits website** on mobile or desktop
2. **Browser detects PWA** capabilities
3. **Install prompt appears** (browser-dependent):
   - Chrome/Edge: Address bar install button
   - Safari iOS: Share → Add to Home Screen
   - Firefox: Menu → Install
4. **User installs** app
5. **App launches** in standalone mode

### Offline Experience

1. **First Visit:** Assets cached automatically
2. **Subsequent Visits:** Loads from cache (faster)
3. **Offline Mode:** 
   - Cached pages work offline
   - API calls fail gracefully
   - User sees cached content

### Update Flow

1. **New Version Deployed:** Service worker detects changes
2. **Background Update:** New service worker installs
3. **User Reload:** New version activates
4. **Old Cache Cleared:** Automatically removed

---

## Browser Support

### Full Support
- ✅ Chrome/Edge (Desktop & Mobile)
- ✅ Firefox (Desktop & Mobile)
- ✅ Safari iOS 11.3+ (with limitations)
- ✅ Samsung Internet

### Partial Support
- ⚠️ Safari Desktop (no service worker, but manifest works)

### Limitations
- **Safari iOS:** Limited service worker support
- **Safari Desktop:** No service worker support
- **Install Prompt:** Varies by browser

---

## Development

### Testing Service Worker

1. **Open DevTools** → Application tab
2. **Service Workers:** See registered workers
3. **Cache Storage:** View cached assets
4. **Offline Mode:** Test offline functionality

### Updating Cache Version

To force cache update:
1. Change `CACHE_NAME` in `sw.js`
2. Deploy new version
3. Users will get new cache on next visit

### Debugging

**Service Worker Logs:**
- Check browser console for `[SW]` prefixed messages
- Use DevTools → Application → Service Workers

**Common Issues:**
- **SW not registering:** Check HTTPS requirement
- **Cache not updating:** Clear cache manually
- **Offline not working:** Check cached assets list

---

## Configuration

### Customizing Cached Assets

Edit `PRECACHE_ASSETS` in `sw.js`:

```javascript
const PRECACHE_ASSETS = [
	'/',
	'/index.html',
	// Add more assets here
];
```

### Customizing Manifest

Edit `manifest.json`:
- Change app name, colors, icons
- Adjust display mode
- Update start URL

### Customizing Install Button

Edit CSS in `custom.css`:
- `.pwa-install-button` styles
- Position, colors, size

---

## Best Practices

### 1. Cache Strategy
- ✅ Cache static assets aggressively
- ✅ Always use network for API calls
- ✅ Provide offline fallback pages

### 2. Update Strategy
- ✅ Version cache names
- ✅ Clean up old caches
- ✅ Notify users of updates (optional)

### 3. Performance
- ✅ Precache critical assets
- ✅ Lazy load non-critical content
- ✅ Optimize cached assets

### 4. User Experience
- ✅ Show install prompt at right time
- ✅ Handle offline gracefully
- ✅ Provide update notifications

---

## Future Enhancements

### Planned
- [ ] Background sync for form submissions
- [ ] Push notifications
- [ ] Advanced caching strategies
- [ ] Offline form queue
- [ ] Update notifications

### Under Consideration
- [ ] IndexedDB for data storage
- [ ] Advanced offline features
- [ ] Background data sync
- [ ] Install analytics

---

## Troubleshooting

### Service Worker Not Registering

**Check:**
1. HTTPS required (or localhost)
2. File exists at `/sw.js`
3. No JavaScript errors
4. Browser supports service workers

### Cache Not Updating

**Solution:**
1. Change `CACHE_NAME` version
2. Clear browser cache
3. Hard reload page

### Install Prompt Not Showing

**Reasons:**
1. Already installed
2. Browser doesn't support
3. Manifest invalid
4. Not served over HTTPS

### Offline Not Working

**Check:**
1. Assets in `PRECACHE_ASSETS`
2. Service worker active
3. Cache populated
4. Network tab in DevTools

---

**Last Updated:** 2025-01-21

