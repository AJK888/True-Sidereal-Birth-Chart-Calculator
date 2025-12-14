# Database Structure Explanation

## Overview

This website uses **SQLAlchemy ORM** with support for both **SQLite** (development) and **PostgreSQL** (production). The database contains 8 main tables that handle user accounts, astrology charts, chat conversations, payments, and famous people data.

## Database Connection

- **Development**: SQLite (`sqlite:///./synthesis_astrology.db`)
- **Production**: PostgreSQL (via `DATABASE_URL` environment variable)
- **Connection Pooling**: Configured for PostgreSQL with connection recycling

## Database Tables

### 1. **users** - User Accounts & Authentication

**Purpose**: Stores user account information, authentication credentials, subscription status, and credit balance.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique user identifier
- `email` (String, Unique, Indexed) - User email address (used for login)
- `hashed_password` (String) - Bcrypt-hashed password
- `full_name` (String, Optional) - User's display name
- `created_at` (DateTime) - Account creation timestamp
- `is_active` (Boolean) - Whether account is active
- `is_admin` (Boolean) - Admin flag for developer access

**Credit System**:
- `credits` (Integer, Default: 10) - Remaining free chat credits (new users get 10 free chats)

**Stripe Subscription Fields**:
- `stripe_customer_id` (String, Indexed) - Stripe customer ID
- `stripe_subscription_id` (String, Indexed) - Stripe subscription ID
- `subscription_status` (String) - Status: `inactive`, `active`, `past_due`, `canceled`, `trialing`
- `subscription_start_date` (DateTime) - When subscription started
- `subscription_end_date` (DateTime) - When subscription ends

**Reading Purchase Fields**:
- `has_purchased_reading` (Boolean) - Has user purchased a $28 full reading?
- `reading_purchase_date` (DateTime) - When reading was purchased
- `free_chat_month_end_date` (DateTime) - End date of free month of chats after reading purchase

**Relationships**:
- One-to-Many with `saved_charts` (cascade delete)
- One-to-Many with `chat_conversations` (cascade delete)
- One-to-Many with `credit_transactions` (cascade delete)

---

### 2. **saved_charts** - User's Birth Charts

**Purpose**: Stores user-saved birth charts with birth data and calculated chart information.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique chart identifier
- `user_id` (Integer, Foreign Key → `users.id`) - Owner of the chart
- `chart_name` (String) - Name of the person the chart is for
- `created_at` (DateTime) - When chart was saved

**Birth Data**:
- `birth_year` (Integer) - Birth year
- `birth_month` (Integer) - Birth month (1-12)
- `birth_day` (Integer) - Birth day
- `birth_hour` (Integer) - Birth hour (0-23)
- `birth_minute` (Integer) - Birth minute (0-59)
- `birth_location` (String) - Birth location (city, country)
- `unknown_time` (Boolean) - Whether exact birth time is unknown

**Chart Data**:
- `chart_data_json` (Text) - Complete calculated chart data stored as JSON string
  - Contains planetary positions, aspects, houses, etc. for both sidereal and tropical systems
- `ai_reading` (Text, Optional) - Generated AI reading text if user purchased a reading

**Relationships**:
- Many-to-One with `users` (via `user_id`)
- One-to-Many with `chat_conversations` (cascade delete)

---

### 3. **chat_conversations** - Chat Sessions

**Purpose**: Represents a chat conversation about a specific chart. Each conversation can contain multiple messages.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique conversation identifier
- `user_id` (Integer, Foreign Key → `users.id`) - Owner of the conversation
- `chart_id` (Integer, Foreign Key → `saved_charts.id`) - Chart being discussed
- `title` (String, Default: "New Conversation") - Conversation title (auto-generated or user-defined)
- `created_at` (DateTime) - When conversation started
- `updated_at` (DateTime) - Last message timestamp (auto-updated)

**Relationships**:
- Many-to-One with `users` (via `user_id`)
- Many-to-One with `saved_charts` (via `chart_id`)
- One-to-Many with `chat_messages` (cascade delete)

---

### 4. **chat_messages** - Individual Chat Messages

**Purpose**: Stores individual messages within a chat conversation. Tracks message content, role (user/assistant), and credit usage.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique message identifier
- `conversation_id` (Integer, Foreign Key → `chat_conversations.id`) - Parent conversation
- `role` (String) - Message role: `'user'` or `'assistant'`
- `content` (Text) - Message text content
- `created_at` (DateTime) - Message timestamp

**Billing/Credit Tracking**:
- `tokens_used` (Integer, Optional) - Number of LLM tokens used (for cost tracking)
- `credits_charged` (Integer, Default: 1) - Credits deducted for this message (usually 1 credit per message)

**Relationships**:
- Many-to-One with `chat_conversations` (via `conversation_id`)

**Note**: Only user messages typically charge credits. Assistant responses are stored but don't charge additional credits.

---

### 5. **credit_transactions** - Credit Purchase & Usage Log

**Purpose**: Audit trail for all credit changes (purchases, deductions, bonuses, refunds).

**Key Fields**:
- `id` (Integer, Primary Key) - Unique transaction identifier
- `user_id` (Integer, Foreign Key → `users.id`) - User involved in transaction
- `amount` (Integer) - Credit amount:
  - **Positive** = Credit purchase/addition
  - **Negative** = Credit usage/deduction
- `transaction_type` (String) - Type: `'purchase'`, `'reading'`, `'chat'`, `'bonus'`, `'refund'`
- `stripe_payment_id` (String, Optional) - Stripe payment ID if purchased via Stripe
- `description` (Text, Optional) - Human-readable description
- `created_at` (DateTime) - Transaction timestamp

**Relationships**:
- Many-to-One with `users` (via `user_id`)

**Usage**: Used for debugging, analytics, and calculating total credits used/purchased.

---

### 6. **subscription_payments** - Subscription Payment History

**Purpose**: Tracks all subscription payment transactions from Stripe.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique payment record identifier
- `user_id` (Integer, Foreign Key → `users.id`) - User who made payment
- `stripe_payment_intent_id` (String, Indexed) - Stripe payment intent ID
- `stripe_invoice_id` (String, Indexed) - Stripe invoice ID
- `amount` (Integer) - Payment amount in cents (e.g., 2000 = $20.00)
- `currency` (String, Default: "usd") - Payment currency
- `status` (String) - Payment status: `succeeded`, `pending`, `failed`, `refunded`
- `payment_date` (DateTime) - When payment was processed
- `billing_period_start` (DateTime, Optional) - Subscription billing period start
- `billing_period_end` (DateTime, Optional) - Subscription billing period end
- `description` (Text, Optional) - Payment description
- `created_at` (DateTime) - Record creation timestamp

**Relationships**:
- Many-to-One with `users` (via `user_id`)

**Usage**: Payment history, receipts, subscription management.

---

### 7. **admin_bypass_logs** - Admin Action Audit Trail

**Purpose**: Logs all admin secret key usage for security auditing.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique log entry identifier
- `user_email` (String, Optional) - User email if available
- `endpoint` (String) - API endpoint accessed
- `ip_address` (String, Optional) - IPv4 or IPv6 address
- `user_agent` (String, Optional) - Browser/user agent string
- `timestamp` (DateTime) - When action occurred
- `details` (Text, Optional) - Additional context about the action

**Usage**: Security auditing, tracking admin access, debugging admin features.

---

### 8. **famous_people** - Famous People Database for Similarity Matching

**Purpose**: Stores birth chart data for famous people to enable "similar charts" feature. Contains ~7,435 records scraped from Wikipedia/Wikidata.

**Key Fields**:
- `id` (Integer, Primary Key) - Unique person identifier
- `name` (String, Unique, Indexed) - Person's full name
- `wikipedia_url` (String) - Link to Wikipedia page
- `occupation` (String, Optional) - Person's profession/occupation

**Birth Data**:
- `birth_year` (Integer) - Birth year
- `birth_month` (Integer) - Birth month
- `birth_day` (Integer) - Birth day
- `birth_hour` (Integer, Optional) - Birth hour (often unknown)
- `birth_minute` (Integer, Optional) - Birth minute (often unknown)
- `birth_location` (String) - Birth location
- `unknown_time` (Boolean, Default: True) - Most famous people don't have exact birth times

**Chart Data**:
- `chart_data_json` (Text, Optional) - Complete chart data as JSON for comparison
- `planetary_placements_json` (Text, Optional) - Planetary placements in structured format
- `top_aspects_json` (Text, Optional) - Top 3 aspects (sidereal and tropical)

**Indexed Sign Fields** (for fast filtering):
- `sun_sign_sidereal` (String, Indexed) - Sun sign in sidereal system
- `sun_sign_tropical` (String, Indexed) - Sun sign in tropical system
- `moon_sign_sidereal` (String, Indexed) - Moon sign in sidereal system
- `moon_sign_tropical` (String, Indexed) - Moon sign in tropical system

**Additional Matching Fields**:
- `life_path_number` (String, Indexed) - Numerology life path number
- `day_number` (String) - Numerology day number
- `chinese_zodiac_animal` (String, Indexed) - Chinese zodiac animal

**Metadata**:
- `page_views` (Integer, Indexed) - Wikipedia page views (for ranking/popularity)
- `created_at` (DateTime) - Record creation timestamp
- `updated_at` (DateTime) - Last update timestamp

**Usage**: Used in similarity matching algorithm to find famous people with similar birth charts to users.

**Performance Note**: The similarity matching endpoint currently loads all records into memory. Should be optimized to filter by Sun/Moon signs first using the indexed columns.

---

## Database Relationships Diagram

```
users (1) ──┬── (many) saved_charts
            ├── (many) chat_conversations
            ├── (many) credit_transactions
            └── (many) subscription_payments

saved_charts (1) ── (many) chat_conversations

chat_conversations (1) ── (many) chat_messages

famous_people (standalone table, no foreign keys)
admin_bypass_logs (standalone table, no foreign keys)
```

## Key Design Patterns

### 1. **Cascade Deletes**
- Deleting a user automatically deletes all their charts, conversations, and credit transactions
- Deleting a chart automatically deletes all conversations about that chart
- Deleting a conversation automatically deletes all messages in that conversation

### 2. **Credit System**
- **Free Users**: Start with 10 credits, each chat message costs 1 credit
- **Subscription Users**: Unlimited chats, bypass credit system
- **Reading Purchase**: Grants 1 month of free chats
- Credits tracked in `users.credits` column (source of truth)
- All credit changes logged in `credit_transactions` table (audit trail)

### 3. **Chart Storage**
- Birth data stored as separate fields (year, month, day, hour, minute, location)
- Calculated chart data stored as JSON string in `chart_data_json`
- Supports both sidereal and tropical astrology systems
- Handles unknown birth times gracefully

### 4. **Chat System**
- Conversations are tied to specific charts
- Messages stored with role (user/assistant) for context
- Credit tracking per message for billing
- Conversation titles auto-updated or user-defined

### 5. **Stripe Integration**
- Customer and subscription IDs stored in `users` table
- Payment history tracked in `subscription_payments` table
- Webhook handlers update subscription status automatically

## Database Operations

### Common Queries

**Get user's charts**:
```python
charts = db.query(SavedChart).filter(SavedChart.user_id == user_id).all()
```

**Get conversation messages**:
```python
messages = db.query(ChatMessage).filter(
    ChatMessage.conversation_id == conversation_id
).order_by(ChatMessage.created_at).all()
```

**Check user credits**:
```python
user = db.query(User).filter(User.id == user_id).first()
has_credits = user.credits >= 1
```

**Find similar famous people** (current - inefficient):
```python
famous_people = db.query(FamousPerson).all()  # Gets all 7,435 records!
```

**Find similar famous people** (optimized - recommended):
```python
candidates = db.query(FamousPerson).filter(
    or_(
        FamousPerson.sun_sign_sidereal == user_sun_s,
        FamousPerson.moon_sign_sidereal == user_moon_s
    )
).limit(500).all()
```

## Migration Notes

- Database uses SQLAlchemy ORM, so switching from SQLite to PostgreSQL requires only changing `DATABASE_URL`
- All table definitions are in `database.py` using SQLAlchemy declarative base
- Tables are created automatically via `Base.metadata.create_all(bind=engine)`
- Migration scripts exist in `scripts/migration/` for moving data to Supabase

## Indexes

**Indexed Columns** (for performance):
- `users.email` - Fast login lookups
- `users.stripe_customer_id` - Fast Stripe webhook processing
- `users.stripe_subscription_id` - Fast subscription lookups
- `famous_people.name` - Fast name lookups
- `famous_people.sun_sign_sidereal` - Fast similarity filtering
- `famous_people.sun_sign_tropical` - Fast similarity filtering
- `famous_people.moon_sign_sidereal` - Fast similarity filtering
- `famous_people.moon_sign_tropical` - Fast similarity filtering
- `famous_people.life_path_number` - Fast numerology matching
- `famous_people.chinese_zodiac_animal` - Fast zodiac matching
- `famous_people.page_views` - Fast popularity ranking
- `subscription_payments.stripe_payment_intent_id` - Fast payment lookups
- `subscription_payments.stripe_invoice_id` - Fast invoice lookups

## Summary

The database is designed to support:
1. **User Management**: Accounts, authentication, subscriptions
2. **Chart Storage**: Birth charts with full astrological calculations
3. **Chat System**: Conversations about charts with credit tracking
4. **Payment Processing**: Stripe integration with payment history
5. **Similarity Matching**: Famous people database for chart comparisons
6. **Audit Trails**: Credit transactions and admin action logging

All tables use proper foreign key relationships, cascade deletes for data integrity, and indexes for performance optimization.
