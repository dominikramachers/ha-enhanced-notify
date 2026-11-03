"""Vorgegebener Katalog der Benachrichtigungstypen.

Jeder Typ erscheint in der Einstellungsübersicht, auch wenn er noch nie
ausgelöst wurde. Unbekannte Typen, die per ``enhanced_notify.send`` ankommen,
werden beim ersten Auslösen automatisch ergänzt (Kategorie "system").

Felder je Typ:
    name         deutscher Anzeigename
    category     Schlüssel aus CATEGORIES
    icon         mdi-Icon
    description  kurze Erklärung für die Einstellungsübersicht
    example      Beispieltext
    default_push "all" = standardmäßig an alle Personen, "none" = niemand
    push_when    "always" oder "away" (nur an Personen, die nicht zuhause sind)
    priority     "normal" oder "high" (high = zeitkritisch auf dem iPhone)
"""

from __future__ import annotations

from typing import Any

CATEGORIES: dict[str, dict[str, str]] = {
    "pakete": {"name": "Pakete", "icon": "mdi:package-variant-closed", "color": "#E0D700"},
    "haustuer": {"name": "Haustür", "icon": "mdi:door-open", "color": "#3B82F6"},
    "waesche": {"name": "Wäsche", "icon": "mdi:washing-machine", "color": "#06B6D4"},
    "saugroboter": {"name": "Saugroboter", "icon": "mdi:robot-vacuum", "color": "#10B981"},
    "kalender": {"name": "Kalender", "icon": "mdi:calendar-plus", "color": "#EF4444"},
    "vorrat": {"name": "Keller-Vorrat", "icon": "mdi:warehouse", "color": "#F59E0B"},
    "system": {"name": "System", "icon": "mdi:cog-outline", "color": "#6B7280"},
}

DEFAULT_CATEGORY = "system"
DEFAULT_ICON = "mdi:bell-outline"

CATALOG: dict[str, dict[str, Any]] = {
    # --- Pakete -----------------------------------------------------------
    "paket_unterwegs": {
        "name": "Paket unterwegs",
        "category": "pakete",
        "icon": "mdi:truck-fast-outline",
        "description": "Statuswechsel einer Sendung, z. B. für den Weitertransport vorbereitet.",
        "example": "Hermes: Wurde für den Weitertransport vorbereitet",
        "default_push": "none",
    },
    "paket_termin": {
        "name": "Voraussichtliche Lieferung",
        "category": "pakete",
        "icon": "mdi:calendar-clock",
        "description": "Neuer oder geänderter Liefertermin bzw. Zeitfenster.",
        "example": "DHL: Voraussichtliche Lieferung am Dienstag, 10–12 Uhr",
        "default_push": "none",
    },
    "paket_in_zustellung": {
        "name": "Paket in Zustellung",
        "category": "pakete",
        "icon": "mdi:truck-delivery-outline",
        "description": "Sendung ist beim Zusteller auf Tour und kommt heute.",
        "example": "Amazon: Dein Paket kommt heute zwischen 14 und 18 Uhr",
        "default_push": "all",
    },
    "paket_zugestellt": {
        "name": "Paket zugestellt",
        "category": "pakete",
        "icon": "mdi:package-variant-closed-check",
        "description": "Sendung wurde zugestellt oder abgegeben.",
        "example": "DPD: Dein Paket wurde zugestellt",
        "default_push": "all",
    },
    "paket_problem": {
        "name": "Paket: Problem",
        "category": "pakete",
        "icon": "mdi:package-variant-remove",
        "description": "Zustellung gescheitert, Sendung verzögert oder Abholung nötig.",
        "example": "DHL: Zustellung nicht möglich",
        "default_push": "all",
    },
    # --- Haustür ----------------------------------------------------------
    "klingel": {
        "name": "Es klingelt",
        "category": "haustuer",
        "icon": "mdi:bell-ring-outline",
        "description": "Jemand klingelt an der Haustür (Gegensprechanlage).",
        "example": "Es hat an der Haustür geklingelt",
        "default_push": "all",
        "push_when": "away",
        "priority": "high",
    },
    # --- Wäsche -----------------------------------------------------------
    "waschmaschine_fertig": {
        "name": "Waschmaschine fertig",
        "category": "waesche",
        "icon": "mdi:washing-machine",
        "description": "Der Waschgang ist beendet.",
        "example": "Die Waschmaschine ist fertig",
        "default_push": "all",
    },
    "trockner_fertig": {
        "name": "Trockner fertig",
        "category": "waesche",
        "icon": "mdi:tumble-dryer",
        "description": "Der Trockner ist fertig.",
        "example": "Der Trockner ist fertig",
        "default_push": "all",
    },
    # --- Saugroboter ------------------------------------------------------
    "saugroboter_fertig": {
        "name": "Saugroboter fertig",
        "category": "saugroboter",
        "icon": "mdi:robot-vacuum",
        "description": "Der Saugvorgang wurde abgeschlossen.",
        "example": "Der Saugvorgang wurde abgeschlossen",
        "default_push": "all",
    },
    "saugroboter_problem": {
        "name": "Saugroboter: Problem",
        "category": "saugroboter",
        "icon": "mdi:robot-vacuum-alert",
        "description": "Der Saugroboter meldet eine Störung, z. B. festgefahren.",
        "example": "Der Saugroboter hat ein Problem gemeldet: festgefahren",
        "default_push": "all",
        "priority": "high",
    },
    "saugroboter_wartung": {
        "name": "Saugroboter: Wartung",
        "category": "saugroboter",
        "icon": "mdi:wrench-clock",
        "description": "Verbrauchsmaterial wechseln, Wassertank, Abwasser u. Ä.",
        "example": "Seitenbürste bald verschlissen",
        "default_push": "none",
    },
    # --- Kalender ---------------------------------------------------------
    "kalender_neuer_termin": {
        "name": "Neuer Kalendertermin",
        "category": "kalender",
        "icon": "mdi:calendar-plus",
        "description": "Im Kalender wurde ein neuer Termin angelegt.",
        "example": "Neuer Termin: Zahnarzt, Do 14:30",
        "default_push": "none",
    },
    # --- Keller-Vorrat ----------------------------------------------------
    "vorrat_niedrig": {
        "name": "Vorrat niedrig",
        "category": "vorrat",
        "icon": "mdi:package-down",
        "description": "Ein Artikel im Keller unterschreitet die Mindestanzahl.",
        "example": "Sprite: nur noch 2 von mindestens 6",
        "default_push": "none",
    },
    "vorrat_mhd": {
        "name": "Haltbarkeit läuft ab",
        "category": "vorrat",
        "icon": "mdi:calendar-alert",
        "description": "Das Mindesthaltbarkeitsdatum eines Artikels läuft bald ab.",
        "example": "Passierte Tomaten: MHD in 7 Tagen",
        "default_push": "none",
    },
    # --- System -----------------------------------------------------------
    "ha_system": {
        "name": "Home-Assistant-Meldung",
        "category": "system",
        "icon": "mdi:home-assistant",
        "description": "Übernommene Meldungen aus der HA-Benachrichtigungsliste.",
        "example": "Neue Geräte entdeckt",
        "default_push": "none",
    },
    "geraet_offline": {
        "name": "Gerät offline",
        "category": "system",
        "icon": "mdi:lan-disconnect",
        "description": "Ein Gerät ist seit längerer Zeit nicht erreichbar.",
        "example": "Steckdose Waschmaschine ist offline",
        "default_push": "none",
    },
}
