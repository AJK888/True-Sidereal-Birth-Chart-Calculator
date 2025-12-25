# Deployment Instructions

## Quick Deployment Guide

Since Render automatically builds and deploys from your repository, deployment is straightforward.

---

## Automatic Deployment (Recommended)

### Step 1: Verify Files Are Ready

All necessary files are in place:
- ✅ `package.json` - Dependencies and build scripts
- ✅ `vite.config.js` - Build configuration
- ✅ `public/` folder - Static assets (service worker, manifest)
- ✅ `index.html` - Main page with all scripts
- ✅ All JavaScript modules in `assets/js/`
- ✅ All CSS files in `assets/css/`

### Step 2: Commit and Push to Repository

```bash
# Add all changes
git add .

# Commit with descriptive message
git commit -m "Frontend v2.0.0: Complete rebuild with modern architecture, PWA, and performance optimizations"

# Push to main branch (or your deployment branch)
git push origin main
```

### Step 3: Render Auto-Deploys

Render will automatically:
1. Detect the push
2. Run `npm ci` to install dependencies
3. Run `npm run build` to build the production version
4. Deploy from the `dist/` folder
5. Make the site live

---

## Render Configuration

### Verify Render Settings

In your Render dashboard, ensure:

**Build Command:**
```
npm ci && npm run build
```

**Publish Directory:**
```
dist
```

**Environment:**
- Node.js version: 18+ (or latest LTS)
- Build environment: Standard

**Custom Headers (Optional but Recommended):**
```
/assets/**/*.js
  Cache-Control: public, max-age=31536000, immutable

/assets/**/*.css
  Cache-Control: public, max-age=31536000, immutable

/images/**
  Cache-Control: public, max-age=2592000

/*.html
  Cache-Control: public, max-age=3600, must-revalidate
```

---

## Manual Build (If Needed)

If you need to build locally before pushing:

### Prerequisites
- Node.js 18+ installed
- npm installed

### Build Steps

```bash
# Navigate to project directory
cd "True-Sidereal-Birth-Chart-Calculator"

# Install dependencies
npm ci

# Run linting (optional)
npm run lint

# Format code (optional)
npm run format

# Build production version
npm run build

# Preview build locally (optional)
npm run preview
```

### Verify Build Output

After building, check:
- [ ] `dist/` folder exists
- [ ] `dist/index.html` exists
- [ ] `dist/assets/` folder with JS and CSS
- [ ] `dist/sw.js` exists (service worker)
- [ ] `dist/manifest.json` exists
- [ ] All assets are hashed correctly

---

## Post-Deployment Verification

After Render deploys, verify:

### 1. Site Loads
- [ ] Visit `https://synthesisastrology.com`
- [ ] Page loads without errors
- [ ] No console errors

### 2. Assets Load
- [ ] All CSS loads
- [ ] All JavaScript loads
- [ ] Images load
- [ ] Fonts load

### 3. Functionality
- [ ] Form submission works
- [ ] Chart calculation works
- [ ] API calls succeed
- [ ] Authentication works

### 4. PWA Features
- [ ] Service worker registers (check DevTools → Application)
- [ ] Manifest loads (`/manifest.json`)
- [ ] Install prompt appears (if supported)

### 5. Performance
- [ ] Run Lighthouse audit
- [ ] Check Core Web Vitals
- [ ] Verify bundle sizes

---

## Troubleshooting

### Build Fails on Render

**Check:**
1. Node.js version in Render settings
2. Build command is correct
3. `package.json` has all dependencies
4. No syntax errors in code

**Solution:**
- Check Render build logs
- Verify `package.json` is correct
- Ensure all files are committed

### Assets Not Loading

**Check:**
1. Publish directory is `dist`
2. Assets are in `dist/assets/`
3. File paths are correct

**Solution:**
- Verify `vite.config.js` configuration
- Check `public/` folder contents
- Review build logs

### Service Worker Not Working

**Check:**
1. Site is served over HTTPS
2. `sw.js` is in root of `dist/`
3. Service worker registration code in HTML

**Solution:**
- Verify HTTPS is enabled
- Check `sw.js` exists in `dist/`
- Review service worker registration

---

## Rollback Plan

If deployment has issues:

### Option 1: Revert Git Commit
```bash
# Revert last commit
git revert HEAD

# Push revert
git push origin main
```

### Option 2: Redeploy Previous Version
- In Render dashboard, find previous successful deployment
- Click "Redeploy" on that deployment

---

## Monitoring

After deployment, monitor:

1. **Error Logs** - Check Render logs for errors
2. **Performance** - Monitor Core Web Vitals
3. **User Feedback** - Watch for user reports
4. **Analytics** - Review traffic and behavior

---

## Success Criteria

Deployment is successful when:
- ✅ Site loads without errors
- ✅ All features work correctly
- ✅ Performance metrics meet targets
- ✅ No critical errors in logs
- ✅ Service worker registers
- ✅ PWA features work

---

**Ready to Deploy:** All files are in place and ready for deployment. Simply commit and push to trigger automatic deployment on Render.

