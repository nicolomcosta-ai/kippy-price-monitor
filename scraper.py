import os, smtplib, time, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── Configurazione ──────────────────────────────────────────────
GMAIL_USER  = os.environ["GMAIL_USER"]
GMAIL_PASS  = os.environ["GMAIL_PASS"]
MAIL_TO     = [m.strip() for m in os.environ["MAIL_TO"].split(",")]
PROXY_USER  = os.environ["PROXY_USER"]
PROXY_PASS  = os.environ["PROXY_PASS"]

REF_PRICE = 69.99

AMAZON_CURRENCY = {
    "amazon.co.uk": "GBP",
    "amazon.se":    "SEK",
    "amazon.pl":    "PLN",
}

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

KIPPY_PRICE_SELECTOR = "span.prezzo-cnt-cls"


# ── Parsing HTML kippy.eu ────────────────────────────────────────
def _parse_kippy_html(html, url):
    soup = BeautifulSoup(html, "lxml")
    el   = soup.select_one(KIPPY_PRICE_SELECTOR)
    if el:
        for text_node in el.strings:
            m = re.search(r'([€£$])\s*(\d+[.,]\d+)', text_node)
            if m:
                symbol = m.group(1)
                price  = float(m.group(2).replace(',', '.'))
                cur    = {"€": "EUR", "£": "GBP", "$": "USD"}.get(symbol, "EUR")
                avail  = "Disponibile" if soup.find(string=re.compile(
                    r'Disponibil|In Stock|En stock|Auf Lager', re.I)) else "N/D"
                return {"price": price, "currency": cur,
                        "available": avail, "raw": f"{symbol}{price:.2f}"}

    # Fallback: primo prezzo trovato in pagina
    for tag in soup.find_all(string=re.compile(r'[€£$]\s*\d+[.,]\d+')):
        m = re.search(r'([€£$])\s*(\d+[.,]\d+)', tag)
        if m:
            symbol = m.group(1)
            price  = float(m.group(2).replace(',', '.'))
            cur    = {"€": "EUR", "£": "GBP", "$": "USD"}.get(symbol, "EUR")
            return {"price": price, "currency": cur,
                    "available": "N/D", "raw": f"{symbol}{price:.2f}"}

    return {"price": None, "currency": "EUR", "available": "Non trovato", "raw": "N/D"}


# ── Parsing HTML Amazon ──────────────────────────────────────────
def _parse_amazon_html(html, url):
    host     = urlparse(url).netloc.replace("www.", "")
    currency = AMAZON_CURRENCY.get(host, "EUR")
    soup     = BeautifulSoup(html, "lxml")

    if "captcha" in html.lower() or "robot check" in html.lower():
        print(f"    ⚠️  CAPTCHA rilevato ({host})")
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


# ── Navigazione pagina con retry ─────────────────────────────────
def _goto_with_retry(page, url, retries=2):
    for attempt in range(retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            if attempt < retries:
                print(f"    ↩️  Retry {attempt+1} per {url}: {e}")
                time.sleep(3)
            else:
                print(f"    ❌ Fallito dopo {retries+1} tentativi: {e}")
                return False


# ── Scraping principale (browser unico) ──────────────────────────
def run_all_scraping():
    """
    Apre un solo browser Playwright con due contesti:
      1. Senza proxy → Kippy.eu
      2. Con proxy Webshare → Amazon
    Restituisce i risultati nell'ordine originale di SOURCES.
    """
    kippy_sources  = [s for s in SOURCES if s["type"] == "kippy"]
    amazon_sources = [s for s in SOURCES if s["type"] == "amazon"]

    results_kippy  = []
    results_amazon = []

    common_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
    ]

    with sync_playwright() as pw:
        # ── 1. Kippy.eu — senza proxy (non necessario) ──────────
        print("\n🌐 Scraping Kippy.eu...")
        browser_k = pw.chromium.launch(headless=True, args=common_args)
        ctx_k = browser_k.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="it-IT",
        )
        ctx_k.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page_k = ctx_k.new_page()

        for s in kippy_sources:
            print(f"  ▶ {s['label']}")
            if _goto_with_retry(page_k, s["url"]):
                # Attende che il selettore prezzo sia presente
                try:
                    page_k.wait_for_selector(KIPPY_PRICE_SELECTOR, timeout=8000)
                except Exception:
                    pass
                r = _parse_kippy_html(page_k.content(), s["url"])
            else:
                r = {"price": None, "currency": "EUR", "available": "Errore", "raw": "N/D"}
            r.update({"label": s["label"], "url": s["url"]})
            results_kippy.append(r)
            print(f"    → {r['raw']} | {r['available']}")
            time.sleep(1)

        page_k.close()
        browser_k.close()

        # ── 2. Amazon — con proxy Webshare rotante ───────────────
        print("\n🛒 Scraping Amazon (proxy Webshare)...")
        browser_a = pw.chromium.launch(
            headless=True,
            args=common_args,
            proxy={
                "server":   "http://proxy.webshare.io:80",
                "username": PROXY_USER,
                "password": PROXY_PASS,
            },
        )
        ctx_a = browser_a.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="it-IT",
            extra_http_headers={"Accept-Language": "it-IT,it;q=0.9,en;q=0.8"},
        )
        ctx_a.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page_a = ctx_a.new_page()

        for s in amazon_sources:
            print(f"  ▶ {s['label']}")
            if _goto_with_retry(page_a, s["url"]):
                try:
                    page_a.wait_for_selector(
                        ", ".join(AMAZON_PRICE_SELECTORS), timeout=8000
                    )
                except Exception:
                    pass
                r = _parse_amazon_html(page_a.content(), s["url"])
            else:
                host = urlparse(s["url"]).netloc.replace("www.", "")
                r = {"price": None, "currency": AMAZON_CURRENCY.get(host, "EUR"),
                     "available": "Errore", "raw": "N/D"}
            r.update({"label": s["label"], "url": s["url"]})
            results_amazon.append(r)
            print(f"    → {r['raw']} | {r['available']}")
            time.sleep(2)

        page_a.close()
        browser_a.close()

    # Ricostruisce ordine originale: Kippy prima, Amazon dopo
    return results_kippy + results_amazon


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
    Amazon: Playwright + Webshare proxy · Kippy.eu: Playwright diretto
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

    results = run_all_scraping()

    fx = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}
    anomalies = sum(1 for r in results
                    if r["price"] and r["price"] * fx.get(r["currency"], 1) < REF_PRICE - 5)

    print(f"\n⚠️  Anomalie rilevate: {anomalies}")
    html_body = build_email(results)
    send_email(html_body, anomalies)
    print("✅ Done.")
