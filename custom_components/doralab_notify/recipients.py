"""Empfänger: Personen und deren Handys (mobile_app-Benachrichtigungsdienste)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify


def person_ids(hass: HomeAssistant) -> list[str]:
    """Alle Personen-Entitäten."""
    return sorted(hass.states.async_entity_ids("person"))


def persons_with_phone(hass: HomeAssistant) -> list[str]:
    """Personen mit mindestens einem registrierten Companion-App-Gerät.

    Nur sie können eine Push-Nachricht bekommen; Personen ohne Handy (z. B.
    reine Anmelde-Konten) tauchen deshalb in der Auswahl nicht auf. Die
    Prüfung läuft über die Geräteregistrierung und hängt nicht davon ab, ob der
    Benachrichtigungsdienst schon geladen ist.
    """
    return [pid for pid in person_ids(hass) if person_services(hass, pid)]


def person_services(hass: HomeAssistant, person_entity_id: str) -> list[str]:
    """Benachrichtigungsdienste (``mobile_app_*``) der Geräte einer Person.

    Die Zuordnung läuft über die Geräte-Tracker der Person: Gehört ein Tracker
    zur Companion App, heißt der Dienst ``mobile_app_<geräte-name>``.
    """
    state = hass.states.get(person_entity_id)
    if state is None:
        return []
    registry = er.async_get(hass)
    services: list[str] = []
    for tracker in state.attributes.get("device_trackers") or []:
        entry = registry.async_get(tracker)
        if entry is None or entry.platform != "mobile_app" or not entry.config_entry_id:
            continue
        config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
        if config_entry is None:
            continue
        name = config_entry.data.get("device_name") or config_entry.title
        service = f"mobile_app_{slugify(name)}"
        if service not in services:
            services.append(service)
    return services


def all_mobile_services(hass: HomeAssistant) -> list[str]:
    """Alle vorhandenen ``notify.mobile_app_*``-Dienste."""
    return sorted(
        service
        for service in hass.services.async_services_for_domain("notify")
        if service.startswith("mobile_app_")
    )


def recipients_view(hass: HomeAssistant, excluded: list[str]) -> list[dict[str, Any]]:
    """Personen mit Handy für die Einstellungsübersicht (ohne Handy: nicht gelistet)."""
    result: list[dict[str, Any]] = []
    for pid in persons_with_phone(hass):
        state = hass.states.get(pid)
        services = [
            s
            for s in person_services(hass, pid)
            if hass.services.has_service("notify", s)
        ]
        result.append(
            {
                "id": pid,
                "name": (state.attributes.get("friendly_name") if state else None) or pid,
                "state": state.state if state else None,
                "picture": state.attributes.get("entity_picture") if state else None,
                "services": services,
                "active_services": [s for s in services if s not in excluded],
            }
        )
    return result
