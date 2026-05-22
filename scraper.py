import os, smtplib, time, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# ── Configurazione ──────────────────────────────────────────────
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_PASS"]
MAIL_TO    = [m.strip() for m in os.environ["MAIL_TO"].split(",")]

REF_PRICE  = 69.99

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── URL da monitorare ────────────────────────────────────────────
SOURCES = [
    # Kippy.eu
    {"label":"Kippy.eu IT – DOG",  "url":"https://www.kippy.eu/it/product/kippy-dog-green", "type":"kippy"},
    {"label":"Kippy.eu EN – DOG",  "url":"https://www.kippy.eu/en/product/kippy-dog-green", "type":"kippy"},
    {"label":"Kippy.eu ES – DOG",  "url":"https://www.kippy.eu/es/product/kippy-dog-green", "type":"kippy"},
    {"label":"Kippy.eu DE – DOG",  "url":"https://www.kippy.eu/de/product/kippy-dog-green", "type":"kippy"},
    {"label":"Kippy.eu FR – DOG",  "url":"https://www.kippy.eu/fr/product/kippy-dog-green", "type":"kippy"},
    {"label":"Kippy.eu IT – CAT",  "url":"https://www.kippy.eu/it/product/kippy-cat",        "type":"kippy"},
    {"label":"Kippy.eu EN – CAT",  "url":"https://www.kippy.eu/en/product/kippy-cat",        "type":"kippy"},
    {"label":"Kippy.eu ES – CAT",  "url":"https://www.kippy.eu/es/product/kippy-cat",        "type":"kippy"},
    {"label":"Kippy.eu DE – CAT",  "url":"https://www.kippy.eu/de/product/kippy-cat",        "type":"kippy"},
    {"label":"Kippy.eu FR – CAT",  "url":"https://www.kippy.eu/fr/product/kippy-cat",        "type":"kippy"},
    # Amazon DOG
    {"label":"Amazon IT – DOG",  "url":"https://www.amazon.it/dp/B0DN71S69G",     "type":"amazon"},
    {"label":"Amazon DE – DOG",  "url":"https://www.amazon.de/dp/B0DN71S69G",     "type":"amazon"},
    {"label":"Amazon FR – DOG",  "url":"https://www.amazon.fr/dp/B0DN71S69G",     "type":"amazon"},
    {"label":"Amazon ES – DOG",  "url":"https://www.amazon.es/dp/B0DN71S69G",     "type":"amazon"},
    {"label":"Amazon NL – DOG",  "url":"https://www.amazon.nl/dp/B0DN71S69G",     "type":"amazon"},
    {"label":"Amazon UK – DOG",  "url":"https://www.amazon.co.uk/dp/B0DN71S69G",  "type":"amazon"},
    {"label":"Amazon SE – DOG",  "url":"https://www.amazon.se/dp/B0DN71S69G",     "type":"amazon"},
    {"label":"Amazon PL – DOG",  "url":"https://www.amazon.pl/dp/B0DN71S69G",     "type":"amazon"},
    # Amazon CAT
    {"label":"Amazon IT – CAT",  "url":"https://www.amazon.it/dp/B0FXFX2L1S",    "type":"amazon"},
    {"label":"Amazon DE – CAT",  "url":"https://www.amazon.de/dp/B0FXFX2L1S",    "type":"amazon"},
    {"label":"Amazon FR – CAT",  "url":"https://www.amazon.fr/dp/B0FXFX2L1S",    "type":"amazon"},
    {"label":"Amazon ES – CAT",  "url":"https://www.amazon.es/dp/B0FXFX2L1S",    "type":"amazon"},
    {"label":"Amazon NL – CAT",  "url":"https://www.amazon.nl/dp/B0FXFX2L1S",    "type":"amazon"},
    {"label":"Amazon UK – CAT",  "url":"https://www.amazon.co.uk/dp/B0FXFX2L1S", "type":"amazon"},
    {"label":"Amazon SE – CAT",  "url":"https://www.amazon.se/dp/B0FXFX2L1S",    "type":"amazon"},
    {"label":"Amazon PL – CAT",  "url":"https://www.amazon.pl/dp/B0FXFX2L1S",    "type":"amazon"},
]

# ── Scraping ─────────────────────────────────────────────────────
def scrape(source):
    time.sleep(2)
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        if source["type"] == "kippy":
            for tag in soup.find_all(string=re.compile(r'[€£]\s*\d+[.,]\d+')):
                m = re.search(r'[€£]\s*(\d+[.,]\d+)', tag)
                if m:
                    price = float(m.group(1).replace(',', '.'))
                    avail = "Disponibile" if soup.find(string=re.compile(
                        r'Disponibil|In Stock|En stock|Auf Lager|En stock', re.I)) else "N/D"
                    return {"price": price, "currency": "EUR",
                            "available": avail, "raw": m.group(0)}

        elif source["type"] == "amazon":
            selectors = [
                "span.a-price-whole",
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                ".a-price .a-offscreen",
                "#corePrice_feature_div .a-offscreen",
            ]
            for sel in selectors:
                el = soup.select_one(sel)
                if el:
                    raw = el.get_text(strip=True)
                    nums = re.findall(r'\d+[.,]\d+', raw.replace(' ', ''))
                    if nums:
                        price = float(nums[0].replace(',', '.'))
                        cur = ("GBP" if "amazon.co.uk" in source["url"] else
                               "SEK" if "amazon.se"    in source["url"] else
                               "PLN" if "amazon.pl"    in source["url"] else "EUR")
                        avail = "Disponibile" if soup.find(
                            string=re.compile(r'In Stock|Disponibil|Auf Lager|En stock|I lager', re.I)) else "Non disponibile"
                        return {"price": price, "currency": cur,
                                "available": avail, "raw": raw}

    except Exception as e:
        print(f"  ERRORE {source['label']}: {e}")

    return {"price": None, "currency": "EUR", "available": "Errore", "raw": "N/D"}

# ── Genera HTML email ─────────────────────────────────────────────
def build_email(results):
    today = datetime.now().strftime("%d/%m/%Y %H:%M")
    fx = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}

    anomalies = []
    for r in results:
        if r["price"]:
            eur_eq = r["price"] * fx.get(r["currency"], 1)
            if eur_eq < REF_PRICE - 5:
                anomalies.append(r)

    alert_html = ""
    if anomalies:
        items = "".join(
            f"<li>{a['label']}: {a['raw']} (≈€{a['price'] * fx.get(a['currency'], 1):.2f}) vs €{REF_PRICE}</li>"
            for a in anomalies
        )
        alert_html = f"""
        <div style="background:#fff5f5;border:2px solid #fc8181;border-radius:8px;padding:16px;margin-bottom:24px;">
          <strong>⚠️ {len(anomalies)} anomalie di prezzo rilevate!</strong>
          <ul style="margin:8px 0 0 0;">{items}</ul>
        </div>"""

    rows = ""
    for r in results:
        if r["price"]:
            eur_eq  = r["price"] * fx.get(r["currency"], 1)
            diff    = eur_eq - REF_PRICE
            diff_s  = f"+€{diff:.2f}" if diff >= 0 else f"€{diff:.2f}"
            bg      = "#fff5f5" if diff < -5 else "#f0fff4" if abs(diff) < 0.5 else "#fffbeb"
            dc      = "#c53030" if diff < -5 else "#276749" if abs(diff) < 0.5 else "#975a16"
            price_s = f"{r['raw']}" if r["raw"] != "N/D" else "N/D"
        else:
            bg, dc, diff_s, price_s = "#f7fafc", "#a0aec0", "N/D", "Non disponibile"

        avail_s = r["available"]
        avail_c = "#276749" if "Disp" in avail_s or "Stock" in avail_s or "lager" in avail_s.lower() else "#c53030"

        rows += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{r["label"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#718096;font-size:12px;">'
            f'{r["url"][:55]}...</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-weight:600;">{price_s}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:{dc};font-weight:600;">{diff_s}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:{avail_c};">{avail_s}</td>'
            f'</tr>'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#f7fafc; margin:0; padding:24px; }}
    .container {{ max-width:860px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
    .header {{ background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:28px 32px; }}
    .header h1 {{ margin:0 0 4px; font-size:22px; }}
    .header p {{ margin:0; opacity:.85; font-size:14px; }}
    .body {{ padding:28px 32px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th {{ background:#edf2f7; padding:10px 12px; text-align:left; font-size:12px; color:#4a5568; text-transform:uppercase; letter-spacing:.05em; }}
    .footer {{ background:#edf2f7; padding:16px 32px; text-align:center; font-size:12px; color:#718096; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🐾 Kippy Price Monitor</h1>
      <p>Report giornaliero prezzi · {today}</p>
    </div>
    <div class="body">
      {alert_html}
      <p style="margin:0 0 16px;color:#4a5568;">Prezzo di riferimento kippy.eu: <strong>€{REF_PRICE}</strong></p>
      <table>
        <thead>
          <tr>
            <th>Sorgente</th><th>URL</th><th>Prezzo</th><th>Diff. vs €{REF_PRICE}</th><th>Disponibilità</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="footer">Kippy Price Monitor · Report automatico · Non rispondere a questa email</div>
  </div>
</body>
</html>"""

# ── Invio email ───────────────────────────────────────────────────
def send_email(html_body, anomaly_count):
    today   = datetime.now().strftime("%d/%m/%Y")
    subject = f"🐾 Kippy Prezzi {today}"
    if anomaly_count > 0:
        subject = f"⚠️ [{anomaly_count} anomalie] " + subject

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(MAIL_TO)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, MAIL_TO, msg.as_string())
    print(f"✅ Email inviata a: {MAIL_TO}")

# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🔍 Avvio scraping – {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    results = []
    for s in SOURCES:
        print(f"  Scraping: {s['label']}")
        r = scrape(s)
        r.update({"label": s["label"], "url": s["url"]})
        results.append(r)
        print(f"    → {r['raw']} | {r['available']}")

    fx = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}
    anomalies = sum(1 for r in results if r["price"] and
                    r["price"] * fx.get(r["currency"], 1) < REF_PRICE - 5)

    print(f"\n📊 Anomalie rilevate: {anomalies}")
    html_body = build_email(results)
    send_email(html_body, anomalies)
    print("✅ Done.")
