# Synthesis Astrology Pricing Strategy

## Cost Basis (Per Reading)
- Gemini 3 API Cost: ~$0.24
- Buffer for retries/errors: ~$0.06
- **Total Cost Per Reading**: ~$0.30

## Recommended Pricing Tiers

### Option A: Credit-Based System (Recommended)
Users purchase credits, spend them on features.

| Feature | Credits | Your Cost | Suggested Price |
|---------|---------|-----------|-----------------|
| Full Chart Reading | 10 credits | $0.30 | $4.99 (10 credits) |
| Chat Message (to AI) | 1 credit | ~$0.02-0.05 | included in bundle |
| Follow-up Deep Dive | 5 credits | ~$0.15 | included in bundle |

**Credit Packages:**
- Starter: 10 credits = $4.99 (1 reading OR 10 chat messages)
- Explorer: 30 credits = $9.99 (3 readings OR mix of features)
- Seeker: 100 credits = $24.99 (10 readings OR heavy chat usage)

**Margins:**
- Starter: $4.99 revenue, $0.30 cost = 94% margin
- Explorer: $9.99 revenue, $0.90 cost = 91% margin  
- Seeker: $24.99 revenue, $3.00 cost = 88% margin

---

### Option B: Subscription Model

| Tier | Price/Month | Includes | Your Cost | Margin |
|------|-------------|----------|-----------|--------|
| Free | $0 | 1 reading, 5 chat messages | $0.40 | Loss leader |
| Basic | $7.99/mo | 3 readings, 50 chat messages | ~$1.50 | 81% |
| Premium | $14.99/mo | Unlimited readings, unlimited chat | ~$5-10 | 33-66% |

---

### Option C: Pay-Per-Use (Simplest)

| Feature | Price | Your Cost | Margin |
|---------|-------|-----------|--------|
| Full Reading | $4.99 | $0.30 | 94% |
| Chat Session (10 messages) | $1.99 | $0.30 | 85% |
| Unlimited Chat (24hr) | $2.99 | ~$0.50 | 83% |

---

## Chat Cost Estimation

Assuming chat uses smaller context windows:
- Input: ~2,000 tokens (chart summary + question)
- Output: ~500 tokens (response)
- **Cost per chat message**: ~$0.01-0.03

For 10 chat messages: ~$0.10-0.30

---

## Recommended Implementation: Hybrid Model

### Free Tier (Account Required)
- 1 free comprehensive reading
- 3 free chat messages to try the feature
- Chart saved permanently

### Credits System
- 10 credits = $4.99
- 30 credits = $9.99 (10% bonus)
- 100 credits = $24.99 (25% bonus)

### Credit Costs
- Full Reading: 10 credits
- Chat Message: 1 credit
- Deep Dive on Topic: 5 credits

---

## Stripe Products to Create

1. **credit_pack_starter** - 10 credits @ $4.99
2. **credit_pack_explorer** - 30 credits @ $9.99
3. **credit_pack_seeker** - 100 credits @ $24.99

Optional subscriptions:
4. **subscription_basic** - $7.99/mo (30 credits/month)
5. **subscription_premium** - $14.99/mo (100 credits/month)

---

## Database Schema Additions Needed

```sql
-- User credits tracking
ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 3;  -- Free starter credits

-- Credit transactions log
CREATE TABLE credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount INTEGER NOT NULL,  -- positive = purchase, negative = usage
    transaction_type VARCHAR(50),  -- 'purchase', 'reading', 'chat', 'bonus'
    stripe_payment_id VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat messages (for billing)
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    chart_id INTEGER REFERENCES saved_charts(id),
    role VARCHAR(20),  -- 'user' or 'assistant'
    content TEXT,
    tokens_used INTEGER,
    credits_charged INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Implementation Phases

### Phase 1: Credit System Backend
- Add credits column to users table
- Create credit_transactions table
- Create endpoints: GET /credits, POST /use_credits

### Phase 2: Stripe Integration
- Set up Stripe products and prices
- Create checkout session endpoint
- Webhook handler for successful payments
- Credit fulfillment on payment success

### Phase 3: Chat Feature
- Chat endpoint that checks/deducts credits
- Chat history storage
- Rate limiting per credit balance

### Phase 4: UI Updates
- Credit balance display
- Purchase flow
- Chat interface with credit warnings

