"""Browser-Smoke-Test der Oberfläche; wird von test_frontend.py in einem eigenen Prozess gestartet."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

JS = Path(__file__).parents[1] / "custom_components" / "enhanced_notify" / "frontend" / "enhanced-notify.js"

SNAPSHOT = {
    "unread": 2,
    "categories": {
        "paket": {"name": "Pakete", "icon": "mdi:package-variant", "color": "#3B82F6"},
        "klingel": {"name": "Haustür", "icon": "mdi:doorbell", "color": "#EF4444"},
    },
    "types": {
        "zabbix_problem": {"id": "zabbix_problem", "name": "Zabbix: Problem", "category": "paket", "icon": "/local/zabbix.png", "auto": True,
                           "recipients_effective": [], "count": 1, "last": "2026-10-16T10:02:00+00:00", "push_when": "always"},
        "klingel": {"id": "klingel", "name": "Klingel", "category": "klingel", "icon": "mdi:doorbell",
                    "recipients_effective": [], "count": 1, "last": "2026-10-16T10:01:00+00:00", "push_when": "always"},
    },
    "recipients": [],
    "items": [
        {"id": "a", "type": "paket_zugestellt", "category": "paket", "title": "Hermes", "message": "Zugestellt", "read": False, "count": 1, "updated": "2026-10-16T10:00:00+00:00", "link": ""},
        {"id": "b", "type": "klingel", "category": "klingel", "title": "Klingel", "message": "Es klingelt", "read": False, "count": 1, "updated": "2026-10-16T10:01:00+00:00", "link": ""},
        {"id": "c", "type": "klingel", "category": "klingel", "title": "Alt", "message": "gelesen", "read": True, "count": 1, "updated": "2026-10-15T10:01:00+00:00", "link": ""},
        # Typ-Icon als Bild (Pfad) und eine unzulässige Icon-Angabe an der Meldung selbst
        {"id": "d", "type": "zabbix_problem", "category": "paket", "title": "Zabbix", "message": "Problem", "read": True, "count": 1, "updated": "2026-10-15T09:00:00+00:00", "link": ""},
        {"id": "e", "type": "klingel", "category": "klingel", "title": "Boese", "message": "x", "read": True, "count": 1, "updated": "2026-10-15T08:00:00+00:00", "link": "", "icon": "javascript:alert(1)"},
    ],
}

PAGE = """<!doctype html><html><body>
<script>
  // Minimal-Attrappe von Home Assistant: home-assistant > home-assistant-main > ha-sidebar
  window.calls = []; window.sidebarOpened = 0;
  class HaIcon extends HTMLElement {} customElements.define('ha-icon', HaIcon);
  const hass = {
    connection: { subscribeMessage: (cb) => { window.push = cb; cb(%SNAP%); return Promise.resolve(() => {}); } },
    callWS: (m) => { window.calls.push(m); return Promise.resolve({}); },
    callService: () => Promise.resolve(),
  };
  const mk = (tag) => { const e = document.createElement(tag); e.attachShadow({ mode: 'open' }); return e; };
  const haEl = mk('home-assistant'); const mainEl = mk('home-assistant-main'); const sbEl = mk('ha-sidebar');
  sbEl.shadowRoot.innerHTML = '<a id="sidebar-notifications"><ha-svg-icon></ha-svg-icon><span class="badge">9</span></a>';
  mainEl.shadowRoot.appendChild(sbEl); haEl.shadowRoot.appendChild(mainEl); haEl.hass = hass;
  document.body.appendChild(haEl);
</script>
</body></html>""".replace("%SNAP%", json.dumps(SNAPSHOT))




def check(cond, msg):
    if not cond:
        print(f"FEHLER: {msg}")
        sys.exit(1)


def main():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as err:  # noqa: BLE001
            print(f"SKIP: Chromium nicht verfügbar: {err}")
            sys.exit(77)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(PAGE)
        # zweimal laden: die zweite Kopie muss wirkungslos bleiben
        page.add_script_tag(path=str(JS), type="module")
        page.add_script_tag(path=str(JS))
        page.wait_for_timeout(500)
        check(errors == [], f"Skriptfehler: {errors}")
        check(
            page.evaluate("['enhanced-notify-bell','enhanced-notify-admin','enhanced-notify-panel'].every(n => !!customElements.get(n))"),
            "Elemente nicht registriert",
        )
        check(page.evaluate("window.customCards.filter(c => c.type === 'enhanced-notify-bell').length") == 1, "Karte doppelt registriert")
        check(page.evaluate("window.doralabNotify === window.enhancedNotify"), "Alias window.doralabNotify fehlt")
        # Sidebar-Glocke ohne Karte: hass kommt direkt vom home-assistant-Element
        page.wait_for_function("window.enhancedNotify.snap && window.enhancedNotify.snap.unread === 2", timeout=6000)
        page.wait_for_function(
            "(() => { const sb = document.querySelector('home-assistant').shadowRoot.querySelector('home-assistant-main').shadowRoot.querySelector('ha-sidebar');"
            " const b = sb.shadowRoot.querySelector('#sidebar-notifications .badge[data-nb]'); return b && b.textContent === '2'; })()",
            timeout=6000,
        )
        # Bell-Karte
        page.evaluate(
            "(() => { const c = document.createElement('enhanced-notify-bell'); c.setConfig({}); c.hass = document.querySelector('home-assistant').hass; c.id = 'bellcard'; document.body.appendChild(c); })()"
        )
        check(page.evaluate("document.getElementById('bellcard').shadowRoot.querySelector('.nb').textContent") == "2", "Zähler der Bell-Karte")
        page.evaluate("document.getElementById('bellcard').shadowRoot.querySelector('.nbell').click()")
        page.wait_for_selector("enhanced-notify-panel.open")
        titles = page.evaluate("[...document.querySelector('enhanced-notify-panel').shadowRoot.querySelectorAll('.it b')].map(b => b.textContent)")
        check(set(titles) == {"Hermes", "Klingel", "Alt", "Zabbix", "Boese"}, f"Liste: {titles}")
        # Bild-Icon: <img> mit dem Pfad; MDI-Namen bleiben <ha-icon>; unzulaessige Angaben werden nie zu <img>
        imgs = page.evaluate("[...document.querySelector('enhanced-notify-panel').shadowRoot.querySelectorAll('.it .ic img')].map(i => i.getAttribute('src'))")
        check(imgs == ["/local/zabbix.png"], f"Bild-Icons in der Liste: {imgs}")
        check(page.evaluate("document.querySelector('enhanced-notify-panel').shadowRoot.querySelectorAll('.it .ic ha-icon').length") == 4, "MDI-Icons in der Liste")
        # Admin-Karte: Typ-Icon als Bild
        page.evaluate("(() => { const c = document.createElement('enhanced-notify-admin'); c.setConfig({}); c.hass = document.querySelector('home-assistant').hass; c.id = 'admincard'; document.body.appendChild(c); })()")
        page.wait_for_function("document.getElementById('admincard').shadowRoot.querySelectorAll('.ty').length === 2", timeout=6000)
        adm = page.evaluate("[...document.getElementById('admincard').shadowRoot.querySelectorAll('.ty .ic')].map(e => e.querySelector('img') ? 'img:' + e.querySelector('img').getAttribute('src') : 'ha-icon:' + e.querySelector('ha-icon').getAttribute('icon'))")
        check(sorted(adm) == ["ha-icon:mdi:doorbell", "img:/local/zabbix.png"], f"Admin-Icons: {adm}")
        page.evaluate("document.querySelector('enhanced-notify-panel').shadowRoot.querySelector('[data-a=\"readall\"]').click()")
        page.wait_for_function("window.calls.some(c => c.type === 'enhanced_notify/mark_read' && c.all)")
        browser.close()
    print("OK")


if __name__ == "__main__":
    main()
