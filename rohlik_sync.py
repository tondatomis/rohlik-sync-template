#!/usr/bin/env python3
import os, re, sys, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Google API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE = "https://couriers-portal.rohlik.cz/cz/"
BLOCKS_URL = BASE + "?p=blocks"
OUT = Path.home()/ "Desktop" / "rohlik_output"
OUT.mkdir(parents=True, exist_ok=True)

TZ = ZoneInfo("Europe/Prague")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Google Calendar colorId palette (classic):
# 1=Lavender, 2=Sage, 3=Grape, 4=Flamingo, 5=Banana, 6=Tangerine,
# 7=Peacock, 8=Graphite, 9=Blueberry, 10=Basil, 11=Tomato
# Requested mapping: 1K→Banana(5), 2K→Grape(3), 3K→Basil(10), 4K→Peacock(7)
COLOR_MAP = {
    1: "5",   # Banana
    2: "3",   # Grape
    3: "10",  # Basil
    4: "7",   # Peacock
}
COLOR_OTHER = "8"  # Graphite (fallback)

# Shift duration mapping in hours
DUR_MAP = {
    1: 5,
    2: 9,
    3: 12,
    4: 15,
}

MONTHS = {
    "leden":1,"led":1,
    "únor":2,"unor":2,"úno":2,"uno":2,
    "březen":3,"brezen":3,"bře":3,"bre":3,
    "duben":4,"dub":4,
    "květen":5,"kveten":5,"kvě":5,"kve":5,
    "červen":6,"cerven":6,"čer":6,"cer":6,
    "červenec":7,"cervenec":7,"čvc":7,"cvc":7,
    "srpen":8,"srp":8,
    "září":9,"zari":9,"zář":9,"zar":9,
    "říjen":10,"rijen":10,"říj":10,"rij":10,
    "listopad":11,"lis":11,
    "prosinec":12,"pro":12
}
TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", re.U)

def load_env_from_dotenv_if_present() -> None:
    """Load environment variables from a .env file next to this script if present.

    Lines use KEY=VALUE, comments starting with # are ignored.
    Existing os.environ values are preserved (do not override).
    """
    try:
        env_path = Path(__file__).with_name(".env")
        if not env_path.exists():
            return
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Fail silently – .env is optional
        pass

def gcal_service():
    tok = Path(__file__).with_name("token.json")
    cred = Path(__file__).with_name("credentials.json")
    creds = None
    if tok.exists():
        try: creds = Credentials.from_authorized_user_file(tok, SCOPES)
        except Exception: creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not cred.exists():
                print("ERROR: Missing credentials.json", file=sys.stderr); sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(cred), SCOPES)
            creds = flow.run_local_server(port=0)
        tok.write_text(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def find_or_create_calendar(service, name: str) -> str:
    resp = service.calendarList().list().execute()
    while True:
        for it in resp.get("items", []):
            if it.get("summary") == name:
                return it["id"]
        token = resp.get("nextPageToken")
        if not token: break
        resp = service.calendarList().list(pageToken=token).execute()
    created = service.calendars().insert(body={"summary": name, "timeZone":"Europe/Prague"}).execute()
    return created["id"]

def upsert(service, cal_id, title, start, end, color_id):
    time_min = (start - timedelta(minutes=1)).isoformat()
    time_max = (end + timedelta(minutes=1)).isoformat()
    items = service.events().list(calendarId=cal_id, timeMin=time_min, timeMax=time_max,
                                  singleEvents=True, orderBy="startTime").execute().get("items", [])
    body = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone":"Europe/Prague"},
        "end":   {"dateTime": end.isoformat(),   "timeZone":"Europe/Prague"},
        "colorId": color_id,
    }
    # Prefer updating an event that already has the exact title
    for ev in items:
        if ev.get("summary") == title:
            service.events().update(calendarId=cal_id, eventId=ev["id"], body=body).execute()
            print(f"[OK] Updated: {title} {start} → {end} (color {color_id})"); return
    # Otherwise, update one that matches the exact time window (rename old titles)
    for ev in items:
        ev_start = ev.get("start", {}).get("dateTime")
        ev_end = ev.get("end", {}).get("dateTime")
        if ev_start == start.isoformat() and ev_end == end.isoformat():
            service.events().update(calendarId=cal_id, eventId=ev["id"], body=body).execute()
            print(f"[OK] Renamed/Updated: {title} {start} → {end} (color {color_id})"); return
    service.events().insert(calendarId=cal_id, body=body).execute()
    print(f"[OK] Inserted: {title} {start} → {end} (color {color_id})")

def wait_ready(driver):
    for _ in range(80):
        txt = driver.find_element(By.TAG_NAME,"body").text
        if ("Načítám bloky" not in txt) and ("Pracuji" not in txt):
            break
        time.sleep(0.5)
    time.sleep(0.5)

def login_and_open(driver, uid, pin):
    wait = WebDriverWait(driver, 20)
    driver.get(BASE)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='number'][name='username'][placeholder='ID']"))).send_keys(uid)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='number'][name='password'][placeholder='PIN']"))).send_keys(pin)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'][value='Přihlásit']"))).click()
    wait.until(EC.presence_of_element_located((By.TAG_NAME,"body")))
    time.sleep(0.8)
    driver.get(BLOCKS_URL)
    wait.until(EC.presence_of_element_located((By.TAG_NAME,"body")))
    wait_ready(driver)

def parse_month_year(driver):
    body = driver.find_element(By.TAG_NAME,"body").text.lower()
    m = re.search(r"(leden|únor|unor|březen|brezen|duben|květen|kveten|červenec|cervenec|červen|cerven|srpen|září|zari|říjen|rijen|listopad|prosinec)\s+(\d{4})", body)
    if m:
        month = MONTHS[m.group(1)]
        year = int(m.group(2))
        return year, month
    now = datetime.now(TZ)
    return now.year, now.month

def collect_grid_shifts(driver):
    """Vrátí list (title, start, end, color_id, raw_text)."""
    result = []
    year, month = parse_month_year(driver)
    els = driver.find_elements(By.XPATH, "//*[contains(@class,'calendar_day_shift')]")
    for el in els:
        txt = (el.text or "").strip()
        if not txt:
            continue
        # den
        day = None
        did = el.get_attribute("id") or ""
        m = re.search(r"cal_day_shift_(\d+)", did)
        if m: day = int(m.group(1))
        if day is None:
            try:
                anc = el.find_element(By.XPATH, "./ancestor::*[starts-with(@id,'cal_day_')]")
                amid = anc.get_attribute("id") or ""
                m2 = re.search(r"cal_day_(\d+)", amid)
                if m2: day = int(m2.group(1))
            except Exception:
                pass
        if day is None:
            continue

        # čas
        tm = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", txt)
        if not tm:
            continue
        hh, mm = int(tm.group(1)), int(tm.group(2))

        # typ směny + barva (detect generic nK or n kola)
        low = txt.lower()
        num_k = None
        m_k = re.search(r"\b(\d+)\s*(k|kola)\b", low)
        if m_k:
            try:
                num_k = int(m_k.group(1))
            except Exception:
                num_k = None
        if num_k == 4:
            dur = DUR_MAP[4]; label = "4K"; color = COLOR_MAP.get(4, COLOR_OTHER)
        elif num_k == 2:
            dur = DUR_MAP[2]; label = "2K"; color = COLOR_MAP.get(2, COLOR_OTHER)
        elif isinstance(num_k, int):
            dur = DUR_MAP.get(num_k, DUR_MAP[1]); label = f"{num_k}K"; color = COLOR_MAP.get(num_k, COLOR_OTHER)
        else:
            dur = DUR_MAP[1]; label = "1K"; color = COLOR_MAP.get(1, COLOR_OTHER)

        start = datetime(year, month, day, hh, mm, tzinfo=TZ)
        end = start + timedelta(hours=dur)
        title = f"{label} {hh}:{mm:02d}"
        result.append((title, start, end, color, txt))
    return result

def click_next_month(driver):
    y1, m1 = parse_month_year(driver)
    candidates = [
        (By.CSS_SELECTOR, "button.fc-next-button, .fc-next-button"),
        (By.XPATH, "//*[self::button or self::a or self::div][normalize-space(text())='»']"),
        (By.XPATH, "//*[contains(@onclick,'next') or contains(@class,'next') or contains(@id,'next')]"),
    ]
    btn = None
    for by, sel in candidates:
        try:
            elems = driver.find_elements(by, sel)
            if elems:
                btn = elems[0]; break
        except Exception:
            pass
    if not btn:
        print("[INFO] Šipka doprava není k dispozici."); return False
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        try: btn.click()
        except Exception: driver.execute_script("arguments[0].click();", btn)
    except Exception as e:
        print("[WARN] Klik na '»' selhal:", e); return False

    for _ in range(40):
        y2, m2 = parse_month_year(driver)
        if (y2, m2) != (y1, m1): break
        time.sleep(0.5)
    wait_ready(driver)
    return True

def process_two_months(driver):
    all_events = []
    all_events += collect_grid_shifts(driver)
    if click_next_month(driver):
        all_events += collect_grid_shifts(driver)

    # dedupe
    uniq, seen = [], set()
    for t,s,e,c,_ in all_events:
        key = (t, s.isoformat(), e.isoformat())
        if key not in seen:
            seen.add(key); uniq.append((t,s,e,c))
    return uniq

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendar-name", default="Rohlik směny")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=False)
    args = ap.parse_args()

    # Optionally load credentials from .env next to this script
    load_env_from_dotenv_if_present()

    uid = os.getenv("ROHLIK_ID"); pin = os.getenv("ROHLIK_PIN")
    if not uid or not pin:
        print("Set ROHLIK_ID and ROHLIK_PIN", file=sys.stderr); sys.exit(1)

    opts = webdriver.ChromeOptions()
    if args.headless: opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,1100"); opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)

    try:
        login_and_open(driver, uid, pin)
        (OUT/"grid.html").write_text(driver.page_source, encoding="utf-8")
        driver.save_screenshot(str(OUT/"grid.png"))

        events = process_two_months(driver)
        print(f"[INFO] Nalezeno směn (2 měsíce): {len(events)}")
        for t,s,e,c in events:
            print(f" - {t}: {s:%Y-%m-%d %H:%M} → {e:%H:%M}  | colorId={c}")

        if not events:
            (OUT/"candidates.txt").write_text(driver.find_element(By.TAG_NAME,"body").text, encoding="utf-8")
            print("[WARN] Nic nenačteno – uložil jsem candidates.txt"); return

        if args.dry_run:
            print("[DRY-RUN] Do Google kalendáře nezapisuju."); return

        svc = gcal_service()
        cal_id = find_or_create_calendar(svc, args.calendar_name)
        for t,s,e,c in events:
            upsert(svc, cal_id, t, s, e, c)
        print("[DONE] Hotovo – zapsáno do Google kalendáře (barvy: 1K=Banana, 2K=Grape, 3K=Basil, 4K=Peacock).")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
