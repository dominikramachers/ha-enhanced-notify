"""Zusteller-Logos in Paket-Meldungen (Liste und Push)."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from custom_components.enhanced_notify.carriers import (
    ALIASES,
    CARRIERS_DIR,
    CARRIERS_URL,
    carrier_icon,
    carrier_id,
)

from .test_integration import _push_data, _setup


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("DHL: Schuhe", "dhl"),
        ("dhl: Schuhe", "dhl"),
        ("DPD: Küchenmaschine", "dpd"),
        ("Hermes: Paket", "hermes"),
        ("Picnic: Einkauf · 24 Artikel", "picnic"),
        ("Amazon: Toaster", "amazon"),
        ("DHL Paket: Schuhe", "dhl"),
        ("  GLS : Teile", "gls"),
        ("Unbekannt: Paket", None),
        ("Paket zugestellt", None),  # kein „Zusteller:“-Präfix
        ("Waschmaschine fertig: Wäsche", None),
        ("", None),
        (None, None),
    ],
)
def test_carrier_id(title, expected):
    assert carrier_id(title) == expected


def test_logo_files_are_valid_and_known():
    """Jede Logo-Datei gehört zu einem bekannten Zusteller und ist ein WebP-Bild."""
    files = sorted(CARRIERS_DIR.glob("*.webp"))
    assert {f.stem for f in files} >= {"dhl", "dpd", "hermes", "picnic"}
    for f in files:
        assert f.stem in ALIASES, f"{f.name} fehlt in ALIASES"
        data = f.read_bytes()
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        assert int.from_bytes(data[4:8], "little") + 8 == len(data)
        assert len(data) < 20000


def test_carrier_icon_only_with_logo_file():
    assert carrier_icon("DHL: Schuhe") == f"{CARRIERS_URL}/dhl.webp"
    assert carrier_icon("Picnic: Einkauf") == f"{CARRIERS_URL}/picnic.webp"
    # bekannter Zusteller, aber (noch) kein Logo
    assert carrier_id("Amazon: Toaster") == "amazon"
    assert not (CARRIERS_DIR / "amazon.webp").exists()
    assert carrier_icon("Amazon: Toaster") is None


async def test_parcel_notification_gets_carrier_logo(hass: HomeAssistant):
    _, manager = await _setup(hass)
    await manager.async_send("paket_in_zustellung", "Heute", title="DHL: Schuhe", tag="paket:1", push=False)
    await manager.async_send("paket_in_zustellung", "Heute", title="Hermes: Buch", tag="paket:2", push=False)
    await manager.async_send("paket_in_zustellung", "Heute", title="Amazon: Toaster", tag="paket:3", push=False)
    icons = {i["tag"]: i["icon"] for i in manager.items}
    assert icons["paket:1"] == f"{CARRIERS_URL}/dhl.webp"
    assert icons["paket:2"] == f"{CARRIERS_URL}/hermes.webp"
    assert icons["paket:3"] is None


async def test_explicit_icon_wins_over_carrier_logo(hass: HomeAssistant):
    _, manager = await _setup(hass)
    await manager.async_send(
        "paket_in_zustellung", "Heute", title="DHL: Schuhe", icon="/local/eigen.png", push=False
    )
    assert manager.items[0]["icon"] == "/local/eigen.png"


async def test_logo_only_for_parcel_category(hass: HomeAssistant):
    """Ein Titel „DHL: …“ in einer anderen Kategorie bekommt kein Zusteller-Logo."""
    _, manager = await _setup(hass)
    await manager.async_send("klingel", "Es klingelt", title="DHL: Haustür", push=False)
    assert manager.items[0]["icon"] is None


async def test_logo_follows_status_update_and_carrier_change(hass: HomeAssistant):
    _, manager = await _setup(hass)
    await manager.async_send("paket_unterwegs", "Unterwegs", title="DHL: Schuhe", tag="paket:1", push=False)
    await manager.async_send("paket_in_zustellung", "In Zustellung", title="DHL: Schuhe", tag="paket:1", push=False)
    assert len(manager.items) == 1 and manager.items[0]["icon"] == f"{CARRIERS_URL}/dhl.webp"
    # Zusteller wechselt (z. B. Übergabe an Hermes): das Logo wechselt mit
    await manager.async_send("paket_zugestellt", "Zugestellt", title="Hermes: Schuhe", tag="paket:1", push=False)
    assert manager.items[0]["icon"] == f"{CARRIERS_URL}/hermes.webp"


async def test_backfill_for_existing_items(hass: HomeAssistant):
    """Vor dem Update angelegte Paket-Meldungen bekommen das Logo beim Laden."""
    _, manager = await _setup(hass)
    await manager.async_send("paket_in_zustellung", "Heute", title="DPD: Schuhe", tag="paket:1", push=False)
    await manager.async_send("klingel", "Es klingelt", title="DPD: Haustür", push=False)
    for item in manager.items:
        item["icon"] = None
    manager._backfill_carrier_icons()
    by_type = {i["type"]: i["icon"] for i in manager.items}
    assert by_type["paket_in_zustellung"] == f"{CARRIERS_URL}/dpd.webp"
    assert by_type["klingel"] is None


async def test_push_uses_carrier_logo(hass: HomeAssistant):
    _, manager = await _setup(hass)
    data = await _push_data(hass, manager, title="DHL: Schuhe")
    assert data["icon_url"] == f"{CARRIERS_URL}/dhl.webp"


async def test_push_without_logo_has_no_icon(hass: HomeAssistant):
    _, manager = await _setup(hass)
    assert "icon_url" not in await _push_data(hass, manager, title="Amazon: Toaster")


async def test_push_logo_beats_default_icon_unless_forced(hass: HomeAssistant):
    _, manager = await _setup(hass, {"push_icon": "/local/logo.png"})
    assert (await _push_data(hass, manager, title="DHL: Schuhe"))["icon_url"] == f"{CARRIERS_URL}/dhl.webp"
    # Pakete ohne Logo behalten das Standard-Icon
    assert (await _push_data(hass, manager, title="Amazon: Toaster"))["icon_url"] == "/local/logo.png"


async def test_push_forced_default_icon_beats_logo(hass: HomeAssistant):
    _, manager = await _setup(hass, {"push_icon": "/local/logo.png", "push_icon_force": True})
    assert (await _push_data(hass, manager, title="DHL: Schuhe"))["icon_url"] == "/local/logo.png"


async def test_push_icon_of_item_data_uri_is_not_sent(hass: HomeAssistant):
    """Eingebettete Bilder (data:) und MDI-Namen gehen nie als icon_url in den Push."""
    _, manager = await _setup(hass)
    data = await _push_data(hass, manager, title="Info", icon="data:image/png;base64,iVBORw0KGgo=")
    assert "icon_url" not in data


async def test_logos_are_served_without_login(hass: HomeAssistant):
    """Das Logo-Verzeichnis wird als statischer Pfad registriert (Push-Bild muss ohne Anmeldung ladbar sein)."""
    from unittest.mock import AsyncMock, patch

    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
    from homeassistant.components.http import HomeAssistantHTTP

    register = AsyncMock()
    hass.config.components.add("frontend")
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])

    with patch.object(HomeAssistantHTTP, "async_register_static_paths", register):
        await _setup(hass)

    (paths,) = register.call_args.args
    carriers = next(p for p in paths if p.url_path == CARRIERS_URL)
    assert carriers.path == str(CARRIERS_DIR) and CARRIERS_DIR.is_dir()
