# Download Swiss Ephemeris Asteroid File

To calculate minor asteroids (Ceres, Pallas, Juno, Vesta), you need the `seas_12.se1` file.

## Download Instructions:

1. **Go to the Swiss Ephemeris download page:**
   - https://www.astro.com/swisseph/swephinfo_e.htm
   - Or search for "Swiss Ephemeris download"

2. **Download the Swiss Ephemeris files package** (usually a ZIP file)

3. **Extract and find `seas_12.se1`** in the package

4. **Copy `seas_12.se1` to this directory:**
   ```
   Synthesis Astrology/True-Sidereal-Birth-Chart/swiss_ephemeris/
   ```

5. **Restart your script** - the asteroids should now calculate!

## Alternative:

If you can't find `seas_12.se1`, the `seas_18.se1` file you have covers 1800-2100.
The error might be a version issue. You can try:
- Copying `seas_18.se1` to `seas_12.se1` (may work for modern dates)
- Or downloading the full Swiss Ephemeris package

## Current Files:
- ✅ `seas_18.se1` - Asteroids 1800-2100 (present)
- ✅ `semo_18.se1` - Moon 1800-2100 (present)
- ✅ `sepl_18.se1` - Planets 1800-2100 (present)
- ❌ `seas_12.se1` - Asteroids 1200-1300 (missing - needed for some calculations)

