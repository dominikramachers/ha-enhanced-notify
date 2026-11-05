"""Zusteller-Logos für Paket-Meldungen.

Paket-Meldungen tragen den Zusteller im Titel (``DHL: Name der Sendung``). Daran
erkennt die Integration den Zusteller und nimmt dessen Logo als Icon der Meldung:
in der Liste und, wenn möglich, als Bild im Push (``icon_url``).

Die Logos liegen als ``<id>.webp`` im Ordner ``carriers/`` und werden unter
``/enhanced_notify/carriers/`` ausgeliefert. Ein weiterer Zusteller braucht nur
eine Datei ``<id>.webp`` (am besten quadratisch, 144 × 144) und bei Bedarf einen
Eintrag in ``ALIASES``.
"""

from __future__ import annotations

from pathlib import Path
import re

from .const import DOMAIN

CARRIERS_DIR = Path(__file__).parent / "carriers"
CARRIERS_URL = f"/{DOMAIN}/carriers"

# Zusteller-ID (= Dateiname) -> Schreibweisen im Titel (klein, ohne Leer- und Sonderzeichen)
ALIASES: dict[str, tuple[str, ...]] = {
    "dhl": ("dhl", "dhlpaket", "dhlexpress", "deutschepost"),
    "dpd": ("dpd",),
    "hermes": ("hermes", "myhermes"),
    "picnic": ("picnic",),
    "amazon": ("amazon", "amazonlogistics"),
    "ups": ("ups",),
    "gls": ("gls",),
    "fedex": ("fedex",),
}

_BY_ALIAS = {alias: cid for cid, aliases in ALIASES.items() for alias in aliases}
_NORMALIZE = re.compile(r"[^a-z0-9]")


def carrier_id(title: str | None) -> str | None:
    """Zusteller aus dem Titel ``<Zusteller>: <Sendung>`` ermitteln, sonst ``None``."""
    if not title or ":" not in title:
        return None
    head = _NORMALIZE.sub("", title.split(":", 1)[0].lower())
    return _BY_ALIAS.get(head)


def carrier_icon(title: str | None) -> str | None:
    """Pfad zum Logo des Zustellers im Titel, ``None`` wenn unbekannt oder kein Logo vorhanden."""
    cid = carrier_id(title)
    if cid and (CARRIERS_DIR / f"{cid}.webp").is_file():
        return f"{CARRIERS_URL}/{cid}.webp"
    return None
