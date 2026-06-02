import os
import io
import base64
import time
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps

import anthropic

# ── Konfiguration ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ["GITHUB_REPOSITORY"]
BREVO_API_KEY     = os.environ["BREVO_API_KEY"]
PEXELS_API_KEY    = os.environ["PEXELS_API_KEY"]
PREVIEW_EMAIL     = "physiogoldschmidt@gmail.com"

W, H = 1080, 1920   # Story-Format (9:16)

GOLD  = (200, 150,  62)
CREAM = (242, 236, 216)

BRAND_COLORS = [
    {"bg": ( 74,  45, 122), "text": CREAM,           "accent": GOLD},
    {"bg": (107, 143, 113), "text": CREAM,           "accent": GOLD},
    {"bg": CREAM,            "text": ( 61,  36,  98), "accent": GOLD},
]

WEEKDAY_PHOTO_SEARCH = {
    0: "misty forest morning light",
    1: "zen garden stones water",
    2: "calm lake reflection nature",
    3: "autumn leaves soft light",
    4: "wildflowers meadow sunlight",
    5: "golden hour landscape nature",
    6: "peaceful forest stillness",
}

# Drei Story-Typen — wechseln täglich
STORY_TYPES = ["frage", "tipp", "zitat"]

FONT_DIR   = os.path.join(os.path.dirname(__file__), "fonts")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


# ── Content-Generierung ────────────────────────────────────────────────────────

def generate_story_content() -> tuple[str, str, str]:
    """Gibt (story_typ, bild_text, sticker_frage) zurück."""
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    weekday = datetime.now().weekday()
    hour = datetime.now().hour
    # Morgens (< 10 Uhr) → Tipp, Mittags (10–15 Uhr) → Frage, Abends (≥ 16 Uhr) → Zitat
    if hour < 10:
        story_typ = "tipp"
    elif hour < 16:
        story_typ = "frage"
    else:
        story_typ = "zitat"

    themen = {
        "frage": "Eine kurze, persönliche Frage die zum Nachdenken anregt — z.B. über den Körper, Stress, Wohlbefinden. Etwas das Follower gerne beantworten.",
        "tipp": "Ein konkreter Körper- oder Gesundheitstipp den man sofort umsetzen kann. Klein, alltagsnah, wirksam.",
        "zitat": "Ein inspirierendes Zitat aus der Naturheilkunde, Osteopathie oder Psychosomatik. Darf ruhig tiefgründig sein.",
    }

    prompt = f"""Du schreibst Instagram Stories für Lisa Goldschmidt (GOLDGESUND, Heilpraktikerin, Osteopathie & Psychosomatik, Berlin).

Wer Lisa ist — damit die Stories wirklich nach ihr klingen:
- Mama eines kleinen Sohnes der sehr auf sie bezogen ist — viel Care-Arbeit, viel Herz
- Ihr Sohn lehrt sie täglich Achtsamkeit und den Fokus auf den Moment
- Sie liebt das Mama-Sein, findet es aber auch herausfordernd — Bedürfnisse begleiten, eigene Grenzen spüren
- Die Spannung zwischen Care-Arbeit und ihrem Business ist ihr täglicher Balanceakt
- Eigene Geschichte: Migräne, Burnout mit 27 — das macht sie authentisch
- Triggered wenn Patienten die Verantwortung abgeben ("der Arzt ist schuld") — übt sich in Annehmen und Loslassen
- Nach ihrem Retreat: will weg von "Symptome wegmachen" hin zu begleiten, ermächtigen, Eigenverantwortung stärken
- Tee und ätherische Öle sind ihr neu wichtig — fließen ins Business ein
- Ton: nahbar, ehrlich, aus dem echten Leben — nicht glatt oder perfekt, sondern menschlich

Story-Typ heute: {story_typ.upper()}
Kontext: {themen[story_typ]}

Die Story soll sich anfühlen als hätte Lisa sie selbst getippt — persönlich, direkt, warm.
Darf ruhig eine kleine persönliche Beobachtung aus dem Alltag enthalten (Mama, Körper, Grenzen, Momente).

BILD_TEXT: Max. 4 Zeilen, pro Zeile max. 28 Zeichen. Kurz und kraftvoll.
STICKER: Ein kurzer Interaktions-Aufruf (max. 8 Wörter).

Antworte GENAU in diesem Format:
===BILD_TEXT===
Zeile 1
Zeile 2
Zeile 3
===STICKER===
Kurzer Interaktions-Aufruf"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    bild_text = raw.split("===BILD_TEXT===")[1].split("===STICKER===")[0].strip()
    sticker   = raw.split("===STICKER===")[1].strip()
    return story_typ, bild_text, sticker


# ── Bild-Erstellung ────────────────────────────────────────────────────────────

def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def download_nature_photo(weekday: int) -> Image.Image:
    query   = WEEKDAY_PHOTO_SEARCH[weekday]
    headers = {"Authorization": PEXELS_API_KEY}
    params  = {"query": query, "orientation": "portrait", "size": "large", "per_page": 10}
    r = requests.get("https://api.pexels.com/v1/search",
                     headers=headers, params=params, timeout=15)
    r.raise_for_status()
    photos = r.json().get("photos", [])
    if not photos:
        params["query"] = "nature green portrait"
        r = requests.get("https://api.pexels.com/v1/search",
                         headers=headers, params=params, timeout=15)
        photos = r.json().get("photos", [])
    week_number = datetime.now().isocalendar()[1]
    photo     = photos[week_number % len(photos)]
    photo_url = photo["src"]["large2x"]
    img_r     = requests.get(photo_url, timeout=30)
    img_r.raise_for_status()
    img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
    return ImageOps.fit(img, (W, H), method=Image.LANCZOS)


def create_story_image(bild_text: str, story_typ: str, sticker: str) -> Image.Image:
    day_of_year = datetime.now().timetuple().tm_yday
    weekday     = datetime.now().weekday()
    palette     = BRAND_COLORS[day_of_year % 3]
    bg_color    = palette["bg"]
    text_color  = palette["text"]
    accent      = palette["accent"]

    try:
        bg = download_nature_photo(weekday)
    except Exception:
        bg = Image.new("RGB", (W, H), bg_color)

    overlay = Image.new("RGBA", (W, H), (*bg_color, 180))
    img = bg.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    f_allura  = load_font("Allura-Regular.ttf", 52)
    f_body    = load_font("Alice-Regular.ttf", 90)
    f_body_sm = load_font("Alice-Regular.ttf", 70)
    f_sticker = load_font("Alice-Regular.ttf", 42)
    f_typ     = load_font("Alice-Regular.ttf", 32)

    # Story-Typ oben
    typ_label = {"frage": "Frage des Tages", "tipp": "Tipp für dich", "zitat": "Gedanke"}.get(story_typ, "")
    bbox = draw.textbbox((0, 0), typ_label, font=f_typ)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 180), typ_label, font=f_typ, fill=accent)

    # Haupttext zentriert in der Mitte
    lines = [l.strip() for l in bild_text.split("\n") if l.strip()]
    f_main = f_body if len(lines) <= 3 else f_body_sm
    line_h = 120 if f_main == f_body else 95
    total_h = len(lines) * line_h
    start_y = (H - total_h) // 2 - 80

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=f_main)
        lw = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, start_y + i * line_h), line, font=f_main, fill=text_color)

    # Sticker-Box unten
    sticker_y = H - 380
    box_pad   = 30
    bbox_s    = draw.textbbox((0, 0), sticker, font=f_sticker)
    sw        = bbox_s[2] - bbox_s[0]
    sh        = bbox_s[3] - bbox_s[1]
    box_x     = (W - sw) // 2 - box_pad
    box_w     = sw + box_pad * 2
    draw.rounded_rectangle([box_x, sticker_y - box_pad, box_x + box_w, sticker_y + sh + box_pad],
                            radius=20, fill=(*accent, 220) if isinstance(accent, tuple) else accent)
    draw.text(((W - sw) // 2, sticker_y), sticker, font=f_sticker, fill=CREAM)

    # „goldgesund" unten
    brand = "goldgesund"
    bbox  = draw.textbbox((0, 0), brand, font=f_allura)
    bw    = bbox[2] - bbox[0]
    draw.text(((W - bw) // 2, H - 120), brand, font=f_allura, fill=accent)

    return img


# ── Upload & E-Mail ───────────────────────────────────────────────────────────

def upload_to_github(content_b64: str, filename: str, commit_msg: str) -> str:
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


def upload_story(img: Image.Image, date_str: str) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    content  = base64.b64encode(buf.getvalue()).decode()
    filename = f"posts/story_{date_str}.jpg"
    return upload_to_github(content, filename, f"Story {date_str}")


def send_story_email(image_url: str, sticker: str, story_typ: str, date_str: str) -> None:
    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="500" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <tr>
          <td style="padding:28px 40px 16px;text-align:center;border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:12px;color:#888;letter-spacing:2px;text-transform:uppercase;">
              Instagram Story · {story_typ.capitalize()}
            </p>
            <h1 style="margin:8px 0 0;font-size:32px;color:#C8963E;font-weight:normal;font-style:italic;">goldgesund</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#999;">{date_str}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 40px 0;text-align:center;">
            <img src="{image_url}" width="240" alt="Story Vorschau"
                 style="width:240px;border-radius:12px;border:1px solid #e0ddd5;">
            <p style="margin:16px 0 0;font-size:14px;color:#555;">
              <strong>Sticker-Text:</strong> {sticker}
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 40px;background:#f8f6f0;border-top:1px solid #e8e5de;">
            <p style="margin:0;font-size:13px;color:#555;line-height:1.7;">
              <strong>So postest du die Story:</strong><br>
              1. Drück lange auf das Bild oben → <em>Bild sichern</em><br>
              2. Öffne Instagram auf deinem Handy<br>
              3. Tippe auf dein Profilbild (+ für neue Story)<br>
              4. Wähle das gespeicherte Bild aus und poste ✓
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
        "subject": f"📱 Instagram Story {date_str} — bitte freigeben",
        "htmlContent": html,
    }
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    print(f"  Story-Vorschau-E-Mail gesendet ✓")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    date_str  = datetime.now().strftime("%Y-%m-%d")
    print(f"GOLDGESUND Story — {date_str}")

    print("1/3  Story-Content wird generiert …")
    story_typ, bild_text, sticker = generate_story_content()
    print(f"     Typ: {story_typ} | Text: {bild_text!r}")

    print("2/3  Story-Bild wird erstellt …")
    img = create_story_image(bild_text, story_typ, sticker)
    print("     Bild erstellt ✓")

    print("3/3  Bild hochladen + E-Mail senden …")
    image_url = upload_story(img, date_str)
    time.sleep(3)
    send_story_email(image_url, sticker, story_typ, date_str)

    print("✓ Fertig! Lisa erhält die Story-Vorschau per E-Mail.")


if __name__ == "__main__":
    main()
