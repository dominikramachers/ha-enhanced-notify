"""Konstanten der DORALAB-Benachrichtigungszentrale."""

from __future__ import annotations

DOMAIN = "doralab_notify"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_RETENTION_READ_DAYS = "retention_read_days"
CONF_RETENTION_DAYS = "retention_days"
CONF_MAX_ITEMS = "max_items"
CONF_IMPORT_PERSISTENT = "import_persistent"
CONF_DISMISS_IMPORTED = "dismiss_imported"
CONF_EXCLUDED_SERVICES = "excluded_notify_services"
CONF_PUSH_ICON = "push_icon"
CONF_PUSH_ICON_FORCE = "push_icon_force"

DEFAULT_RETENTION_READ_DAYS = 14
DEFAULT_RETENTION_DAYS = 60
DEFAULT_MAX_ITEMS = 200

PUSH_ALWAYS = "always"
PUSH_AWAY = "away"
PUSH_MODES = (PUSH_ALWAYS, PUSH_AWAY)

PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"

EVENT_CREATED = f"{DOMAIN}_created"
ACTION_READ_PREFIX = "DORALAB_READ_"
MOBILE_APP_ACTION_EVENT = "mobile_app_notification_action"

SOURCE_PERSISTENT = "persistent_notification"
TAG_PERSISTENT_PREFIX = "ha:"
