"""DORALAB Benachrichtigungszentrale.

Zentrale Meldungsliste mit Lesestatus, Push-Steuerung pro Meldungstyp und
Person sowie Übernahme/Übersetzung der HA-eigenen Benachrichtigungen.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import (
    CONF_DISMISS_IMPORTED,
    CONF_IMPORT_PERSISTENT,
    DOMAIN,
    MOBILE_APP_ACTION_EVENT,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PUSH_MODES,
)
from .manager import NotificationManager
from .websocket_api import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

FRONTEND_FILE = Path(__file__).parent / "frontend" / "doralab-notify.js"
FRONTEND_URL = f"/{DOMAIN}/doralab-notify.js"

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Icon eines Typs: Icon-Name (mdi:cog), Pfad auf diese HA-Instanz (/local/logo.png),
# Webadresse (https://...) oder eingebettetes Bild (data:image/png;base64,...).
_ICON_REF = re.compile(
    r"^(?:[a-z][a-z0-9_-]*:[a-z0-9_.-]+"
    r"|/(?!/)\S*"
    r"|https?://\S+"
    r"|data:image/(?:png|jpeg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+)$"
)
MAX_ICON_LENGTH = 20000


def _icon_ref(value: Any) -> str:
    """Icon-Angabe prüfen; leer bedeutet \"Icon der Kategorie\"."""
    text = cv.string(value).strip()
    if text and (len(text) > MAX_ICON_LENGTH or not _ICON_REF.match(text)):
        raise vol.Invalid(
            "Ungültiges Icon: erlaubt sind mdi:name, ein Pfad wie /local/logo.png, "
            "eine http(s)-Adresse oder data:image/...;base64,..."
        )
    return text


SEND_SCHEMA = vol.Schema(
    {
        vol.Required("type"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("tag"): cv.string,
        vol.Optional("link"): cv.string,
        vol.Optional("icon"): cv.string,
        vol.Optional("push", default=True): cv.boolean,
        vol.Optional("priority"): vol.In((PRIORITY_NORMAL, PRIORITY_HIGH)),
        vol.Optional("category"): cv.string,
        vol.Optional("type_name"): cv.string,
        vol.Optional("type_icon"): _icon_ref,
        vol.Optional("data"): dict,
        vol.Optional("once", default=False): cv.boolean,
        vol.Optional("baseline", default=False): cv.boolean,
    }
)
MARK_READ_SCHEMA = vol.Schema(
    {
        vol.Optional("ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("all", default=False): cv.boolean,
        vol.Optional("read", default=True): cv.boolean,
    }
)
DELETE_SCHEMA = vol.Schema(
    {
        vol.Optional("ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("tags"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("all", default=False): cv.boolean,
        vol.Optional("only_read", default=False): cv.boolean,
    }
)
SET_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): cv.string,
        vol.Optional("recipients"): vol.Any(None, vol.All(cv.ensure_list, [cv.entity_id])),
        vol.Optional("push_when"): vol.In(PUSH_MODES),
        vol.Optional("reset", default=False): cv.boolean,
    }
)


def _manager(hass: HomeAssistant) -> NotificationManager:
    manager: NotificationManager | None = hass.data.get(DOMAIN)
    if manager is None:
        raise ServiceValidationError("Die Benachrichtigungszentrale ist nicht eingerichtet")
    return manager


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Glocke, Meldungsliste und Karten (JavaScript) selbst ausliefern und in HA laden.

    Damit ist keine Dashboard-Ressource nötig. Das Skript lädt sich nur einmal
    (Schutz im Skript), eine zusätzlich von Hand eingebundene Kopie schadet nicht.
    """
    if getattr(hass, "http", None) is None or "frontend" not in hass.config.components:
        _LOGGER.debug("Kein Frontend/HTTP vorhanden, Oberfläche wird nicht ausgeliefert")
        return
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL, str(FRONTEND_FILE), cache_headers=False)]
        )
        version = (await async_get_integration(hass, DOMAIN)).version
        add_extra_js_url(hass, f"{FRONTEND_URL}?v={version}")
    except Exception:  # noqa: BLE001 - die Oberfläche ist optional, Dienste laufen weiter
        _LOGGER.exception("Die Oberfläche konnte nicht registriert werden")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Websocket-API und Services registrieren."""
    async_register_websocket_api(hass)

    async def handle_send(call: ServiceCall) -> ServiceResponse:
        d = call.data
        return await _manager(hass).async_send(
            d["type"],
            d["message"],
            title=d.get("title"),
            tag=d.get("tag"),
            link=d.get("link"),
            icon=d.get("icon"),
            push=d["push"],
            priority=d.get("priority"),
            category=d.get("category"),
            type_name=d.get("type_name"),
            type_icon=d.get("type_icon"),
            data=d.get("data"),
            once=d["once"],
            baseline=d["baseline"],
        )

    async def handle_mark_read(call: ServiceCall) -> None:
        d = call.data
        await _manager(hass).async_mark_read(d.get("ids"), mark_all=d["all"], read=d["read"])

    async def handle_delete(call: ServiceCall) -> None:
        d = call.data
        await _manager(hass).async_delete(
            d.get("ids"), delete_all=d["all"], only_read=d["only_read"], tags=d.get("tags")
        )

    async def handle_set_type(call: ServiceCall) -> None:
        d = call.data
        kwargs: dict[str, Any] = {"reset": d["reset"]}
        if "recipients" in d:
            kwargs["recipients"] = d["recipients"]
        if "push_when" in d:
            kwargs["push_when"] = d["push_when"]
        _manager(hass).async_set_type(d["type"], **kwargs)

    await _async_register_frontend(hass)

    hass.services.async_register(
        DOMAIN, "send", handle_send, schema=SEND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, "mark_read", handle_mark_read, schema=MARK_READ_SCHEMA)
    hass.services.async_register(DOMAIN, "delete", handle_delete, schema=DELETE_SCHEMA)
    hass.services.async_register(DOMAIN, "set_type", handle_set_type, schema=SET_TYPE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = NotificationManager(hass, entry)
    await manager.async_load()
    hass.data[DOMAIN] = manager

    # Button „Gelesen“ in der Push-Meldung
    @callback
    def _on_push_action(event: Any) -> None:
        hass.async_create_task(manager.async_handle_push_action(event.data.get("action")))

    entry.async_on_unload(hass.bus.async_listen(MOBILE_APP_ACTION_EVENT, _on_push_action))

    # Persistente HA-Meldungen übernehmen und übersetzen
    if entry.options.get(CONF_IMPORT_PERSISTENT, True):
        from homeassistant.components import persistent_notification as pn

        dismiss = entry.options.get(CONF_DISMISS_IMPORTED, True)

        async def _import(notification_id: str, notification: dict[str, Any]) -> None:
            await manager.async_import_persistent(
                notification_id, notification.get("title"), notification.get("message")
            )
            if dismiss:
                pn.async_dismiss(hass, notification_id)

        @callback
        def _on_persistent(update_type: Any, notifications: dict[str, Any]) -> None:
            if update_type not in (
                pn.UpdateType.ADDED,
                pn.UpdateType.UPDATED,
                pn.UpdateType.CURRENT,
            ):
                return
            for notification_id, notification in notifications.items():
                hass.async_create_task(_import(notification_id, notification))

        entry.async_on_unload(pn.async_register_callback(hass, _on_persistent))

        # Bereits vorhandene Meldungen beim Start übernehmen. Dafür gibt es keine
        # öffentliche Schnittstelle, daher abgesichert.
        try:
            existing = dict(pn._async_get_or_create_notifications(hass))  # noqa: SLF001
        except Exception:  # noqa: BLE001
            existing = {}
        for notification_id, notification in existing.items():
            hass.async_create_task(_import(notification_id, notification))

    # Aufräumen: einmal täglich nachts und beim Start
    @callback
    def _daily_cleanup(_now: Any) -> None:
        hass.async_create_task(manager.async_cleanup())

    entry.async_on_unload(async_track_time_change(hass, _daily_cleanup, hour=3, minute=30, second=0))
    await manager.async_cleanup()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager: NotificationManager = hass.data.pop(DOMAIN)
        await manager.async_flush()
    return unloaded
