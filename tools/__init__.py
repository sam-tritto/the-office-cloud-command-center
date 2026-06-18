"""
ScrantonOS — Tool Dispatcher
==============================
Imports from mock_tools or cloud_tools based on the ENV config.
All other modules should import tools from this package, never
directly from mock_tools or cloud_tools.

Usage:
    from tools import fetch_app_logs, query_billing_data, apply_iam_grant
"""

from __future__ import annotations

from config import get_config

_cfg = get_config()

if _cfg.is_dev:
    from tools.mock_tools import (
        fetch_app_logs,
        analyze_logs_structured,
        query_billing_data,
        compute_billing_metrics,
        check_iam_whitelist,
        generate_approval_token,
        verify_approval_token,
        apply_iam_grant,
        hard_purge_user_data,
        scan_tech_debt,
        fetch_git_pipeline_status,
        fetch_firebase_crashlytics,
    )
else:
    from tools.cloud_tools import (
        fetch_app_logs,
        analyze_logs_structured,
        query_billing_data,
        compute_billing_metrics,
        check_iam_whitelist,
        generate_approval_token,
        verify_approval_token,
        apply_iam_grant,
        hard_purge_user_data,
        scan_tech_debt,
        fetch_git_pipeline_status,
        fetch_firebase_crashlytics,
    )

__all__ = [
    "fetch_app_logs",
    "analyze_logs_structured",
    "query_billing_data",
    "compute_billing_metrics",
    "check_iam_whitelist",
    "generate_approval_token",
    "verify_approval_token",
    "apply_iam_grant",
    "hard_purge_user_data",
    "scan_tech_debt",
    "fetch_git_pipeline_status",
    "fetch_firebase_crashlytics",
]

