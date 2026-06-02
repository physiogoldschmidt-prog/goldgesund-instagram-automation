import os
import base64
import requests
from datetime import datetime
from urllib.parse import urlencode

import anthropic

# ── Konfiguration ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPOSITORY"]
BREVO_API_KEY      = os.environ["BREVO_API_KEY"]
PREVIEW_EMAIL      = "physiogoldschmidt@gmail.com"
BREVO_LIST_ID      = 5   # Newsletter-Liste (ID aus Brevo)


# ── Aktuelles Briefing laden ───────────────────────────────────────────────────

def get_latest_briefing() -> str:
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/briefings"
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        r.raise_for_status()
        files = [f for f in r.json() if f["name"].endswith(".md")]
        if not files:
            return ""
        files.sort(key=lambda f: f["name"], reverse=True)
        latest = files[0]
        content_r = requests.get(latest["url"], headers=headers, timeout=15)
        content_r.raise_for_status()
        raw_bytes = base64.b64decode(content_r.json()["content"])
        return raw_bytes.decode("utf-8")
    except Exception as e:
        print(f"  Briefing konnte nicht geladen werden: {e}")
        return ""


# ── Newsletter-Text generieren ────────────────────────────────────────────────

def generate_newsletter(briefing: str) -> tuple[str, str]:
    """Gibt (betreff, html_inhalt) zurück."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    monat  = datetime.now().strftime("%B %Y")

    briefing_section = ""
    if briefing:
        briefing_section = f"\n\nAktuelle Forschungserkenntnisse aus dem Briefing (zur Inspiration):\n{briefing[:800]}\n"

    prompt = f"""Du bist Lisa Goldschmidts Newsletter-Assistentin für GOLDGESUND.
Lisa ist Heilpraktikerin (Osteopathie, Psychosomatik) in Berlin Mariendorf.
Ton: warm, persönlich, wie ein Brief von einer klugen Freundin — keine Heilungsversprechen.
{briefing_section}

Schreibe den GOLDGESUND Newsletter für {monat}.

Struktur:
1. Persönliche Begrüßung (2-3 Sätze — warm, saisonal, menschlich)
2. Thema des Monats (Überschrift + 2 Absätze — wissenschaftlich fundiert, alltagsnah)
3. Übung oder Tipp zum Sofortausprobieren (konkret, körpernah)
4. Einladung (sanft auf Praxis oder Kurs hinweisen — kein harter Verkauf)
5. Persönlicher Abschluss von Lisa

Antworte GENAU in diesem Format:
===BETREFF===
Der E-Mail-Betreff (max. 50 Zeichen, neugierig machend)
===INHALT===
Der vollständige Newsletter-Text (Fließtext, kein HTML)"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw     = message.content[0].text.strip()
    betreff = raw.split("===BETREFF===")[1].split("===INHALT===")[0].strip()
    inhalt  = raw.split("===INHALT===")[1].strip()
    return betreff, inhalt


# ── E-Mail-HTML bauen ─────────────────────────────────────────────────────────

def build_newsletter_html(inhalt: str, date_str: str) -> str:
    inhalt_html = inhalt.replace("\n\n", "</p><p style='margin:0 0 16px;'>").replace("\n", "<br>")
    monat = datetime.now().strftime("%B %Y")
    return f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#FAFAF7;padding:36px 40px 20px;text-align:center;
                     border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:12px;color:#888;letter-spacing:2px;text-transform:uppercase;">Newsletter · {monat}</p>
            <h1 style="margin:8px 0 0;font-size:42px;color:#C8963E;font-weight:normal;
                       font-style:italic;font-family:'Palatino Linotype',Palatino,serif;">goldgesund</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px;font-size:16px;line-height:1.8;color:#2C2C2A;">
            <p style="margin:0 0 16px;">{inhalt_html}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 40px 36px;text-align:center;">
            <p style="margin:0;font-size:13px;color:#888;font-style:italic;">
              Lisa Goldschmidt · Heilpraktikerin · Berlin Mariendorf
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 40px 24px;text-align:center;border-top:1px solid #e8e5de;">
            <p style="margin:0;font-size:11px;color:#bbb;">
              Du erhältst diesen Newsletter weil du dich angemeldet hast.
              <a href="{{{{unsubscribe}}}}" style="color:#bbb;">Abmelden</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── Vorschau an Lisa senden ───────────────────────────────────────────────────

def send_preview_to_lisa(betreff: str, inhalt: str, html: str, date_str: str) -> None:
    """Sendet Lisa eine Vorschau — mit Bestätigungs-Button zum echten Versand."""
    inhalt_preview = inhalt.replace("\n", "<br>")

    # Approval-URL: löst den echten Brevo-Versand aus (via GitHub Actions workflow_dispatch)
    approval_url = (
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/newsletter_send.yml/dispatches"
    )

    preview_html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <tr>
          <td style="padding:28px 40px 16px;text-align:center;border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:12px;color:#888;letter-spacing:2px;text-transform:uppercase;">
              Newsletter-Vorschau — bitte freigeben
            </p>
            <h1 style="margin:8px 0 0;font-size:36px;color:#C8963E;font-weight:normal;font-style:italic;">goldgesund</h1>
            <p style="margin:6px 0 0;font-size:13px;color:#999;">Betreff: <strong>{betreff}</strong></p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 40px 0;font-size:15px;line-height:1.8;color:#2C2C2A;
                     background:#f8f6f0;border-left:3px solid #C8963E;margin:0 40px;">
            <div style="padding:0 20px;">
              {inhalt_preview}
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px;text-align:center;">
            <p style="margin:0 0 20px;font-size:14px;color:#555;">
              Wenn alles passt, klicke den Button — dann geht der Newsletter an alle Abonnentinnen raus.
            </p>
            <a href="mailto:physiogoldschmidt@gmail.com?subject=NEWSLETTER_FREIGABE_{date_str}&body=Ja%2C%20bitte%20den%20Newsletter%20vom%20{date_str}%20verschicken."
               style="display:inline-block;background:#1D9E75;color:#fff;
                      text-decoration:none;font-size:16px;font-weight:bold;
                      padding:16px 48px;border-radius:4px;">
              ✅ &nbsp; Newsletter jetzt an alle verschicken
            </a>
            <p style="margin:16px 0 0;font-size:12px;color:#aaa;">
              Wenn du nichts tust, wird kein Newsletter versendet.
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
        "subject": f"📧 Newsletter-Vorschau {date_str} — bitte freigeben",
        "htmlContent": preview_html,
    }
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    r.raise_for_status()
    print(f"  Vorschau-E-Mail an Lisa gesendet ✓")


def send_newsletter_to_list(betreff: str, html: str) -> None:
    """Versendet den Newsletter über Brevo an die Abonnentinnen-Liste."""
    monat   = datetime.now().strftime("%B %Y")
    payload = {
        "name": f"GOLDGESUND Newsletter {monat}",
        "subject": betreff,
        "sender": {"name": "Lisa von GOLDGESUND", "email": "physiogoldschmidt@gmail.com"},
        "type": "classic",
        "htmlContent": html,
        "recipients": {"listIds": [BREVO_LIST_ID]},
        "scheduledAt": None,
    }
    # Kampagne erstellen
    r = requests.post(
        "https://api.brevo.com/v3/emailCampaigns",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    r.raise_for_status()
    campaign_id = r.json()["id"]

    # Sofort versenden
    r2 = requests.post(
        f"https://api.brevo.com/v3/emailCampaigns/{campaign_id}/sendNow",
        headers={"api-key": BREVO_API_KEY},
        timeout=20,
    )
    r2.raise_for_status()
    print(f"  Newsletter an Abonnentinnen-Liste versendet (Kampagne #{campaign_id}) ✓")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    mode     = os.environ.get("NEWSLETTER_MODE", "preview")  # "preview" oder "send"
    print(f"GOLDGESUND Newsletter — {date_str} (Modus: {mode})")

    if mode == "send":
        # Echter Versand: HTML aus GitHub laden und an Liste schicken
        # (wird durch Lisa's Freigabe-Klick ausgelöst)
        print("Lade gespeicherten Newsletter-Entwurf …")
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/newsletter/entwurf.html"
        r = requests.get(api_url, headers=headers, timeout=10)
        r.raise_for_status()
        html    = base64.b64decode(r.json()["content"]).decode("utf-8")
        betreff_r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/newsletter/betreff.txt",
            headers=headers, timeout=10,
        )
        betreff_r.raise_for_status()
        betreff = base64.b64decode(betreff_r.json()["content"]).decode("utf-8").strip()
        send_newsletter_to_list(betreff, html)
        return

    print("1/3  Briefing laden …")
    briefing = get_latest_briefing()

    print("2/3  Newsletter-Text generieren …")
    betreff, inhalt = generate_newsletter(briefing)
    print(f"     Betreff: {betreff}")

    print("3/3  HTML bauen + Entwurf speichern + Vorschau senden …")
    html = build_newsletter_html(inhalt, date_str)

    # Entwurf in GitHub speichern (für späteren Versand nach Freigabe)
    for filename, content_str in [
        ("newsletter/entwurf.html", html),
        ("newsletter/betreff.txt", betreff),
    ]:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(api_url, headers=headers, timeout=10)
        payload = {
            "message": f"Newsletter-Entwurf {date_str}",
            "content": base64.b64encode(content_str.encode("utf-8")).decode(),
        }
        if r.status_code == 200:
            payload["sha"] = r.json()["sha"]
        r2 = requests.put(api_url, headers=headers, json=payload, timeout=20)
        r2.raise_for_status()

    send_preview_to_lisa(betreff, inhalt, html, date_str)
    print("✓ Fertig! Lisa erhält die Newsletter-Vorschau per E-Mail.")


if __name__ == "__main__":
    main()
