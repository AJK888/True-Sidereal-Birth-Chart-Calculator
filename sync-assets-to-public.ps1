# Sync script to copy menu-related files from assets/ to public/assets/
# This ensures the build process uses the correct files

Write-Host "Syncing menu files from assets/ to public/assets/..." -ForegroundColor Cyan

# Menu-related files that must be synced
$filesToSync = @(
    @{Source = "assets\js\main.js"; Destination = "public\assets\js\main.js"},
    @{Source = "assets\css\custom.css"; Destination = "public\assets\css\custom.css"},
    @{Source = "assets\css\main.css"; Destination = "public\assets\css\main.css"}
)

$syncedCount = 0
$errorCount = 0

foreach ($file in $filesToSync) {
    if (Test-Path $file.Source) {
        $destDir = Split-Path $file.Destination -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -Path $file.Source -Destination $file.Destination -Force
        Write-Host "  ✓ Synced: $($file.Source) -> $($file.Destination)" -ForegroundColor Green
        $syncedCount++
    } else {
        Write-Host "  ✗ Source not found: $($file.Source)" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host "`nSync complete: $syncedCount files synced" -ForegroundColor Cyan
if ($errorCount -gt 0) {
        Write-Host "Errors: $errorCount files not found" -ForegroundColor Red
}

