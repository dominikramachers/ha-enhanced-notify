"""Websocket-API für Karten (Glocke, Liste, Einstellungsübersicht)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, PUSH_MODES
from .manager import NotificationManager


def _manager(hass: HomeAssistant) -> NotificationManager | None:
    return hass.data.get(DOMAIN)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_mark_read)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_set_type)


def _not_loaded(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_error(msg["id"], "not_loaded", "Benachrichtigungszentrale ist nicht geladen")


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Liefert den kompletten Stand und danach bei jeder Änderung einen neuen."""
    manager = _manager(hass)
    if manager is None:
        _not_loaded(connection, msg)
        return

    @callback
    def forward() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], manager.snapshot()))

    connection.subscriptions[msg["id"]] = manager.async_add_listener(forward)
    connection.send_result(msg["id"])
    forward()


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/mark_read",
        vol.Optional("ids"): [str],
        vol.Optional("all", default=False): bool,
        vol.Optional("read", default=True): bool,
    }
)
@websocket_api.async_response
async def ws_mark_read(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    manager = _manager(hass)
    if manager is None:
        _not_loaded(connection, msg)
        return
    count = await manager.async_mark_read(
        msg.get("ids"), mark_all=msg["all"], read=msg["read"]
    )
    connection.send_result(msg["id"], {"changed": count})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete",
        vol.Optional("ids"): [str],
        vol.Optional("all", default=False): bool,
        vol.Optional("only_read", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    manager = _manager(hass)
    if manager is None:
        _not_loaded(connection, msg)
        return
    count = await manager.async_delete(
        msg.get("ids"), delete_all=msg["all"], only_read=msg["only_read"]
    )
    connection.send_result(msg["id"], {"removed": count})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_type",
        vol.Required("type_id"): str,
        vol.Optional("recipients"): vol.Any(None, [str]),
        vol.Optional("push_when"): vol.In(PUSH_MODES),
        vol.Optional("reset", default=False): bool,
    }
)
@websocket_api.require_admin
@callback
def ws_set_type(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Push-Empfänger und -Modus eines Typs ändern (nur Administratoren)."""
    manager = _manager(hass)
    if manager is None:
        _not_loaded(connection, msg)
        return
    kwargs: dict[str, Any] = {"reset": msg["reset"]}
    if "recipients" in msg:
        kwargs["recipients"] = msg["recipients"]
    if "push_when" in msg:
        kwargs["push_when"] = msg["push_when"]
    try:
        manager.async_set_type(msg["type_id"], **kwargs)
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "invalid", str(err))
        return
    connection.send_result(msg["id"])
