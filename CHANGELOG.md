# Changelog

## 1.0.0

Erste stabile Version. Sie fasst die Vorabversionen bis `1.0.0-rc.1` zusammen.

- **Umbenennung:** *DORALAB Benachrichtigungen* (`doralab_notify`) heißt jetzt **Enhanced Notify** (`enhanced_notify`): Aktionen `enhanced_notify.send|mark_read|delete|set_type`, Ereignis `enhanced_notify_created`, Karten `custom:enhanced-notify-bell` und `custom:enhanced-notify-admin`.
- **Umstieg von 0.3.x:** Beim Einrichten von *Enhanced Notify* werden Meldungen, Typ-Einstellungen, Optionen und der Zähler-Sensor (Entity-ID und Verlauf) automatisch übernommen. Schritte: siehe README, Abschnitt *Umstieg*.
- Die alten Aktionen `doralab_notify.*` und Kartennamen funktionieren bis 2.0 weiter (Warnung im Protokoll und Hinweis unter *Reparaturen*).
- Enthalten seit 0.3: Oberfläche (Glocke, Liste, Admin-Karte) wird von der Integration selbst ausgeliefert, Standard-Icon für Push-Meldungen, Push nur an Personen mit Handy, `once`/`baseline` und Duplikat-Erkennung über `tag`.

## 1.0.0-rc.1 (Release Candidate)

**Umbenennung:** Aus *DORALAB Benachrichtigungen* (`doralab_notify`) wird **Enhanced Notify** (`enhanced_notify`). Das Repository heißt weiterhin `ha-enhanced-notify`.

- **Geändert (Breaking):** Domain `enhanced_notify`, Ordner `custom_components/enhanced_notify`, Aktionen `enhanced_notify.send|mark_read|delete|set_type`, Ereignis `enhanced_notify_created`, Speicherdatei `.storage/enhanced_notify`, Karten `custom:enhanced-notify-bell` und `custom:enhanced-notify-admin`, Websocket-Befehle `enhanced_notify/*`, Button-Kennung der Push-Meldung `ENHANCED_NOTIFY_READ_`.
- **Neu:** Automatischer Umstieg. Beim Einrichten von *Enhanced Notify* werden Meldungen, Typ-Einstellungen, Merkzettel und Optionen der alten Integration übernommen, der Zähler-Sensor behält Entity-ID und Verlauf, der alte Eintrag wird entfernt. `.storage/doralab_notify` bleibt als Sicherung liegen.
- **Neu:** Bis 2.0 funktionieren die alten Aktionen `doralab_notify.*` und die alten Kartennamen weiter. Ein Aufruf der alten Aktion erzeugt eine Warnung im Protokoll und einen Hinweis unter *Reparaturen*. Push-Buttons bereits zugestellter Meldungen („Gelesen“) wirken weiter.
- **Neu:** Nur noch ein Eintrag der Integration möglich (`single_config_entry`).
- Schritte für den Umstieg: siehe README, Abschnitt *Umstieg*.

## 0.3.0-beta.4 (Beta)

- **Neu:** Option *Standard-Icon für Push-Meldungen* (Pfad oder Adresse eines Bildes). Die Meldung trägt es als `icon_url`, sodass es auf dem Handy statt des Standardsymbols erscheint. Hat ein Typ ein eigenes Bild (`type_icon`), gilt dieses; der Schalter *Standard-Icon auch bei Typen mit eigenem Bild verwenden* erzwingt das Standard-Icon für alle.
- Abwärtskompatibel: ohne die Option ändert sich der Push nicht.

## 0.3.0-beta.3 (Beta)

- **Neu:** `doralab_notify.send` kennt `type_icon`: Icon des Typs als Icon-Name, Pfad (`/local/…`), Webadresse oder eingebettetes Bild. Gilt für automatisch angelegte Typen und folgt der Quelle bei jedem Aufruf (leer = Icon der Kategorie).
- **Neu:** Liste und Admin-Übersicht stellen Bilder als Icons dar (Pfad, `http(s)`, `data:image`); Icon-Namen funktionieren wie zuvor. Unzulässige Angaben wie `javascript:` werden abgelehnt.
- Abwärtskompatibel: ohne `type_icon` ändert sich nichts.

## 0.3.0-beta.2 (Beta)

- **Geändert:** In der Push-Auswahl (Admin-Karte) erscheinen nur noch Personen mit registrierter Companion-App (Handy). Personen ohne Gerät, etwa reine Anmelde-Konten, werden nicht mehr gelistet. „Alle“ als Standard eines Typs meint ebenfalls nur Personen mit Handy; gespeicherte Auswahlen bleiben unverändert (nicht mehr auffindbare Personen sind einfach nicht wirksam).

## 0.3.0-beta.1 (Beta)

- **Neu:** Die Integration liefert die Oberfläche (Glocke, Liste, Karten) selbst aus und lädt sie automatisch. Eine Dashboard-Ressource ist nicht mehr nötig; eine bereits eingetragene Kopie schadet nicht (das Skript lädt sich nur einmal).
- **Neu:** Karte `custom:doralab-notify-bell` (Glocke mit Zähler) für beliebige Dashboards.
- **Neu:** Die Glocke der HA-Seitenleiste funktioniert auf jeder HA-Seite, auch ohne dass dort eine Karte der Integration sichtbar ist.
- **Neu:** Saugroboter-Meldungen (deutsch oder englisch) werden dem Saugroboter zugeordnet (fertig, Problem, Wartung) statt „System“; bereits als „System“ übernommene werden beim Start neu eingeordnet.
- **Neu:** Beispiele (`examples/`), englische Übersetzung der Dienste, Lizenz (MIT), automatische Prüfungen (hassfest, HACS, Tests).
- Abwärtskompatibel: Speicher, Optionen und Dienste bleiben unverändert. Neue Abhängigkeiten: `http` (ohnehin vorhanden), `frontend` (optional, nur Ladereihenfolge).

## 0.2.2

- Saugroboter-Meldungen in der Kategorie Saugroboter statt System.

## 0.2.1

- Gelesene oder gelöschte Meldungen kommen nicht wieder (Inhalt je `tag` wird dauerhaft gemerkt), auch nicht nach einem Neustart.

## 0.2.0

- `doralab_notify.send` mit `once` und `baseline`, `doralab_notify.delete` mit `tags`.
- Glocke der HA-Seitenleiste wird übernommen, Filter „Ungelesen“.

## 0.1.0

- Erste Version: Zentrale Liste, Lesestatus, Push pro Typ und Person, Übernahme persistenter HA-Meldungen.
