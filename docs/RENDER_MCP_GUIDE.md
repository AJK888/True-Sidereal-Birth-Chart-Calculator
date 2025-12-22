# Render MCP Server Guide

**Date:** 2025-01-21  
**Status:** ✅ Integrated

---

## Overview

The Render MCP (Model Context Protocol) server provides programmatic access to your Render services, allowing you to monitor, manage, and interact with your deployments directly from Cursor.

---

## Available Functions

### Service Management
- `mcp_render_list_services()` - List all services in your account
- `mcp_render_get_service(service_id)` - Get detailed service information
- `mcp_render_update_web_service(service_id)` - Update service configuration

### Deployment Management
- `mcp_render_list_deploys(service_id)` - List all deployments for a service
- `mcp_render_get_deploy(service_id, deploy_id)` - Get deployment details

### Monitoring & Logs
- `mcp_render_list_logs(resource)` - Get logs for a service
- `mcp_render_get_metrics(resource_id, metric_types)` - Get performance metrics
- `mcp_render_list_log_label_values(resource, label)` - Get log label values

### Database Management
- `mcp_render_list_postgres_instances()` - List Postgres databases
- `mcp_render_get_postgres(postgres_id)` - Get database details
- `mcp_render_query_render_postgres(postgres_id, sql)` - Run SQL queries

### Workspace Management
- `mcp_render_list_workspaces()` - List available workspaces
- `mcp_render_select_workspace(ownerID)` - Select a workspace
- `mcp_render_get_selected_workspace()` - Get current workspace

---

## Usage Examples

### In Cursor Chat

You can use natural language to interact with Render:

```
"List my Render services"
"Show me the latest deployment for true-sidereal-api"
"Get logs for my API service from the last hour"
"Show me metrics for my service"
"Check if migrations ran successfully in the logs"
```

### Direct Function Calls

If you need to call functions directly:

```python
# List all services
services = mcp_render_list_services()

# Get service details
service = mcp_render_get_service(service_id="srv-xxxxx")

# Get latest deployment
deploys = mcp_render_list_deploys(service_id="srv-xxxxx")
latest_deploy = deploys[0] if deploys else None

# Get logs
logs = mcp_render_list_logs(
    resource=["srv-xxxxx"],
    startTime="2025-01-21T00:00:00Z",
    endTime="2025-01-21T23:59:59Z"
)

# Get metrics
metrics = mcp_render_get_metrics(
    resourceId="srv-xxxxx",
    metricTypes=["cpu_usage", "memory_usage", "http_request_count"],
    startTime="2025-01-21T00:00:00Z",
    endTime="2025-01-21T23:59:59Z"
)
```

---

## Deployment Verification Workflow

### 1. Check Service Status
```
"List my Render services and show their status"
```

### 2. Verify Latest Deployment
```
"Show me the latest deployment for true-sidereal-api"
```

Look for:
- Status: `live` ✅
- Build status: `succeeded` ✅
- No errors in build logs

### 3. Check Migration Logs
```
"Get logs for my API service and search for 'migration'"
```

Look for:
- `"Running database migrations..."`
- `"Database migrations completed successfully"` ✅
- No migration errors

### 4. Verify Application Started
```
"Get logs for my API service and search for 'started' or 'uvicorn'"
```

Look for:
- `"Application startup complete"`
- `"Uvicorn running on"`
- No startup errors

### 5. Check Metrics
```
"Show me CPU and memory usage for my API service"
```

Verify:
- CPU usage is reasonable (< 80%)
- Memory usage is stable
- HTTP requests are being served

---

## Common Tasks

### Monitor Service Health
```
"Show me the health status and metrics for my API service"
```

### Debug Issues
```
"Get error logs from my API service in the last hour"
```

### Check Database
```
"List my Postgres databases"
"Show me the connection details for my database"
```

### View Deployment History
```
"Show me all deployments for my API service"
```

### Check Resource Usage
```
"Show me CPU, memory, and request metrics for my service"
```

---

## Troubleshooting

### Migrations Not Running
1. Check logs: `"Get logs for my API service"`
2. Search for: `"run_migrations"` or `"alembic"`
3. Verify `scripts/run_migrations.py` is in the start command
4. Check for errors in migration logs

### Service Not Starting
1. Check build logs: `"Show me the latest deployment build logs"`
2. Check runtime logs: `"Get logs for my API service"`
3. Look for import errors or missing dependencies

### High Resource Usage
1. Check metrics: `"Show me CPU and memory metrics"`
2. Review logs for errors or infinite loops
3. Check request counts: `"Show me HTTP request metrics"`

---

## Best Practices

1. **Regular Monitoring**
   - Check service status daily
   - Monitor metrics weekly
   - Review logs when issues occur

2. **Before Deployments**
   - Verify migrations are ready
   - Check service health
   - Review recent errors

3. **After Deployments**
   - Verify deployment succeeded
   - Check migration logs
   - Test critical endpoints
   - Monitor metrics for anomalies

4. **Log Management**
   - Use log filters to find specific issues
   - Check logs from different time ranges
   - Search for error patterns

---

## Integration with Your Workflow

### Pre-Deployment Checklist
- [ ] Migrations tested locally
- [ ] Service health checked
- [ ] Recent errors reviewed

### Post-Deployment Checklist
- [ ] Deployment status verified
- [ ] Migrations completed successfully
- [ ] Service started correctly
- [ ] Endpoints responding
- [ ] Metrics normal

---

## Quick Reference

| Task | MCP Function | Example Query |
|------|--------------|---------------|
| List services | `list_services()` | "List my Render services" |
| Get service | `get_service()` | "Show details for true-sidereal-api" |
| List deploys | `list_deploys()` | "Show deployments for my API" |
| Get logs | `list_logs()` | "Get logs for my service" |
| Get metrics | `get_metrics()` | "Show metrics for my service" |
| Query DB | `query_render_postgres()` | "Query my database" |

---

**The Render MCP server is now integrated and ready to use!** 🎉

Use natural language queries in Cursor to interact with your Render services.

