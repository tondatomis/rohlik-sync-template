# Rohlík → Google Calendar (měsíční sync)

Automat přihlásí Rohlík kurýrní portál, načte **Moje bloky** (aktuální + příští měsíc)
a zapíše směny do Google kalendáře. Běží **1× měsíčně** a lze ho spustit **ručně**.

- Skript: `rohlik_blocks_grid.py`
- Typy směn:
  - **2K** → 9 h → barva **Lavender**
  - **4K** → 15 h → barva **Grape**
  - ostatní → 9 h → barva **Peacock**
- Názvy událostí: např. `2K 05:30`, `4K 14:00`, atd.

---

## 1) Fork / Use this template
- Klikni **Use this template** → vytvoř si vlastní repo (doporučeně Public, ať to jde sdílet).

## 2) Přidej Secrets (repo → Settings → Secrets and variables → Actions)
Vytvoř postupně **5** secrets (každý přes „New repository secret“):

- `ROHLIK_ID` — tvoje číselné ID (např. `16550`)
- `ROHLIK_PIN` — PIN
- `GCAL_CALENDAR_NAME` — název kalendáře (např. `Rohlik směny`)
- `GOOGLE_CREDENTIALS_JSON` — **obsah** tvého `credentials.json` (z Google Cloud, OAuth Client „Desktop“)
- `GOOGLE_TOKEN_JSON` — **obsah** tvého `token.json` (vznikne po prvním lokálním autorizování, nebo ho už máš)

> Vkládej **čistý JSON** (začíná `{` a končí `}`), bez zpětných apostrofů nebo uvozovek okolo.

### Tip (macOS): rychlé zkopírování do schránky
```bash
pbcopy < /cesta/k/credentials.json
pbcopy < /cesta/k/token.json
