# Cleanup Guide: Removing Old Endpoint Definitions

## Status

✅ **Routers Created and Included** - All endpoints have been moved to routers in `app/api/v1/`  
⚠️ **Old Endpoints Partially Commented** - Some decorators commented, but function bodies remain active  
❌ **Syntax Errors Present** - Partial commenting has caused syntax errors that need fixing

## What Was Done

1. ✅ Created all routers in `app/api/v1/`
2. ✅ Included routers in `api.py`
3. ⚠️ Started commenting out old endpoint decorators
4. ❌ Function bodies still active (causing syntax errors)

## Current Issues

The file `api.py` has syntax errors because:
- Function decorators are commented out
- But function bodies are still active
- This creates unmatched parentheses and unterminated strings

## Recommended Approach

### Option 1: Remove Old Endpoints Entirely (Recommended)

After testing that routers work correctly, **delete** the old endpoint functions entirely:

1. **Charts Endpoints** (Lines ~1160-1682)
   - Delete `calculate_chart_endpoint` function
   - Delete `generate_reading_endpoint` function  
   - Delete `get_reading_endpoint` function

2. **Auth Endpoints** (Lines ~1701-1779)
   - Delete `register_endpoint` function
   - Delete `login_endpoint` function
   - Delete `get_current_user_endpoint` function

3. **Saved Charts Endpoints** (Lines ~1815-1903)
   - Delete `save_chart_endpoint` function
   - Delete `list_charts_endpoint` function
   - Delete `get_chart_endpoint` function
   - Delete `delete_chart_endpoint` function

4. **Subscription Endpoints** (Lines ~2532-2654)
   - Delete `get_subscription_status` function
   - Delete `create_reading_checkout_endpoint` function
   - Delete `create_subscription_checkout_endpoint` function
   - Delete `render_deploy_webhook` function
   - Delete `stripe_webhook_endpoint` function

5. **Utility Endpoints** (Line ~2412)
   - Delete `log_clicks_endpoint` function

### Option 2: Fix Commenting (If You Want to Keep Code for Reference)

If you want to keep the old code for reference, you need to comment out **entire functions**, not just decorators:

```python
# @app.post("/calculate_chart")
# @limiter.limit("200/day")
# async def calculate_chart_endpoint(...):
#     # ... entire function body commented ...
```

## Testing Before Cleanup

1. **Start the server:**
   ```bash
   uvicorn api:app --reload
   ```

2. **Run test script:**
   ```bash
   python test_endpoints.py
   ```

3. **Verify all endpoints work through routers:**
   - Check that endpoints return proper responses (not 404)
   - Verify no duplicate route errors

## After Cleanup

Once old endpoints are removed:

1. ✅ All endpoints will be served through routers
2. ✅ Codebase will be cleaner and more maintainable
3. ✅ No duplicate route conflicts
4. ✅ Easier to test and maintain

## Files to Keep

- ✅ `app/api/v1/*.py` - All router files (keep)
- ✅ `app/config.py` - Configuration module (keep)
- ✅ `app/core/cache.py` - Cache module (keep)
- ✅ `test_endpoints.py` - Test script (keep for future use)

## Files That Can Be Removed After Cleanup

- ❌ Old endpoint functions in `api.py` (remove after verification)
- ❌ `comment_out_old_endpoints.py` (helper script, can remove)
- ❌ `ENDPOINT_MIGRATION_STATUS.md` (can archive)

## Next Steps

1. **Fix syntax errors** - Either fully comment out functions or remove them
2. **Test endpoints** - Verify routers work correctly
3. **Remove old code** - Delete old endpoint functions
4. **Update imports** - Consider using `app.config` instead of direct `os.getenv()`

