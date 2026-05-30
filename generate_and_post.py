import os
import sys
import json
import io
import base64
import time
import textwrap
from datetime import datetime
from urllib.parse import urlencode

import anthropic
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps


# ── Konfiguration aus Umgebungsvariablen ──────────────────────────────────────

ANTHROPIC_API_KEY       = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN            = os.environ["GITHUB_TOKEN"]
GITHUB_REPO             = os.environ["GITHUB_REPOSITORY"]
BREVO_API_KEY           = os.environ["BREVO_API_KEY"]
MAKE_APPROVAL_WEBHOOK   = os.environ["MAKE_APPROVAL_WEBHOOK"]
PEXELS_API_KEY          = os.environ["PEXELS_API_KEY"]
PREVIEW_EMAIL           = "physiogoldschmidt@gmail.com"

# Pexels-Suchbegriffe je Wochentag (passend zum Thema)
WEEKDAY_PHOTO_SEARCH = {
    0: "misty forest morning light",
    1: "zen garden stones water",
    2: "calm lake reflection nature",
    3: "autumn leaves soft light",
    4: "wildflowers meadow sunlight",
    5: "golden hour landscape nature",
    6: "peaceful forest stillness",
}

# Themen je Wochentag (Montag=0 … Sonntag=6)
WEEKDAY_THEMES = {
    0: "Stressregulation und Nervensystem — wie der Körper Stress speichert und loslässt",
    1: "Osteopathie-Wissen — Zusammenhänge im Körper die die meisten nicht kennen",
    2: "Vagusnerv und innere Ruhe — praktische Einblicke",
    3: "Psychosomatik — wenn der Körper spricht was der Kopf nicht sagt",
    4: "Selbstfürsorge und Körperbewusstsein — konkrete kleine Schritte",
    5: "Inspiration und Zitat — Weisheit aus der Arbeit mit dem Körper",
    6: "Innehalten und Reflexion — Raum für Tiefe",
}


# ── Content-Generierung via Claude ───────────────────────────────────────────

def generate_content() -> tuple[str, str]:
    """Gibt (bild_text, caption) zurück."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    weekday = datetime.now().weekday()
    week_number = datetime.now().isocalendar()[1]
    theme = WEEKDAY_THEMES[weekday]

    prompt = f"""Du bist Lisa Goldschmidts Content-Assistentin für ihren Instagram-Account GOLDGESUND.
Lisa ist Heilpraktikerin (Osteopathie, Psychosomatik) in Berlin. Ihr Ton: warm, ruhig, klar, wissenschaftlich fundiert aber alltagsnah — keine Heilungsversprechen, keine lauten Claims.

Wochentag-Thema: {theme}
Wochennummer {week_number} — wähle einen frischen, spezifischen Aspekt dieses Themas.

Erstelle bitte:

IMAGE_TEXT:
Kurzer, kraftvoller Text für die Bildkarte.
Max. 3 Zeilen, pro Zeile max. 32 Zeichen.
Kann ein Zitat, eine Frage oder eine kurze Aussage sein.
Schreib jeden Satz/jede Zeile in eine neue Zeile.

CAPTION:
Instagram-Caption, 180–240 Wörter.
Aufbau:
1. Erste Zeile: starker Hook (Frage oder Gefühl ansprechen) — macht Lust weiterzulesen
2. Kurzer Absatz: Erklärung oder Einblick aus Lisas Arbeit
3. Kurzer praktischer Impuls oder Gedanke
4. Sanfter Abschluss (kein harter CTA, eher: "Komm gerne in die Praxis", "Speichern lohnt sich", o.ä.)
5. Leerzeile
6. 10–12 relevante Hashtags (deutsch + englisch gemischt)

Antworte GENAU in diesem Format — keine anderen Texte davor oder danach:

===IMAGE_TEXT===
Zeile 1
Zeile 2
Zeile 3
===CAPTION===
Die vollständige Caption inkl. Hashtags"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    if "===IMAGE_TEXT===" not in raw or "===CAPTION===" not in raw:
        raise ValueError(f"Unerwartetes Antwort-Format:\n{raw}")

    image_text = raw.split("===IMAGE_TEXT===")[1].split("===CAPTION===")[0].strip()
    caption = raw.split("===CAPTION===")[1].strip()

    return image_text, caption


# ── Bild-Erstellung via Pillow ────────────────────────────────────────────────

W, H = 1080, 1080

GOLD  = (200, 150,  62)   # #C8963E
CREAM = (242, 236, 216)   # warmes Creme

# Hintergrundfarben je Wochentag — Lila / Salbeigrün / Creme abwechselnd
WEEKDAY_PALETTES = {
    0: {"bg": ( 74,  45, 122), "text": CREAM,          "accent": GOLD},  # Mo: Lila
    1: {"bg": (107, 143, 113), "text": CREAM,          "accent": GOLD},  # Di: Salbeigrün
    2: {"bg": CREAM,           "text": ( 61,  36,  98), "accent": GOLD},  # Mi: Creme
    3: {"bg": ( 74,  45, 122), "text": CREAM,          "accent": GOLD},  # Do: Lila
    4: {"bg": (107, 143, 113), "text": CREAM,          "accent": GOLD},  # Fr: Salbeigrün
    5: {"bg": ( 94,  59, 130), "text": CREAM,          "accent": GOLD},  # Sa: Dunkellila
    6: {"bg": CREAM,           "text": ( 61,  36,  98), "accent": GOLD},  # So: Creme
}

FONT_DIR   = os.path.join(os.path.dirname(__file__), "fonts")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def download_nature_photo(weekday: int, week_number: int) -> Image.Image:
    """Lädt ein passendes Naturfoto von Pexels (kostenlos)."""
    query = WEEKDAY_PHOTO_SEARCH[weekday]
    headers = {"Authorization": PEXELS_API_KEY}
    params  = {"query": query, "orientation": "square", "size": "large", "per_page": 15}
    r = requests.get("https://api.pexels.com/v1/search",
                     headers=headers, params=params, timeout=15)
    r.raise_for_status()
    photos = r.json().get("photos", [])
    if not photos:
        # Fallback auf allgemeines Naturfoto
        params["query"] = "nature green"
        r = requests.get("https://api.pexels.com/v1/search",
                         headers=headers, params=params, timeout=15)
        photos = r.json().get("photos", [])
    # Wochennummer sorgt für Abwechslung
    photo    = photos[week_number % len(photos)]
    photo_url = photo["src"]["large2x"]
    img_r    = requests.get(photo_url, timeout=30)
    img_r.raise_for_status()
    img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
    return ImageOps.fit(img, (W, H), method=Image.LANCZOS)


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def load_ornament(filename: str) -> Image.Image:
    """Lädt ein Ornament-PNG aus dem assets/-Ordner (mit Transparenz)."""
    path = os.path.join(ASSETS_DIR, filename)
    return Image.open(path).convert("RGBA")


def wrap_text(text: str, font, max_width: int) -> list[str]:
    """Bricht Text auf mehrere Zeilen um."""
    words = text.split()
    lines, current = [], ""
    draw_tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for word in words:
        test = (current + " " + word).strip()
        w = draw_tmp.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_image(image_text: str) -> Image.Image:
    weekday     = datetime.now().weekday()
    week_number = datetime.now().isocalendar()[1]
    palette     = WEEKDAY_PALETTES[weekday]
    bg_color    = palette["bg"]
    text_color  = palette["text"]
    accent      = palette["accent"]

    # ── Naturfoto laden + Overlay drüberlegen ────────────────────
    try:
        bg = download_nature_photo(weekday, week_number)
        print(f"     Foto geladen ✓")
    except Exception as e:
        print(f"     Foto-Download fehlgeschlagen ({e}), nutze Volltonfarbe")
        bg = Image.new("RGB", (W, H), bg_color)

    overlay = Image.new("RGBA", (W, H), (*bg_color, 168))   # ~66 % Deckkraft
    img = bg.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Schriften
    f_allura = load_font("Allura-Regular.ttf", 38)
    f_body   = load_font("CormorantGaramond-Regular.ttf", 82)
    f_body_sm= load_font("CormorantGaramond-Regular.ttf", 66)

    # ── Ornamente aus Canva-Vorlage einblenden ───────────────────
    img_rgba = img.convert("RGBA")

    orn_top = load_ornament("ornament_top.png")
    img_rgba.paste(orn_top, (0, 45), orn_top)

    orn_bot = load_ornament("ornament_bottom.png")
    img_rgba.paste(orn_bot, (0, 810), orn_bot)

    img  = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Haupttext zentriert ───────────────────────────────────────
    max_text_w = W - 140
    lines_raw = image_text.split("\n")
    # Schriftgröße wählen
    all_lines = []
    for raw_line in lines_raw:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        wrapped = wrap_text(raw_line, f_body, max_text_w)
        all_lines.extend(wrapped)

    f_main = f_body if len(all_lines) <= 3 else f_body_sm
    line_h = 105 if f_main == f_body else 88

    # Nochmal umbrechen mit ggf. kleinerer Schrift
    all_lines = []
    for raw_line in lines_raw:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        wrapped = wrap_text(raw_line, f_main, max_text_w)
        all_lines.extend(wrapped)

    total_h  = len(all_lines) * line_h
    start_y  = (H - total_h) // 2 - 10

    for i, line in enumerate(all_lines):
        bbox = draw.textbbox((0, 0), line, font=f_main)
        lw_px = bbox[2] - bbox[0]
        x = (W - lw_px) // 2
        draw.text((x, start_y + i * line_h), line, font=f_main, fill=text_color)

    # ── „goldgesund" klein unten ──────────────────────────────────
    brand = "goldgesund"
    bbox  = draw.textbbox((0, 0), brand, font=f_allura)
    bw    = bbox[2] - bbox[0]
    draw.text(((W - bw) // 2, H - 38), brand, font=f_allura, fill=accent)

    return img


# ── Bild-Upload via GitHub ────────────────────────────────────────────────────

def upload_to_github(content_b64: str, filename: str, commit_msg: str) -> str:
    """Datei in GitHub-Repo speichern und Raw-URL zurückgeben."""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    r = requests.get(api_url, headers=headers, timeout=10)
    payload = {"message": commit_msg, "content": content_b64}
    if r.status_code == 200:
        payload["sha"] = r.json()["sha"]

    r = requests.put(api_url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"


def upload_image(img: Image.Image, date_str: str) -> str:
    """Bild in GitHub-Repo speichern."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    content = base64.b64encode(buf.getvalue()).decode()
    filename = f"posts/{date_str}.jpg"
    upload_to_github(content, filename, f"Post image {date_str}")
    time.sleep(5)
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"


def upload_caption(caption: str, date_str: str) -> None:
    """Caption als .txt in GitHub-Repo speichern (wird vom Freigabe-Szenario gelesen)."""
    content = base64.b64encode(caption.encode("utf-8")).decode()
    filename = f"posts/{date_str}.txt"
    upload_to_github(content, filename, f"Post caption {date_str}")


# ── Vorschau-E-Mail via Brevo ─────────────────────────────────────────────────

def send_preview_email(image_url: str, caption: str, date_str: str) -> None:
    """Schickt Lisa eine Vorschau-E-Mail. Erst nach Klick auf den Button wird gepostet."""

    # Bild-URL und Caption direkt im Link übergeben → Make.com postet beim Klick sofort
    params = urlencode({"image_url": image_url, "caption": caption})
    approval_url = f"{MAKE_APPROVAL_WEBHOOK}?{params}"

    # Caption-Zeilenumbrüche für HTML umwandeln
    caption_html = caption.replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#FAFAF7;padding:32px 40px 16px;text-align:center;
                     border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:13px;color:#888;letter-spacing:2px;
                      text-transform:uppercase;">Dein heutiger Instagram-Post</p>
            <h1 style="margin:8px 0 0;font-size:36px;color:#C8963E;font-weight:normal;
                       font-family:'Palatino Linotype',Palatino,serif;
                       font-style:italic;">goldgesund</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#999;">{date_str}</p>
          </td>
        </tr>

        <!-- Bild-Vorschau -->
        <tr>
          <td style="padding:32px 40px 0;text-align:center;">
            <p style="margin:0 0 12px;font-size:13px;color:#888;
                      letter-spacing:1px;text-transform:uppercase;">Bildkarte</p>
            <img src="{image_url}" width="480" alt="Instagram Bildkarte"
                 style="width:480px;max-width:100%;border-radius:4px;
                        border:1px solid #e0ddd5;">
          </td>
        </tr>

        <!-- Caption -->
        <tr>
          <td style="padding:28px 40px 0;">
            <p style="margin:0 0 10px;font-size:13px;color:#888;
                      letter-spacing:1px;text-transform:uppercase;">Caption</p>
            <div style="background:#f8f6f0;border-left:3px solid #C8963E;
                        padding:16px 20px;border-radius:0 4px 4px 0;
                        font-size:15px;line-height:1.7;color:#2C2C2A;">
              {caption_html}
            </div>
          </td>
        </tr>

        <!-- Button -->
        <tr>
          <td style="padding:36px 40px;text-align:center;">
            <a href="{approval_url}"
               style="display:inline-block;background:#1D9E75;color:#ffffff;
                      text-decoration:none;font-size:17px;font-weight:bold;
                      padding:16px 48px;border-radius:4px;
                      letter-spacing:0.5px;">
              ✅ &nbsp; Jetzt auf Instagram veröffentlichen
            </a>
            <p style="margin:16px 0 0;font-size:13px;color:#aaa;">
              Wenn du nichts tust, wird heute kein Post veröffentlicht.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 40px 28px;text-align:center;
                     border-top:1px solid #e8e5de;">
            <p style="margin:0;font-size:12px;color:#bbb;">
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
        "subject": f"✨ Instagram-Vorschau {date_str} — bitte freigeben",
        "htmlContent": html,
    }

    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    print(f"  Vorschau-E-Mail gesendet an {PREVIEW_EMAIL} ✓")


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"GOLDGESUND Instagram — {date_str}")

    print("1/4  Content wird generiert …")
    image_text, caption = generate_content()
    print(f"     Bild-Text: {image_text!r}")
    print(f"     Caption-Vorschau: {caption[:80]}…")

    print("2/4  Bild wird erstellt …")
    img = create_image(image_text)

    print("3/4  Bild + Caption werden hochgeladen …")
    image_url = upload_image(img, date_str)
    upload_caption(caption, date_str)
    print(f"     Bild-URL: {image_url}")

    print("4/4  Vorschau-E-Mail wird gesendet …")
    send_preview_email(image_url, caption, date_str)

    print("✓ Fertig! Lisa erhält jetzt die Vorschau-E-Mail zur Freigabe.")


if __name__ == "__main__":
    main()
