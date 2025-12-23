"""
Security Audit Utilities

Utilities for security auditing and vulnerability detection.
"""

import logging
import os
from typing import Dict, Any, List
from datetime import datetime

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class SecurityAuditor:
    """Security audit utilities."""
    
    @staticmethod
    def audit_environment() -> Dict[str, Any]:
        """Audit environment configuration for security issues."""
        issues = []
        warnings = []
        
        # Check for default/weak secrets
        secret_key = os.getenv("SECRET_KEY", "")
        if not secret_key or secret_key == "your-secret-key-change-in-production":
            issues.append({
                "severity": "critical",
                "issue": "Default or missing SECRET_KEY",
                "recommendation": "Set a strong, unique SECRET_KEY in environment variables"
            })
        
        jwt_secret = os.getenv("JWT_SECRET_KEY", "")
        if not jwt_secret or jwt_secret == "your-secret-key-change-in-production-please-use-env-var":
            issues.append({
                "severity": "critical",
                "issue": "Default or missing JWT_SECRET_KEY",
                "recommendation": "Set a strong, unique JWT_SECRET_KEY in environment variables"
            })
        
        # Check database URL
        database_url = os.getenv("DATABASE_URL", "")
        if database_url.startswith("sqlite"):
            warnings.append({
                "severity": "warning",
                "issue": "Using SQLite database (not recommended for production)",
                "recommendation": "Use PostgreSQL for production deployments"
            })
        
        # Check HTTPS enforcement
        api_base_url = os.getenv("API_BASE_URL", "")
        if api_base_url and not api_base_url.startswith("https://"):
            warnings.append({
                "severity": "warning",
                "issue": "API base URL not using HTTPS",
                "recommendation": "Use HTTPS for all API endpoints in production"
            })
        
        # Check admin email
        admin_email = os.getenv("ADMIN_EMAIL", "")
        if not admin_email:
            warnings.append({
                "severity": "warning",
                "issue": "ADMIN_EMAIL not configured",
                "recommendation": "Set ADMIN_EMAIL for admin notifications"
            })
        
        return {
            "audit_date": datetime.utcnow().isoformat(),
            "critical_issues": [i for i in issues if i["severity"] == "critical"],
            "warnings": warnings,
            "total_issues": len(issues) + len(warnings),
            "status": "secure" if not issues else "vulnerable"
        }
    
    @staticmethod
    def audit_dependencies() -> Dict[str, Any]:
        """Audit dependencies for known vulnerabilities."""
        # This would integrate with a vulnerability scanner
        # For now, return basic info
        return {
            "audit_date": datetime.utcnow().isoformat(),
            "status": "not_scanned",
            "message": "Dependency scanning not implemented. Consider using safety or pip-audit."
        }
    
    @staticmethod
    def get_security_recommendations() -> List[Dict[str, Any]]:
        """Get security recommendations."""
        recommendations = [
            {
                "priority": "high",
                "category": "authentication",
                "recommendation": "Implement refresh tokens for better security",
                "description": "Refresh tokens allow for shorter access token lifetimes"
            },
            {
                "priority": "high",
                "category": "authorization",
                "recommendation": "Implement rate limiting per user",
                "description": "Prevent abuse by limiting requests per user"
            },
            {
                "priority": "medium",
                "category": "data",
                "recommendation": "Encrypt sensitive data at rest",
                "description": "Ensure sensitive user data is encrypted in the database"
            },
            {
                "priority": "medium",
                "category": "monitoring",
                "recommendation": "Set up security monitoring and alerting",
                "description": "Monitor for suspicious activity and security events"
            },
            {
                "priority": "low",
                "category": "headers",
                "recommendation": "Add HSTS headers",
                "description": "HTTP Strict Transport Security headers for better security"
            }
        ]
        
        return recommendations
    
    @staticmethod
    def get_security_status() -> Dict[str, Any]:
        """Get overall security status."""
        env_audit = SecurityAuditor.audit_environment()
        
        return {
            "status": env_audit["status"],
            "environment_audit": env_audit,
            "recommendations": SecurityAuditor.get_security_recommendations(),
            "timestamp": datetime.utcnow().isoformat()
        }

