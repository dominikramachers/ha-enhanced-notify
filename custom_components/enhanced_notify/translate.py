"""Übersetzung übernommener HA-Meldungen ins Deutsche.

Persistente HA-Benachrichtigungen (z. B. vom Saugroboter) kommen meist auf
Englisch. ``translate_persistent`` ordnet sie einem Typ zu und formuliert sie
auf Deutsch um. Was nicht erkannt wird, landet unverändert als
``ha_system``. Die Regeln lassen sich unten einfach erweitern.
"""

from __future__ import annotations

import re
from typing import Any

_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKUP = re.compile(r"[*_`#>]+")

# Saugroboter-Kontext: Dreame meldet je nach Spracheinstellung deutsch oder englisch.
_VACUUM = re.compile(
    r"staubsauger|saugroboter|wischroboter|roboter|robot|vacuum|dreame|cleanup|cleaning|reinigung"
    r"|frischwasser|schmutzwasser|abwasser|wassertank|water tank|clean water|dirty water|waste water"
    r"|wischpad|wischmopp|seitenb(ü|ue)rste|hauptb(ü|ue)rste|side brush|main brush|dust bag|staubbeutel"
)

# Verbrauchsmaterial (Dreame): Begriff (deutsch/englisch) -> deutscher Name
_CONSUMABLES: list[tuple[str, str]] = [
    (r"main\s*brush|hauptb(ü|ue)rste", "Hauptbürste"),
    (r"side\s*brush|seitenb(ü|ue)rste", "Seitenbürste"),
    (r"mop\s*pad|mop\s*cloth|mop|wischpad|wischmopp|wischtuch", "Wischpad"),
    (r"filter", "Filter"),
    (r"sensor", "Sensoren"),
    (r"silver\s*ion|silberion", "Silberionen-Modul"),
    (r"detergent|reinigungsmittel", "Reinigungsmittel"),
    (r"dust\s*bag|staubbeutel", "Staubbeutel"),
    (r"dust\s*collection|dust\s*bin|staubbeh(ä|ae)lter", "Staubbehälter"),
]

_DONE = r"cleanup completed|cleaning completed|cleaning (job )?(is )?(finished|completed)|reinigung (ist )?(abgeschlossen|beendet|fertig)|saugvorgang (ist )?(abgeschlossen|beendet)"
_PROBLEM = r"stuck|trapped|blocked|error|failed|festgefahren|fehler|blockiert|fehlgeschlagen|steckt fest|h(ä|ae)ngt fest"
_DIRTY = r"drain|dirty water|waste water|schmutzwasser|abwasser|entleer"
_FRESH = r"low water|water tank|water level|clean water|fresh water|frischwasser|wassertank|wasser.{0,40}(aufgebraucht|leer|nachf(ü|ue)llen|auff(ü|ue)llen)|(auff(ü|ue)llen|nachf(ü|ue)llen).{0,40}wasser"


def clean(text: str | None) -> str:
    """Markdown-Links und -Auszeichnungen entfernen."""
    if not text:
        return ""
    text = _LINK.sub(r"\1", text)
    text = _MARKUP.sub("", text)
    return re.sub(r"\s+\n", "\n", text).strip()


def _consumable_name(text: str) -> str | None:
    lowered = text.lower()
    for pattern, name in _CONSUMABLES:
        if re.search(pattern, lowered):
            return name
    return None


def translate_persistent(
    notification_id: str, title: str | None, message: str | None
) -> dict[str, Any]:
    """Liefert ``{"type", "title", "message"}`` für eine HA-Meldung."""
    raw_title = clean(title)
    raw_message = clean(message)
    haystack = f"{notification_id} {raw_title} {raw_message}".lower()

    # --- Saugroboter ------------------------------------------------------
    vacuum = bool(_VACUUM.search(haystack))
    if vacuum:
        if re.search(_DONE, haystack):
            return {
                "type": "saugroboter_fertig",
                "title": "Reinigung abgeschlossen",
                "message": "Der Saugroboter hat die Reinigung abgeschlossen.",
            }
        if re.search(_PROBLEM, haystack):
            return {
                "type": "saugroboter_problem",
                "title": raw_title or "Saugroboter: Problem",
                "message": raw_message or "Der Saugroboter meldet ein Problem.",
            }
        if re.search(_DIRTY, haystack):
            return {
                "type": "saugroboter_wartung",
                "title": "Abwasser entleeren",
                "message": "Das Abwasser muss manuell entleert werden.",
            }
        if re.search(_FRESH, haystack):
            return {
                "type": "saugroboter_wartung",
                "title": "Wassertank fast leer",
                "message": "Der Saugroboter braucht frisches Wasser im Tank.",
            }
        if re.search(
            r"consumable|depleted|worn out|replace|life|verbraucht|verschlissen|abgenutzt|ersetzen|austauschen|wechseln|lebensdauer|verbrauchsmaterial",
            haystack,
        ):
            name = _consumable_name(haystack)
            if name:
                depleted = bool(
                    re.search(r"depleted|worn out|ended|expired|verbraucht|verschlissen|abgenutzt|ersetzen|austauschen", haystack)
                    and not re.search(r"bald|soon|low|geht zur neige|fast", haystack)
                )
                return {
                    "type": "saugroboter_wartung",
                    "title": f"{name} wechseln" if depleted else f"{name} bald verschlissen",
                    "message": (
                        f"{name} ist verbraucht und sollte ersetzt werden."
                        if depleted
                        else f"Die Lebensdauer von {name} geht zur Neige."
                    ),
                }

    # --- Home Assistant ---------------------------------------------------
    if re.search(r"new devices? discovered|discovered", haystack):
        return {
            "type": "ha_system",
            "title": "Neue Geräte entdeckt",
            "message": "Home Assistant hat neue Geräte gefunden. Hinzufügen unter Einstellungen → Geräte & Dienste.",
        }
    if re.search(r"re-?authenticat|reauth", haystack):
        return {
            "type": "ha_system",
            "title": "Erneute Anmeldung nötig",
            "message": "Eine Integration braucht eine erneute Anmeldung. Öffne Einstellungen → Geräte & Dienste.",
        }
    if re.search(r"invalid config|configuration (is )?invalid|check_config", haystack):
        return {
            "type": "ha_system",
            "title": "Konfigurationsfehler",
            "message": raw_message or "In der Home-Assistant-Konfiguration wurde ein Fehler gefunden.",
        }

    if vacuum:
        # Alles andere vom Saugroboter bleibt beim Saugroboter (Wartung), Text unverändert
        return {
            "type": "saugroboter_wartung",
            "title": raw_title or "Saugroboter",
            "message": raw_message or raw_title or "Neue Meldung vom Saugroboter.",
        }

    return {
        "type": "ha_system",
        "title": raw_title or "Home Assistant",
        "message": raw_message or raw_title or "Neue Meldung von Home Assistant.",
    }
