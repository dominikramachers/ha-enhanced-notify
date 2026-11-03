"""Einrichtung und Optionen."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_DISMISS_IMPORTED,
    CONF_EXCLUDED_SERVICES,
    CONF_IMPORT_PERSISTENT,
    CONF_MAX_ITEMS,
    CONF_PUSH_ICON,
    CONF_PUSH_ICON_FORCE,
    CONF_RETENTION_DAYS,
    CONF_RETENTION_READ_DAYS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_RETENTION_READ_DAYS,
    DOMAIN,
)
from .recipients import all_mobile_services


class DoralabNotifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung: ein Klick, alles Weitere in den Optionen."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="DORALAB Benachrichtigungen", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> OptionsFlow:
        return DoralabNotifyOptionsFlow()


# Bild für das Push-Icon: Pfad auf diese HA-Instanz (/local/logo.png) oder Webadresse.
# Ein MDI-Name oder ein eingebettetes Bild taugt nicht, die Companion-App lädt das Bild.
_PUSH_ICON = re.compile(r"^(?:/(?!/)\S+|https?://\S+)$")


def _days(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX)
    )


class DoralabNotifyOptionsFlow(OptionsFlow):
    """Aufbewahrung, HA-Meldungen übernehmen, ausgeschlossene Geräte."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            for key in (CONF_RETENTION_READ_DAYS, CONF_RETENTION_DAYS, CONF_MAX_ITEMS):
                if key in user_input:
                    user_input[key] = int(user_input[key])
            user_input[CONF_PUSH_ICON] = str(user_input.get(CONF_PUSH_ICON) or "").strip()
            if user_input[CONF_PUSH_ICON] and not _PUSH_ICON.match(user_input[CONF_PUSH_ICON]):
                return self._show_form(user_input, {CONF_PUSH_ICON: "invalid_push_icon"})
            return self.async_create_entry(data=user_input)

        return self._show_form(self.config_entry.options, {})

    def _show_form(self, values: Any, errors: dict[str, str]) -> ConfigFlowResult:
        options = values
        excluded = list(options.get(CONF_EXCLUDED_SERVICES, []))
        services = sorted({*all_mobile_services(self.hass), *excluded})
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RETENTION_READ_DAYS,
                    default=options.get(CONF_RETENTION_READ_DAYS, DEFAULT_RETENTION_READ_DAYS),
                ): _days(1, 365),
                vol.Required(
                    CONF_RETENTION_DAYS,
                    default=options.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS),
                ): _days(1, 730),
                vol.Required(
                    CONF_MAX_ITEMS, default=options.get(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS)
                ): _days(20, 2000),
                vol.Required(
                    CONF_IMPORT_PERSISTENT, default=options.get(CONF_IMPORT_PERSISTENT, True)
                ): BooleanSelector(),
                vol.Required(
                    CONF_DISMISS_IMPORTED, default=options.get(CONF_DISMISS_IMPORTED, True)
                ): BooleanSelector(),
                vol.Optional(CONF_EXCLUDED_SERVICES, default=excluded): SelectSelector(
                    SelectSelectorConfig(options=services, multiple=True, custom_value=True)
                ),
                vol.Optional(
                    CONF_PUSH_ICON, description={"suggested_value": options.get(CONF_PUSH_ICON, "")}
                ): TextSelector(),
                vol.Required(
                    CONF_PUSH_ICON_FORCE, default=options.get(CONF_PUSH_ICON_FORCE, False)
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
