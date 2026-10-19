"""Kern der Benachrichtigungszentrale: Speicher, Typen, Push, Aufbewahrung."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import hashlib
import logging
from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .catalog import CATALOG, CATEGORIES, DEFAULT_CATEGORY, DEFAULT_ICON
from .const import (
    ACTION_READ_PREFIX,
    CONF_EXCLUDED_SERVICES,
    CONF_MAX_ITEMS,
    CONF_RETENTION_DAYS,
    CONF_RETENTION_READ_DAYS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_RETENTION_READ_DAYS,
    EVENT_CREATED,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PUSH_ALWAYS,
    PUSH_AWAY,
    PUSH_MODES,
    SOURCE_PERSISTENT,
    STORAGE_KEY,
    STORAGE_VERSION,
    TAG_PERSISTENT_PREFIX,
)
from .recipients import person_ids, person_services, persons_with_phone, recipients_view
from .translate import translate_persistent

_LOGGER = logging.getLogger(__name__)

_UNSET: Any = object()

MAX_SEEN = 5000


class NotificationManager:
    """Hält alle Meldungen und Typ-Einstellungen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.items: list[dict[str, Any]] = []  # neueste zuerst
        self.custom_types: dict[str, dict[str, Any]] = {}
        self.type_settings: dict[str, dict[str, Any]] = {}
        self.stats: dict[str, dict[str, Any]] = {}
        # Bereits gemeldete Tags (für ``once``), älteste zuerst, begrenzt
        self.seen: dict[str, None] = {}
        # Zuletzt gemeldeter Inhalt je Tag (tag -> Fingerabdruck). Verhindert, dass
        # gelesene oder gelöschte Meldungen mit gleichem Inhalt neu auftauchen.
        self.announced: dict[str, str] = {}
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------ Speicher

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.items = list(data.get("items", []))
        self.custom_types = dict(data.get("custom_types", {}))
        self.type_settings = dict(data.get("type_settings", {}))
        self.stats = dict(data.get("stats", {}))
        self.seen = dict.fromkeys(data.get("seen", []))
        self.announced = dict(data.get("announced", {}))
        # Bestehende Meldungen mit Tag merken (Update von einer Version ohne Merkzettel)
        for item in reversed(self.items):
            item_tag = item.get("tag")
            if item_tag and item_tag not in self.announced and not str(item_tag).startswith(
                TAG_PERSISTENT_PREFIX
            ):
                self.announced[item_tag] = self._fingerprint(item["title"], item["message"])
        self._retranslate_persistent()

    def _retranslate_persistent(self) -> None:
        """Als „System“ übernommene HA-Meldungen mit den aktuellen Regeln neu einordnen."""
        types = self.types_view()
        for item in self.items:
            tag = str(item.get("tag") or "")
            data = item.get("data") or {}
            if (
                item.get("type") != "ha_system"
                or not tag.startswith(TAG_PERSISTENT_PREFIX)
                or data.get("source") != SOURCE_PERSISTENT
            ):
                continue
            result = translate_persistent(
                tag[len(TAG_PERSISTENT_PREFIX):],
                data.get("original_title"),
                data.get("original_message"),
            )
            info = types.get(result["type"])
            if result["type"] == "ha_system" or not info:
                continue
            item.update(
                type=result["type"],
                category=info["category"],
                title=result["title"],
                message=result["message"],
                icon=None,
            )
            self._changed()

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "custom_types": self.custom_types,
            "type_settings": self.type_settings,
            "stats": self.stats,
            "seen": list(self.seen),
            "announced": self.announced,
        }

    async def async_flush(self) -> None:
        await self._store.async_save(self._data_to_save())

    @callback
    def _changed(self) -> None:
        """Speichern verzögert und Beobachter (Sensor, Websocket) informieren."""
        self._store.async_delay_save(self._data_to_save, 1)
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Fehler in Beobachter der Benachrichtigungszentrale")

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    # ------------------------------------------------------------------ Optionen

    def _opt(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, default)

    @property
    def excluded_services(self) -> list[str]:
        return list(self._opt(CONF_EXCLUDED_SERVICES, []))

    # ------------------------------------------------------------------ Typen

    def _type_defs(self) -> dict[str, dict[str, Any]]:
        defs: dict[str, dict[str, Any]] = {k: dict(v) for k, v in CATALOG.items()}
        for key, value in self.custom_types.items():
            defs.setdefault(key, dict(value))
        return defs

    def types_view(self) -> dict[str, dict[str, Any]]:
        # Nur Personen mit Handy können einen Push bekommen
        persons = persons_with_phone(self.hass)
        result: dict[str, dict[str, Any]] = {}
        for tid, d in self._type_defs().items():
            settings = self.type_settings.get(tid, {})
            explicit = settings.get("recipients")
            if explicit is not None:
                effective = [p for p in explicit if p in persons]
            else:
                effective = list(persons) if d.get("default_push", "none") == "all" else []
            stat = self.stats.get(tid, {})
            result[tid] = {
                "id": tid,
                "name": d.get("name", tid),
                "category": d.get("category", DEFAULT_CATEGORY),
                "icon": d.get("icon", DEFAULT_ICON),
                "description": d.get("description", ""),
                "example": d.get("example", ""),
                "push_when": settings.get("push_when") or d.get("push_when", PUSH_ALWAYS),
                "priority": d.get("priority", PRIORITY_NORMAL),
                "recipients": explicit,
                "recipients_effective": effective,
                "customized": bool(settings),
                "auto": bool(d.get("auto", False)),
                "last": stat.get("last"),
                "count": stat.get("count", 0),
            }
        return result

    @callback
    def async_set_type(
        self,
        type_id: str,
        *,
        recipients: Any = _UNSET,
        push_when: str | None = None,
        reset: bool = False,
    ) -> None:
        """Push-Empfänger und -Modus eines Typs setzen."""
        if type_id not in self._type_defs():
            raise ServiceValidationError(f"Unbekannter Typ: {type_id}")
        if reset:
            self.type_settings.pop(type_id, None)
            self._changed()
            return
        settings = dict(self.type_settings.get(type_id, {}))
        if recipients is not _UNSET:
            if recipients is None:
                settings.pop("recipients", None)
            else:
                unknown = [p for p in recipients if p not in person_ids(self.hass)]
                if unknown:
                    raise ServiceValidationError(f"Unbekannte Personen: {', '.join(unknown)}")
                settings["recipients"] = list(dict.fromkeys(recipients))
        if push_when is not None:
            if push_when not in PUSH_MODES:
                raise ServiceValidationError(f"Ungültiger Push-Modus: {push_when}")
            settings["push_when"] = push_when
        if settings:
            self.type_settings[type_id] = settings
        else:
            self.type_settings.pop(type_id, None)
        self._changed()

    def _register_custom_type(
        self, type_id: str, name: str | None, category: str | None
    ) -> None:
        category = category if category in CATEGORIES else DEFAULT_CATEGORY
        self.custom_types[type_id] = {
            "name": name or type_id.replace("_", " ").capitalize(),
            "category": category,
            "icon": CATEGORIES[category]["icon"],
            "description": "Automatisch angelegt beim ersten Auslösen.",
            "default_push": "none",
            "auto": True,
        }

    # ------------------------------------------------------------------ Zähler

    @property
    def unread(self) -> int:
        return sum(1 for item in self.items if not item.get("read"))

    def snapshot(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "unread": self.unread,
            "types": self.types_view(),
            "categories": CATEGORIES,
            "recipients": recipients_view(self.hass, self.excluded_services),
        }

    # ------------------------------------------------------------------ Senden

    @staticmethod
    def _fingerprint(title: str, message: str) -> str:
        return hashlib.sha1(f"{title}\x1f{message}".encode()).hexdigest()[:16]  # noqa: S324

    async def async_send(
        self,
        type_id: str,
        message: str,
        *,
        title: str | None = None,
        tag: str | None = None,
        link: str | None = None,
        icon: str | None = None,
        push: bool = True,
        priority: str | None = None,
        category: str | None = None,
        type_name: str | None = None,
        data: dict[str, Any] | None = None,
        once: bool = False,
        baseline: bool = False,
        remember: bool = True,
    ) -> dict[str, Any]:
        """Neue Meldung anlegen (oder per ``tag`` aktualisieren) und pushen.

        ``once``: Der ``tag`` wird nur ein einziges Mal gemeldet, auch wenn die
        Meldung inzwischen gelöscht wurde (z. B. neue Kalendertermine).
        ``baseline`` (nur mit ``once``): den ``tag`` nur als gesehen vormerken,
        ohne Meldung und Push (stiller Erstlauf).
        ``remember``: Mit ``tag`` wird der zuletzt gemeldete Inhalt dauerhaft
        gemerkt. Dieselbe Meldung (gleicher Titel und Text) taucht danach nicht
        wieder auf, auch nicht nach Lesen, Löschen oder einem Neustart; erst ein
        geänderter Inhalt meldet wieder.
        """
        if (once or baseline) and not tag:
            raise ServiceValidationError("once und baseline brauchen einen tag")
        if once or baseline:
            if tag in self.seen:
                return {"id": None, "deduplicated": True}
            self.seen[tag] = None
            while len(self.seen) > MAX_SEEN:
                self.seen.pop(next(iter(self.seen)))
            self._changed()
            if baseline:
                return {"id": None, "deduplicated": False, "baseline": True}
        type_id = slugify(type_id)
        if not type_id:
            raise ServiceValidationError("Der Typ darf nicht leer sein")
        if type_id not in self._type_defs():
            self._register_custom_type(type_id, type_name, category)
        info = self.types_view()[type_id]
        final_title = title or info["name"]
        now = dt_util.utcnow().isoformat()

        fingerprint: str | None = None
        if tag and remember:
            fingerprint = self._fingerprint(final_title, message)
            if self.announced.get(tag) == fingerprint:
                known = next((i for i in self.items if i.get("tag") == tag), None)
                return {"id": known["id"] if known else None, "deduplicated": True}

        existing = next((i for i in self.items if tag and i.get("tag") == tag), None)
        if existing is not None:
            if existing["title"] == final_title and existing["message"] == message:
                return {"id": existing["id"], "deduplicated": True}
            existing.update(
                type=type_id,
                category=info["category"],
                title=final_title,
                message=message,
                updated=now,
                read=False,
                read_at=None,
                count=existing.get("count", 1) + 1,
                link=link or existing.get("link"),
                icon=icon or existing.get("icon"),
            )
            if data:
                existing["data"] = {**existing.get("data", {}), **data}
            self.items.remove(existing)
            self.items.insert(0, existing)
            item = existing
        else:
            item = {
                "id": uuid.uuid4().hex,
                "type": type_id,
                "category": info["category"],
                "title": final_title,
                "message": message,
                "tag": tag,
                "link": link,
                "icon": icon,
                "created": now,
                "updated": now,
                "read": False,
                "read_at": None,
                "count": 1,
                "pushed": [],
                "data": dict(data or {}),
            }
            self.items.insert(0, item)

        if fingerprint and tag:
            self.announced.pop(tag, None)
            self.announced[tag] = fingerprint
            while len(self.announced) > MAX_SEEN:
                self.announced.pop(next(iter(self.announced)))

        stat = self.stats.setdefault(type_id, {"count": 0})
        stat["last"] = now
        stat["count"] = stat.get("count", 0) + 1

        self._apply_max_items()
        self._changed()
        self.hass.bus.async_fire(
            EVENT_CREATED,
            {
                "id": item["id"],
                "type": type_id,
                "category": item["category"],
                "title": item["title"],
                "message": item["message"],
            },
        )
        if push:
            await self._async_push(item, info, priority)
        return {"id": item["id"], "deduplicated": False}

    # ------------------------------------------------------------------ Push

    def _push_targets(self, info: dict[str, Any]) -> list[str]:
        """Dienstnamen, an die gepusht werden soll."""
        excluded = self.excluded_services
        services: list[str] = []
        for pid in info["recipients_effective"]:
            state = self.hass.states.get(pid)
            if state is None:
                continue
            if info["push_when"] == PUSH_AWAY and state.state == "home":
                continue
            for service in person_services(self.hass, pid):
                if service in excluded or service in services:
                    continue
                if self.hass.services.has_service("notify", service):
                    services.append(service)
        return services

    async def _async_push(
        self, item: dict[str, Any], info: dict[str, Any], priority: str | None
    ) -> None:
        services = self._push_targets(info)
        if not services:
            return
        data: dict[str, Any] = {
            "tag": item["id"],
            "group": item["category"],
            "actions": [{"action": f"{ACTION_READ_PREFIX}{item['id']}", "title": "Gelesen"}],
        }
        if item.get("link"):
            data["url"] = item["link"]
            data["clickAction"] = item["link"]
        if (priority or info["priority"]) == PRIORITY_HIGH:
            data["push"] = {"interruption-level": "time-sensitive"}
        for service in services:
            await self.hass.services.async_call(
                "notify",
                service,
                {"title": item["title"], "message": item["message"], "data": data},
                blocking=False,
            )
        item["pushed"] = list(dict.fromkeys([*item.get("pushed", []), *services]))
        self._changed()

    async def _async_clear_push(self, item: dict[str, Any]) -> None:
        """Push auf den Handys entfernen, sobald die Meldung gelesen/gelöscht ist."""
        for service in item.get("pushed", []):
            if not self.hass.services.has_service("notify", service):
                continue
            await self.hass.services.async_call(
                "notify",
                service,
                {"message": "clear_notification", "data": {"tag": item["id"]}},
                blocking=False,
            )
        item["pushed"] = []

    # ------------------------------------------------------------------ Lesen / Löschen

    async def async_mark_read(
        self, ids: list[str] | None = None, *, mark_all: bool = False, read: bool = True
    ) -> int:
        wanted = set(ids or [])
        now = dt_util.utcnow().isoformat()
        changed: list[dict[str, Any]] = []
        for item in self.items:
            if not mark_all and item["id"] not in wanted:
                continue
            if bool(item.get("read")) != read:
                item["read"] = read
                item["read_at"] = now if read else None
                changed.append(item)
        if changed:
            if read:
                for item in changed:
                    await self._async_clear_push(item)
            self._changed()
        return len(changed)

    async def async_delete(
        self,
        ids: list[str] | None = None,
        *,
        delete_all: bool = False,
        only_read: bool = False,
        tags: list[str] | None = None,
    ) -> int:
        wanted = set(ids or [])
        wanted_tags = set(tags or [])
        removed: list[dict[str, Any]] = []
        kept: list[dict[str, Any]] = []
        for item in self.items:
            hit = (
                (
                    delete_all
                    or item["id"] in wanted
                    or (bool(item.get("tag")) and item["tag"] in wanted_tags)
                )
                and (not only_read or item.get("read"))
            )
            (removed if hit else kept).append(item)
        if removed:
            self.items = kept
            for item in removed:
                await self._async_clear_push(item)
            self._changed()
        return len(removed)

    async def async_handle_push_action(self, action: str | None) -> None:
        """Button „Gelesen“ in der Push-Meldung."""
        if action and action.startswith(ACTION_READ_PREFIX):
            await self.async_mark_read([action[len(ACTION_READ_PREFIX):]])

    # ------------------------------------------------------------------ HA-Meldungen

    async def async_import_persistent(
        self, notification_id: str, title: str | None, message: str | None
    ) -> bool:
        """Persistente HA-Meldung übersetzt übernehmen."""
        translated = translate_persistent(notification_id, title, message)
        await self.async_send(
            translated["type"],
            translated["message"],
            title=translated["title"],
            tag=f"{TAG_PERSISTENT_PREFIX}{notification_id}",
            data={
                "source": SOURCE_PERSISTENT,
                "original_title": title,
                "original_message": message,
            },
            # HA-Meldungen können sich legitim wiederholen (gleicher Text, neues Ereignis)
            remember=False,
        )
        return True

    # ------------------------------------------------------------------ Aufbewahrung

    def _apply_max_items(self) -> None:
        limit = int(self._opt(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS))
        while len(self.items) > limit:
            for index in range(len(self.items) - 1, -1, -1):
                if self.items[index].get("read"):
                    del self.items[index]
                    break
            else:
                self.items.pop()

    async def async_cleanup(self) -> int:
        """Alte Meldungen entfernen (gelesene früher als ungelesene)."""
        now = dt_util.utcnow()
        read_cut = now - timedelta(days=int(self._opt(CONF_RETENTION_READ_DAYS, DEFAULT_RETENTION_READ_DAYS)))
        all_cut = now - timedelta(days=int(self._opt(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)))
        kept: list[dict[str, Any]] = []
        removed = 0
        for item in self.items:
            updated = dt_util.parse_datetime(item.get("updated", "")) or now
            if updated < all_cut or (item.get("read") and updated < read_cut):
                removed += 1
                continue
            kept.append(item)
        if removed:
            self.items = kept
        before = len(self.items)
        self._apply_max_items()
        removed += before - len(self.items)
        if removed:
            self._changed()
        return removed
