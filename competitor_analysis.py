import os
import requests
import base64
from datetime import datetime

import anthropic

# ── Konfiguration ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BREVO_API_KEY     = os.environ["BREVO_API_KEY"]
PREVIEW_EMAIL     = "physiogoldschmidt@gmail.com"

KONKURRENTEN = [
    {"name": "Familienheilpraktikerin", "handle": "familienheilpraktikerin"},
    {"name": "Julia PhysioGlück",       "handle": "julia.physioglueck"},
    {"name": "Happydings",              "handle": "happydings"},
    {"name": "Doc Felix",               "handle": "doc.felix"},
    {"name": "Holistic Doc Maria",      "handle": "holisticdoc.maria"},
]


# ── Recherche via Claude (Web-Suche) ──────────────────────────────────────────

def recherchiere_konkurrent(client: anthropic.Anthropic, konkurrent: dict) -> str:
    """Recherchiert einen Konkurrenten über öffentliche Quellen."""
    handle = konkurrent["handle"]
    name   = konkurrent["name"]

    prompt = f"""Recherchiere den Instagram-Account @{handle} ({name}) — eine/n Heilpraktiker/in oder Gesundheits-Creator auf Instagram.

Suche nach:
1. Was sind die aktuellen Themen und Inhalte dieses Accounts?
2. Welche Formate nutzen sie (Videos, Carousels, Reels, Quotes)?
3. Welche Hashtags oder Keywords tauchen auf?
4. Was macht dieser Account besonders gut?
5. Wo gibt es Schwächen oder Lücken die Lisa (GOLDGESUND, Heilpraktikerin Berlin, Osteopathie/Psychosomatik) besser machen könnte?

Antworte kompakt in 5–8 Sätzen auf Deutsch. Wenn du keine aktuellen Informationen findest, sag das kurz."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def erstelle_gesamtanalyse(client: anthropic.Anthropic, einzelanalysen: list[dict]) -> str:
    """Erstellt eine übergeordnete Analyse mit konkreten Empfehlungen für Lisa."""
    analysen_text = "\n\n".join(
        f"**@{a['handle']}:** {a['analyse']}" for a in einzelanalysen
    )

    prompt = f"""Du bist ein Social-Media-Stratege für Lisa Goldschmidt (GOLDGESUND, Heilpraktikerin Berlin, Osteopathie & Psychosomatik).

Hier sind die Analysen von Lisas Mitbewerbern auf Instagram:

{analysen_text}

Erstelle daraus 3 konkrete, sofort umsetzbare Empfehlungen für Lisa:
- Was kann sie besser machen als die Konkurrenz?
- Welche Themen oder Formate sind gerade gefragt, die sie noch nicht nutzt?
- Wo hat sie einen einzigartigen Vorteil den sie stärker ausspielen sollte?

Schreib direkt und persönlich an Lisa. Max. 150 Wörter."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


# ── E-Mail senden ──────────────────────────────────────────────────────────────

def send_analyse_email(einzelanalysen: list[dict], gesamtanalyse: str, date_str: str) -> None:
    karten_html = ""
    for a in einzelanalysen:
        analyse_html = a["analyse"].replace("\n", "<br>")
        karten_html += f"""
        <tr>
          <td style="padding:20px 40px;border-bottom:1px solid #e8e5de;">
            <p style="margin:0 0 6px;font-size:13px;color:#C8963E;letter-spacing:1px;
                      text-transform:uppercase;font-weight:bold;">@{a['handle']}</p>
            <p style="margin:0;font-size:14px;line-height:1.7;color:#2C2C2A;">{analyse_html}</p>
          </td>
        </tr>"""

    gesamtanalyse_html = gesamtanalyse.replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="660" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="padding:28px 40px 16px;text-align:center;border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:12px;color:#888;letter-spacing:2px;text-transform:uppercase;">
              Wöchentliche Konkurrenz-Analyse
            </p>
            <h1 style="margin:8px 0 0;font-size:36px;color:#C8963E;font-weight:normal;font-style:italic;">goldgesund</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#999;">{date_str}</p>
          </td>
        </tr>

        <!-- Empfehlungen für Lisa -->
        <tr>
          <td style="padding:28px 40px 20px;background:#f0f7f4;border-bottom:2px solid #1D9E75;">
            <p style="margin:0 0 8px;font-size:13px;color:#1D9E75;letter-spacing:1px;
                      text-transform:uppercase;font-weight:bold;">✨ Deine 3 Empfehlungen diese Woche</p>
            <p style="margin:0;font-size:15px;line-height:1.8;color:#2C2C2A;">{gesamtanalyse_html}</p>
          </td>
        </tr>

        <!-- Einzelanalysen -->
        <tr>
          <td style="padding:20px 40px 8px;">
            <p style="margin:0;font-size:13px;color:#888;letter-spacing:1px;text-transform:uppercase;">
              Was machen die anderen?
            </p>
          </td>
        </tr>
        {karten_html}

        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px 28px;text-align:center;">
            <p style="margin:0;font-size:11px;color:#bbb;">
              GOLDGESUND · Lisa Goldschmidt · Heilpraktikerin Berlin
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    payload = {
        "sender": {"name": "GOLDGESUND", "email": "physiogoldschmidt@gmail.com"},
        "to": [{"email": PREVIEW_EMAIL, "name": "Lisa"}],
        "subject": f"🔍 Konkurrenz-Analyse {date_str} — was machen die anderen?",
        "htmlContent": html,
    }
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    print(f"  Konkurrenz-Analyse-E-Mail gesendet an {PREVIEW_EMAIL} ✓")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"GOLDGESUND Konkurrenz-Analyse — {date_str}")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print(f"1/{len(KONKURRENTEN)+1}  Recherche startet …")
    einzelanalysen = []
    for i, k in enumerate(KONKURRENTEN, 1):
        print(f"  {i}/{len(KONKURRENTEN)} @{k['handle']} wird analysiert …")
        analyse = recherchiere_konkurrent(client, k)
        einzelanalysen.append({"handle": k["handle"], "name": k["name"], "analyse": analyse})
        print(f"     ✓ fertig")

    print(f"{len(KONKURRENTEN)+1}/{len(KONKURRENTEN)+1}  Gesamtanalyse + E-Mail …")
    gesamtanalyse = erstelle_gesamtanalyse(client, einzelanalysen)
    send_analyse_email(einzelanalysen, gesamtanalyse, date_str)

    print("✓ Fertig! Konkurrenz-Analyse wurde per E-Mail gesendet.")


if __name__ == "__main__":
    main()
