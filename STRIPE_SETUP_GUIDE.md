# Stripe Subscription Setup Guide

Complete step-by-step instructions to set up Stripe for the $88/month subscription.

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

## Step 2: Create a Product in Stripe

1. In Stripe Dashboard, go to **Products** (left sidebar)
2. Click **"+ Add product"** button
3. Fill in the product details:
   - **Name**: `Synthesis Astrology Premium Subscription`
   - **Description**: `Monthly subscription for unlimited full readings and chat access`
   - Leave other fields as default
4. Click **"Save product"**

---

## Step 3: Create a Price for the Product

1. After creating the product, you'll see a **"Add price"** section
2. Click **"Add price"** or go to the product and click **"Add another price"**
3. Configure the price:
   - **Pricing model**: Select **"Standard pricing"**
   - **Price**: Enter `88.00`
   - **Currency**: Select `USD` (or your preferred currency)
   - **Billing period**: Select **"Monthly"** (recurring)
   - **Usage type**: Select **"Licensed"**
4. Click **"Save price"**

---

## Step 4: Get Your Price ID

1. After saving the price, you'll see it listed under your product
2. The **Price ID** will be displayed (starts with `price_`)
   - Example: `price_1ABC123def456GHI789jkl012`
3. **Copy this Price ID** - you'll need it for the environment variable `STRIPE_PRICE_ID_MONTHLY`

💡 **Tip**: You can also find it by:
   - Going to **Products** → Click your product → Click the price → The ID is shown at the top

---

## Step 5: Set Up Webhook Endpoint

Webhooks allow Stripe to notify your server when subscription events occur (payment succeeded, subscription canceled, etc.).

1. In Stripe Dashboard, go to **Developers** → **Webhooks** (left sidebar)
2. Click **"+ Add endpoint"**
3. Configure the endpoint:
   - **Endpoint URL**: Enter your API URL + webhook path
     - Example: `https://true-sidereal-api.onrender.com/api/webhooks/stripe`
     - Replace with your actual API base URL
   - **Description**: `Synthesis Astrology Subscription Webhooks`
   - **Events to send**: Click **"Select events"** and choose:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `invoice.payment_failed`
4. Click **"Add endpoint"**

---

## Step 6: Get Your Webhook Signing Secret

1. After creating the webhook endpoint, click on it to view details
2. In the **"Signing secret"** section, click **"Reveal"**
3. **Copy the signing secret** (starts with `whsec_`)
   - Example: `whsec_1ABC123def456GHI789jkl012`
4. This is your `STRIPE_WEBHOOK_SECRET` value

⚠️ **Important**: 
   - You'll have different secrets for Test mode and Live mode
   - Make sure you use the correct one for your environment

---

## Step 7: Set Environment Variables

Set these environment variables in your deployment platform (Render, Heroku, etc.):

### Required Variables:

1. **STRIPE_SECRET_KEY**
   - Value: Your Stripe Secret Key (from Step 1)
   - Example: `sk_test_51ABC123...` or `sk_live_51ABC123...`

2. **STRIPE_WEBHOOK_SECRET**
   - Value: Your Webhook Signing Secret (from Step 6)
   - Example: `whsec_1ABC123...`

3. **STRIPE_PRICE_ID_MONTHLY**
   - Value: Your Price ID (from Step 4)
   - Example: `price_1ABC123...`

### Optional Variables (if different from defaults):

4. **FRONTEND_URL** (optional)
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
heroku config:set STRIPE_PRICE_ID_MONTHLY=price_...
```

**On Other Platforms:**
- Check your platform's documentation for setting environment variables

---

## Step 8: Verify Your Setup

### Test the Configuration:

1. **Check API logs** after restarting your service:
   - You should see: `"Stripe initialized for subscriptions"`
   - If you see: `"Stripe not configured - subscription features disabled"`, check your environment variables

2. **Test the checkout flow**:
   - Log in to your website
   - Click "Subscribe Now"
   - You should be redirected to Stripe Checkout
   - Use Stripe test card: `4242 4242 4242 4242`
   - Any future expiry date, any CVC

3. **Test webhook delivery**:
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
- [ ] Created product: "Synthesis Astrology Premium Subscription"
- [ ] Created price: $88/month recurring
- [ ] Copied Price ID (`price_...`)
- [ ] Created webhook endpoint pointing to `/api/webhooks/stripe`
- [ ] Selected required webhook events
- [ ] Copied webhook signing secret (`whsec_...`)
- [ ] Set `STRIPE_SECRET_KEY` environment variable
- [ ] Set `STRIPE_WEBHOOK_SECRET` environment variable
- [ ] Set `STRIPE_PRICE_ID_MONTHLY` environment variable
- [ ] Set `FRONTEND_URL` (if different from default)
- [ ] Restarted service to load new environment variables
- [ ] Verified "Stripe initialized" message in logs
- [ ] Tested checkout flow with test card
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
- Test a full subscription flow end-to-end
- Monitor webhook events to ensure they're processing correctly
- Switch to Live mode when ready for production
- Update your frontend to handle subscription status changes

