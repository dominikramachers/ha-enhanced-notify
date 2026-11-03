"""Sensor: Anzahl ungelesener Meldungen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .manager import NotificationManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([UnreadSensor(hass.data[DOMAIN], entry)])


class UnreadSensor(SensorEntity):
    """Ungelesene Benachrichtigungen (für Glocken-Zähler und Automationen)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "unread"
    _attr_icon = "mdi:bell-badge-outline"

    def __init__(self, manager: NotificationManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_unread"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Enhanced Notify",
            manufacturer="Enhanced Notify",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._manager.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> int:
        return self._manager.unread

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latest = self._manager.items[0] if self._manager.items else None
        attrs: dict[str, Any] = {"total": len(self._manager.items)}
        if latest:
            attrs.update(
                latest_title=latest["title"],
                latest_message=latest["message"],
                latest_type=latest["type"],
                latest_time=latest["updated"],
            )
        return attrs
