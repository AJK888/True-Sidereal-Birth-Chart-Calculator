# Example Chart Generator Script

This script allows you to generate example JSON files for the astrology website by calling the API endpoints. It can be used as a standalone calculator outside of the website.

## Features

- **Interactive Mode**: Run without arguments to be prompted for all birth data
- **Command-Line Mode**: Provide all data as arguments for batch processing
- **Flexible Date/Time Parsing**: Supports multiple date and time formats
- **Automatic File Naming**: Creates filenames from person's name (e.g., "Elon Musk" → `elon-musk.json`)
- **Complete Data**: Generates both chart data and AI reading

## Installation

The script requires Python 3.7+ and the `requests` library:

```bash
pip install requests
```

## Usage

### Interactive Mode

Simply run the script without arguments:

```bash
python generate_example.py
```

You'll be prompted to enter:
- Full name
- Birth date (multiple formats accepted)
- Birth time (optional, can mark as unknown)
- Birth location

### Command-Line Mode

Provide all required information as arguments:

```bash
python generate_example.py \
  --name "Elon Musk" \
  --year 1971 \
  --month 6 \
  --day 28 \
  --hour 7 \
  --minute 30 \
  --location "Pretoria, South Africa"
```

### Using Date/Time Strings

You can also use natural date/time strings:

```bash
python generate_example.py \
  --name "Barack Obama" \
  --date "August 4, 1961" \
  --time "7:24 PM" \
  --location "Honolulu, Hawaii, USA"
```

### Unknown Birth Time

If birth time is unknown:

```bash
python generate_example.py \
  --name "Person Name" \
  --date "January 1, 2000" \
  --unknown-time \
  --location "City, Country"
```

### Custom Output Directory

Specify a different output directory:

```bash
python generate_example.py \
  --name "Elon Musk" \
  --date "June 28, 1971" \
  --time "7:30 AM" \
  --location "Pretoria, South Africa" \
  --output-dir "./my-examples"
```

## Supported Date Formats

- `June 28, 1971`
- `Jun 28, 1971`
- `6/28/1971`
- `1971-06-28`

## Supported Time Formats

- `7:30 AM`
- `7:30 PM`
- `19:30` (24-hour format)
- `7:30` (24-hour format, assumes AM if no period specified)

## Output

The script generates a JSON file in the format expected by the examples page:

```json
{
  "metadata": {
    "name": "Elon Musk",
    "birth_date": "June 28, 1971",
    "birth_time": "7:30 AM",
    "location": "Pretoria, South Africa",
    "unknown_time": false
  },
  "ai_reading": "...",
  "chart_data": {...}
}
```

Files are saved to `True-Sidereal-Birth-Chart-Calculator/examples/data/` by default, with filenames based on the person's name (e.g., `elon-musk.json`).

## Examples

### Generate Example for Elon Musk

```bash
python generate_example.py \
  --name "Elon Musk" \
  --date "June 28, 1971" \
  --time "7:30 AM" \
  --location "Pretoria, South Africa"
```

### Generate Example for Barack Obama

```bash
python generate_example.py \
  --name "Barack Obama" \
  --date "August 4, 1961" \
  --time "7:24 PM" \
  --location "Honolulu, Hawaii, USA"
```

## Error Handling

The script will:
- Validate date and time formats
- Check API responses for errors
- Display helpful error messages
- Save files only after successful API calls

## Notes

- The script calls the live API at `https://true-sidereal-api.onrender.com`
- Chart calculation typically takes 10-30 seconds
- AI reading generation typically takes 30-60 seconds
- Total time per example: ~1-2 minutes

## Troubleshooting

**API Connection Errors**: Make sure the API is running and accessible.

**Date/Time Parsing Errors**: Use one of the supported formats listed above.

**File Permission Errors**: Ensure you have write permissions to the output directory.

