# Performance Budget

Performance targets and monitoring guidelines for the Synthesis Astrology frontend.

---

## Core Web Vitals Targets

### Largest Contentful Paint (LCP)
- **Target:** < 2.5 seconds
- **Good:** < 2.5s
- **Needs Improvement:** 2.5s - 4.0s
- **Poor:** > 4.0s

**How to Measure:**
- Chrome DevTools → Lighthouse
- Chrome User Experience Report
- Performance Monitor (built-in)

**Optimization:**
- Optimize images
- Preload critical resources
- Reduce server response time
- Eliminate render-blocking resources

---

### First Input Delay (FID)
- **Target:** < 100 milliseconds
- **Good:** < 100ms
- **Needs Improvement:** 100ms - 300ms
- **Poor:** > 300ms

**How to Measure:**
- Chrome DevTools → Performance
- Real User Monitoring
- Performance Monitor (built-in)

**Optimization:**
- Reduce JavaScript execution time
- Code splitting
- Lazy load non-critical scripts
- Optimize third-party scripts

---

### Cumulative Layout Shift (CLS)
- **Target:** < 0.1
- **Good:** < 0.1
- **Needs Improvement:** 0.1 - 0.25
- **Poor:** > 0.25

**How to Measure:**
- Chrome DevTools → Lighthouse
- Chrome User Experience Report
- Performance Monitor (built-in)

**Optimization:**
- Set size attributes on images/videos
- Reserve space for ads/embeds
- Avoid inserting content above existing content
- Prefer transform animations

---

## Load Time Targets

### Time to Interactive (TTI)
- **Target:** < 3.5 seconds
- **Current:** ~5s (needs improvement)

**Optimization:**
- Code splitting
- Lazy loading
- Reduce JavaScript bundle size
- Optimize critical rendering path

---

### First Contentful Paint (FCP)
- **Target:** < 1.8 seconds
- **Good:** < 1.8s
- **Needs Improvement:** 1.8s - 3.0s
- **Poor:** > 3.0s

**Optimization:**
- Minimize render-blocking resources
- Optimize CSS delivery
- Preload critical resources
- Reduce server response time

---

## Bundle Size Targets

### JavaScript
- **Initial Bundle:** < 200KB (gzipped)
- **Total JavaScript:** < 500KB (gzipped)
- **Vendor Chunk:** < 150KB (gzipped)
- **Calculator Chunk:** < 100KB (gzipped)
- **Chart Rendering:** < 50KB (gzipped)

**How to Measure:**
```bash
npm run analyze
npm run bundle-size
```

**Optimization:**
- Code splitting
- Tree shaking
- Remove unused dependencies
- Lazy load non-critical code

---

### CSS
- **Total CSS:** < 100KB (gzipped)
- **Critical CSS:** < 20KB (inline)

**Optimization:**
- Remove unused CSS
- Minify CSS
- Use design tokens (reduce duplication)
- Critical CSS inline

---

### Images
- **Total Images:** < 500KB
- **Per Image:** < 100KB
- **Format:** WebP with JPEG fallback

**Optimization:**
- Compress images
- Use WebP format
- Lazy load images
- Responsive images (srcset)

---

## Network Targets

### Total Page Weight
- **Target:** < 1MB (first load)
- **Subsequent Loads:** < 500KB (cached)

**Breakdown:**
- HTML: < 50KB
- CSS: < 100KB
- JavaScript: < 500KB
- Images: < 500KB
- Fonts: < 100KB

---

### API Response Times
- **Chart Calculation:** < 1 second
- **Reading Generation:** < 15 seconds (background)
- **Famous People:** < 2 seconds
- **Authentication:** < 500ms

**Monitoring:**
- Backend logs
- Performance Monitor (custom metrics)
- Error Tracker (API errors)

---

## Lighthouse Score Targets

### Overall Score
- **Target:** > 90
- **Current:** ~65 (needs improvement)

### Category Targets
- **Performance:** > 90
- **Accessibility:** > 95
- **Best Practices:** > 90
- **SEO:** > 90

**How to Measure:**
- Chrome DevTools → Lighthouse
- PageSpeed Insights
- CI/CD integration (future)

---

## Monitoring

### Automatic Monitoring
- **Performance Monitor:** Tracks Core Web Vitals
- **Error Tracker:** Captures errors and performance issues
- **Click Tracker:** Tracks user interactions

### Manual Monitoring
- **Weekly Lighthouse Audits**
- **Monthly Performance Review**
- **Quarterly Bundle Size Review**

### Tools
- Chrome DevTools
- Lighthouse
- PageSpeed Insights
- Bundle Analyzer (`npm run analyze`)

---

## Performance Budget Enforcement

### Pre-Deployment Checks
- [ ] Lighthouse score > 90
- [ ] Bundle size within targets
- [ ] Core Web Vitals meet targets
- [ ] No performance regressions

### CI/CD Integration (Future)
- Automated Lighthouse checks
- Bundle size warnings
- Performance regression detection
- Automated performance budgets

---

## Optimization Roadmap

### Completed
- ✅ Code splitting
- ✅ Lazy loading (transit chart)
- ✅ Service worker caching
- ✅ Performance monitoring
- ✅ Design tokens (CSS optimization)

### In Progress
- ⏳ Image optimization
- ⏳ Critical CSS extraction
- ⏳ Bundle size reduction

### Planned
- [ ] Advanced caching strategies
- [ ] Resource hints (preload, prefetch)
- [ ] HTTP/2 server push
- [ ] CDN integration
- [ ] Advanced image optimization

---

## Performance Budget Violations

### When Targets Are Missed

1. **Investigate:**
   - Run bundle analyzer
   - Check Lighthouse report
   - Review recent changes

2. **Optimize:**
   - Reduce bundle size
   - Optimize images
   - Lazy load more content
   - Code splitting improvements

3. **Monitor:**
   - Track improvements
   - Verify targets met
   - Document changes

---

## Best Practices

### Development
- Monitor bundle size during development
- Use performance budgets in CI/CD
- Regular performance audits
- Optimize before merging

### Production
- Monitor Core Web Vitals
- Track bundle sizes
- Review performance trends
- Optimize based on real user data

---

**Last Updated:** 2025-01-21

