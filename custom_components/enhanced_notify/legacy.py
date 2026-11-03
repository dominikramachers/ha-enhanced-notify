"""Umstieg von „DORALAB Benachrichtigungen“ (Domain ``doralab_notify``, bis 0.3.x).

Seit 1.0 heißt die Integration Enhanced Notify (Domain ``enhanced_notify``). Home
Assistant kann eine Domain nicht umbenennen: Eintrag, Speicher und Entität der
alten Integration gehören zur alten Domain. Deshalb übernimmt die neue Integration
beim Einrichten alles selbst:

* Meldungen, Typ-Einstellungen und Merkzettel aus ``.storage/doralab_notify``,
* die Optionen des alten Eintrags,
* den Zähler-Sensor (Entity-ID und Verlauf bleiben erhalten),

und entfernt danach den alten Eintrag. Die alte Speicherdatei bleibt als Sicherung
liegen. Zusätzlich gibt es für eine Übergangszeit die alten Dienstnamen
(``doralab_notify.send`` usw.), damit Automationen nicht sofort brechen.

Alles hier entfällt in Version 2.0.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LEGACY_DOMAIN, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

SENSOR_SUFFIX = "_unread"


async def async_migrate_legacy(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Daten, Optionen und Sensor der alten Integration übernehmen (einmalig).

    Läuft vor dem Laden des Speichers. Ist nichts Altes vorhanden, passiert nichts.
    Fehler werden protokolliert und brechen das Einrichten nicht ab.
    """
    old_entries = hass.config_entries.async_entries(LEGACY_DOMAIN)
    old_store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, LEGACY_DOMAIN)
    # Alte Integration (falls ihr Ordner noch da ist) zuerst anhalten, damit sie ihre
    # Daten fertig schreibt und nicht mehr dazwischenfunkt.
    for old in old_entries:
        if old.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(old.entry_id)

    old_data = await old_store.async_load()
    if not old_entries and old_data is None:
        return

    _LOGGER.warning(
        "Umstieg von %s auf %s: Daten, Optionen und Sensor werden übernommen", LEGACY_DOMAIN, DOMAIN
    )

    try:
        new_store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        if old_data and await new_store.async_load() is None:
            await new_store.async_save(old_data)
            _LOGGER.info("%s Meldungen übernommen", len(old_data.get("items", [])))
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Die Meldungen der alten Integration konnten nicht übernommen werden")

    if old_entries and not entry.options:
        hass.config_entries.async_update_entry(entry, options=dict(old_entries[0].options))

    registry = er.async_get(hass)
    for item in list(registry.entities.values()):
        if item.platform != LEGACY_DOMAIN or not item.unique_id.endswith(SENSOR_SUFFIX):
            continue
        try:
            registry.async_update_entity_platform(
                item.entity_id,
                DOMAIN,
                new_config_entry_id=entry.entry_id,
                new_unique_id=f"{entry.entry_id}{SENSOR_SUFFIX}",
            )
            _LOGGER.info("Sensor %s übernommen", item.entity_id)
        except ValueError:
            _LOGGER.warning("Sensor %s konnte nicht übernommen werden", item.entity_id)

    for old in old_entries:
        await hass.config_entries.async_remove(old.entry_id)


def _deprecated(name: str, handler: Any) -> Any:
    """Alten Dienstnamen weiter bedienen und einen Hinweis in den Reparaturen anlegen."""

    async def wrapper(call: ServiceCall) -> ServiceResponse:
        _LOGGER.warning(
            "Der Dienst %s.%s ist veraltet, bitte %s.%s verwenden (entfällt in 2.0)",
            LEGACY_DOMAIN,
            name,
            DOMAIN,
            name,
        )
        ir.async_create_issue(
            call.hass,
            DOMAIN,
            f"deprecated_service_{name}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_service",
            translation_placeholders={"old": f"{LEGACY_DOMAIN}.{name}", "new": f"{DOMAIN}.{name}"},
        )
        return await handler(call)

    return wrapper


def async_register_legacy_services(
    hass: HomeAssistant, services: dict[str, tuple[Any, Any, Any]]
) -> None:
    """Die alten Dienstnamen unter ``doralab_notify`` bereitstellen.

    ``services``: Name -> (Handler, Schema, Antwortmodus).
    """
    for name, (handler, schema, response) in services.items():
        hass.services.async_register(
            LEGACY_DOMAIN,
            name,
            _deprecated(name, handler),
            schema=schema,
            supports_response=response,
        )
