import os, smtplib, time, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── Configurazione ──────────────────────────────────────────────
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_PASS"]
MAIL_TO    = [m.strip() for m in os.environ["MAIL_TO"].split(",")]

REF_PRICE = 69.99

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

CURRENCY_MAP = {
    "€":  "EUR",
    "£":  "GBP",
    "$":  "USD",
    "kr": "SEK",
    "zł": "PLN",
}

AMAZON_CURRENCY = {
    "amazon.co.uk": "GBP",
    "amazon.se":    "SEK",
    "amazon.pl":    "PLN",
}

# ── URL da monitorare ────────────────────────────────────────────
SOURCES = [
    # Kippy.eu DOG
    {"label": "Kippy.eu IT – DOG", "url": "https://www.kippy.eu/it/product/kippy-dog-green", "type": "kippy"},
    {"label": "Kippy.eu EN – DOG", "url": "https://www.kippy.eu/en/product/kippy-dog-green", "type": "kippy"},
    {"label": "Kippy.eu ES – DOG", "url": "https://www.kippy.eu/es/product/kippy-dog-green", "type": "kippy"},
    {"label": "Kippy.eu DE – DOG", "url": "https://www.kippy.eu/de/product/kippy-dog-green", "type": "kippy"},
    {"label": "Kippy.eu FR – DOG", "url": "https://www.kippy.eu/fr/product/kippy-dog-green", "type": "kippy"},
    # Kippy.eu CAT
    {"label": "Kippy.eu IT – CAT", "url": "https://www.kippy.eu/it/product/kippy-cat", "type": "kippy"},
    {"label": "Kippy.eu EN – CAT", "url": "https://www.kippy.eu/en/product/kippy-cat", "type": "kippy"},
    {"label": "Kippy.eu ES – CAT", "url": "https://www.kippy.eu/es/product/kippy-cat", "type": "kippy"},
    {"label": "Kippy.eu DE – CAT", "url": "https://www.kippy.eu/de/product/kippy-cat", "type": "kippy"},
    {"label": "Kippy.eu FR – CAT", "url": "https://www.kippy.eu/fr/product/kippy-cat", "type": "kippy"},
    # Amazon DOG
    {"label": "Amazon IT – DOG", "url": "https://www.amazon.it/dp/B0DN71S69G",    "type": "amazon"},
    {"label": "Amazon DE – DOG", "url": "https://www.amazon.de/dp/B0DN71S69G",    "type": "amazon"},
    {"label": "Amazon FR – DOG", "url": "https://www.amazon.fr/dp/B0DN71S69G",    "type": "amazon"},
    {"label": "Amazon ES – DOG", "url": "https://www.amazon.es/dp/B0DN71S69G",    "type": "amazon"},
    {"label": "Amazon NL – DOG", "url": "https://www.amazon.nl/dp/B0DN71S69G",    "type": "amazon"},
    {"label": "Amazon UK – DOG", "url": "https://www.amazon.co.uk/dp/B0DN71S69G", "type": "amazon"},
    {"label": "Amazon SE – DOG", "url": "https://www.amazon.se/dp/B0DN71S69G",    "type": "amazon"},
    {"label": "Amazon PL – DOG", "url": "https://www.amazon.pl/dp/B0DN71S69G",    "type": "amazon"},
    # Amazon CAT
    {"label": "Amazon IT – CAT", "url": "https://www.amazon.it/dp/B0FXFX2L1S",    "type": "amazon"},
    {"label": "Amazon DE – CAT", "url": "https://www.amazon.de/dp/B0FXFX2L1S",    "type": "amazon"},
    {"label": "Amazon FR – CAT", "url": "https://www.amazon.fr/dp/B0FXFX2L1S",    "type": "amazon"},
    {"label": "Amazon ES – CAT", "url": "https://www.amazon.es/dp/B0FXFX2L1S",    "type": "amazon"},
    {"label": "Amazon NL – CAT", "url": "https://www.amazon.nl/dp/B0FXFX2L1S",    "type": "amazon"},
    {"label": "Amazon UK – CAT", "url": "https://www.amazon.co.uk/dp/B0FXFX2L1S", "type": "amazon"},
    {"label": "Amazon SE – CAT", "url": "https://www.amazon.se/dp/B0FXFX2L1S",    "type": "amazon"},
    {"label": "Amazon PL – CAT", "url": "https://www.amazon.pl/dp/B0FXFX2L1S",    "type": "amazon"},
]

AMAZON_PRICE_SELECTORS = [
    ".a-price .a-offscreen",
    "#corePrice_feature_div .a-offscreen",
    "#apex_offerDisplay_desktop .a-offscreen",
    "#newBuyBoxPrice",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
]

# ── Scraping kippy.eu (requests + BS4) ──────────────────────────
def scrape_kippy(source):
    time.sleep(2)
    try:
        r    = requests.get(source["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        el = soup.select_one("span.prezzo-cnt-cls")
        if el:
            # Itera i text node diretti: il primo col numero è il prezzo prodotto
            # (esclude il tag <a> figlio che contiene prezzi abbonamento)
            for text_node in el.strings:
                m = re.search(r'([€£$])\s*(\d+[.,]\d+)', text_node)
                if m:
                    symbol = m.group(1)
                    price  = float(m.group(2).replace(',', '.'))
                    cur    = CURRENCY_MAP.get(symbol, "EUR")
                    avail  = "Disponibile" if soup.find(string=re.compile(
                        r'Disponibil|In Stock|En stock|Auf Lager', re.I)) else "N/D"
                    return {"price": price, "currency": cur,
                            "available": avail, "raw": f"{symbol}{price:.2f}"}

        # Fallback generico sulla pagina
        for tag in soup.find_all(string=re.compile(r'[€£$]\s*\d+[.,]\d+')):
            m = re.search(r'([€£$])\s*(\d+[.,]\d+)', tag)
            if m:
                symbol = m.group(1)
                price  = float(m.group(2).replace(',', '.'))
                cur    = CURRENCY_MAP.get(symbol, "EUR")
                avail  = "Disponibile" if soup.find(string=re.compile(
                    r'Disponibil|In Stock|En stock|Auf Lager', re.I)) else "N/D"
                return {"price": price, "currency": cur,
                        "available": avail, "raw": f"{symbol}{price:.2f}"}

        print(f"  ⚠️ Prezzo non trovato: {source['label']} (HTTP {r.status_code})")

    except Exception as e:
        print(f"  ❌ ERRORE kippy {source['label']}: {e}")

    return {"price": None, "currency": "EUR", "available": "Errore", "raw": "N/D"}


# ── Parsing HTML Amazon (condiviso) ─────────────────────────────
def _parse_amazon_html(html, url):
    host     = urlparse(url).netloc.replace("www.", "")
    currency = AMAZON_CURRENCY.get(host, "EUR")
    soup     = BeautifulSoup(html, "lxml")

    # Rilevamento blocco
    if "captcha" in html.lower() or "robot check" in html.lower():
        print(f"  ⚠️ CAPTCHA rilevato ({host})")
        return {"price": None, "currency": currency, "available": "Bloccato", "raw": "N/D"}

    for sel in AMAZON_PRICE_SELECTORS:
        el = soup.select_one(sel)
        if el:
            raw  = el.get_text(strip=True).rstrip(".")
            nums = re.findall(r'\d+[.,]\d+', raw.replace(" ", ""))
            if nums:
                price    = float(nums[0].replace(",", "."))
                avail_el = soup.select_one("#availability span")
                avail    = avail_el.get_text(strip=True) if avail_el else "Disponibile"
                return {"price": price, "currency": currency,
                        "available": avail, "raw": raw}

    return {"price": None, "currency": currency, "available": "Non trovato", "raw": "N/D"}


# ── Scraping Amazon (browser condiviso) ─────────────────────────
def scrape_all_amazon(sources, playwright_instance):
    """
    Riceve la lista delle sorgenti Amazon e un'istanza Playwright già aperta.
    Usa un singolo browser con tab parallele (una alla volta per non fare spam).
    Restituisce una lista di risultati nello stesso ordine di `sources`.
    """
    browser = playwright_instance.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="it-IT",
        extra_http_headers={"Accept-Language": "it-IT,it;q=0.9,en;q=0.8"},
        # Disabilita WebDriver flag per ridurre rilevamento bot
        java_script_enabled=True,
    )

    # Nasconde il flag navigator.webdriver
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    results = []
    page    = context.new_page()

    for source in sources:
        print(f"  ▶ {source['label']}")
        try:
            page.goto(source["url"], wait_until="domcontentloaded", timeout=25000)

            # Aspetta che compaia un selettore prezzo (o timeout dopo 8s)
            try:
                page.wait_for_selector(
                    ", ".join(AMAZON_PRICE_SELECTORS),
                    timeout=8000
                )
            except Exception:
                pass  # Procede comunque, _parse troverà quello che c'è

            html = page.content()
            r    = _parse_amazon_html(html, source["url"])

        except Exception as e:
            print(f"  ❌ ERRORE Playwright {source['label']}: {e}")
            host     = urlparse(source["url"]).netloc.replace("www.", "")
            currency = AMAZON_CURRENCY.get(host, "EUR")
            r        = {"price": None, "currency": currency,
                        "available": "Errore", "raw": "N/D"}

        r.update({"label": source["label"], "url": source["url"]})
        results.append(r)
        print(f"    → {r['raw']} | {r['available']}")

        time.sleep(2)  # pausa tra una pagina e l'altra

    page.close()
    browser.close()
    return results


# ── Build email HTML ─────────────────────────────────────────────
def build_email(results):
    today = datetime.now().strftime("%d/%m/%Y %H:%M")
    fx    = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}

    anomalies = [r for r in results
                 if r["price"] and r["price"] * fx.get(r["currency"], 1) < REF_PRICE - 5]

    def row_color(r):
        if not r["price"]: return "#f5f5f5"
        if r in anomalies: return "#fff3cd"
        return "#ffffff"

    rows = ""
    for r in results:
        src  = "🛒 Amazon" if "Amazon" in r["label"] else "🌐 Kippy.eu"
        bg   = row_color(r)
        flag = "⚠️" if r in anomalies else ("✅" if r["price"] else "❌")
        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:6px 12px">{flag}</td>
          <td style="padding:6px 12px">{src}</td>
          <td style="padding:6px 12px">{r['label']}</td>
          <td style="padding:6px 12px;font-weight:bold">{r['raw']}</td>
          <td style="padding:6px 12px">{r['available']}</td>
          <td style="padding:6px 12px"><a href="{r['url']}">Link</a></td>
        </tr>"""

    anomaly_block = ""
    if anomalies:
        n     = len(anomalies)
        items = "".join(f"<li>{a['label']}: <b>{a['raw']}</b></li>" for a in anomalies)
        anomaly_block = f"""
        <div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;
                    margin-bottom:20px;border-radius:6px">
          <b>⚠️ {n} anomali{'a' if n==1 else 'e'} rilevat{'a' if n==1 else 'e'}
             (prezzo &lt; {REF_PRICE - 5:.2f} €):</b>
          <ul>{items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px">
  <h2 style="color:#1a1a2e">📊 Kippy Price Monitor — {today}</h2>
  <p>Prezzo di riferimento: <b>€ {REF_PRICE:.2f}</b> &nbsp;|&nbsp;
     Soglia anomalia: <b>€ {REF_PRICE - 5:.2f}</b></p>
  {anomaly_block}
  <table border="0" cellspacing="0" cellpadding="0"
         style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#1a1a2e;color:#fff">
        <th style="padding:8px 12px"></th>
        <th style="padding:8px 12px;text-align:left">Fonte</th>
        <th style="padding:8px 12px;text-align:left">Mercato</th>
        <th style="padding:8px 12px;text-align:left">Prezzo</th>
        <th style="padding:8px 12px;text-align:left">Disponibilità</th>
        <th style="padding:8px 12px;text-align:left">URL</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#999;font-size:12px;margin-top:20px">
    Amazon: Playwright headless · Kippy.eu: scraping diretto
  </p>
</body></html>"""


# ── Invio email ───────────────────────────────────────────────────
def send_email(html_body, anomaly_count):
    today   = datetime.now().strftime("%d/%m/%Y")
    subject = f"Kippy Prezzi {today}"
    if anomaly_count > 0:
        subject = f"[{anomaly_count} anomali{'a' if anomaly_count==1 else 'e'}] " + subject

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(MAIL_TO)
    msg.attach(MIMEText(f"Kippy Price Monitor - Report {today}\nVedi la versione HTML.", "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, MAIL_TO, msg.as_string())
    print(f"✅ Email inviata a: {MAIL_TO}")


# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🚀 Avvio scraping — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    kippy_sources  = [s for s in SOURCES if s["type"] == "kippy"]
    amazon_sources = [s for s in SOURCES if s["type"] == "amazon"]

    # 1. Scraping Kippy.eu (requests, nessun browser)
    print("\n🌐 Scraping Kippy.eu...")
    kippy_results = []
    for s in kippy_sources:
        print(f"  ▶ {s['label']}")
        r = scrape_kippy(s)
        r.update({"label": s["label"], "url": s["url"]})
        kippy_results.append(r)
        print(f"    → {r['raw']} | {r['available']}")

    # 2. Scraping Amazon (un solo browser Playwright per tutti gli URL)
    print("\n🛒 Scraping Amazon (browser condiviso)...")
    with sync_playwright() as pw:
        amazon_results = scrape_all_amazon(amazon_sources, pw)

    # 3. Ricostruisce l'ordine originale (kippy prima, amazon dopo)
    results = kippy_results + amazon_results

    # 4. Calcola anomalie e invia email
    fx = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}
    anomalies = sum(1 for r in results
                    if r["price"] and r["price"] * fx.get(r["currency"], 1) < REF_PRICE - 5)

    print(f"\n⚠️  Anomalie rilevate: {anomalies}")
    html_body = build_email(results)
    send_email(html_body, anomalies)
    print("✅ Done.")
