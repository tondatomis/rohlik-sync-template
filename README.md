# Rohlík → Google Calendar (měsíční sync)

Tento skript `rohlik_sync.py` se přihlásí do **Rohlík kurýrního portálu**, otevře stránku „Moje bloky“,  
vyčte směny z aktuálního a příštího měsíce a zapíše je do **Google kalendáře**.

- Funguje při **ručním spuštění** nebo v rámci GitHub Actions (měsíční CRON).
- Automaticky rozlišuje délku směn a přiřazuje jim barvy v kalendáři podle počtu „kol“.

---

## Mapa barev a délek směn

| Počet kol | Délka (hod) | Název události | Google `colorId` | Barva v kalendáři |
|-----------|-------------|----------------|------------------|-------------------|
| 1K        | 5           | `1K HH:MM`     | `5`              | Banana            |
| 2K        | 9           | `2K HH:MM`     | `3`              | Grape             |
| 3K        | 12          | `3K HH:MM`     | `10`             | Basil             |
| 4K        | 15          | `4K HH:MM`     | `7`              | Peacock           |
| jiné / bez `K` | 5 (default) | `1K HH:MM` | `8`              | Graphite          |

> Čas začátku se bere přímo z textu v buňce dne (např. `06:30`). Konec se dopočítá.

---

## Co je potřeba nastavit (Secrets v GitHubu)

V repozitáři na GitHubu jdi do **Settings → Secrets and variables → Actions** a přidej:

- `ROHLIK_ID` – tvoje kurýrní ID  
- `ROHLIK_PIN` – tvůj PIN  
- `GCAL_CALENDAR_NAME` – název cílového Google kalendáře (např. `Rohlik směny`)  
- `GOOGLE_CREDENTIALS_JSON` – **obsah** souboru `credentials.json` z Google Cloud Console (OAuth Desktop)  
- `GOOGLE_TOKEN_JSON` – **obsah** souboru `token.json` po prvním úspěšném přihlášení

> Vkládej **čistý JSON** bez dodatečných uvozovek.

---

## Spuštění v GitHub Actions

Workflow je v `.github/workflows/rohlik_blocks_grid.yml`:

- **Automaticky:** 1× měsíčně (`15 1 1 * *`, tedy 01:15 UTC prvního dne v měsíci)
- **Ručně:**  
  Repo → **Actions → Monthly Rohlik sync → Run workflow**

Po doběhu se v artefaktech (`rohlik_output`) objeví:
- `grid.html` – HTML verze kalendáře
- `grid.png` – screenshot
- `candidates.txt` – fallback, pokud se nepodaří najít žádnou směnu

---

## Lokální spuštění

```bash
pip install -r requirements.txt

export ROHLIK_ID=...
export ROHLIK_PIN=...

python rohlik_sync.py --calendar-name "Rohlik směny"
