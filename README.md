# DORALAB Benachrichtigungen (`doralab_notify`)

> *Central notification center for Home Assistant: one shared list with unread status, a bell with counter, push per notification type and person, German-language UI. (Documentation is in German.)*

Zentrale Benachrichtigungsliste für Home Assistant, gedacht für Wand-Tablet (Kiosk), Web und Companion App. Alles, was dein Zuhause dir mitteilen will (Paket, Klingel, Waschmaschine fertig, Saugroboter, neuer Termin, Vorrat, Systemmeldungen), landet an einer Stelle, mit Lesestatus und Push nach deinen Regeln.

- **Gemeinsamer Lesestatus**: gelesen/ungelesen liegt in Home Assistant und ist damit auf Kiosk, Web und App identisch und live synchron.
- **Glocke mit Zähler**: in der HA-Seitenleiste (Web und App) automatisch, zusätzlich als Karte für jedes Dashboard. Die Liste hat Filter (Alle / Ungelesen / Kategorie), löschen, „Alle gelesen“ und „Gelesene löschen“.
- **Push pro Typ und Person**: Welche Personen welchen Meldungstyp als Push bekommen und ob immer oder nur, wenn die Person nicht zuhause ist, stellst du in einem Admin-Dashboard ein.
- **Push-Aufräumen**: Wird eine Meldung irgendwo gelesen oder gelöscht, verschwindet der Push auf den Handys. Der Button „Gelesen“ in der Push-Meldung markiert sie in der Zentrale als gelesen (auf iOS nach langem Drücken).
- **Keine Wiederholungen**: Eine gelesene oder gelöschte Meldung kommt nicht wieder, auch nicht nach einem Neustart (siehe [Meldung senden](#meldung-senden)).
- **Katalog der Meldungstypen** (Pakete, Haustür, Wäsche, Saugroboter, Kalender, Vorrat, System). Unbekannte Typen legen sich beim ersten Auslösen selbst an und tauchen im Admin-Dashboard auf.
- **HA-Benachrichtigungen übernehmen**: persistente HA-Meldungen (z. B. vom Saugroboter) werden ins Deutsche übersetzt und in die Zentrale übernommen.
- Sensor `Ungelesen` (Zähler), Aufbewahrung per Optionen.

## Voraussetzungen

- Home Assistant **2025.8** oder neuer, [HACS](https://hacs.xyz)
- Für Push: Home-Assistant-Companion-App auf den Handys und je Person eine `person`-Entität mit zugeordnetem Handy (Geräte-Tracker der App)

## Installation

### Über HACS (empfohlen)

1. HACS → Integrationen → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/dominikramachers/ha-enhanced-notify`, Kategorie *Integration*.
2. **DORALAB Benachrichtigungen** installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → **DORALAB Benachrichtigungen**.

Die Oberfläche (Glocke, Liste, Karten) liefert die Integration selbst aus. Es ist **keine Dashboard-Ressource** einzutragen, ein Browser-Neuladen (Strg+F5) genügt.

### Beta-Versionen

Vorabversionen (`…-beta.N`) erscheinen in HACS nur, wenn du sie freischaltest: Integration in HACS öffnen → ⋮ → **Neu herunterladen** → *Beta-Versionen anzeigen* aktivieren. Danach zeigt Home Assistant neue Betas wie jedes andere Update unter Einstellungen → System → Updates an. Ohne diese Option bekommst du nur stabile Versionen.

### Manuell

Den Ordner `custom_components/doralab_notify` in dein `config/custom_components/` kopieren und neu starten.

## Einrichtung

1. **Glocke**: Die Glocke der HA-Seitenleiste öffnet die Liste und zeigt den Zähler, sobald die Integration eingerichtet ist. Zusätzlich gibt es eine Karte für beliebige Dashboards:

   ```yaml
   type: custom:doralab-notify-bell
   ```

2. **Admin-Dashboard** für die Push-Einstellungen: ein Dashboard (nur für Administratoren) mit der Karte `custom:doralab-notify-admin`, siehe [`examples/dashboard/admin-view.yaml`](examples/dashboard/admin-view.yaml). Dort wählst du je Meldungstyp die Personen und den Modus *Immer* oder *Nur unterwegs*, kannst eine Testmeldung senden oder auf den Standard zurücksetzen.
3. **Meldungen auslösen**: aus deinen Automationen mit `doralab_notify.send`. Fertige Vorlagen liegen in [`examples/automations/`](examples/automations).

Optionen der Integration (Einstellungen → Geräte & Dienste → Konfigurieren): Aufbewahrung gelesener/aller Meldungen, maximale Anzahl, HA-Meldungen übernehmen und übersetzen, Geräte ohne Push (z. B. ein iPad).

## Meldung senden

```yaml
action: doralab_notify.send
data:
  type: paket_zugestellt          # Typ aus dem Katalog (oder neu: wird automatisch angelegt)
  message: "Hermes: Dein Paket wurde zugestellt"
  title: "Paket zugestellt"       # optional, Standard = Name des Typs
  tag: "paket:H1234567890"        # optional: gleicher Tag aktualisiert statt neu anzulegen
  link: /lovelace/pakete          # optional: öffnet beim Tippen auf Meldung oder Push
  push: true                      # optional: false = nur in die Zentrale
```

Weitere optionale Felder: `icon`, `priority` (`normal`/`high`), `category` und `type_name` (nur beim automatischen Anlegen eines neuen Typs), `data`.

Gleicher `tag` mit geändertem Text aktualisiert die vorhandene Meldung (wird wieder ungelesen, rückt nach oben, Push wird ersetzt). Gleicher Tag mit gleichem Titel und Text wird ignoriert, solange sich der Inhalt nicht ändert: Die Integration merkt sich je Tag dauerhaft den zuletzt gemeldeten Inhalt. Eine gelesene oder gelöschte Meldung taucht deshalb nicht wieder auf, auch nicht nach einem Neustart oder wenn eine Automation sie erneut sendet; erst ein geänderter Text meldet wieder (neu, ungelesen, mit Push). Meldungen ohne `tag` und übernommene HA-Meldungen sind davon ausgenommen. Soll dieselbe Lage später erneut gemeldet werden können, gehört ein Datum o. Ä. in den Text.

### Nur einmal melden (`once`, `baseline`)

Für Ereignisse, die nicht wiederkehren sollen, z. B. neue Kalendertermine:

```yaml
action: doralab_notify.send
data:
  type: kalender_neuer_termin
  message: "Do., 29.10. 08:00"
  tag: "kal:calendar.xyz:UID-123"
  once: true        # dieser Tag wird nur ein einziges Mal gemeldet, auch nach dem Löschen
  baseline: true    # optional, nur mit once: Tag nur vormerken, keine Meldung und kein Push (stiller Erstlauf)
```

Die gesehenen Tags werden dauerhaft gespeichert (bis 5000, die ältesten fallen heraus). Ein vollständiges Beispiel mit stillem Erstlauf: [`examples/automations/kalender_neuer_termin.yaml`](examples/automations/kalender_neuer_termin.yaml).

### Weitere Aktionen

| Aktion | Zweck |
|---|---|
| `doralab_notify.mark_read` | `ids`, `all`, `read` |
| `doralab_notify.delete` | `ids`, `tags` (löscht alle Meldungen mit diesem Tag), `all`, `only_read` |
| `doralab_notify.set_type` | `type`, `recipients` (Personen), `push_when` (`always`/`away`), `reset` |

Beim Senden löst die Integration das Ereignis `doralab_notify_created` aus (für eigene Automationen).

## Meldungstypen

Eingebauter Katalog (`catalog.py`). Der Push-Standard gilt, bis du im Admin-Dashboard etwas anderes einstellst; automatisch angelegte Typen pushen anfangs nicht.

| Typ | Name | Kategorie | Push-Standard |
|---|---|---|---|
| `paket_unterwegs` | Paket unterwegs | Pakete | kein Push |
| `paket_termin` | Voraussichtliche Lieferung | Pakete | kein Push |
| `paket_in_zustellung` | Paket in Zustellung | Pakete | alle Personen |
| `paket_zugestellt` | Paket zugestellt | Pakete | alle Personen |
| `paket_problem` | Paket: Problem | Pakete | alle Personen |
| `klingel` | Es klingelt | Haustür | alle Personen |
| `waschmaschine_fertig` | Waschmaschine fertig | Wäsche | alle Personen |
| `trockner_fertig` | Trockner fertig | Wäsche | alle Personen |
| `saugroboter_fertig` | Saugroboter fertig | Saugroboter | alle Personen |
| `saugroboter_problem` | Saugroboter: Problem | Saugroboter | alle Personen |
| `saugroboter_wartung` | Saugroboter: Wartung | Saugroboter | kein Push |
| `kalender_neuer_termin` | Neuer Kalendertermin | Kalender | kein Push |
| `vorrat_niedrig` | Vorrat niedrig | Keller-Vorrat | kein Push |
| `vorrat_mhd` | Haltbarkeit läuft ab | Keller-Vorrat | kein Push |
| `ha_system` | Home-Assistant-Meldung | System | kein Push |
| `geraet_offline` | Gerät offline | System | kein Push |

## Push-Empfänger

Die Handys einer Person werden über deren Geräte-Tracker (Companion App) gefunden, der Dienst heißt `notify.mobile_app_<gerätename>`. Geräte, die nie Push bekommen sollen (z. B. ein iPad), lassen sich in den Integrationsoptionen ausschließen. „Nur unterwegs“ bedeutet: Push nur an Personen, deren `person`-Entität nicht `home` ist.

## Übersetzung der HA-Meldungen

Persistente Meldungen von Home Assistant und Integrationen werden übernommen und, wo bekannt, ins Deutsche übersetzt und dem passenden Typ zugeordnet (Regeln in `translate.py`, derzeit u. a. Dreame-Saugroboter und Standardmeldungen von HA). Was nicht erkannt wird, landet unverändert als Typ `ha_system`. Die Original-Texte stehen in `data.original_title` / `data.original_message`, damit sich Regeln anhand echter Meldungen nachschärfen lassen. Bei Bedarf in den Optionen abschaltbar.

## Oberfläche im Detail

Das JavaScript (`custom_components/doralab_notify/frontend/doralab-notify.js`) liefert die Integration unter `/doralab_notify/doralab-notify.js` aus und lädt es automatisch in Home Assistant. Es bringt:

- Meldungsliste als Popup (Filter Alle / Ungelesen / Kategorie, löschen, „Alle gelesen“, „Gelesene löschen“, Tippen öffnet den Link)
- Übernahme der Standard-Glocke der HA-Seitenleiste (Web und App): öffnet diese Liste und zeigt den Zähler der Integration
- Karte `custom:doralab-notify-bell` (Glocke mit Zähler für beliebige Dashboards)
- Karte `custom:doralab-notify-admin` (Push je Typ und Person, Testmeldung, Zurücksetzen)
- Optional: Anbindung an die eigenen Header-Elemente `doralab-kt-page` / `doralab-home-header` (nur aktiv, wenn es sie gibt; für andere Setups ohne Bedeutung)

Alles läuft über die Websocket-Befehle der Integration (`doralab_notify/subscribe`, `mark_read`, `delete`, `set_type`; Letzteres nur für Admins). Die Oberfläche ist derzeit deutschsprachig.

## Updates und Versionen

Releases stehen unter [Releases](https://github.com/dominikramachers/ha-enhanced-notify/releases), die Änderungen im [CHANGELOG](CHANGELOG.md). Stabile Versionen erkennt HACS automatisch, Vorabversionen nur mit freigeschalteten Beta-Versionen (siehe oben). Beim Update bleiben Meldungen, Einstellungen und Optionen erhalten; nach der Installation ist ein Neustart von Home Assistant nötig.

## Fehlersuche

- **Glocke fehlt nach der Installation**: Home Assistant neu starten, Browser mit Strg+F5 neu laden (in der App: Frontend-Cache leeren).
- **Kein Push**: Im Admin-Dashboard prüfen, ob die Person beim Typ ausgewählt ist und ob unter dem Namen ein Handy angezeigt wird. Steht dort „Kein Handy gefunden“, fehlt der Person ein Geräte-Tracker der Companion App.
- **Meldung kommt nicht erneut**: Gewollt, siehe [Meldung senden](#meldung-senden). Ein geänderter Text oder ein anderer `tag` meldet wieder.
- Protokoll: Einstellungen → System → Protokolle, Filter `doralab_notify`.

## Entwicklung

```
python -m venv venv && venv/bin/pip install pytest-homeassistant-custom-component pyyaml
venv/bin/pytest
```

Der Browser-Test der Oberfläche (`tests/test_frontend.py`) braucht zusätzlich `pip install playwright` und einen Chromium-Browser, ohne beides wird er übersprungen. Pull Requests und Meldungen über [Issues](https://github.com/dominikramachers/ha-enhanced-notify/issues) sind willkommen.

## Lizenz

[MIT](LICENSE)
