@echo off
REM Batch script to generate example JSON files
REM Make sure you have Python and requests installed first

echo Installing requests library if needed...
pip install requests

echo.
echo Generating Elon Musk example...
python generate_example.py --name "Elon Musk" --date "June 28, 1971" --time "7:30 AM" --location "Pretoria, South Africa"

echo.
echo Generating Barack Obama example (with complete chart_data)...
python generate_example.py --name "Barack Obama" --date "August 4, 1961" --time "7:24 PM" --location "Honolulu, Hawaii, USA"

echo.
echo Done! Check the True-Sidereal-Birth-Chart-Calculator\examples\data\ folder for the generated files.
pause

