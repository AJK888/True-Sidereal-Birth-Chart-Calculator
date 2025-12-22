"""
Helper script for using Render MCP server.

This script demonstrates how to interact with Render services
using the MCP (Model Context Protocol) server.

Usage:
    python scripts/render_mcp_helper.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_render_services_info():
    """Print information about Render services."""
    print("=" * 60)
    print("Render MCP Server - Service Information")
    print("=" * 60)
    print("\nAvailable MCP Functions:")
    print("- mcp_render_list_services() - List all services")
    print("- mcp_render_get_service(service_id) - Get service details")
    print("- mcp_render_list_deploys(service_id) - List deployments")
    print("- mcp_render_get_deploy(service_id, deploy_id) - Get deploy details")
    print("- mcp_render_list_logs(resource) - Get service logs")
    print("- mcp_render_get_metrics(resource_id, metric_types) - Get metrics")
    print("\nNote: You need to select a workspace first using:")
    print("  mcp_render_select_workspace(ownerID)")
    print("\nTo use these functions, call them directly in your IDE/terminal")
    print("or use the MCP server interface.")
    print("=" * 60)


def print_deployment_checklist():
    """Print deployment verification checklist."""
    print("\n" + "=" * 60)
    print("Deployment Verification Checklist")
    print("=" * 60)
    print("\n1. Check Service Status:")
    print("   - Use mcp_render_list_services() to see all services")
    print("   - Verify 'true-sidereal-api' is running")
    print("\n2. Check Latest Deployment:")
    print("   - Use mcp_render_list_deploys(service_id)")
    print("   - Verify latest deploy status is 'live'")
    print("\n3. Check Logs:")
    print("   - Use mcp_render_list_logs(resource=[service_id])")
    print("   - Look for 'Database migrations completed successfully'")
    print("   - Check for any errors")
    print("\n4. Check Metrics:")
    print("   - Use mcp_render_get_metrics()")
    print("   - Verify CPU/memory usage is normal")
    print("   - Check HTTP request counts")
    print("\n5. Test Endpoints:")
    print("   - GET /ping - Should return 200")
    print("   - GET / - Should return 200")
    print("   - GET /check_email_config - Should return config status")
    print("=" * 60)


if __name__ == "__main__":
    print_render_services_info()
    print_deployment_checklist()
    
    print("\n" + "=" * 60)
    print("Quick Start")
    print("=" * 60)
    print("\nTo use Render MCP in Cursor:")
    print("1. Select your Render workspace (if not already selected)")
    print("2. Use MCP functions directly in chat:")
    print("   - 'List my Render services'")
    print("   - 'Show me the latest deployment for true-sidereal-api'")
    print("   - 'Get logs for my API service'")
    print("   - 'Show metrics for my service'")
    print("\nThe MCP server will handle the API calls automatically!")
    print("=" * 60)

