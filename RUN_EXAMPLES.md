# Running the Example Generator

Since terminal commands are being canceled, here are the manual steps to run:

## Step 1: Install Dependencies

Open PowerShell or Command Prompt in this directory and run:

```powershell
pip install requests
```

## Step 2: Generate Example Files

### Option A: Use the Batch Script

Double-click `generate_examples.bat` or run:

```powershell
.\generate_examples.bat
```

### Option B: Run Commands Manually

**Generate Elon Musk example:**
```powershell
python generate_example.py --name "Elon Musk" --date "June 28, 1971" --time "7:30 AM" --location "Pretoria, South Africa"
```

**Generate Barack Obama example (with complete chart_data):**
```powershell
python generate_example.py --name "Barack Obama" --date "August 4, 1961" --time "7:24 PM" --location "Honolulu, Hawaii, USA"
```

### Option C: Interactive Mode

Run without arguments for interactive prompts:

```powershell
python generate_example.py
```

## Step 3: Verify Files

After running, check that these files exist:
- `True-Sidereal-Birth-Chart-Calculator\examples\data\elon-musk.json`
- `True-Sidereal-Birth-Chart-Calculator\examples\data\barack-obama.json` (updated with complete chart_data)

## Notes

- Each API call takes 1-2 minutes (chart calculation + AI reading generation)
- Make sure your API is running at `https://true-sidereal-api.onrender.com`
- The script will create the `examples/data` directory if it doesn't exist

