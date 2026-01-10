"""
Core module for business rules and permissions.
"""

from app.core.enforcement import (
    EnforcementError,
    can_generate_invoice,
    can_publish_gallery,
    can_download_final_gallery,
    can_create_contract,
    enforce_job_workflow
)

from app.core.permissions import (
    Role,
    Permission,
    has_permission,
    require_permission,
    require_role
)

from app.core.decorators import (
    api_endpoint,
    public_endpoint,
    handle_errors,
    enforce_business_rule,
    admin_only,
    photographer_only,
    accountant_only,
    authenticated
)

__all__ = [
    # Enforcement
    'EnforcementError',
    'can_generate_invoice',
    'can_publish_gallery',
    'can_download_final_gallery',
    'can_create_contract',
    'enforce_job_workflow',
    
    # Permissions
    'Role',
    'Permission',
    'has_permission',
    'require_permission',
    'require_role',
    
    # Decorators
    'api_endpoint',
    'public_endpoint',
    'handle_errors',
    'enforce_business_rule',
    'admin_only',
    'photographer_only',
    'accountant_only',
    'authenticated',
]
