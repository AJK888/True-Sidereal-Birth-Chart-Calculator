# Vite Build Setup for Render Static Site

This project uses Vite to build the frontend with content-hashed assets for optimal caching.

## Render Static Site Configuration

Update your Render Static Site settings:

### Build Command
```
npm ci && npm run build
```

### Publish Directory
```
dist
```

## Local Development

### Install Dependencies
```bash
npm install
```

### Development Server
```bash
npm run dev
```
Starts Vite dev server at `http://localhost:5173`

### Build for Production
```bash
npm run build
```
Outputs to `dist/` directory with content-hashed assets.

### Preview Production Build
```bash
npm run preview
```
Preview the production build locally.

## Asset Hashing

All JavaScript and CSS files are automatically content-hashed during build:
- `assets/js/*.js` → `assets/js/[name]-[hash].js`
- `assets/css/*.css` → `assets/css/[name]-[hash].css`

This enables long-term caching with cache invalidation on content changes.

## Render Headers Configuration

After deploying with Vite, configure Render to set cache headers:

For `/assets/**` paths:
```
Cache-Control: public, max-age=31536000, immutable
```

This tells browsers to cache hashed assets for 1 year, since the hash changes when content changes.

## Project Structure

```
True-Sidereal-Birth-Chart-Calculator/
├── index.html              # Main entry point
├── full-reading.html       # Full reading page
├── examples/               # Example pages
├── assets/                 # Source assets (JS, CSS, fonts)
│   ├── js/
│   ├── css/
│   └── webfonts/
├── public/                 # Static assets (copied as-is)
│   └── images/
├── dist/                   # Build output (generated)
├── vite.config.js          # Vite configuration
└── package.json            # Dependencies and scripts
```

## Initial Setup

Before first build, ensure the image is in the correct location:

```bash
# Copy the star background image to public directory
mkdir -p public/images
cp assets/images/star-background.jpg public/images/star-background.jpg
```

Or on Windows PowerShell:
```powershell
New-Item -ItemType Directory -Path "public\images" -Force
Copy-Item "assets\images\star-background.jpg" -Destination "public\images\star-background.jpg"
```

## Notes

- Base path is set to `./` for relative asset paths
- All HTML files are processed as entry points
- Static assets in `public/` are copied to `dist/` without processing
- Source assets in `assets/` are processed, bundled, and hashed
- Images referenced as `images/` in HTML should be in `public/images/`

