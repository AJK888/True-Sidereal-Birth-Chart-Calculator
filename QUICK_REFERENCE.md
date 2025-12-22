# Quick Reference Guide

Quick reference for common tasks and information.

---

## Development Commands

```bash
# Development server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint

# Format code
npm run format

# Analyze bundle
npm run analyze

# Check bundle size
npm run bundle-size
```

---

## File Structure

```
True-Sidereal-Birth-Chart-Calculator/
├── assets/
│   ├── css/
│   │   ├── custom.css          # Custom styles
│   │   ├── design-tokens.css   # Design system
│   │   └── main.css            # Theme styles
│   └── js/
│       ├── calculator.js       # Main calculator logic
│       ├── api-client.js       # API communication
│       ├── state-manager.js    # State management
│       ├── form-validator.js   # Form validation
│       └── ...                 # Other modules
├── public/                     # Static assets (copied to dist/)
│   ├── sw.js                   # Service worker
│   └── manifest.json           # PWA manifest
├── dist/                       # Production build output
├── index.html                  # Main page
└── vite.config.js              # Build configuration
```

---

## Key Modules

### API Client (`api-client.js`)
```javascript
// Calculate chart
await apiClient.calculateChart(data);

// Generate reading
await apiClient.generateReading(chartHash, email);

// Get reading
await apiClient.getReading(readingId);
```

### State Manager (`state-manager.js`)
```javascript
// Get state
const state = stateManager.getState();

// Set state
stateManager.setState('key', value);

// Subscribe to changes
stateManager.subscribe('key', (value) => {
  // Handle change
});
```

### Form Validator (`form-validator.js`)
```javascript
// Validate field
const isValid = formValidator.validateField(field);

// Validate form
const isValid = formValidator.validateForm(form);

// Show error
formValidator.showFieldError(field, message);
```

---

## Design Tokens

### Colors
```css
var(--color-primary)           /* Primary purple */
var(--color-secondary)         /* Secondary blue */
var(--color-success)           /* Success green */
var(--color-error)             /* Error red */
var(--color-text)              /* Text color */
var(--color-text-inverse)      /* Inverse text */
```

### Spacing
```css
var(--spacing-xs)    /* 0.25rem */
var(--spacing-sm)    /* 0.5rem */
var(--spacing-md)    /* 1rem */
var(--spacing-lg)    /* 1.5rem */
var(--spacing-xl)    /* 2rem */
var(--spacing-2xl)   /* 3rem */
var(--spacing-3xl)   /* 4rem */
```

### Typography
```css
var(--font-size-xs)   /* 0.75rem */
var(--font-size-sm)   /* 0.875rem */
var(--font-size-base) /* 1rem */
var(--font-size-lg)   /* 1.125rem */
var(--font-size-xl)   /* 1.25rem */
```

---

## Testing Utilities

### Browser Console
```javascript
// Run all tests
runTests()

// Individual tests
testHelpers.runAccessibilityAudit()
testHelpers.testFormValidation()
testHelpers.getPerformanceMetrics()
testHelpers.validateDesignTokens()
```

---

## Common Tasks

### Add New Module
1. Create file in `assets/js/`
2. Add JSDoc documentation
3. Include in `index.html`
4. Copy to `public/assets/js/` for production

### Update Design Token
1. Edit `assets/css/design-tokens.css`
2. Use in `assets/css/custom.css`
3. Copy both to `public/` for production

### Add New API Endpoint
1. Add method to `api-client.js`
2. Use in `calculator.js` or other modules
3. Handle errors appropriately

### Debug Performance
1. Open Chrome DevTools
2. Run Lighthouse audit
3. Check Performance tab
4. Review bundle with `npm run analyze`

---

## Troubleshooting

### Build Fails
- Check for syntax errors
- Run `npm run lint`
- Verify all imports correct
- Check file paths

### Assets Not Loading
- Verify files in `public/` folder
- Check Vite config `publicDir`
- Clear browser cache
- Check network tab

### Service Worker Not Working
- Check HTTPS (required)
- Verify `sw.js` exists
- Check browser console
- Clear service worker cache

### Performance Issues
- Run `npm run analyze`
- Check bundle sizes
- Verify lazy loading
- Review Lighthouse report

---

## Important URLs

- **Production Site:** `https://synthesisastrology.com`
- **API Endpoint:** `https://true-sidereal-api.onrender.com`
- **Render Dashboard:** Check Render for service status

---

## Documentation Files

- `DEVELOPER_GUIDE.md` - Complete development guide
- `BUILD_OPTIMIZATION.md` - Build and performance guide
- `PWA_FEATURES.md` - PWA features documentation
- `DEPLOYMENT_CHECKLIST.md` - Deployment guide
- `PERFORMANCE_BUDGET.md` - Performance targets
- `CHANGELOG.md` - Version history
- `IMPROVEMENTS_SUMMARY.md` - Summary of improvements

---

**Last Updated:** 2025-01-21

