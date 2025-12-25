# Deployment Checklist

Complete this checklist before deploying to production.

---

## Pre-Deployment

### Code Quality
- [ ] All code passes linting (`npm run lint`)
- [ ] Code formatted with Prettier (`npm run format`)
- [ ] No console errors in browser
- [ ] No TypeScript/JavaScript errors
- [ ] All TODO/FIXME comments addressed or documented

### Build
- [ ] Build succeeds without errors (`npm run build`)
- [ ] All assets generated correctly in `dist/`
- [ ] Bundle size within targets (check with `npm run analyze`)
- [ ] No missing files or broken references
- [ ] Service worker builds correctly
- [ ] Manifest file included

### Testing
- [ ] Test form submission end-to-end
- [ ] Test chart calculation
- [ ] Test reading generation
- [ ] Test authentication (login/register)
- [ ] Test saved charts
- [ ] Test synastry page (if applicable)
- [ ] Test on mobile device
- [ ] Test on desktop browser
- [ ] Test keyboard navigation
- [ ] Test screen reader (basic)

### Performance
- [ ] Lighthouse score > 90
- [ ] Time to Interactive < 3.5s
- [ ] First Contentful Paint < 1.8s
- [ ] Largest Contentful Paint < 2.5s
- [ ] Cumulative Layout Shift < 0.1
- [ ] Bundle size within targets
- [ ] Images optimized
- [ ] Service worker caching working

### Accessibility
- [ ] WCAG 2.1 AA compliance
- [ ] All images have alt text
- [ ] All form inputs have labels
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] Color contrast meets standards
- [ ] Screen reader tested (basic)

### Browser Compatibility
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)
- [ ] Samsung Internet (if applicable)

---

## Deployment Steps

### 1. Build Production Version
```bash
cd "True-Sidereal-Birth-Chart-Calculator"
npm ci
npm run build
```

### 2. Verify Build Output
- [ ] Check `dist/` folder exists
- [ ] Verify all HTML files present
- [ ] Verify all assets copied
- [ ] Check service worker file (`sw.js`)
- [ ] Check manifest file (`manifest.json`)

### 3. Test Production Build Locally
```bash
npm run preview
```
- [ ] Site loads correctly
- [ ] All assets load
- [ ] No 404 errors
- [ ] Service worker registers
- [ ] Form submission works
- [ ] API calls succeed

### 4. Render Configuration
- [ ] Build command: `npm ci && npm run build`
- [ ] Publish directory: `dist`
- [ ] Environment variables set (if needed)
- [ ] Custom domain configured
- [ ] HTTPS enabled
- [ ] Cache headers configured

### 5. Deploy to Render
- [ ] Push to main branch
- [ ] Render auto-deploys
- [ ] Monitor deployment logs
- [ ] Verify deployment succeeds

---

## Post-Deployment

### Immediate Checks
- [ ] Site loads at production URL
- [ ] All pages accessible
- [ ] No console errors
- [ ] Service worker registers
- [ ] API endpoints working
- [ ] Form submission works
- [ ] Authentication works

### Performance Verification
- [ ] Run Lighthouse audit
- [ ] Check Core Web Vitals
- [ ] Verify bundle sizes
- [ ] Check load times
- [ ] Test on slow 3G connection

### Functionality Verification
- [ ] Calculate chart
- [ ] Generate snapshot reading
- [ ] Generate full reading
- [ ] Save chart
- [ ] Load saved chart
- [ ] Chat functionality (if applicable)
- [ ] Synastry page (if applicable)

### Monitoring
- [ ] Error tracking active
- [ ] Performance monitoring active
- [ ] Click tracking working
- [ ] Logs visible in Render
- [ ] No critical errors in logs

### Accessibility Verification
- [ ] Run accessibility audit
- [ ] Test keyboard navigation
- [ ] Test screen reader
- [ ] Check color contrast
- [ ] Verify ARIA labels

---

## Rollback Plan

If issues are detected:

1. **Immediate Rollback:**
   - Revert to previous deployment in Render
   - Or redeploy previous working version

2. **Investigation:**
   - Check error logs
   - Review recent changes
   - Test locally with production build

3. **Fix:**
   - Fix issues in development
   - Test thoroughly
   - Redeploy

---

## Emergency Contacts

- **Backend API:** `https://true-sidereal-api.onrender.com`
- **Frontend Site:** `https://synthesisastrology.com`
- **Render Dashboard:** Check Render dashboard for service status

---

## Post-Deployment Monitoring

### First 24 Hours
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Review user feedback
- [ ] Check server logs
- [ ] Monitor API response times

### First Week
- [ ] Review analytics
- [ ] Check conversion rates
- [ ] Monitor error patterns
- [ ] Review performance trends
- [ ] Collect user feedback

---

## Success Criteria

Deployment is successful if:
- ✅ Site loads without errors
- ✅ All features work correctly
- ✅ Performance targets met
- ✅ No critical bugs reported
- ✅ User experience smooth
- ✅ Monitoring active

---

**Last Updated:** 2025-01-21

