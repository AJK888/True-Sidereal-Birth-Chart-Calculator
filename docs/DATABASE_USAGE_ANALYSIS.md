# Database Usage Analysis

## How Your Website Works with the Database

### Database Connection Pattern

Your application uses **SQLAlchemy ORM** with **FastAPI dependency injection**:

```python
from database import get_db, User, SavedChart, FamousPerson, etc.

@app.post("/endpoint")
async def some_endpoint(db: Session = Depends(get_db)):
    # Use db here
    user = db.query(User).filter(User.email == email).first()
    db.add(new_record)
    db.commit()
```

### Key Database Operations

#### 1. **User Management**
- **Registration**: Creates `User` records
- **Login**: Queries `User` table by email
- **Authentication**: Uses `get_current_user` dependency

```python
# Example from api.py line 2684
user = create_user(db, user_create)
db.add(user)
db.commit()
```

#### 2. **Chart Saving**
- **Save Chart**: Creates `SavedChart` records
- **List Charts**: Queries `SavedChart` filtered by `user_id`
- **Delete Chart**: Deletes `SavedChart` records

```python
# Example from api.py line 2795
saved_chart = SavedChart(user_id=current_user.id, ...)
db.add(saved_chart)
db.commit()
db.refresh(saved_chart)
```

#### 3. **Chat Conversations**
- **Create Conversation**: Creates `ChatConversation` records
- **Save Messages**: Creates `ChatMessage` records
- **Get History**: Queries `ChatMessage` filtered by `conversation_id`

```python
# Example from api.py line 3069
conversation = ChatConversation(user_id=current_user.id, ...)
db.add(conversation)
db.commit()
```

#### 4. **Famous People Matching** ⚠️ **NEEDS OPTIMIZATION**
- **Current**: Gets ALL famous people, then calculates similarity
- **Location**: `api.py` line 3458

```python
# Current implementation (INEFFICIENT)
famous_people = db.query(FamousPerson).all()  # Gets all 7,435 records!
for fp in famous_people:
    score = calculate_chart_similarity(chart_data, fp)
```

**Problem**: This loads all 7,435 records into memory every time!

**Solution**: Use database filters to narrow down candidates first:
```python
# Better approach - filter by Sun/Moon signs first
user_sun_s = extract_sun_sign_sidereal(chart_data)
user_moon_s = extract_moon_sign_sidereal(chart_data)

# Query only people with matching Sun or Moon signs
candidates = db.query(FamousPerson).filter(
    or_(
        FamousPerson.sun_sign_sidereal == user_sun_s,
        FamousPerson.moon_sign_sidereal == user_moon_s,
        FamousPerson.sun_sign_tropical == user_sun_t,
        FamousPerson.moon_sign_tropical == user_moon_t
    )
).limit(500).all()  # Limit to top 500 candidates

# Then calculate similarity on smaller set
```

#### 5. **Stripe Webhooks**
- **Update Subscriptions**: Updates `User` records with Stripe data
- **Reading Purchases**: Updates `has_purchased_reading`, `reading_purchase_date`

### Database Models Used

1. **User** - User accounts, authentication, subscriptions
2. **SavedChart** - User's saved birth charts
3. **ChatConversation** - Chat sessions
4. **ChatMessage** - Individual chat messages
5. **CreditTransaction** - Credit usage tracking
6. **FamousPerson** - Famous people for similarity matching
7. **AdminBypassLog** - Admin action logging

### Migration to Supabase Impact

**✅ Good News**: Your code uses SQLAlchemy ORM, which abstracts the database layer!

**What Changes:**
- **Nothing in your code!** Just update `DATABASE_URL` environment variable
- SQLAlchemy handles the PostgreSQL connection automatically
- All your `db.query()`, `db.add()`, `db.commit()` calls work the same

**What to Update:**
1. Set `DATABASE_URL` to Supabase connection string
2. That's it! Your code will work the same

**Performance Improvements Available:**
1. Optimize famous people query (use filters instead of loading all records)
2. Add database indexes (already done during migration)
3. Use connection pooling (already configured with Supabase)

### Current Database Connection

Your `database.py` already supports PostgreSQL:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./synthesis_astrology.db")

# Automatically handles PostgreSQL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL with connection pool settings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
    )
```

### After Migration

Once you set `DATABASE_URL` to Supabase:
- All endpoints work the same
- All database operations work the same
- No code changes needed
- Better performance with connection pooling
- Scalable for production

### Recommended Optimization

Update the famous people matching endpoint to use database filters:

```python
# In api.py, around line 3458
# Instead of: famous_people = db.query(FamousPerson).all()

# Use filters to narrow down candidates first
from sqlalchemy import or_

# Extract user's signs
user_sun_s = extract_sign(chart_data, 'Sun', 'sidereal')
user_moon_s = extract_sign(chart_data, 'Moon', 'sidereal')
user_sun_t = extract_sign(chart_data, 'Sun', 'tropical')
user_moon_t = extract_sign(chart_data, 'Moon', 'tropical')

# Query only candidates with matching signs (uses indexes!)
candidates = db.query(FamousPerson).filter(
    or_(
        FamousPerson.sun_sign_sidereal == user_sun_s,
        FamousPerson.moon_sign_sidereal == user_moon_s,
        FamousPerson.sun_sign_tropical == user_sun_t,
        FamousPerson.moon_sign_tropical == user_moon_t
    )
).limit(1000).all()  # Limit to 1000 candidates max

# Then calculate similarity on smaller set
for fp in candidates:
    score = calculate_chart_similarity(chart_data, fp)
    ...
```

This will be **much faster** with Supabase's indexed columns!

