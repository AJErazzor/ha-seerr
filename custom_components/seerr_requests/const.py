"""Constants for the Seerr Requests integration."""

from __future__ import annotations

DOMAIN = "seerr_requests"
VERSION = "0.1.0"

CONF_EXTERNAL_URL = "external_url"
CONF_WEBHOOK_ID = "webhook_id"
CONF_NOTIFY_SERVICES = "notify_services"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 15

CARD_FILENAME = "seerr-requests-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"

EVENT_NEW_REQUEST = f"{DOMAIN}_new_request"
EVENT_REQUEST_ACTIONED = f"{DOMAIN}_request_actioned"

SERVICE_APPROVE = "approve"
SERVICE_DECLINE = "decline"
ATTR_REQUEST_ID = "request_id"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

# Seerr request status codes
REQUEST_STATUS_PENDING = 1
