"""
Billing & Usage Tracking Module

This module is optional and only activated when BILLING_ENABLED=true.

For local/self-hosted deployments: Leave BILLING_ENABLED=false (default).
For remote/SaaS deployments: Set BILLING_ENABLED=true and configure Stripe keys.

Architecture:
    - billing.models: Database models for usage records, quotas, subscriptions
    - billing.service: Business logic for metering, quota enforcement
    - billing.api: REST endpoints for billing management
    - billing.middleware: Request-level usage tracking (injected conditionally)
"""
