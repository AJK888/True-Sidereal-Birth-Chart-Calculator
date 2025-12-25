# Synthesis Astrology - Frontend Calculator

Frontend application for the Synthesis Astrology birth chart calculator. Built with Vite and based on the HTML5 UP "Forty" theme.

## 🚀 Quick Start

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Important: Syncing Assets

**CRITICAL:** After editing files in `assets/`, you MUST sync them to `public/`:

```powershell
.\sync-assets-to-public.ps1
```

Or manually:
```powershell
Copy-Item -Path "assets\js\main.js" -Destination "public\assets\js\main.js" -Force
Copy-Item -Path "assets\css\custom.css" -Destination "public\assets\css\custom.css" -Force
Copy-Item -Path "assets\css\main.css" -Destination "public\assets\css\main.css" -Force
```

**Why?** The build process copies `public/` → `dist/`, not `assets/`. See `BUILD_PROCESS.md` for details.

## 📁 Directory Structure

```
True-Sidereal-Birth-Chart-Calculator/
├── assets/              # SOURCE FILES (edit here)
│   ├── js/             # JavaScript source
│   │   ├── main.js     # Menu functionality
│   │   ├── calculator.js # Chart calculation
│   │   └── ...
│   ├── css/            # CSS source
│   │   ├── main.css    # Base theme
│   │   └── custom.css  # Custom styles
│   └── sass/           # SCSS source files
│
├── public/              # STATIC FILES (copied to dist/)
│   └── assets/         # Must match assets/ structure
│
├── index.html          # Main page
├── full-reading.html   # Full reading page
├── synastry.html       # Synastry analysis page
├── examples/           # Example readings
│
├── package.json        # Dependencies
├── vite.config.js      # Build configuration
└── sync-assets-to-public.ps1 # Sync script
```

## 🏗️ Build Process

### How It Works

1. **Edit source files** in `assets/` directory
2. **Sync to public** using `sync-assets-to-public.ps1`
3. **Build** with `npm run build`
4. **Output** goes to `dist/` directory

### Vite Configuration

- **Public Directory:** `public/` (copied as-is to `dist/`)
- **Assets Directory:** `assets/` (processed if ES modules)
- **Legacy Scripts:** Must be in `public/assets/` (not bundled)

See `BUILD_PROCESS.md` for complete details.

## 🎨 Key Features

### Menu System

- **Location:** `assets/js/main.js`
- **Features:**
  - Single consolidated handler (no duplicates)
  - Hamburger icon styling
  - Mobile-friendly touch targets
  - Proper z-index management (99999)

### Chart Visualization

- SVG-based chart wheels
- Sidereal and Tropical systems
- Transit charts
- Responsive design

### API Integration

- Centralized API client (`api-client.js`)
- State management (`state-manager.js`)
- Error handling (`error-tracker.js`)
- Performance monitoring (`performance-monitor.js`)

## 📚 Documentation

- **`BUILD_PROCESS.md`** - Build system explanation
- **`ASSETS_VS_PUBLIC.md`** - Understanding the two directories
- **`../README.md`** - Main project README
- **`../AI_CONTEXT.md`** - Context for AI editors

## 🔧 Development Workflow

1. **Make changes** in `assets/` directory
2. **Sync to public** with `sync-assets-to-public.ps1`
3. **Test locally** with `npm run dev`
4. **Build** with `npm run build`
5. **Commit and push**

## ⚠️ Common Issues

### Changes Not Appearing

**Problem:** Edited `assets/` but changes don't show in build

**Solution:** Run `sync-assets-to-public.ps1` to copy files to `public/`

### Menu Not Working

**Problem:** Menu button doesn't open menu

**Check:**
- Are both `assets/js/main.js` and `public/assets/js/main.js` updated?
- Check browser console for errors
- Verify z-index is 99999

## 📦 Dependencies

- **Vite** - Build tool
- **jQuery** - Theme functionality (legacy)
- **Font Awesome** - Icons

See `package.json` for complete list.

## 🚢 Deployment

The frontend is deployed as a static site on Render.com:
- **Build Command:** `npm ci && npm run build`
- **Publish Directory:** `dist/`

---

**For backend documentation, see:** `../README.md`
