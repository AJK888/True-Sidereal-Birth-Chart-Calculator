# Troubleshooting Guide

**Last Updated:** 2025-01-22

---

## Common Issues and Solutions

### Database Connection Issues

**Problem:** Database connection errors or timeouts

**Solutions:**
1. Check `DATABASE_URL` environment variable
2. Verify database is accessible
3. Check connection pool settings
4. Review database logs

**Debug:**
```bash
# Check database health
curl https://your-api.onrender.com/health

# Check database connection
# Use admin endpoint: GET /api/v1/admin/system/health
```

---

### Slow API Responses

**Problem:** API endpoints responding slowly

**Solutions:**
1. Check query performance: `GET /api/v1/performance/queries`
2. Review slow queries in logs
3. Check cache hit rates: `GET /api/v1/performance/cache`
4. Review database indexes

**Debug:**
```bash
# Get performance summary
curl https://your-api.onrender.com/api/v1/performance/summary

# Check query statistics
curl https://your-api.onrender.com/api/v1/performance/queries
```

---

### High Error Rates

**Problem:** High number of errors in API

**Solutions:**
1. Check error summary: `GET /api/v1/monitoring/errors`
2. Review top errors: `GET /api/v1/monitoring/errors/top`
3. Check alerts: `GET /api/v1/monitoring/alerts`
4. Review application logs

**Debug:**
```bash
# Get error summary
curl https://your-api.onrender.com/api/v1/monitoring/errors

# Get top errors
curl https://your-api.onrender.com/api/v1/monitoring/errors/top
```

---

### Cache Issues

**Problem:** Cache not working or high cache miss rate

**Solutions:**
1. Check Redis connection: `GET /health`
2. Review cache statistics: `GET /api/v1/performance/cache`
3. Verify `REDIS_URL` is set (optional, falls back to in-memory)
4. Check cache hit rates

**Debug:**
```bash
# Check cache statistics
curl https://your-api.onrender.com/api/v1/performance/cache
```

---

### Authentication Issues

**Problem:** Authentication failures or token issues

**Solutions:**
1. Verify `SECRET_KEY` and `JWT_SECRET_KEY` are set
2. Check token expiration settings
3. Review authentication logs
4. Verify user accounts are active

**Debug:**
```bash
# Test authentication
curl -X POST https://your-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'
```

---

### Rate Limiting Issues

**Problem:** Rate limit errors

**Solutions:**
1. Check rate limit settings
2. Verify rate limit key generation
3. Review rate limit logs
4. Consider increasing limits if needed

---

### Background Job Issues

**Problem:** Background jobs failing or not processing

**Solutions:**
1. Check job queue status: `GET /api/v1/jobs/stats/queue`
2. Review job errors
3. Check job handlers are registered
4. Review job logs

**Debug:**
```bash
# Check job queue statistics
curl https://your-api.onrender.com/api/v1/jobs/stats/queue

# List jobs
curl https://your-api.onrender.com/api/v1/jobs
```

---

## Performance Issues

### Slow Chart Calculations

**Problem:** Chart calculations taking too long

**Solutions:**
1. Check Swiss Ephemeris files are present
2. Review calculation logic
3. Consider caching chart results
4. Check system resources

---

### High Memory Usage

**Problem:** Application using too much memory

**Solutions:**
1. Review cache size limits
2. Check for memory leaks
3. Review query result sizes
4. Consider pagination

---

## Monitoring and Debugging

### Health Checks

```bash
# Basic health check
curl https://your-api.onrender.com/health

# Readiness probe
curl https://your-api.onrender.com/health/ready

# Liveness probe
curl https://your-api.onrender.com/health/live
```

### Performance Monitoring

```bash
# Performance summary
curl https://your-api.onrender.com/api/v1/performance/summary

# Monitoring dashboard
curl https://your-api.onrender.com/api/v1/monitoring/dashboard
```

### Alerts

```bash
# Check alerts
curl https://your-api.onrender.com/api/v1/monitoring/alerts

# Check thresholds
curl -X POST https://your-api.onrender.com/api/v1/monitoring/alerts/check
```

---

## Getting Help

1. Check application logs
2. Review error aggregation: `GET /api/v1/monitoring/errors`
3. Check performance metrics: `GET /api/v1/performance/summary`
4. Review alerts: `GET /api/v1/monitoring/alerts`

---

## Emergency Procedures

### Restart Application

If the application becomes unresponsive:
1. Check health endpoints
2. Review recent errors
3. Restart the application
4. Monitor recovery

### Database Issues

If database issues occur:
1. Check database health: `GET /health`
2. Review connection pool
3. Check database logs
4. Consider read replica if available

### High Error Rate

If error rate spikes:
1. Check error summary: `GET /api/v1/monitoring/errors`
2. Review top errors
3. Check alerts
4. Review recent changes

---

**For more help, check the developer guide or contact support.**

