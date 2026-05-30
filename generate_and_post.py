import os
import sys
import json
import io
import textwrap
from datetime import datetime

import anthropic
import cloudinary
import cloudinary.uploader
import requests
from PIL import Image, ImageDraw, ImageFont


# ── Konfiguration aus Umgebungsvariablen ──────────────────────────────────────

ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
IG_ACCESS_TOKEN     = os.environ["INSTAGRAM_ACCESS_TOKEN"]
IG_BUSINESS_ID      = os.environ["INSTAGRAM_BUSINESS_ID"]
CLOUDINARY_CLOUD    = os.environ["CLOUDINARY_CLOUD_NAME"]
CLOUDINARY_API_KEY  = os.environ["CLOUDINARY_API_KEY"]
CLOUDINARY_API_SECRET = os.environ["CLOUDINARY_API_SECRET"]

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
    # Wochen-Nummer sorgt für Abwechslung innerhalb desselben Wochentags
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

Antworte NUR im folgenden JSON-Format, kein Text davor oder danach:
{{
  "image_text": "Zeile 1\\nZeile 2\\nZeile 3",
  "caption": "Die vollständige Caption inkl. Hashtags"
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # JSON-Block herausschneiden falls Backticks dabei
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)
    return data["image_text"], data["caption"]


# ── Bild-Erstellung via Pillow ────────────────────────────────────────────────

W, H = 1080, 1080

# GOLDGESUND-Farben
CREAM  = (250, 250, 247)   # #FAFAF7
GOLD   = (200, 150,  62)   # #C8963E
GREEN  = ( 29, 158, 117)   # #1D9E75
DARK   = ( 44,  44,  42)   # #2C2C2A

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def centered_text(draw, text, y, font, color, max_width=860):
    """Zeichnet Text horizontal zentriert bei y."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    # Falls Text zu breit: leicht kleiner wrappen (einfach zeichnen, kein weiteres Wrapping hier)
    draw.text((x, y), text, font=font, fill=color)
    return bbox[3] - bbox[1]  # Höhe der Zeile


def create_image(image_text: str) -> Image.Image:
    img = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)

    # Schriften laden
    f_allura    = load_font("Allura-Regular.ttf",       64)
    f_brand_sm  = load_font("CormorantGaramond-Regular.ttf", 30)
    f_body      = load_font("CormorantGaramond-Regular.ttf", 62)
    f_body_sm   = load_font("CormorantGaramond-Regular.ttf", 50)

    # ── Rahmen-Linien (oben + unten) ──
    margin = 80
    lw = 2  # Linienbreite
    draw.rectangle([margin, margin, W - margin, margin + lw], fill=GOLD)
    draw.rectangle([margin, H - margin - lw, W - margin, H - margin], fill=GOLD)

    # ── Ecken-Punkte ──
    for cx, cy in [(margin, margin), (W - margin, margin),
                   (margin, H - margin), (W - margin, H - margin)]:
        r = 6
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)

    # ── Markenname oben ──
    brand = "goldgesund"
    bbox = draw.textbbox((0, 0), brand, font=f_allura)
    bw = bbox[2] - bbox[0]
    draw.text(((W - bw) // 2, 125), brand, font=f_allura, fill=GOLD)

    # ── Dünne goldene Linie unter Markenname ──
    sep_y = 215
    draw.rectangle([300, sep_y, W - 300, sep_y + 1], fill=GOLD)

    # ── Haupt-Text (zentriert, mehrzeilig) ──
    lines = image_text.split("\n")
    # Schriftgröße je nach Zeilenanzahl anpassen
    f_main = f_body if len(lines) <= 2 else f_body_sm
    line_h = 75 if len(lines) <= 2 else 65

    total_text_h = len(lines) * line_h
    text_start_y = (H - total_text_h) // 2 + 30  # leicht nach unten versetzt (Markenname oben)

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        bbox = draw.textbbox((0, 0), line, font=f_main)
        lw_px = bbox[2] - bbox[0]
        x = (W - lw_px) // 2
        draw.text((x, text_start_y + i * line_h), line, font=f_main, fill=DARK)

    # ── Trennlinie + Name unten ──
    draw.rectangle([280, H - 195, W - 280, H - 193], fill=GOLD)

    footer = "Lisa Goldschmidt · Heilpraktikerin"
    bbox = draw.textbbox((0, 0), footer, font=f_brand_sm)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, H - 175), footer, font=f_brand_sm, fill=GOLD)

    return img


# ── Cloudinary-Upload ─────────────────────────────────────────────────────────

def upload_image(img: Image.Image) -> str:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    result = cloudinary.uploader.upload(
        buf,
        folder="goldgesund-instagram",
        public_id=f"post-{datetime.now().strftime('%Y%m%d-%H%M')}",
        overwrite=True,
    )
    return result["secure_url"]


# ── Instagram Graph API ───────────────────────────────────────────────────────

BASE = "https://graph.facebook.com/v21.0"


def post_to_instagram(image_url: str, caption: str) -> str:
    # Schritt 1: Media-Container erstellen
    r = requests.post(
        f"{BASE}/{IG_BUSINESS_ID}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    r.raise_for_status()
    creation_id = r.json()["id"]
    print(f"  Media-Container: {creation_id}")

    # Schritt 2: Veröffentlichen
    r = requests.post(
        f"{BASE}/{IG_BUSINESS_ID}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    r.raise_for_status()
    post_id = r.json()["id"]
    print(f"  Veröffentlicht! Post-ID: {post_id}")
    return post_id


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"GOLDGESUND Instagram — {today}")

    print("1/4  Content wird generiert …")
    image_text, caption = generate_content()
    print(f"     Bild-Text: {image_text!r}")
    print(f"     Caption-Vorschau: {caption[:80]}…")

    print("2/4  Bild wird erstellt …")
    img = create_image(image_text)

    print("3/4  Bild wird hochgeladen …")
    image_url = upload_image(img)
    print(f"     URL: {image_url}")

    print("4/4  Wird auf Instagram gepostet …")
    post_to_instagram(image_url, caption)

    print("✓ Fertig!")


if __name__ == "__main__":
    main()
