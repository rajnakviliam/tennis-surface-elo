import csv, re
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.flashscore.com/tennis/"
DAYS = [("Today", BASE_URL), ("Day+1", BASE_URL + "?d=1")]
OUT = "flashscore_com_test.csv"
RAW = Path("data/raw_flashscore_com")
RAW.mkdir(parents=True, exist_ok=True)

def clean(x):
    return " ".join(str(x or "").replace("\xa0"," ").split()).strip()

def parse_header(text):
    t = clean(text)
    u = t.upper()
    if "SINGLES" not in u or "DOUBLES" in u or "UTR" in u:
        return None
    tour = "WTA" if ("WTA" in u or "WOMEN" in u or "GIRLS" in u) else "ATP"
    low = t.lower()
    surface = ""
    for s in ("hard","clay","grass","indoor"):
        if re.search(rf"\b{s}\b", low):
            surface = "hard" if s == "indoor" else s
            break
    m = re.search(r"SINGLES\s*[:\-]?\s*(.+?)(?:,\s*(?:hard|clay|grass|indoor)\b|$)", t, re.I)
    tournament = clean(m.group(1)) if m else t
    return tour, tournament, surface

def extract(page, date_label):
    try:
        page.wait_for_selector(".event__match, .event__header", timeout=20000)
    except Exception:
        pass

    for _ in range(10):
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(250)

    items = page.locator(".event__header, .event__match")
    current_header = ""
    rows = []

    for i in range(items.count()):
        item = items.nth(i)
        cls = item.get_attribute("class") or ""

        if "event__header" in cls:
            try:
                current_header = clean(item.inner_text())
            except Exception:
                current_header = ""
            continue

        if "event__match" not in cls:
            continue

        parsed = parse_header(current_header)
        if not parsed:
            continue

        home = item.locator(".event__participant--home")
        away = item.locator(".event__participant--away")
        if home.count() == 0 or away.count() == 0:
            continue

        p1 = clean(home.first.inner_text())
        p2 = clean(away.first.inner_text())
        if not p1 or not p2 or "/" in p1 or "/" in p2:
            continue

        tloc = item.locator(".event__time")
        tm = ""
        if tloc.count():
            mt = re.search(r"\b\d{1,2}:\d{2}\b", clean(tloc.first.inner_text()))
            if mt:
                tm = mt.group(0)

        tour, tournament, surface = parsed
        rows.append([date_label,tour,tournament,surface,tm,p1,p2,current_header])

    return rows

def main():
    all_rows = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
        context = browser.new_context(
            locale="en-US",
            timezone_id="Europe/Bratislava",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36",
        )
        page = context.new_page()

        for label, url in DAYS:
            print("Sťahujem:", label, url)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            safe = label.lower().replace("+","_plus_")
            (RAW / f"{safe}.html").write_text(page.content(), encoding="utf-8")
            (RAW / f"{safe}.txt").write_text(page.locator("body").inner_text(), encoding="utf-8")

            rows = extract(page, label)
            print("  nájdených singles zápasov:", len(rows))
            all_rows.extend(rows)

        browser.close()

    seen, unique = set(), []
    for r in all_rows:
        key = (r[0],r[2],r[5],r[6])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    with open(OUT,"w",newline="",encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["DateLabel","Tour","Tournament","Surface","Time","Player 1","Player 2","RawHeader"])
        w.writerows(unique)

    diac = sorted({n for r in unique for n in (r[5],r[6]) if any(ord(ch)>127 for ch in n)})
    print("Hotovo.")
    print("Zápasov:", len(unique))
    print("Súbor:", OUT)
    print("Mená s non-ASCII znakmi:", len(diac))
    for n in diac[:30]:
        print(" ", n)

if __name__ == "__main__":
    main()
