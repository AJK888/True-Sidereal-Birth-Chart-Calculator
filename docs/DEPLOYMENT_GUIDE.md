# Deployment Guide

## Overview

This guide covers deploying the Synthesis Astrology API to production environments.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or SQLite for development)
- Redis (optional, for caching)
- Environment variables configured

---

## Environment Variables

### Required Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Security
SECRET_KEY=your-secret-key-here  # For JWT tokens

# AI Services
GEMINI_API_KEY=your-gemini-api-key

# Email
SENDGRID_API_KEY=your-sendgrid-api-key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com

# Swiss Ephemeris
SWEP_PATH=/path/to/swiss/ephemeris/files
```

### Optional Variables

```bash
# Caching
REDIS_URL=redis://host:port/db
CACHE_EXPIRY_HOURS=24

# Monitoring
LOGTAIL_API_KEY=your-logtail-key

# Deployment
WEBPAGE_DEPLOY_HOOK_URL=https://your-webhook-url
```

---

## Deployment Methods

### 1. Render.com (Current Production)

**Automatic Deployment:**
- Push to `main` branch triggers deployment
- Render automatically runs migrations
- Health checks ensure service is ready

**Manual Deployment:**
1. Go to Render dashboard
2. Select your service
3. Click "Manual Deploy"
4. Select branch/commit

**Health Checks:**
- Readiness: `GET /health/ready`
- Liveness: `GET /health/live`
- Full Health: `GET /health`

**Configuration:**
- See `render.yaml` for service configuration
- Environment variables set in Render dashboard

---

### 2. Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and Run:**
```bash
docker build -t synthesis-astrology-api .
docker run -p 8000:8000 --env-file .env synthesis-astrology-api
```

---

### 3. Manual Deployment

**Steps:**
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

3. **Start server:**
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

**Production Server (Gunicorn):**
```bash
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Health Checks

### Readiness Probe

**Endpoint:** `GET /health/ready`

**Use Case:** Determine if service can accept traffic

**Response:**
```json
{
  "ready": true,
  "status": "ready",
  "timestamp": "2025-01-22T12:00:00",
  "database": "healthy"
}
```

**Kubernetes Example:**
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

### Liveness Probe

**Endpoint:** `GET /health/live`

**Use Case:** Determine if service should be restarted

**Response:**
```json
{
  "alive": true,
  "status": "alive",
  "timestamp": "2025-01-22T12:00:00"
}
```

**Kubernetes Example:**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Comprehensive Health Check

**Endpoint:** `GET /health`

**Use Case:** Monitor all dependencies

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-22T12:00:00",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5.2,
      "pool": {
        "size": 5,
        "checked_in": 3,
        "checked_out": 2
      }
    },
    "cache": {
      "status": "healthy",
      "type": "redis",
      "response_time_ms": 1.5
    },
    "ephemeris": {
      "status": "healthy",
      "path": "/app/swiss_ephemeris"
    }
  }
}
```

---

## Database Migrations

### Automatic Migrations (Render)

Migrations run automatically on deployment via `render.yaml`:

```yaml
services:
  - type: web
    name: api
    buildCommand: pip install -r requirements.txt && alembic upgrade head
```

### Manual Migrations

**Create migration:**
```bash
alembic revision --autogenerate -m "Description"
```

**Apply migrations:**
```bash
alembic upgrade head
```

**Rollback:**
```bash
alembic downgrade -1
```

---

## Monitoring

### Metrics Endpoint

**Endpoint:** `GET /metrics`

Returns performance metrics and health status.

### Logging

- **Structured Logging:** JSON format for production
- **Logtail Integration:** Centralized log management
- **Log Levels:** INFO, WARNING, ERROR

### Alerts

Configure alerts for:
- High error rates (>5%)
- Slow response times (>2s average)
- Unhealthy dependencies
- Database connection failures

---

## Zero-Downtime Deployment

### Strategy

1. **Blue-Green Deployment:**
   - Deploy new version to separate instance
   - Health check new instance
   - Switch traffic to new instance
   - Keep old instance for rollback

2. **Rolling Deployment:**
   - Deploy to subset of instances
   - Health check each instance
   - Gradually shift traffic
   - Monitor for issues

### Graceful Shutdown

The application includes graceful shutdown handlers that:
- Close database connections
- Close Redis connections
- Complete in-flight requests
- Log shutdown status

**Shutdown Timeout:** 30 seconds (configurable)

---

## Rollback Procedures

### Render.com

1. Go to Render dashboard
2. Select service
3. Go to "Deploys" tab
4. Select previous successful deploy
5. Click "Redeploy"

### Manual Rollback

1. **Revert code:**
   ```bash
   git revert HEAD
   git push
   ```

2. **Rollback database (if needed):**
   ```bash
   alembic downgrade -1
   ```

3. **Restart service:**
   ```bash
   # Restart via your deployment method
   ```

---

## Troubleshooting

### Deployment Failures

**Check logs:**
- Render: Dashboard → Logs
- Docker: `docker logs <container>`
- Manual: Application logs

**Common Issues:**
- Missing environment variables
- Database connection failures
- Migration errors
- Port conflicts

### Health Check Failures

**Database Unhealthy:**
- Check `DATABASE_URL` is correct
- Verify database is accessible
- Check connection pool settings

**Cache Unhealthy:**
- Check `REDIS_URL` (if using Redis)
- Verify Redis is accessible
- Falls back to in-memory if Redis unavailable

**Ephemeris Unhealthy:**
- Verify `SWEP_PATH` is correct
- Check ephemeris files exist
- Verify file permissions

---

## Performance Optimization

### Database

- Use connection pooling
- Optimize queries with indexes
- Monitor slow queries
- Use read replicas for scaling

### Caching

- Enable Redis for production
- Set appropriate cache expiry
- Monitor cache hit rates
- Use cache warming for critical data

### Application

- Use async operations where possible
- Monitor response times
- Optimize slow endpoints
- Use background jobs for long tasks

---

## Security

### Production Checklist

- [ ] `SECRET_KEY` is strong and unique
- [ ] Database credentials are secure
- [ ] API keys are stored securely
- [ ] HTTPS is enabled
- [ ] CORS is properly configured
- [ ] Rate limiting is enabled
- [ ] Security headers are set
- [ ] Input validation is comprehensive

---

## Backup and Recovery

### Database Backups

**Automated (Render):**
- Render provides automatic backups
- Configure backup schedule in dashboard

**Manual:**
```bash
pg_dump $DATABASE_URL > backup.sql
```

### Recovery

1. Restore database from backup
2. Verify data integrity
3. Run health checks
4. Monitor for issues

---

## Scaling

### Vertical Scaling

- Increase instance size (CPU/RAM)
- Increase database resources
- Optimize application code

### Horizontal Scaling

- Deploy multiple instances
- Use load balancer
- Share Redis cache
- Use database read replicas

---

## Support

For deployment issues:
- Check logs first
- Review health check endpoints
- Verify environment variables
- Contact support if needed

---

**Last Updated:** 2025-01-22

