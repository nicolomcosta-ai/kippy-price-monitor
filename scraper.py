import os, smtplib, time, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import keepa

# ── Configurazione ──────────────────────────────────────────────
GMAIL_USER  = os.environ["GMAIL_USER"]
GMAIL_PASS  = os.environ["GMAIL_PASS"]
MAIL_TO     = [m.strip() for m in os.environ["MAIL_TO"].split(",")]
KEEPA_KEY   = os.environ["KEEPA_KEY"]

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

# Mappa dominio Amazon → codice marketplace Keepa
KEEPA_DOMAIN = {
    "amazon.it":     3,   # Italy
    "amazon.de":     3,   # Germany (stessa API, locale diverso)
    "amazon.fr":     4,   # France
    "amazon.es":     9,   # Spain
    "amazon.nl":     8,   # Netherlands
    "amazon.co.uk":  2,   # UK
    "amazon.se":     5,   # Sweden
    "amazon.pl":     11,  # Poland
}

# Mappa dominio → valuta
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
    {"label": "Amazon IT – DOG", "url": "https://www.amazon.it/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon DE – DOG", "url": "https://www.amazon.de/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon FR – DOG", "url": "https://www.amazon.fr/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon ES – DOG", "url": "https://www.amazon.es/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon NL – DOG", "url": "https://www.amazon.nl/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon UK – DOG", "url": "https://www.amazon.co.uk/dp/B0DN71S69G", "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon SE – DOG", "url": "https://www.amazon.se/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    {"label": "Amazon PL – DOG", "url": "https://www.amazon.pl/dp/B0DN71S69G",    "type": "amazon", "asin": "B0DN71S69G"},
    # Amazon CAT
    {"label": "Amazon IT – CAT", "url": "https://www.amazon.it/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon DE – CAT", "url": "https://www.amazon.de/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon FR – CAT", "url": "https://www.amazon.fr/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon ES – CAT", "url": "https://www.amazon.es/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon NL – CAT", "url": "https://www.amazon.nl/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon UK – CAT", "url": "https://www.amazon.co.uk/dp/B0FXFX2L1S", "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon SE – CAT", "url": "https://www.amazon.se/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
    {"label": "Amazon PL – CAT", "url": "https://www.amazon.pl/dp/B0FXFX2L1S",    "type": "amazon", "asin": "B0FXFX2L1S"},
]

# ── Keepa: carica tutti gli ASIN in batch ────────────────────────
def fetch_keepa_prices():
    """
    Restituisce un dizionario:
    { (asin, domain_int): {"price": float, "currency": str, "available": str, "raw": str} }
    Keepa consente batch per dominio → raggruppiamo per dominio.
    """
    keepa_api = keepa.Keepa(KEEPA_KEY)
    results = {}

    # Raggruppa le sorgenti Amazon per dominio Keepa
    from urllib.parse import urlparse
    from collections import defaultdict
    domain_groups = defaultdict(list)
    for s in SOURCES:
        if s["type"] != "amazon":
            continue
        host = urlparse(s["url"]).netloc.replace("www.", "")
        domain_int = KEEPA_DOMAIN.get(host)
        if domain_int is None:
            print(f"  ⚠️ Dominio Keepa non mappato: {host}")
            continue
        domain_groups[domain_int].append(s)

    for domain_int, sources in domain_groups.items():
        asins = list({s["asin"] for s in sources})
        try:
            print(f"  📡 Keepa query: dominio={domain_int}, asins={asins}")
            products = keepa_api.query(asins, domain=domain_int, history=False)
        except Exception as e:
            print(f"  ❌ Keepa errore dominio {domain_int}: {e}")
            for s in sources:
                results[(s["asin"], domain_int)] = {
                    "price": None, "currency": "EUR",
                    "available": "Errore Keepa", "raw": "N/D"
                }
            continue

        for prod in products:
            asin = prod.get("asin", "")
            # Prezzo corrente: Keepa usa AMAZON (venduto da Amazon) o NEW (terze parti)
            # I valori sono in centesimi * 10 (quindi dividiamo per 100)
            raw_price = None
            for price_type in ["AMAZON", "NEW"]:
                data = prod.get("data", {}).get(price_type, [])
                # L'ultimo valore non-negativo è il prezzo corrente
                valid = [v for v in (data or []) if v and v > 0]
                if valid:
                    raw_price = valid[-1] / 100.0
                    break

            # Disponibilità
            avail = "Disponibile" if raw_price else "Non disponibile"

            # Valuta basata sul dominio
            host_map = {v: k for k, v in KEEPA_DOMAIN.items()}
            host = host_map.get(domain_int, "")
            currency = AMAZON_CURRENCY.get(host, "EUR")

            results[(asin, domain_int)] = {
                "price":     raw_price,
                "currency":  currency,
                "available": avail,
                "raw":       f"{raw_price:.2f} {currency}" if raw_price else "N/D"
            }

    return results


# ── Scraping kippy.eu ────────────────────────────────────────────
def scrape_kippy(source):
    time.sleep(2)
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        el = soup.select_one("span.prezzo-cnt-cls")
        if el:
            # Itera i text node diretti: il primo con un numero è il prezzo prodotto
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

        # Fallback generico
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

        print(f"  ⚠️ Prezzo non trovato per {source['label']} (status: {r.status_code})")

    except Exception as e:
        print(f"  ❌ ERRORE {source['label']}: {e}")

    return {"price": None, "currency": "EUR", "available": "Errore", "raw": "N/D"}


# ── Build email HTML ─────────────────────────────────────────────
def build_email(results):
    today = datetime.now().strftime("%d/%m/%Y %H:%M")
    fx    = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}

    anomalies = []
    for r in results:
        if r["price"]:
            eur_eq = r["price"] * fx.get(r["currency"], 1)
            if eur_eq < REF_PRICE - 5:
                anomalies.append(r)

    def row_color(r):
        if not r["price"]:
            return "#f5f5f5"
        eur_eq = r["price"] * fx.get(r["currency"], 1)
        if eur_eq < REF_PRICE - 5:
            return "#fff3cd"   # giallo anomalia
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
        items = "".join(f"<li>{a['label']}: <b>{a['raw']}</b></li>" for a in anomalies)
        anomaly_block = f"""
        <div style="background:#fff3cd;border:1px solid #ffc107;padding:12px;margin-bottom:20px;border-radius:6px">
          <b>⚠️ {len(anomalies)} anomali{('a' if len(anomalies)==1 else 'e')} rilevat{('a' if len(anomalies)==1 else 'e')} (prezzo &lt; {REF_PRICE - 5:.2f} €):</b>
          <ul>{items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px">
  <h2 style="color:#1a1a2e">📊 Kippy Price Monitor — {today}</h2>
  <p>Prezzo di riferimento: <b>€ {REF_PRICE:.2f}</b> | Soglia anomalia: <b>€ {REF_PRICE - 5:.2f}</b></p>
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
    Amazon: dati via Keepa API · Kippy.eu: scraping diretto
  </p>
</body></html>"""


# ── Invio email ───────────────────────────────────────────────────
def send_email(html_body, anomaly_count):
    today   = datetime.now().strftime("%d/%m/%Y")
    subject = f"Kippy Prezzi {today}"
    if anomaly_count > 0:
        subject = f"[{anomaly_count} anomali{'a' if anomaly_count == 1 else 'e'}] " + subject

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

    # 1. Keepa batch per tutte le sorgenti Amazon
    print("\n📡 Recupero prezzi Amazon via Keepa...")
    from urllib.parse import urlparse
    keepa_prices = fetch_keepa_prices()

    # 2. Scraping kippy.eu + merge Amazon da Keepa
    results = []
    for s in SOURCES:
        print(f"  ▶ {s['label']}")
        if s["type"] == "kippy":
            r = scrape_kippy(s)
        else:
            # Amazon: recupera da cache Keepa già scaricata
            host       = urlparse(s["url"]).netloc.replace("www.", "")
            domain_int = KEEPA_DOMAIN.get(host)
            r = keepa_prices.get((s["asin"], domain_int), {
                "price": None, "currency": "EUR",
                "available": "Non trovato", "raw": "N/D"
            })
        r.update({"label": s["label"], "url": s["url"]})
        results.append(r)
        print(f"    → {r['raw']} | {r['available']}")

    # 3. Conta anomalie ed invia email
    fx = {"EUR": 1.0, "GBP": 1.17, "SEK": 0.089, "PLN": 0.23}
    anomalies = sum(1 for r in results
                    if r["price"] and r["price"] * fx.get(r["currency"], 1) < REF_PRICE - 5)

    print(f"\n⚠️  Anomalie rilevate: {anomalies}")
    html_body = build_email(results)
    send_email(html_body, anomalies)
    print("✅ Done.")
