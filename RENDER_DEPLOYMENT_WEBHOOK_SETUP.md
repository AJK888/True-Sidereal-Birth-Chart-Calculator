# Render Deployment Webhook Setup

This guide explains how to automatically trigger the webpage deployment whenever the API server completes a new deploy.

## Overview

When the API server (`true-sidereal-api`) completes a deployment, it will automatically trigger a deployment of the webpage service using Render's Deploy Hook URL.

## Setup Instructions

### Step 1: Get Your Webpage Deploy Hook URL

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Navigate to your **webpage service** (not the API service)
3. Go to the **Settings** tab
4. Scroll down to find **Deploy Hook** section
5. You'll see a private URL that looks like:
   ```
   https://api.render.com/deploy/srv-xxxxx?key=xxxxx
   ```
6. **Copy this entire URL** - this is your Deploy Hook URL
   - ⚠️ **Important**: Keep this URL secret! Anyone with this URL can trigger deployments.

### Step 2: Add Environment Variable to API Service

1. Go to your **API service** (`true-sidereal-api`) in Render Dashboard
2. Navigate to **Environment** tab
3. Click **Add Environment Variable**
4. Add:
   - **Key**: `WEBPAGE_DEPLOY_HOOK_URL`
   - **Value**: Paste the Deploy Hook URL you copied in Step 1
5. Click **Save Changes**

### Step 3: Configure Deployment Hook in API Service

1. Go to your **API service** (`true-sidereal-api`) in Render Dashboard
2. Navigate to **Settings** tab
3. Scroll down to **Deploy Hook** section
4. You should see your API service's deploy hook URL
5. Now we need to set up a way to call the webhook endpoint after deployment

**Option A: Using Render's Deployment Hook (if available)**
- Look for **Deployment Hooks** or **Post-Deploy Scripts** section
- Add a command:
  ```bash
  curl -X POST https://true-sidereal-api.onrender.com/api/webhooks/render-deploy
  ```

**Option B: Using a Simple Script**
- If Render doesn't have deployment hooks, you can use a GitHub Action or similar
- Or manually trigger the webhook after each API deployment

## How It Works

1. API service completes deployment successfully
2. A deployment hook (or manual trigger) calls `/api/webhooks/render-deploy`
3. The endpoint uses the webpage's Deploy Hook URL to trigger a new deployment
4. Webpage service starts deploying automatically

## Security Considerations

- ⚠️ **Keep your Deploy Hook URL secret!** Anyone with this URL can trigger deployments
- Store it only as an environment variable, never commit it to git
- The webhook endpoint is public, but it only triggers deployments if the Deploy Hook URL is configured
- Consider adding authentication to the webhook endpoint if needed

## Testing

1. Make a change to the API code
2. Commit and push to trigger a deployment
3. Once API deployment completes, check the logs to see if the webpage deployment was triggered
4. Verify the webpage service shows a new deployment in progress

## Troubleshooting

### Webpage deployment not triggering

1. Check API service logs for webhook errors
2. Verify `WEBPAGE_DEPLOY_HOOK_URL` environment variable is set correctly
3. Make sure the Deploy Hook URL is from the **webpage service**, not the API service
4. Verify the deployment hook/script is calling the webhook endpoint correctly
5. Test the Deploy Hook URL manually:
   ```bash
   curl -X POST https://your-webpage-deploy-hook-url
   ```

### Deploy Hook URL errors

- Make sure you copied the entire URL including the `?key=xxxxx` part
- Verify the URL is from the webpage service settings
- Check that the webpage service is active and not paused
- The URL should start with `https://api.render.com/deploy/`

### Deployment hook not running

- If Render doesn't have a deployment hook feature, you may need to:
  - Use a GitHub Action to trigger the webhook after API deployment
  - Manually call the webhook endpoint after deployments
  - Set up a monitoring service to detect API deployments and trigger the webhook

