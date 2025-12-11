# Synthesis Astrology Pricing Strategy

## Cost Basis (Per Reading)
- Gemini 3 API Cost: ~$0.24
- Buffer for retries/errors: ~$0.06
- **Total Cost Per Reading**: ~$0.30

## Current Pricing Model

### Full Reading Purchase
- **Price**: $28 (one-time payment)
- **Includes**: 
  - One comprehensive full reading (15+ page deep analysis)
  - **Free month of unlimited chats** - Ask our AI astrologer anything about your chart
- **Margin**: $28 revenue, $0.30 cost = 98.9% margin

### Monthly Subscription (After Free Month)
- **Price**: $8/month
- **Includes**:
  - Unlimited chat conversations about your chart
  - Access to all premium features and benefits
  - Ongoing support and guidance
- **When it starts**: After your free month expires (if you want to continue chatting)
- **Cancel anytime**: No long-term commitment

## Pricing Flow

1. **User purchases full reading** ($28)
   - Receives comprehensive full reading
   - Gets 1 free month of unlimited chats
   - Free month starts immediately upon purchase

2. **After free month expires**
   - User can continue with $8/month subscription to keep chatting
   - Or choose not to subscribe (reading remains accessible)

## Chat Cost Estimation

Assuming chat uses smaller context windows:
- Input: ~2,000 tokens (chart summary + question)
- Output: ~500 tokens (response)
- **Cost per chat message**: ~$0.01-0.03

For unlimited chats in a month: ~$0.50-3.00 (depending on usage)

## Free Tier (Always Available)

- Unlimited Chart Calculations
- Complete Astrological Placements (Sidereal & Tropical)
- Chinese Zodiac & Numerology Analysis
- **Unlimited Snapshot Readings** - Quick AI-generated insights delivered instantly via email
- Chart Visualization Wheels
- Full Raw Chart Data

## Stripe Products to Create

1. **Full Reading Purchase** - $28 one-time payment
   - Product: "Synthesis Astrology Full Reading"
   - Price: $28.00 (one-time)
   - Price ID environment variable: `STRIPE_PRICE_ID_READING`

2. **Monthly Subscription** - $8/month recurring
   - Product: "Synthesis Astrology Monthly Subscription"
   - Price: $8.00/month (recurring)
   - Price ID environment variable: `STRIPE_PRICE_ID_MONTHLY`

## Database Schema

The following fields track reading purchases and free month status:

```sql
-- User table additions
ALTER TABLE users ADD COLUMN has_purchased_reading BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN reading_purchase_date TIMESTAMP;
ALTER TABLE users ADD COLUMN free_chat_month_end_date TIMESTAMP;
```

## Implementation Details

### Reading Purchase Flow
1. User clicks "Purchase Full Reading" ($28)
2. Stripe Checkout session created (one-time payment)
3. Upon successful payment:
   - `has_purchased_reading` = True
   - `reading_purchase_date` = current timestamp
   - `free_chat_month_end_date` = current timestamp + 30 days
4. User can now:
   - Generate full reading (if not already done)
   - Use unlimited chats for 30 days

### Subscription Flow (After Free Month)
1. User's free month is about to expire or has expired
2. User clicks "Subscribe" ($8/month)
3. Stripe Checkout session created (recurring subscription)
4. Upon successful subscription:
   - `subscription_status` = "active"
   - `subscription_start_date` = current timestamp
   - `subscription_end_date` = current timestamp + 30 days
5. User continues to have unlimited chat access

### Access Control Logic

**For Full Readings:**
- Requires: `has_purchased_reading` = True OR `subscription_status` = "active"

**For Chat:**
- Requires: 
  - In free month (`free_chat_month_end_date` > now) OR
  - Active subscription (`subscription_status` = "active")

## API Endpoints

- `POST /api/reading/checkout` - Create checkout for $28 reading purchase
- `POST /api/subscription/checkout` - Create checkout for $8/month subscription
- `GET /api/subscription/status` - Get current subscription/reading status
- `POST /api/webhooks/stripe` - Handle Stripe webhook events

## Webhook Events Handled

- `checkout.session.completed` - Reading purchase or subscription signup
- `customer.subscription.updated` - Subscription status changes
- `customer.subscription.deleted` - Subscription canceled
- `invoice.paid` - Monthly subscription payment succeeded
- `invoice.payment_failed` - Payment failed

## Benefits of This Model

1. **Lower barrier to entry**: $28 one-time vs $88/month subscription
2. **Value demonstration**: Free month lets users experience chat feature
3. **Flexible commitment**: Users can try without long-term commitment
4. **High margin**: 98.9% margin on reading purchase
5. **Recurring revenue**: $8/month is affordable for ongoing users
