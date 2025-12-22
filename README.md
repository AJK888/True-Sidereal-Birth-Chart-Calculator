# Synthesis Astrology - True Sidereal Birth Chart

A comprehensive astrology application that calculates true sidereal birth charts, provides AI-powered readings, and matches users with famous people who share similar astrological placements.

## Project Structure

```
True-Sidereal-Birth-Chart/
├── api.py                    # Main FastAPI application
├── auth.py                   # Authentication and user management
├── chat_api.py               # Chat/conversation API endpoints
├── database.py               # SQLAlchemy models and database setup
├── llm_schemas.py            # LLM request/response schemas
├── natal_chart.py            # Core chart calculation logic
├── pdf_generator.py          # PDF report generation
├── stripe_integration.py     # Stripe payment integration
├── subscription.py           # Subscription management
├── v2_pipeline_functions.py  # Pipeline processing functions
├── requirements.txt          # Python dependencies
├── render.yaml               # Render deployment configuration
│
├── docs/                     # Documentation
│   ├── MIGRATE_TO_SUPABASE.md
│   ├── MIGRATE_USERS_TO_SUPABASE.md
│   ├── DATABASE_USAGE_ANALYSIS.md
│   ├── PRICING_STRATEGY.md
│   ├── STRIPE_SETUP_GUIDE.md
│   └── ...
│
├── scripts/                  # Utility scripts
│   ├── migration/            # Database migration scripts
│   │   ├── migrate_to_supabase.py
│   │   └── migrate_all_to_supabase.py
│   │
│   ├── scrapers/            # Web scraping scripts
│   │   ├── scrape_famous_people_by_category.py
│   │   ├── scrape_wikidata_5000.py
│   │   └── scrape_and_calculate_5000.py
│   │
│   ├── maintenance/         # Database maintenance scripts
│   │   ├── quality_control_database.py
│   │   ├── fix_database_issues.py
│   │   ├── calculate_all_placements.py
│   │   ├── update_pageviews.py
│   │   └── export_to_csv.py
│   │
│   └── utils/               # Utility scripts
│       ├── check_database_status.py
│       ├── download_swiss_ephemeris.py
│       └── ...
│
├── swiss_ephemeris/         # Swiss Ephemeris data files
│   ├── seas_18.se1
│   ├── semo_18.se1
│   └── sepl_18.se1
│
└── True-Sidereal-Birth-Chart-Calculator/  # Frontend calculator
    ├── index.html
    ├── assets/
    └── examples/
```

## Features

- **True Sidereal Chart Calculation**: Uses the Swiss Ephemeris for accurate astronomical calculations
- **Tropical & Sidereal Systems**: Supports both tropical and sidereal zodiac systems
- **AI-Powered Readings**: Generates personalized astrological readings using Google Gemini
- **Famous People Matching**: Matches users with famous people who share similar chart placements
- **User Accounts**: User registration, authentication, and saved charts
- **Chat Interface**: Interactive chat about birth charts
- **PDF Reports**: Generate downloadable PDF birth chart reports
- **Stripe Integration**: Payment processing for subscriptions and readings

## Database

The application uses **Supabase (PostgreSQL)** for data storage:

- **famous_people**: Database of famous people with birth chart data (7,435+ records)
- **users**: User accounts and authentication
- **saved_charts**: User-saved birth charts
- **chat_conversations**: Chat conversation metadata
- **chat_messages**: Individual chat messages
- **credit_transactions**: Credit purchase/usage tracking
- **subscription_payments**: Stripe subscription payment history

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   ```bash
   DATABASE_URL=postgresql://...  # Supabase connection string
   SECRET_KEY=...                  # JWT secret key
   GEMINI_API_KEY=...              # For AI features
   SENDGRID_API_KEY=...            # For email
   STRIPE_SECRET_KEY=...           # For payments
   REDIS_URL=...                   # Optional, for caching
   ```

3. **Download Swiss Ephemeris Files**
   - See `docs/SWISS_EPHEMERIS.md` for instructions
   - Or run: `python scripts/utils/download_swiss_ephemeris.py`

4. **Run Database Migrations**
   ```bash
   alembic upgrade head
   ```

5. **Run the Application**
   ```bash
   # Development
   uvicorn api:app --reload
   
   # Production
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

6. **Access API Documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Testing

Run the test suite:

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/unit/test_auth.py
```

See `tests/README.md` for more testing information.

## Scripts

### Migration Scripts (`scripts/migration/`)
- `migrate_to_supabase.py` - Migrate famous_people data to Supabase
- `migrate_all_to_supabase.py` - Migrate all user data to Supabase

### Maintenance Scripts (`scripts/maintenance/`)
- `quality_control_database.py` - Run quality checks on database
- `fix_database_issues.py` - Automatically fix common data issues
- `calculate_all_placements.py` - Calculate planetary placements
- `update_pageviews.py` - Update Wikipedia pageview data
- `export_to_csv.py` - Export database to CSV

### Scraper Scripts (`scripts/scrapers/`)
- `scrape_famous_people_by_category.py` - Scrape famous people by category
- `scrape_wikidata_5000.py` - Scrape from Wikidata
- `scrape_and_calculate_5000.py` - Scrape and calculate charts

## Documentation

### API Documentation
- **Interactive API Docs**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when server is running
- **API_DOCUMENTATION.md** - Complete API reference with examples
- **DEVELOPER_GUIDE.md** - Developer setup, architecture, and guidelines

### Other Documentation
All documentation is in the `docs/` directory:

- **MIGRATE_TO_SUPABASE.md** - Guide for migrating to Supabase
- **DATABASE_USAGE_ANALYSIS.md** - How the application uses the database
- **PRICING_STRATEGY.md** - Pricing and subscription strategy
- **STRIPE_SETUP_GUIDE.md** - Stripe integration guide

### Phase Documentation
- **PHASE_0_COMPLETE.md** - Phase 0 (Quick Wins) completion
- **PHASE_1_FINAL_SUMMARY.md** - Phase 1 (Structural Refactoring) summary
- **PHASE_2_COMPLETE.md** - Phase 2 (Advanced Features) completion
- **PHASE_3_START.md** - Phase 3 (Testing & Documentation) status

## License

See LICENSE file for details.

