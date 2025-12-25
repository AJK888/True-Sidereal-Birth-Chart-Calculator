# Build Optimization Guide

## Overview

This guide covers build optimizations, performance improvements, and deployment best practices for the Synthesis Astrology frontend.

---

## Vite Build Configuration

### Code Splitting

The build is configured with intelligent code splitting:

```javascript
// vite.config.js
manualChunks: (id) => {
  // Vendor libraries (jQuery, etc.)
  if (id.includes('node_modules')) {
    if (id.includes('jquery')) {
      return 'vendor-jquery';
    }
    return 'vendor';
  }
  // Large modules
  if (id.includes('calculator.js')) {
    return 'calculator';
  }
  if (id.includes('chart') || id.includes('wheel')) {
    return 'chart-rendering';
  }
}
```

**Benefits:**
- Vendor code cached separately (changes less frequently)
- Calculator logic isolated
- Chart rendering code separate
- Faster initial page load

### Content Hashing

All assets are content-hashed for optimal caching:

- `assets/js/[name]-[hash].js` - JavaScript files
- `assets/css/[name]-[hash].css` - CSS files
- `images/[name]-[hash].[ext]` - Images

**Cache Strategy:**
- Hashed assets: Cache for 1 year (`max-age=31536000, immutable`)
- HTML files: Cache for shorter period or no-cache

---

## Performance Optimizations

### 1. Lazy Loading

**Transit Chart:**
- Uses IntersectionObserver
- Loads when section becomes visible
- Reduces initial page load time

**Implementation:**
```javascript
// Automatically lazy loads transit chart
const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting) {
    loadTransitChart();
  }
}, { rootMargin: '100px' });
```

### 2. Script Loading

**Critical Scripts (Load Immediately):**
- jQuery (required for theme)
- Main.js (theme initialization)
- Utils.js (utilities)
- State manager, API client, form validator
- Calculator.js (core functionality)

**Deferred Scripts (Load After Page):**
- jQuery plugins (scrolly, scrollex)
- Browser detection
- Breakpoints
- Click tracker

### 3. CSS Optimization

**Design Tokens:**
- Single source of truth
- Reduced CSS duplication
- Easier to maintain
- Smaller final bundle

**Critical CSS:**
- Inline critical styles in `<head>`
- Load non-critical CSS asynchronously (future enhancement)

---

## Bundle Size Optimization

### Current Strategy

1. **Code Splitting**: Separate vendor, calculator, chart code
2. **Tree Shaking**: Vite automatically removes unused code
3. **Minification**: Automatic in production build
4. **Gzip Compression**: Enable on server (Render)

### Monitoring Bundle Size

```bash
# Analyze bundle
npm run analyze

# Check dist folder size
du -sh dist/
```

### Target Sizes

- **Initial JS**: < 200KB (gzipped)
- **Total JS**: < 500KB (gzipped)
- **CSS**: < 100KB (gzipped)
- **Images**: Optimized, < 500KB total

---

## Image Optimization

### Current Images

- `star-background.jpg` - Used as favicon
- Chart SVGs - Generated dynamically

### Optimization Recommendations

1. **Compress Images:**
   ```bash
   # Use tools like imagemin, sharp, or online tools
   # Target: < 100KB per image
   ```

2. **Use WebP Format:**
   - Better compression than JPEG
   - Fallback to JPEG for older browsers

3. **Lazy Load Images:**
   ```html
   <img loading="lazy" src="..." alt="...">
   ```

4. **Responsive Images:**
   ```html
   <img srcset="image-small.jpg 480w, image-large.jpg 1200w"
        sizes="(max-width: 480px) 100vw, 1200px"
        src="image-large.jpg" alt="...">
   ```

---

## Caching Strategy

### Render Static Site Headers

Configure in Render dashboard:

**For Hashed Assets (`/assets/**`):**
```
Cache-Control: public, max-age=31536000, immutable
```

**For HTML Files:**
```
Cache-Control: public, max-age=3600, must-revalidate
```

**For Images:**
```
Cache-Control: public, max-age=2592000
```

### Service Worker (Future)

Consider adding a service worker for:
- Offline support
- Advanced caching
- Background sync

---

## Performance Monitoring

### Core Web Vitals

Tracked automatically by `performance-monitor.js`:

- **LCP** (Largest Contentful Paint): Target < 2.5s
- **FID** (First Input Delay): Target < 100ms
- **CLS** (Cumulative Layout Shift): Target < 0.1

### Custom Metrics

Track important operations:

```javascript
const stopTimer = performanceMonitor.startTimer('chart_calculation');
// ... do work ...
stopTimer();
```

### Monitoring Dashboard

Metrics are sent to backend via `apiClient.logClicks()`:
- Can be viewed in backend logs
- Can be integrated with analytics dashboard

---

## Build Commands

### Development

```bash
npm run dev
# Starts Vite dev server with HMR
```

### Production Build

```bash
npm run build
# Creates optimized production build in dist/
```

### Preview Production Build

```bash
npm run preview
# Preview production build locally
```

### Code Quality

```bash
npm run lint
# Lint JavaScript files

npm run format
# Format code with Prettier
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Run `npm run build` successfully
- [ ] Check `dist/` folder contains all files
- [ ] Verify asset paths are correct
- [ ] Test locally with `npm run preview`
- [ ] Run accessibility audit
- [ ] Check console for errors

### Render Configuration

- [ ] Build command: `npm ci && npm run build`
- [ ] Publish directory: `dist`
- [ ] Environment variables set (if needed)
- [ ] Cache headers configured
- [ ] Custom domain configured (if applicable)

### Post-Deployment

- [ ] Verify site loads correctly
- [ ] Check all assets load (no 404s)
- [ ] Test form submission
- [ ] Verify API calls work
- [ ] Check mobile experience
- [ ] Run Lighthouse audit
- [ ] Monitor error logs

---

## Troubleshooting

### Build Fails

**Issue:** Module not found
- **Solution:** Check file paths, ensure all files exist

**Issue:** Syntax errors
- **Solution:** Run `npm run lint` to find issues

### Assets Not Loading

**Issue:** 404 errors for assets
- **Solution:** Check `public/` folder has all files
- **Solution:** Verify Vite config `publicDir` setting

### Performance Issues

**Issue:** Slow page load
- **Solution:** Check bundle size with `npm run analyze`
- **Solution:** Verify lazy loading is working
- **Solution:** Check network tab for large files

### Cache Issues

**Issue:** Changes not appearing
- **Solution:** Clear browser cache
- **Solution:** Check asset hashes changed in `dist/`
- **Solution:** Verify cache headers on server

---

## Best Practices

### 1. Keep Bundle Size Small

- Use code splitting
- Lazy load non-critical code
- Remove unused dependencies
- Optimize images

### 2. Optimize Critical Path

- Load critical CSS inline
- Defer non-critical scripts
- Minimize render-blocking resources

### 3. Monitor Performance

- Track Core Web Vitals
- Monitor bundle size
- Check error rates
- Review user feedback

### 4. Regular Audits

- Run Lighthouse monthly
- Check bundle size after major changes
- Review accessibility
- Test on multiple devices

---

## Future Optimizations

### Short Term

1. **Image Optimization:**
   - Compress existing images
   - Convert to WebP format
   - Add responsive image sizes

2. **CSS Optimization:**
   - Extract critical CSS
   - Remove unused CSS
   - Minify CSS further

3. **Service Worker:**
   - Add basic caching
   - Offline support
   - Background sync

### Long Term

1. **Framework Migration:**
   - Consider React/Vue for better code splitting
   - Component-based architecture
   - Better developer experience

2. **Advanced Caching:**
   - Service worker with cache strategies
   - IndexedDB for data storage
   - Background sync

3. **Performance Budget:**
   - Set performance budgets
   - CI/CD integration
   - Automated performance testing

---

**Last Updated:** 2025-01-21

