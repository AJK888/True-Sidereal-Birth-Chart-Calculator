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

### Step 3: That's It!

The API service is now configured to automatically trigger the webpage deployment whenever it starts up (which happens after every deployment).

**How it works:**
- When the API service deploys and starts, it automatically calls the webpage's Deploy Hook URL
- The webpage service will then start deploying automatically
- No additional configuration needed!

## How It Works

1. API service completes deployment and starts up
2. On startup, the API automatically calls the webpage's Deploy Hook URL
3. Webpage service receives the deploy trigger and starts deploying automatically
4. Both services are now in sync!

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

### Webpage not deploying automatically

- The deployment trigger happens on API startup, so check API logs for messages like:
  - "Triggering webpage deployment via deploy hook..."
  - "Successfully triggered webpage deployment"
- If you see warnings, verify the `WEBPAGE_DEPLOY_HOOK_URL` is set correctly
- The trigger happens automatically - no manual steps needed!

