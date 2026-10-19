# Changelog

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
