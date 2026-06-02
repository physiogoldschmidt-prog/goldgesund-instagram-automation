import os
import base64
import requests
from datetime import datetime

import anthropic

# ── Konfiguration ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ["GITHUB_REPOSITORY"]
BREVO_API_KEY     = os.environ["BREVO_API_KEY"]
PREVIEW_EMAIL     = "physiogoldschmidt@gmail.com"

# Blog-Themen je Woche (rotieren durch 8 Themen)
BLOG_THEMEN = [
    "Vagusnerv im Alltag — was er ist und wie du ihn sanft aktivieren kannst",
    "Osteopathie erklärt — was bei einer Behandlung wirklich passiert",
    "Wenn der Körper spricht: Psychosomatik für den Alltag",
    "Darm und Stimmung — die erstaunliche Verbindung zwischen Bauch und Gehirn",
    "Atemtherapie: Warum die Art wie du atmest alles verändert",
    "Stressreaktionen im Körper — und wie du wieder in die Ruhe findest",
    "Schlaf und Selbstheilung — was nachts in deinem Körper passiert",
    "Trauma im Körper — warum manche Schmerzen keine körperliche Ursache haben",
]


# ── Briefing laden ─────────────────────────────────────────────────────────────

def get_latest_briefing() -> str:
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/briefings",
            headers=headers, timeout=10,
        )
        r.raise_for_status()
        files = sorted([f for f in r.json() if f["name"].endswith(".md")],
                       key=lambda f: f["name"], reverse=True)
        if not files:
            return ""
        content_r = requests.get(files[0]["url"], headers=headers, timeout=15)
        content_r.raise_for_status()
        return base64.b64decode(content_r.json()["content"]).decode("utf-8")
    except Exception as e:
        print(f"  Briefing nicht geladen: {e}")
        return ""


# ── Blog-Artikel generieren ────────────────────────────────────────────────────

def generate_blog_artikel(briefing: str) -> tuple[str, str, str]:
    """Gibt (titel, meta_description, artikel_text) zurück."""
    client      = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    week_number = datetime.now().isocalendar()[1]
    thema       = BLOG_THEMEN[week_number % len(BLOG_THEMEN)]

    briefing_section = ""
    if briefing:
        briefing_section = f"\n\nAktuelle Forschungserkenntnisse (zur Inspiration, natürlich einbauen):\n{briefing[:600]}\n"

    prompt = f"""Du bist Lisa Goldschmidts Blog-Autorin für die Website GOLDGESUND.
Lisa ist Heilpraktikerin (Osteopathie, Psychosomatik) in Berlin Mariendorf.
Ton: warm, wissenschaftlich fundiert, alltagsnah — wie eine kluge Freundin erklärt.
Keine Heilungsversprechen. Schreib in der Ich-Perspektive von Lisa.
{briefing_section}

Schreibe einen Blog-Artikel zum Thema:
"{thema}"

Anforderungen:
- Länge: 600–800 Wörter
- Aufbau: Einleitung (persönlicher Einstieg) → Hintergrundwissen → praktischer Teil → Abschluss mit Einladung
- SEO: Thema-Keywords natürlich einbauen
- Am Ende: 1–2 Sätze die sanft auf Lisas Praxis oder einen Kurs hinweisen

Antworte GENAU in diesem Format:
===TITEL===
Der Blog-Titel (neugierig, max. 60 Zeichen)
===META===
Meta-Description für Google (max. 155 Zeichen)
===ARTIKEL===
Der vollständige Artikel-Text"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw   = message.content[0].text.strip()
    titel = raw.split("===TITEL===")[1].split("===META===")[0].strip()
    meta  = raw.split("===META===")[1].split("===ARTIKEL===")[0].strip()
    text  = raw.split("===ARTIKEL===")[1].strip()
    return titel, meta, text


# ── E-Mail an Lisa ─────────────────────────────────────────────────────────────

def send_blog_email(titel: str, meta: str, artikel: str, date_str: str) -> None:
    artikel_html = artikel.replace("\n\n", "</p><p style='margin:0 0 16px;'>").replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="660" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <tr>
          <td style="padding:28px 40px 16px;text-align:center;border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:12px;color:#888;letter-spacing:2px;text-transform:uppercase;">
              Blog-Artikel · {date_str}
            </p>
            <h1 style="margin:8px 0 0;font-size:36px;color:#C8963E;font-weight:normal;font-style:italic;">goldgesund</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 40px 0;">
            <h2 style="margin:0 0 8px;font-size:22px;color:#2C2C2A;">{titel}</h2>
            <p style="margin:0 0 20px;font-size:13px;color:#888;font-style:italic;">
              <strong>Meta-Description (für Google):</strong> {meta}
            </p>
            <hr style="border:none;border-top:1px solid #e8e5de;margin:0 0 20px;">
            <div style="font-size:15px;line-height:1.85;color:#2C2C2A;">
              <p style="margin:0 0 16px;">{artikel_html}</p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 40px;background:#f8f6f0;border-top:1px solid #e8e5de;">
            <p style="margin:0;font-size:13px;color:#555;">
              <strong>So veröffentlichst du den Artikel:</strong><br>
              1. Geh auf deine Ionos-Website<br>
              2. Erstelle einen neuen Blog-Eintrag<br>
              3. Kopiere Titel und Text oben hinein<br>
              4. Füge ein passendes Foto hinzu und veröffentliche ✓
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:12px 40px 24px;text-align:center;border-top:1px solid #e8e5de;">
            <p style="margin:0;font-size:11px;color:#bbb;">GOLDGESUND · Lisa Goldschmidt · Heilpraktikerin Berlin</p>
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
        "subject": f"✍️ Neuer Blog-Artikel: {titel}",
        "htmlContent": html,
    }
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    r.raise_for_status()
    print(f"  Blog-Artikel-E-Mail gesendet ✓")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"GOLDGESUND Blog — {date_str}")

    print("1/3  Briefing laden …")
    briefing = get_latest_briefing()

    print("2/3  Blog-Artikel generieren …")
    titel, meta, artikel = generate_blog_artikel(briefing)
    print(f"     Titel: {titel}")

    print("3/3  E-Mail an Lisa senden …")
    send_blog_email(titel, meta, artikel, date_str)

    print("✓ Fertig! Lisa erhält den Blog-Artikel per E-Mail.")


if __name__ == "__main__":
    main()
