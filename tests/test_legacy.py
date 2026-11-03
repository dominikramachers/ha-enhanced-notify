"""Umstieg von „DORALAB Benachrichtigungen“ (doralab_notify) auf Enhanced Notify."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.enhanced_notify.const import DOMAIN, LEGACY_DOMAIN

from .test_integration import _add_person, _sensor_state

OLD_SENSOR = "sensor.doralab_benachrichtigungen_ungelesen"
OLD_ITEMS = {
    "items": [
        {
            "id": "abc123",
            "type": "klingel",
            "category": "haus",
            "title": "Klingel",
            "message": "Es hat geklingelt",
            "created": "2026-10-01T10:00:00+00:00",
            "updated": "2026-10-01T10:00:00+00:00",
            "read": False,
            "tag": None,
            "data": {},
        }
    ],
    "type_settings": {"klingel": {"recipients": ["person.dominik"]}},
    "seen": [],
    "announced": {},
}


def _old_entry(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    """Alten Eintrag samt Sensor und Gerät anlegen, wie ihn 0.3.x hinterlässt."""
    old = MockConfigEntry(domain=LEGACY_DOMAIN, data={}, options=options or {}, title="DORALAB")
    old.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=old.entry_id, identifiers={(LEGACY_DOMAIN, old.entry_id)}, name="DORALAB"
    )
    er.async_get(hass).async_get_or_create(
        "sensor",
        LEGACY_DOMAIN,
        f"{old.entry_id}_unread",
        config_entry=old,
        device_id=device.id,
        suggested_object_id="doralab_benachrichtigungen_ungelesen",
    )
    return old


async def _setup_new(hass: HomeAssistant, options: dict | None = None):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options or {}, title="Enhanced Notify")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, hass.data[DOMAIN]


async def test_migration_takes_over_data_options_and_sensor(hass: HomeAssistant, hass_storage):
    hass_storage[LEGACY_DOMAIN] = {"version": 1, "key": LEGACY_DOMAIN, "data": OLD_ITEMS}
    old = _old_entry(hass, {"push_default_icon": "/local/logo.png"})
    registry = er.async_get(hass)
    assert registry.async_get(OLD_SENSOR).platform == LEGACY_DOMAIN

    entry, manager = await _setup_new(hass)

    # Meldungen und Typ-Einstellungen sind übernommen
    assert [i["message"] for i in manager.items] == ["Es hat geklingelt"]
    assert manager.type_settings["klingel"]["recipients"] == ["person.dominik"]
    assert manager.unread == 1
    # Optionen sind übernommen
    assert entry.options == {"push_default_icon": "/local/logo.png"}
    # Der alte Eintrag ist weg, der Sensor behält Entity-ID und gehört jetzt zur neuen Integration
    assert hass.config_entries.async_get_entry(old.entry_id) is None
    sensor = registry.async_get(OLD_SENSOR)
    assert sensor is not None
    assert sensor.platform == DOMAIN
    assert sensor.config_entry_id == entry.entry_id
    assert sensor.unique_id == f"{entry.entry_id}_unread"
    assert hass.states.get(OLD_SENSOR).state == "1"
    assert _sensor_state(hass).entity_id == OLD_SENSOR
    # Die alte Speicherdatei bleibt als Sicherung unverändert
    assert hass_storage[LEGACY_DOMAIN]["data"]["items"][0]["id"] == "abc123"
    # Das alte Gerät ist ersetzt, es bleibt genau eines
    devices = dr.async_get(hass).devices.values()
    assert [d.name for d in devices] == ["Enhanced Notify"]


async def test_migration_works_without_old_entry_but_with_old_storage(
    hass: HomeAssistant, hass_storage
):
    """Alter Eintrag wurde schon gelöscht, die Speicherdatei ist noch da."""
    hass_storage[LEGACY_DOMAIN] = {"version": 1, "key": LEGACY_DOMAIN, "data": OLD_ITEMS}
    _, manager = await _setup_new(hass)
    assert [i["id"] for i in manager.items] == ["abc123"]


async def test_migration_does_not_overwrite_existing_new_data(hass: HomeAssistant, hass_storage):
    hass_storage[LEGACY_DOMAIN] = {"version": 1, "key": LEGACY_DOMAIN, "data": OLD_ITEMS}
    new_data = {**OLD_ITEMS, "items": [{**OLD_ITEMS["items"][0], "id": "neu", "message": "Neu"}]}
    hass_storage[DOMAIN] = {"version": 1, "key": DOMAIN, "data": new_data}
    _old_entry(hass)
    _, manager = await _setup_new(hass)
    assert [i["id"] for i in manager.items] == ["neu"]


async def test_migration_keeps_options_set_on_new_entry(hass: HomeAssistant):
    _old_entry(hass, {"push_default_icon": "/local/alt.png"})
    entry, _ = await _setup_new(hass, {"push_default_icon": "/local/neu.png"})
    assert entry.options == {"push_default_icon": "/local/neu.png"}


async def test_fresh_install_is_untouched(hass: HomeAssistant, caplog):
    entry, manager = await _setup_new(hass)
    assert manager.items == []
    assert "Umstieg" not in caplog.text
    assert entry.options == {}


async def test_migration_runs_only_once(hass: HomeAssistant, hass_storage):
    hass_storage[LEGACY_DOMAIN] = {"version": 1, "key": LEGACY_DOMAIN, "data": OLD_ITEMS}
    _old_entry(hass)
    entry, manager = await _setup_new(hass)
    await manager.async_mark_read(mark_all=True)
    await manager.async_flush()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    # Nach dem Neuladen gilt der neue Speicher, die gelesene Meldung kommt nicht zurück
    assert hass.data[DOMAIN].unread == 0
    assert hass.states.get(OLD_SENSOR).state == "0"


async def test_old_service_names_still_work_and_raise_repair(hass: HomeAssistant):
    _, manager = await _setup_new(hass)
    assert hass.services.has_service(LEGACY_DOMAIN, "send")
    result = await hass.services.async_call(
        LEGACY_DOMAIN,
        "send",
        {"type": "klingel", "message": "Alt aufgerufen", "push": False},
        blocking=True,
        return_response=True,
    )
    assert result["id"]
    assert [i["message"] for i in manager.items] == ["Alt aufgerufen"]

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "deprecated_service_send")
    assert issue is not None
    assert issue.translation_key == "deprecated_service"
    assert issue.translation_placeholders == {
        "old": "doralab_notify.send",
        "new": "enhanced_notify.send",
    }
    assert not issue.is_persistent

    item_id = manager.items[0]["id"]
    await hass.services.async_call(LEGACY_DOMAIN, "mark_read", {"ids": [item_id]}, blocking=True)
    assert manager.unread == 0
    await hass.services.async_call(LEGACY_DOMAIN, "delete", {"ids": [item_id]}, blocking=True)
    assert manager.items == []


async def test_old_push_button_still_marks_read(hass: HomeAssistant):
    """Bereits zugestellte Push-Meldungen tragen noch die alte Button-Kennung."""
    _, manager = await _setup_new(hass)
    calls, _ = _add_person(hass, "dominik", "Dominik", "Dominik iPhone")
    await manager.async_send("paket_zugestellt", "da")
    await hass.async_block_till_done()
    item_id = manager.items[0]["id"]

    hass.bus.async_fire("mobile_app_notification_action", {"action": f"DORALAB_READ_{item_id}"})
    await hass.async_block_till_done()
    assert manager.unread == 0
    assert calls[-1].data == {"message": "clear_notification", "data": {"tag": item_id}}
