"""Integrationstests der Benachrichtigungszentrale."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant.components import persistent_notification as pn
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.doralab_notify.const import DOMAIN, EVENT_CREATED, TAG_PERSISTENT_PREFIX


def _sensor_state(hass: HomeAssistant):
    """Zähler-Sensor über die Registry finden (Entity-ID hängt von der Sprache ab)."""
    entity_id = next(
        e.entity_id
        for e in er.async_get(hass).entities.values()
        if e.platform == DOMAIN and e.domain == "sensor"
    )
    return hass.states.get(entity_id)


async def _setup(hass: HomeAssistant, options: dict | None = None):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, hass.data[DOMAIN]


def _add_person(hass: HomeAssistant, slug: str, name: str, device: str, state: str = "home"):
    """Person mit Companion-App-Gerät anlegen; liefert den Notify-Dienstnamen."""
    mobile = MockConfigEntry(domain="mobile_app", data={"device_name": device}, title=device)
    mobile.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "device_tracker",
        "mobile_app",
        f"uid_{slug}",
        suggested_object_id=f"{slug}_tracker",
        config_entry=mobile,
    )
    hass.states.async_set(
        f"person.{slug}",
        state,
        {"friendly_name": name, "device_trackers": [f"device_tracker.{slug}_tracker"]},
    )
    service = "mobile_app_" + device.lower().replace(" ", "_")
    return async_mock_service(hass, "notify", service), service


async def test_setup_sensor_and_services(hass: HomeAssistant):
    await _setup(hass)
    state = _sensor_state(hass)
    assert state is not None and state.state == "0"
    for service in ("send", "mark_read", "delete", "set_type"):
        assert hass.services.has_service(DOMAIN, service)


async def test_send_creates_item_and_updates_sensor(hass: HomeAssistant):
    _, manager = await _setup(hass)
    events = []
    hass.bus.async_listen(EVENT_CREATED, events.append)
    result = await hass.services.async_call(
        DOMAIN,
        "send",
        {"type": "paket_zugestellt", "message": "Hermes: zugestellt"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert result["deduplicated"] is False
    assert manager.unread == 1
    item = manager.items[0]
    assert item["title"] == "Paket zugestellt"  # Standardtitel = Typ-Name
    assert item["category"] == "pakete"
    assert _sensor_state(hass).state == "1"
    assert len(events) == 1


async def test_tag_updates_and_dedupes(hass: HomeAssistant):
    _, manager = await _setup(hass)
    base = {"type": "paket_termin", "tag": "paket:1"}
    await hass.services.async_call(DOMAIN, "send", {**base, "message": "Montag"}, blocking=True)
    first = manager.items[0]["id"]
    await manager.async_mark_read([first])
    # identischer Text: nichts passiert, bleibt gelesen
    res = await hass.services.async_call(
        DOMAIN, "send", {**base, "message": "Montag"}, blocking=True, return_response=True
    )
    assert res["deduplicated"] is True
    assert manager.unread == 0 and len(manager.items) == 1
    # neuer Text: gleiche Meldung, wieder ungelesen, nach oben
    await hass.services.async_call(DOMAIN, "send", {**base, "message": "Dienstag"}, blocking=True)
    assert len(manager.items) == 1
    assert manager.items[0]["id"] == first
    assert manager.items[0]["message"] == "Dienstag"
    assert manager.items[0]["read"] is False and manager.items[0]["count"] == 2


async def test_mark_read_and_delete(hass: HomeAssistant):
    _, manager = await _setup(hass)
    for n in range(3):
        await manager.async_send("klingel", f"m{n}", push=False)
    ids = [i["id"] for i in manager.items]
    await hass.services.async_call(DOMAIN, "mark_read", {"ids": [ids[0]]}, blocking=True)
    assert manager.unread == 2
    await hass.services.async_call(DOMAIN, "mark_read", {"ids": [ids[0]], "read": False}, blocking=True)
    assert manager.unread == 3
    await hass.services.async_call(DOMAIN, "mark_read", {"all": True}, blocking=True)
    assert manager.unread == 0
    await hass.services.async_call(DOMAIN, "delete", {"ids": [ids[1]]}, blocking=True)
    assert len(manager.items) == 2
    await manager.async_mark_read([ids[0]], read=False)
    await hass.services.async_call(DOMAIN, "delete", {"only_read": True, "all": True}, blocking=True)
    assert [i["id"] for i in manager.items] == [ids[0]]
    await hass.services.async_call(DOMAIN, "delete", {"all": True}, blocking=True)
    assert manager.items == []


async def test_unknown_type_is_registered(hass: HomeAssistant):
    _, manager = await _setup(hass)
    assert "garage_offen" not in manager.types_view()
    await manager.async_send("garage_offen", "Garagentor steht offen", category="system", type_name="Garage offen", push=False)
    view = manager.types_view()["garage_offen"]
    assert view["auto"] is True and view["name"] == "Garage offen"
    assert view["recipients_effective"] == []  # automatisch angelegte Typen pushen nicht


async def test_push_defaults_and_away_mode(hass: HomeAssistant):
    _, manager = await _setup(hass)
    dom_calls, _ = _add_person(hass, "dominik", "Dominik", "Dominik iPhone", "home")
    sina_calls, _ = _add_person(hass, "sina", "Sina", "iPhone von Sina", "not_home")

    # Klingel: Standard = alle, aber nur wer nicht zuhause ist
    await manager.async_send("klingel", "Es klingelt", link="/kiosk-test/home")
    await hass.async_block_till_done()
    assert len(dom_calls) == 0
    assert len(sina_calls) == 1
    data = sina_calls[0].data["data"]
    assert data["tag"] == manager.items[0]["id"]
    assert data["url"] == "/kiosk-test/home"
    assert data["push"] == {"interruption-level": "time-sensitive"}
    assert data["actions"][0]["action"].startswith("DORALAB_READ_")

    # Paket in Zustellung: alle, immer
    await manager.async_send("paket_in_zustellung", "kommt heute")
    await hass.async_block_till_done()
    assert len(dom_calls) == 1 and len(sina_calls) == 2

    # Typ ohne Standard-Push
    await manager.async_send("paket_unterwegs", "unterwegs")
    await hass.async_block_till_done()
    assert len(dom_calls) == 1 and len(sina_calls) == 2


async def test_set_type_recipients(hass: HomeAssistant):
    _, manager = await _setup(hass)
    dom_calls, _ = _add_person(hass, "dominik", "Dominik", "Dominik iPhone")
    sina_calls, _ = _add_person(hass, "sina", "Sina", "iPhone von Sina")

    await hass.services.async_call(
        DOMAIN, "set_type", {"type": "waschmaschine_fertig", "recipients": ["person.sina"]}, blocking=True
    )
    await manager.async_send("waschmaschine_fertig", "fertig")
    await hass.async_block_till_done()
    assert len(dom_calls) == 0 and len(sina_calls) == 1

    # Leere Liste = kein Push
    await hass.services.async_call(DOMAIN, "set_type", {"type": "waschmaschine_fertig", "recipients": []}, blocking=True)
    await manager.async_send("waschmaschine_fertig", "nochmal")
    await hass.async_block_till_done()
    assert len(sina_calls) == 1

    # Zurücksetzen = Katalog-Vorgabe (alle)
    await hass.services.async_call(DOMAIN, "set_type", {"type": "waschmaschine_fertig", "reset": True}, blocking=True)
    assert manager.types_view()["waschmaschine_fertig"]["customized"] is False
    await manager.async_send("waschmaschine_fertig", "dritte")
    await hass.async_block_till_done()
    assert len(dom_calls) == 1 and len(sina_calls) == 2

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "set_type", {"type": "waschmaschine_fertig", "recipients": ["person.gibtsnicht"]}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "set_type", {"type": "gibtsnicht", "push_when": "away"}, blocking=True)


async def test_persons_without_phone_are_not_listed(hass: HomeAssistant):
    """Personen ohne Companion-App-Gerät (Anmelde-Konten) erscheinen nicht als Empfänger."""
    _, manager = await _setup(hass)
    _add_person(hass, "dominik", "Dominik", "Dominik iPhone")
    _add_person(hass, "sina", "Sina", "iPhone von Sina")
    hass.states.async_set("person.administrator", "unknown", {"friendly_name": "LocalAdmin", "device_trackers": []})
    hass.states.async_set("person.adm01", "unknown", {"friendly_name": "adm01"})
    # Tracker, der nicht zur Companion App gehört, zählt nicht
    hass.states.async_set("person.gast", "home", {"friendly_name": "Gast", "device_trackers": ["device_tracker.router_gast"]})
    await hass.async_block_till_done()

    view = manager.snapshot()
    assert [p["id"] for p in view["recipients"]] == ["person.dominik", "person.sina"]
    # Standard „alle“ meint nur Personen mit Handy
    assert manager.types_view()["paket_zugestellt"]["recipients_effective"] == ["person.dominik", "person.sina"]
    # Gespeicherte Auswahl: nur Personen mit Handy bleiben wirksam
    await hass.services.async_call(
        DOMAIN, "set_type", {"type": "klingel", "recipients": ["person.dominik", "person.administrator"]}, blocking=True
    )
    assert manager.types_view()["klingel"]["recipients_effective"] == ["person.dominik"]
    assert [p["id"] for p in manager.snapshot()["recipients"]] == ["person.dominik", "person.sina"]


async def test_excluded_device_gets_no_push(hass: HomeAssistant):
    _, manager = await _setup(hass, {"excluded_notify_services": ["mobile_app_iphone_von_sina"]})
    sina_calls, _ = _add_person(hass, "sina", "Sina", "iPhone von Sina")
    await manager.async_send("paket_zugestellt", "da")
    await hass.async_block_till_done()
    assert sina_calls == []


async def test_clear_push_on_read_and_action_button(hass: HomeAssistant):
    _, manager = await _setup(hass)
    calls, _ = _add_person(hass, "dominik", "Dominik", "Dominik iPhone")
    await manager.async_send("paket_zugestellt", "da")
    await hass.async_block_till_done()
    item_id = manager.items[0]["id"]
    assert len(calls) == 1

    # Button „Gelesen“ in der Push-Meldung
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"DORALAB_READ_{item_id}"})
    await hass.async_block_till_done()
    assert manager.unread == 0
    assert len(calls) == 2
    assert calls[1].data == {"message": "clear_notification", "data": {"tag": item_id}}


async def test_retention(hass: HomeAssistant):
    _, manager = await _setup(hass, {"retention_read_days": 14, "retention_days": 60, "max_items": 200})
    for n in range(4):
        await manager.async_send("klingel", f"m{n}", push=False)
    now = dt_util.utcnow()
    old_read, old_unread, young_read, young_unread = manager.items
    old_read.update(read=True, updated=(now - timedelta(days=20)).isoformat())
    old_unread.update(read=False, updated=(now - timedelta(days=30)).isoformat())
    young_read.update(read=True, updated=(now - timedelta(days=2)).isoformat())
    young_unread["updated"] = (now - timedelta(days=90)).isoformat()  # zu alt, auch ungelesen
    removed = await manager.async_cleanup()
    assert removed == 2
    assert {i["message"] for i in manager.items} == {"m1", "m2"}


async def test_max_items_prefers_removing_read(hass: HomeAssistant):
    _, manager = await _setup(hass, {"max_items": 20})
    for n in range(20):
        await manager.async_send("klingel", f"m{n}", push=False)
    await manager.async_mark_read([manager.items[10]["id"]])
    await manager.async_send("klingel", "neu", push=False)
    assert len(manager.items) == 20
    assert all(i["message"] != "m9" for i in manager.items)  # die einzige gelesene fliegt zuerst


async def test_import_persistent_notification(hass: HomeAssistant):
    assert await async_setup_component(hass, "persistent_notification", {})
    _, manager = await _setup(hass)
    pn.async_create(hass, "Cleaning completed", title="Dreame", notification_id="dreame_done")
    await hass.async_block_till_done()
    assert manager.items[0]["type"] == "saugroboter_fertig"
    assert manager.items[0]["title"] == "Reinigung abgeschlossen"
    assert manager.items[0]["tag"] == "ha:dreame_done"
    # im HA-Original ausgeblendet
    assert "dreame_done" not in hass.data["persistent_notification"]


async def test_import_existing_on_start_without_dismiss(hass: HomeAssistant):
    assert await async_setup_component(hass, "persistent_notification", {})
    pn.async_create(hass, "Hallo", title="Test", notification_id="alt")
    await hass.async_block_till_done()
    _, manager = await _setup(hass, {"dismiss_imported": False})
    assert manager.items[0]["tag"] == "ha:alt"
    assert "alt" in hass.data["persistent_notification"]


async def test_persists_across_reload(hass: HomeAssistant):
    entry, manager = await _setup(hass)
    await manager.async_send("klingel", "bleibt", push=False)
    await manager.async_mark_read(mark_all=True)
    await manager.async_send("klingel", "ungelesen", push=False)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    assert [i["message"] for i in manager.items] == ["ungelesen", "bleibt"]
    assert manager.unread == 1
    assert _sensor_state(hass).state == "1"


async def _collect(client, msg_id: int):
    """Nachrichten lesen, bis das Ergebnis zu ``msg_id`` da ist (Events können davor kommen)."""
    events = []
    while True:
        msg = await client.receive_json()
        if msg["type"] == "event":
            events.append(msg["event"])
        elif msg["id"] == msg_id:
            return msg, events


async def test_websocket_flow(hass: HomeAssistant, hass_ws_client):
    _, manager = await _setup(hass)
    _add_person(hass, "dominik", "Dominik", "Dominik iPhone")
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "doralab_notify/subscribe"})
    result, events = await _collect(client, 1)
    assert result["success"] is True
    snap = events[0] if events else (await client.receive_json())["event"]
    assert snap["unread"] == 0 and "klingel" in snap["types"]
    assert snap["recipients"][0]["id"] == "person.dominik"

    await manager.async_send("klingel", "ding", push=False)
    update = (await client.receive_json())["event"]
    assert update["unread"] == 1
    item_id = update["items"][0]["id"]

    await client.send_json({"id": 2, "type": "doralab_notify/mark_read", "ids": [item_id]})
    result, events = await _collect(client, 2)
    assert result["result"] == {"changed": 1}
    assert events[-1]["unread"] == 0

    await client.send_json(
        {"id": 3, "type": "doralab_notify/set_type", "type_id": "klingel", "recipients": ["person.dominik"], "push_when": "always"}
    )
    result, events = await _collect(client, 3)
    assert result["success"] is True
    assert events[-1]["types"]["klingel"]["recipients"] == ["person.dominik"]
    assert events[-1]["types"]["klingel"]["push_when"] == "always"

    await client.send_json({"id": 4, "type": "doralab_notify/set_type", "type_id": "klingel", "recipients": ["person.x"]})
    result, _ = await _collect(client, 4)
    assert result["success"] is False

    await client.send_json({"id": 5, "type": "doralab_notify/delete", "ids": [item_id]})
    result, _ = await _collect(client, 5)
    assert result["result"] == {"removed": 1}


async def test_options_flow(hass: HomeAssistant):
    entry, _ = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"retention_read_days": 7, "retention_days": 30, "max_items": 100, "import_persistent": False, "dismiss_imported": False, "excluded_notify_services": []},
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].entry.options["retention_read_days"] == 7


async def test_once_and_baseline(hass: HomeAssistant):
    _, manager = await _setup(hass)
    # stiller Erstlauf: nur vormerken
    res = await hass.services.async_call(
        DOMAIN,
        "send",
        {"type": "kalender_neuer_termin", "message": "alt", "tag": "kal:1", "once": True, "baseline": True},
        blocking=True,
        return_response=True,
    )
    assert res["baseline"] is True and manager.items == []
    # vorgemerkte und neue Tags
    res = await hass.services.async_call(
        DOMAIN,
        "send",
        {"type": "kalender_neuer_termin", "message": "alt", "tag": "kal:1", "once": True},
        blocking=True,
        return_response=True,
    )
    assert res["deduplicated"] is True and manager.items == []
    await hass.services.async_call(
        DOMAIN,
        "send",
        {"type": "kalender_neuer_termin", "message": "neu", "tag": "kal:2", "once": True, "push": False},
        blocking=True,
    )
    assert [i["message"] for i in manager.items] == ["neu"]
    # nach dem Löschen nicht erneut melden
    await hass.services.async_call(DOMAIN, "delete", {"all": True}, blocking=True)
    await hass.services.async_call(
        DOMAIN,
        "send",
        {"type": "kalender_neuer_termin", "message": "neu", "tag": "kal:2", "once": True, "push": False},
        blocking=True,
    )
    assert manager.items == []
    with pytest.raises(ServiceValidationError):
        await manager.async_send("klingel", "x", once=True)


async def test_delete_by_tag(hass: HomeAssistant):
    _, manager = await _setup(hass)
    await manager.async_send("vorrat_niedrig", "a", tag="v:a", push=False)
    await manager.async_send("vorrat_niedrig", "b", tag="v:b", push=False)
    await manager.async_send("klingel", "c", push=False)
    await hass.services.async_call(DOMAIN, "delete", {"tags": ["v:a", "gibt-es-nicht"]}, blocking=True)
    assert sorted(i["message"] for i in manager.items) == ["b", "c"]


async def test_seen_persists_across_reload(hass: HomeAssistant):
    entry, manager = await _setup(hass)
    await manager.async_send("kalender_neuer_termin", "x", tag="kal:9", once=True, baseline=True)
    await manager.async_flush()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    assert "kal:9" in manager.seen


async def test_deleted_or_read_message_does_not_return(hass: HomeAssistant):
    """Gleicher Inhalt zum gleichen Tag darf nach Lesen/Löschen nicht neu auftauchen."""
    _, manager = await _setup(hass)
    r = await manager.async_send("paket_unterwegs", "Unterwegs", title="Hermes", tag="paket:1", push=False)
    assert r["deduplicated"] is False
    await manager.async_mark_read([r["id"]])
    again = await manager.async_send("paket_unterwegs", "Unterwegs", title="Hermes", tag="paket:1", push=False)
    assert again["deduplicated"] is True and manager.items[0]["read"] is True
    await manager.async_delete([r["id"]])
    assert manager.items == []
    again = await manager.async_send("paket_unterwegs", "Unterwegs", title="Hermes", tag="paket:1", push=False)
    assert again["deduplicated"] is True and manager.items == []
    # geänderter Inhalt meldet wieder, danach wieder A -> kommt auch wieder
    await manager.async_send("paket_unterwegs", "In Zustellung", title="Hermes", tag="paket:1", push=False)
    assert [i["message"] for i in manager.items] == ["In Zustellung"]
    await manager.async_delete(tags=["paket:1"])
    back = await manager.async_send("paket_unterwegs", "Unterwegs", title="Hermes", tag="paket:1", push=False)
    assert back["deduplicated"] is False and [i["message"] for i in manager.items] == ["Unterwegs"]


async def test_untagged_and_persistent_still_repeat(hass: HomeAssistant):
    _, manager = await _setup(hass)
    await manager.async_send("klingel", "Es klingelt", push=False)
    await manager.async_send("klingel", "Es klingelt", push=False)
    assert len(manager.items) == 2
    await manager.async_import_persistent("dreame_x", "Staubsauger", "Reinigung abgeschlossen")
    first = [i for i in manager.items if i["tag"] == f"{TAG_PERSISTENT_PREFIX}dreame_x"]
    await manager.async_delete([first[0]["id"]])
    await manager.async_import_persistent("dreame_x", "Staubsauger", "Reinigung abgeschlossen")
    assert any(i["tag"] == f"{TAG_PERSISTENT_PREFIX}dreame_x" for i in manager.items)


async def test_announced_survives_restart_and_bootstraps(hass: HomeAssistant):
    entry, manager = await _setup(hass)
    r = await manager.async_send("paket_unterwegs", "A", title="T", tag="paket:9", push=False)
    await manager.async_delete([r["id"]])
    await manager.async_flush()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    res = await manager.async_send("paket_unterwegs", "A", title="T", tag="paket:9", push=False)
    assert res["deduplicated"] is True and manager.items == []
    # Bestehende Meldung aus einem alten Speicher (ohne announced) wird übernommen
    await manager.async_send("paket_unterwegs", "B", title="T", tag="paket:10", push=False)
    manager.announced.clear()
    await manager.async_flush()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    res = await manager.async_send("paket_unterwegs", "B", title="T", tag="paket:10", push=False)
    assert res["deduplicated"] is True


async def test_old_system_vacuum_items_move_to_saugroboter(hass: HomeAssistant):
    _, manager = await _setup(hass)
    manager.items.append(
        {
            "id": "old1", "type": "ha_system", "category": "system", "title": "Staubsauger",
            "message": "Bitte füllen Sie den Frischwassertank auf.", "tag": f"{TAG_PERSISTENT_PREFIX}dreame_w",
            "link": None, "icon": None, "created": "2026-10-16T08:00:00+00:00", "updated": "2026-10-16T08:00:00+00:00",
            "read": False, "read_at": None, "count": 1, "pushed": [],
            "data": {"source": "persistent_notification", "original_title": "Staubsauger",
                     "original_message": "Bitte füllen Sie den Frischwassertank auf."},
        }
    )
    manager._retranslate_persistent()
    item = next(i for i in manager.items if i["id"] == "old1")
    assert item["type"] == "saugroboter_wartung" and item["category"] == "saugroboter"
    assert item["title"] == "Wassertank fast leer"


async def test_frontend_is_served_and_registered(hass: HomeAssistant):
    """Die Integration liefert das JavaScript selbst aus und lädt es in HA."""
    from unittest.mock import AsyncMock, patch

    from homeassistant.components.http import HomeAssistantHTTP
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager

    from custom_components.doralab_notify import FRONTEND_FILE, FRONTEND_URL

    register = AsyncMock()
    hass.config.components.add("frontend")
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])

    with patch.object(HomeAssistantHTTP, "async_register_static_paths", register):
        await _setup(hass)

    assert FRONTEND_FILE.is_file()
    (paths,) = register.call_args.args
    assert paths[0].url_path == FRONTEND_URL and paths[0].path == str(FRONTEND_FILE)
    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert any(u.startswith(f"{FRONTEND_URL}?v=") for u in urls)


async def test_setup_works_without_frontend(hass: HomeAssistant):
    """Ohne Frontend/HTTP (z. B. Tests, Headless) laufen die Dienste trotzdem."""
    _, manager = await _setup(hass)
    result = await manager.async_send("klingel", "Es klingelt", push=False)
    assert result["id"]
