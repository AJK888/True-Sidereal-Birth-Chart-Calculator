# Stripe Setup Guide

Complete step-by-step instructions to set up Stripe for the new pricing model:
- $28 one-time full reading purchase
- $8/month subscription for continued chat access

## Prerequisites
- Stripe account (sign up at https://stripe.com if needed)
- Access to your deployment environment (Render, Heroku, etc.) to set environment variables
- Your API base URL (e.g., `https://true-sidereal-api.onrender.com`)

---

## Step 1: Get Your Stripe API Keys

1. Go to https://dashboard.stripe.com
2. Make sure you're in **Test mode** (toggle in top right) for testing, or **Live mode** for production
3. Navigate to **Developers** → **API keys** (in the left sidebar)
4. Copy these values (you'll need them later):
   - **Publishable key** (starts with `pk_test_` or `pk_live_`)
   - **Secret key** (starts with `sk_test_` or `sk_live_`) - Click "Reveal test key" or "Reveal live key"

⚠️ **Important**: Use Test mode keys for development/testing, Live mode keys for production.

---

## Step 2: Create Product for Full Reading Purchase

1. In Stripe Dashboard, go to **Products** (left sidebar)
2. Click **"+ Add product"** button
3. Fill in the product details:
   - **Name**: `Synthesis Astrology Full Reading`
   - **Description**: `Comprehensive 15+ page full reading with free month of unlimited chats`
   - Leave other fields as default
4. Click **"Save product"**

### Step 2a: Create Price for Full Reading

1. After creating the product, you'll see a **"Add price"** section
2. Click **"Add price"** or go to the product and click **"Add another price"**
3. Configure the price:
   - **Pricing model**: Select **"Standard pricing"**
   - **Price**: Enter `28.00`
   - **Currency**: Select `USD` (or your preferred currency)
   - **Billing period**: Select **"One time"** (not recurring)
4. Click **"Save price"**
5. **Copy the Price ID** (starts with `price_`) - This is your `STRIPE_PRICE_ID_READING`

---

## Step 3: Create Product for Monthly Subscription

1. In Stripe Dashboard, go to **Products** (left sidebar)
2. Click **"+ Add product"** button
3. Fill in the product details:
   - **Name**: `Synthesis Astrology Monthly Subscription`
   - **Description**: `Monthly subscription for unlimited chat conversations and premium features`
   - Leave other fields as default
4. Click **"Save product"**

### Step 3a: Create Price for Monthly Subscription

1. After creating the product, you'll see a **"Add price"** section
2. Click **"Add price"** or go to the product and click **"Add another price"**
3. Configure the price:
   - **Pricing model**: Select **"Standard pricing"**
   - **Price**: Enter `8.00`
   - **Currency**: Select `USD` (or your preferred currency)
   - **Billing period**: Select **"Monthly"** (recurring)
   - **Usage type**: Select **"Licensed"**
4. Click **"Save price"**
5. **Copy the Price ID** (starts with `price_`) - This is your `STRIPE_PRICE_ID_MONTHLY`

💡 **Tip**: You can find Price IDs by:
   - Going to **Products** → Click your product → Click the price → The ID is shown at the top

---

## Step 4: Set Up Webhook Endpoint

Webhooks allow Stripe to notify your server when payment events occur (payment succeeded, subscription canceled, etc.).

1. In Stripe Dashboard, go to **Developers** → **Webhooks** (left sidebar)
2. Click **"+ Add endpoint"**
3. Configure the endpoint:
   - **Endpoint URL**: Enter your API URL + webhook path
     - Example: `https://true-sidereal-api.onrender.com/api/webhooks/stripe`
     - Replace with your actual API base URL
   - **Description**: `Synthesis Astrology Payment Webhooks`
   - **Events to send**: Click **"Select events"** and choose:
     - `checkout.session.completed` (for both reading purchase and subscription)
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid` (for monthly subscription renewals)
     - `invoice.payment_failed`
4. Click **"Add endpoint"**

---

## Step 5: Get Your Webhook Signing Secret

1. After creating the webhook endpoint, click on it to view details
2. In the **"Signing secret"** section, click **"Reveal"**
3. **Copy the signing secret** (starts with `whsec_`)
   - Example: `whsec_1ABC123def456GHI789jkl012`
4. This is your `STRIPE_WEBHOOK_SECRET` value

⚠️ **Important**: 
   - You'll have different secrets for Test mode and Live mode
   - Make sure you use the correct one for your environment

---

## Step 6: Set Environment Variables

Set these environment variables in your deployment platform (Render, Heroku, etc.):

### Required Variables:

1. **STRIPE_SECRET_KEY**
   - Value: Your Stripe Secret Key (from Step 1)
   - Example: `sk_test_51ABC123...` or `sk_live_51ABC123...`

2. **STRIPE_WEBHOOK_SECRET**
   - Value: Your Webhook Signing Secret (from Step 5)
   - Example: `whsec_1ABC123...`

3. **STRIPE_PRICE_ID_READING**
   - Value: Your Full Reading Price ID (from Step 2a)
   - Example: `price_1ABC123...`

4. **STRIPE_PRICE_ID_MONTHLY**
   - Value: Your Monthly Subscription Price ID (from Step 3a)
   - Example: `price_1XYZ789...`

### Optional Variables (if different from defaults):

5. **FRONTEND_URL** (optional)
   - Value: Your frontend website URL
   - Default: `https://synthesisastrology.com`
   - Example: `https://synthesisastrology.com`

### How to Set Environment Variables:

**On Render:**
1. Go to your service dashboard
2. Click **"Environment"** tab
3. Click **"Add Environment Variable"**
4. Enter the variable name and value
5. Click **"Save Changes"**
6. Your service will restart automatically

**On Heroku:**
```bash
heroku config:set STRIPE_SECRET_KEY=sk_test_...
heroku config:set STRIPE_WEBHOOK_SECRET=whsec_...
heroku config:set STRIPE_PRICE_ID_READING=price_...
heroku config:set STRIPE_PRICE_ID_MONTHLY=price_...
```

**On Other Platforms:**
- Check your platform's documentation for setting environment variables

---

## Step 7: Database Migration

You'll need to add new columns to track reading purchases and free month status:

```sql
ALTER TABLE users ADD COLUMN has_purchased_reading BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN reading_purchase_date TIMESTAMP;
ALTER TABLE users ADD COLUMN free_chat_month_end_date TIMESTAMP;
```

Or if using SQLAlchemy migrations, the schema has already been updated in `database.py`.

---

## Step 8: Verify Your Setup

### Test the Configuration:

1. **Check API logs** after restarting your service:
   - You should see: `"Stripe initialized for subscriptions"`
   - If you see: `"Stripe not configured - subscription features disabled"`, check your environment variables

2. **Test the reading purchase flow**:
   - Log in to your website
   - Click "Purchase Full Reading" ($28)
   - You should be redirected to Stripe Checkout
   - Use Stripe test card: `4242 4242 4242 4242`
   - Any future expiry date, any CVC
   - After payment, verify free month is granted

3. **Test the subscription flow**:
   - After free month expires (or manually test)
   - Click "Subscribe" ($8/month)
   - You should be redirected to Stripe Checkout
   - Use Stripe test card: `4242 4242 4242 4242`
   - Verify subscription is activated

4. **Test webhook delivery**:
   - In Stripe Dashboard → **Developers** → **Webhooks**
   - Click your webhook endpoint
   - You should see recent events listed
   - Click on an event to see if it was successfully delivered

---

## Step 9: Test Mode vs Live Mode

### Test Mode (Development):
- Use test API keys (`sk_test_...`, `pk_test_...`)
- Use test webhook secret (`whsec_...` from test mode webhook)
- Use test cards (e.g., `4242 4242 4242 4242`)
- No real charges are made

### Live Mode (Production):
- Use live API keys (`sk_live_...`, `pk_live_...`)
- Use live webhook secret (`whsec_...` from live mode webhook)
- Real charges are made
- Switch to Live mode in Stripe Dashboard when ready

⚠️ **Important**: 
- Create separate webhook endpoints for Test and Live modes
- Update environment variables when switching between modes

---

## Step 10: Monitor Webhook Events

1. Go to **Developers** → **Webhooks** in Stripe Dashboard
2. Click your webhook endpoint
3. View **"Recent events"** to see:
   - Which events were sent
   - Whether they succeeded or failed
   - Response codes from your server

### Common Issues:

- **404 Not Found**: Check your webhook URL is correct
- **401 Unauthorized**: Check your webhook secret is correct
- **500 Server Error**: Check your server logs for errors

---

## Summary Checklist

- [ ] Created Stripe account
- [ ] Got API keys (Secret Key and Publishable Key)
- [ ] Created product: "Synthesis Astrology Full Reading"
- [ ] Created price: $28.00 one-time payment
- [ ] Copied Reading Price ID (`price_...`) → `STRIPE_PRICE_ID_READING`
- [ ] Created product: "Synthesis Astrology Monthly Subscription"
- [ ] Created price: $8.00/month recurring
- [ ] Copied Subscription Price ID (`price_...`) → `STRIPE_PRICE_ID_MONTHLY`
- [ ] Created webhook endpoint pointing to `/api/webhooks/stripe`
- [ ] Selected required webhook events
- [ ] Copied webhook signing secret (`whsec_...`)
- [ ] Set `STRIPE_SECRET_KEY` environment variable
- [ ] Set `STRIPE_WEBHOOK_SECRET` environment variable
- [ ] Set `STRIPE_PRICE_ID_READING` environment variable
- [ ] Set `STRIPE_PRICE_ID_MONTHLY` environment variable
- [ ] Set `FRONTEND_URL` (if different from default)
- [ ] Ran database migration (if needed)
- [ ] Restarted service to load new environment variables
- [ ] Verified "Stripe initialized" message in logs
- [ ] Tested reading purchase flow with test card
- [ ] Tested subscription flow with test card
- [ ] Verified webhook events are being received

---

## Support

If you encounter issues:
1. Check your server logs for error messages
2. Verify all environment variables are set correctly
3. Test webhook delivery in Stripe Dashboard
4. Ensure your API endpoint is publicly accessible (for webhooks)

---

## Next Steps

After setup is complete:
- Test a full reading purchase flow end-to-end
- Test subscription signup after free month
- Monitor webhook events to ensure they're processing correctly
- Switch to Live mode when ready for production
- Update your frontend to handle the new pricing model
