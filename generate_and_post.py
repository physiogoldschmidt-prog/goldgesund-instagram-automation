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

# Optionale manuelle Vorgaben (leer = automatisch)
CUSTOM_THEME     = os.environ.get("CUSTOM_THEME", "").strip()
CUSTOM_POST_TYPE = os.environ.get("CUSTOM_POST_TYPE", "").strip().lower()

NUM_SLIDES = 4   # Anzahl Karten im Carousel

# Mo=0, Mi=2, Fr=4 → Carousel  |  Di=1, Do=3, Sa=5, So=6 → Einzelbild
CAROUSEL_DAYS = {0, 2, 4}

# Stil wechselt täglich: gerade Tageszahl = Naturfoto, ungerade = Clean+Ornament
# → nie zwei gleiche Stile hintereinander im Feed

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


# ── Wöchentliches Briefing laden ─────────────────────────────────────────────

def get_latest_briefing() -> str:
    """Lädt das aktuellste Briefing aus dem briefings/-Ordner im GitHub-Repo."""
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
        # Neueste Datei zuerst (Dateiname beginnt mit YYYY-MM-DD)
        files.sort(key=lambda f: f["name"], reverse=True)
        latest = files[0]
        content_r = requests.get(latest["url"], headers=headers, timeout=15)
        content_r.raise_for_status()
        raw_bytes = base64.b64decode(content_r.json()["content"])
        text = raw_bytes.decode("utf-8")
        print(f"     Briefing geladen: {latest['name']} ✓")
        return text
    except Exception as e:
        print(f"     Briefing konnte nicht geladen werden ({e}) — wird ohne Briefing fortgesetzt")
        return ""


def extract_briefing_highlights(briefing: str) -> str:
    """Extrahiert die wichtigsten Abschnitte aus dem Briefing für den Prompt."""
    if not briefing:
        return ""
    relevant_keywords = [
        "Was die Wissenschaft sagt",
        "Was gerade im Trend ist",
        "Neue Erkenntnisse",
        "Highlights",
        "Wichtigste Erkenntnisse",
        "Forschung",
        "Studien",
    ]
    lines = briefing.split("\n")
    selected_lines = []
    capturing = False
    captured_sections = 0
    for line in lines:
        if line.startswith("#"):
            capturing = any(kw.lower() in line.lower() for kw in relevant_keywords)
            if capturing:
                selected_lines.append(line)
                captured_sections += 1
            if captured_sections >= 2:
                break
        elif capturing:
            selected_lines.append(line)
    result = "\n".join(selected_lines).strip()
    if len(result) > 600:
        result = result[:597] + "…"
    return result


# ── Content-Generierung via Claude ───────────────────────────────────────────

def generate_content() -> tuple[list[str], str]:
    """Gibt (liste mit Bild-Texten, caption) zurück.
    Carousel-Tage (Mo/Mi/Fr): 4 Karten.
    Einzelbild-Tage (Di/Do/Sa/So): 1 Karte.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    weekday     = datetime.now().weekday()
    week_number = datetime.now().isocalendar()[1]
    theme       = CUSTOM_THEME if CUSTOM_THEME else WEEKDAY_THEMES[weekday]
    # Post-Typ: manuelle Vorgabe hat Vorrang, sonst Wochentag-Regel
    if CUSTOM_POST_TYPE in ("carousel", "single"):
        is_carousel = (CUSTOM_POST_TYPE == "carousel")
    else:
        is_carousel = weekday in CAROUSEL_DAYS

    # Aktuelles Briefing laden
    briefing_raw        = get_latest_briefing()
    briefing_highlights = extract_briefing_highlights(briefing_raw)
    briefing_section    = ""
    if briefing_highlights:
        briefing_section = f"""
Aktuelle Forschungserkenntnisse aus dem wöchentlichen Briefing:
{briefing_highlights}

Beziehe diese Erkenntnisse passend in den Content ein — als Inspiration, konkretes Beispiel oder aktuellen Bezug. Zitiere keine Studie namentlich, sondern integriere das Wissen natürlich.
"""

    base_intro = f"""Du bist Lisa Goldschmidts Content-Assistentin für ihren Instagram-Account GOLDGESUND.
Lisa ist Heilpraktikerin (Osteopathie, Psychosomatik) in Berlin. Ihr Ton: warm, ruhig, klar, wissenschaftlich fundiert aber alltagsnah — keine Heilungsversprechen, keine lauten Claims.

Wochentag-Thema: {theme}
Wochennummer {week_number} — wähle einen frischen, spezifischen Aspekt dieses Themas.{briefing_section}"""

    if is_carousel:
        prompt = base_intro + """

Erstelle bitte einen Instagram-CAROUSEL mit 4 Bildkarten + Caption.

Aufbau der 4 Karten:
KARTE 1 – Hook: Große Aussage oder Frage die sofort neugierig macht. Soll Lust machen weiterzuswipen.
KARTE 2 – Hintergrundwissen: Erklärung, Zusammenhang im Körper, wissenschaftliche Einordnung (alltagsnah).
KARTE 3 – Praktischer Impuls: Was kann die Person jetzt sofort tun oder spüren? Konkret, körpernah.
KARTE 4 – Abschluss: Ruhiger, einladender Abschluss. Kein harter Verkauf — eher: "Komm gerne vorbei" oder eine offene Frage ans Publikum.

Für jede Karte gilt:
- Max. 3 Zeilen, pro Zeile max. 32 Zeichen
- Jede Zeile auf einer neuen Zeile
- Kraftvoll und kurz — kein Fülltext

CAPTION (für den ganzen Carousel-Post):
1. Erste Zeile: starker Hook — macht Lust zu lesen
2. Kurzer Absatz: Vertiefung aus Lisas Arbeit
3. Kurzer praktischer Impuls
4. Sanfter Abschluss (kein harter CTA)
5. Leerzeile
6. 10–12 relevante Hashtags (deutsch + englisch gemischt)
Länge: 180–240 Wörter

Antworte GENAU in diesem Format — keine anderen Texte davor oder danach:

===SLIDE_1===
Zeile 1
Zeile 2
Zeile 3
===SLIDE_2===
Zeile 1
Zeile 2
Zeile 3
===SLIDE_3===
Zeile 1
Zeile 2
Zeile 3
===SLIDE_4===
Zeile 1
Zeile 2
Zeile 3
===CAPTION===
Die vollständige Caption inkl. Hashtags"""

    else:
        prompt = base_intro + """

Erstelle bitte ein Instagram-EINZELBILD + Caption.

IMAGE_TEXT:
Kurzer, kraftvoller Text für die Bildkarte.
Max. 3 Zeilen, pro Zeile max. 32 Zeichen.
Kann ein Zitat, eine Frage oder eine kurze Aussage sein.
Schreib jeden Satz/jede Zeile in eine neue Zeile.

CAPTION:
1. Erste Zeile: starker Hook — macht Lust weiterzulesen
2. Kurzer Absatz: Einblick aus Lisas Arbeit
3. Kurzer praktischer Impuls oder Gedanke
4. Sanfter Abschluss (kein harter CTA)
5. Leerzeile
6. 10–12 relevante Hashtags (deutsch + englisch gemischt)
Länge: 180–240 Wörter

Antworte GENAU in diesem Format — keine anderen Texte davor oder danach:

===SLIDE_1===
Zeile 1
Zeile 2
Zeile 3
===CAPTION===
Die vollständige Caption inkl. Hashtags"""

    n_slides = NUM_SLIDES if is_carousel else 1

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1600,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    # Validierung
    for i in range(1, n_slides + 1):
        if f"===SLIDE_{i}===" not in raw:
            raise ValueError(f"Unerwartetes Antwort-Format (SLIDE_{i} fehlt):\n{raw}")
    if "===CAPTION===" not in raw:
        raise ValueError(f"Unerwartetes Antwort-Format (CAPTION fehlt):\n{raw}")

    # Parsen
    slides = []
    for i in range(1, n_slides + 1):
        marker_start = f"===SLIDE_{i}==="
        marker_end   = f"===SLIDE_{i+1}===" if i < n_slides else "===CAPTION==="
        text = raw.split(marker_start)[1].split(marker_end)[0].strip()
        slides.append(text)

    caption = raw.split("===CAPTION===")[1].strip()
    return slides, caption


# ── Bild-Erstellung via Pillow ────────────────────────────────────────────────

W, H = 1080, 1080

GOLD  = (200, 150,  62)   # #C8963E
CREAM = (242, 236, 216)   # warmes Creme

# Drei Brand-Farben — rotieren täglich: Lila → Salbeigrün → Creme → …
# Im Feed (3 Spalten) zeigt jede Reihe automatisch alle drei Farben
BRAND_COLORS = [
    {"bg": ( 74,  45, 122), "text": CREAM,           "accent": GOLD},  # Lila
    {"bg": (107, 143, 113), "text": CREAM,           "accent": GOLD},  # Salbeigrün
    {"bg": CREAM,            "text": ( 61,  36,  98), "accent": GOLD},  # Creme
]

def get_palette() -> dict:
    """Gibt die Tagesfarbe zurück — rotiert täglich durch alle drei Brand-Farben."""
    day_of_year = datetime.now().timetuple().tm_yday
    return BRAND_COLORS[day_of_year % 3]

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
        params["query"] = "nature green"
        r = requests.get("https://api.pexels.com/v1/search",
                         headers=headers, params=params, timeout=15)
        photos = r.json().get("photos", [])
    photo     = photos[week_number % len(photos)]
    photo_url = photo["src"]["large2x"]
    img_r     = requests.get(photo_url, timeout=30)
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


def create_slide(image_text: str,
                 bg_photo: Image.Image,
                 weekday: int,
                 slide_num: int,
                 total_slides: int,
                 use_clean: bool = False) -> Image.Image:
    """Erstellt eine einzelne Carousel-Karte."""
    palette    = get_palette()
    bg_color   = palette["bg"]
    text_color = palette["text"]
    accent     = palette["accent"]

    if use_clean:
        # ── Einfarbiger Hintergrund ───────────────────────────────
        img  = bg_photo.copy()   # ist bereits Volltonfarbe aus main()
        draw = ImageDraw.Draw(img)
        # Ornament oben
        img_rgba = img.convert("RGBA")
        orn_top  = load_ornament("ornament_top.png")
        img_rgba.paste(orn_top, (0, 45), orn_top)
        img  = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)
    else:
        # ── Naturfoto + Farboverlay ───────────────────────────────
        overlay = Image.new("RGBA", (W, H), (*bg_color, 168))
        img = bg_photo.convert("RGBA")
        img = Image.alpha_composite(img, overlay).convert("RGB")
        # kein Ornament bei Naturfotos
        draw = ImageDraw.Draw(img)

    # Schriften
    f_allura  = load_font("Allura-Regular.ttf", 38)
    f_body    = load_font("Alice-Regular.ttf", 72)
    f_body_sm = load_font("Alice-Regular.ttf", 56)
    f_small   = load_font("Alice-Regular.ttf", 26)

    # ── Haupttext zentriert ───────────────────────────────────────
    max_text_w = W - 140
    lines_raw  = image_text.split("\n")

    # Schriftgröße ermitteln
    all_lines = []
    for raw_line in lines_raw:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        wrapped = wrap_text(raw_line, f_body, max_text_w)
        all_lines.extend(wrapped)

    f_main = f_body if len(all_lines) <= 3 else f_body_sm
    line_h = 105 if f_main == f_body else 88

    # Nochmal umbrechen mit korrekter Schrift
    all_lines = []
    for raw_line in lines_raw:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        wrapped = wrap_text(raw_line, f_main, max_text_w)
        all_lines.extend(wrapped)

    total_h = len(all_lines) * line_h
    start_y = (H - total_h) // 2 - 10

    for i, line in enumerate(all_lines):
        bbox = draw.textbbox((0, 0), line, font=f_main)
        lw_px = bbox[2] - bbox[0]
        x = (W - lw_px) // 2
        draw.text((x, start_y + i * line_h), line, font=f_main, fill=text_color)

    # ── „goldgesund" klein unten ──────────────────────────────────
    brand = "goldgesund"
    bbox  = draw.textbbox((0, 0), brand, font=f_allura)
    bw    = bbox[2] - bbox[0]
    draw.text(((W - bw) // 2, H - 75), brand, font=f_allura, fill=accent)

    # ── Swipe-Hinweis auf Karte 1 ─────────────────────────────────
    if slide_num == 1 and total_slides > 1:
        swipe_text = "→ weitertippen"
        bbox_s  = draw.textbbox((0, 0), swipe_text, font=f_small)
        sw      = bbox_s[2] - bbox_s[0]
        draw.text((W - sw - 32, H - 135), swipe_text, font=f_small, fill=accent)

    # ── Karten-Nummer (Punkte) — nur bei Carousel ─────────────────
    if total_slides > 1:
        dot_r    = 5
        dot_gap  = 18
        total_w  = total_slides * dot_r * 2 + (total_slides - 1) * (dot_gap - dot_r * 2)
        start_x  = (W - total_w) // 2
        dot_y    = H - 112
        for j in range(total_slides):
            cx = start_x + j * dot_gap
            filled = (j == slide_num - 1)
            draw.ellipse(
                [cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r],
                fill=accent if filled else (*accent[:3], 100),
            )

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


def upload_slide(img: Image.Image, date_str: str, slide_num: int) -> str:
    """Eine Carousel-Karte in GitHub speichern, Raw-URL zurückgeben."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    content  = base64.b64encode(buf.getvalue()).decode()
    filename = f"posts/{date_str}_{slide_num}.jpg"
    upload_to_github(content, filename, f"Carousel slide {slide_num} {date_str}")
    time.sleep(3)
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"


def upload_caption(caption: str, date_str: str) -> None:
    """Caption als .txt in GitHub-Repo speichern."""
    content  = base64.b64encode(caption.encode("utf-8")).decode()
    filename = f"posts/{date_str}.txt"
    upload_to_github(content, filename, f"Post caption {date_str}")


# ── Vorschau-E-Mail via Brevo ─────────────────────────────────────────────────

def send_preview_email(image_urls: list[str], caption: str,
                       date_str: str, post_type: str = "carousel") -> None:
    """Schickt Lisa eine Vorschau-E-Mail mit allen Karten."""

    # Alle Bild-URLs + Caption + post_type im Webhook-Link übergeben
    params = {"post_type": post_type, "caption": caption}
    for i, url in enumerate(image_urls, start=1):
        params[f"image_url_{i}"] = url
    approval_url = f"{MAKE_APPROVAL_WEBHOOK}?{urlencode(params)}"

    # Caption-Zeilenumbrüche für HTML
    caption_html = caption.replace("\n", "<br>")

    # Karten-Vorschau: nebeneinander (2 × 2)
    def slide_cell(url: str, num: int) -> str:
        return f"""
        <td style="padding:6px;vertical-align:top;width:50%;">
          <p style="margin:0 0 4px;font-size:11px;color:#aaa;
                    letter-spacing:1px;text-transform:uppercase;text-align:center;">
            Karte {num}
          </p>
          <img src="{url}" width="220" alt="Karte {num}"
               style="width:220px;max-width:100%;border-radius:4px;
                      border:1px solid #e0ddd5;display:block;margin:0 auto;">
        </td>"""

    rows_html = ""
    for i in range(0, len(image_urls), 2):
        pair = image_urls[i:i+2]
        cells = "".join(slide_cell(u, i + j + 1) for j, u in enumerate(pair))
        rows_html += f'<tr>{cells}</tr>'

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
                      text-transform:uppercase;">{"Carousel · 4 Karten" if post_type == "carousel" else "Einzelbild"}</p>
            <h1 style="margin:8px 0 0;font-size:36px;color:#C8963E;font-weight:normal;
                       font-family:'Palatino Linotype',Palatino,serif;
                       font-style:italic;">goldgesund</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#999;">{date_str} &nbsp;·&nbsp; {len(image_urls)} {"Karten" if len(image_urls) > 1 else "Karte"}</p>
          </td>
        </tr>

        <!-- Karten-Vorschau -->
        <tr>
          <td style="padding:28px 40px 0;">
            <p style="margin:0 0 14px;font-size:13px;color:#888;
                      letter-spacing:1px;text-transform:uppercase;">Bildkarten</p>
            <table width="100%" cellpadding="0" cellspacing="0">
              {rows_html}
            </table>
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
              ✅ &nbsp; {"Jetzt als Carousel auf Instagram veröffentlichen" if post_type == "carousel" else "Jetzt auf Instagram veröffentlichen"}
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
        "subject": f"✨ Instagram-{'Carousel' if post_type == 'carousel' else 'Post'} {date_str} — bitte freigeben",
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
    date_str    = datetime.now().strftime("%Y-%m-%d")
    weekday     = datetime.now().weekday()
    week_number = datetime.now().isocalendar()[1]
    if CUSTOM_POST_TYPE in ("carousel", "single"):
        is_carousel = (CUSTOM_POST_TYPE == "carousel")
    else:
        is_carousel = weekday in CAROUSEL_DAYS
    post_type   = "carousel" if is_carousel else "single"
    day_names   = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    print(f"GOLDGESUND Instagram — {date_str} ({day_names[weekday]}, {post_type.upper()})")

    print(f"1/4  Content wird generiert ({post_type}, inkl. Briefing-Recherche) …")
    slides_text, caption = generate_content()
    for i, t in enumerate(slides_text, 1):
        print(f"     Karte {i}: {t!r}")
    print(f"     Caption-Vorschau: {caption[:80]}…")

    print("2/4  Hintergrund laden + Karten erstellen …")
    day_of_year = datetime.now().timetuple().tm_yday
    use_clean   = (day_of_year % 2 == 1)   # täglich abwechselnd
    if use_clean:
        bg_color = WEEKDAY_PALETTES[weekday]["bg"]
        bg_photo = Image.new("RGB", (W, H), bg_color)
        print(f"     Stil: Clean (einfarbig + Ornament) ✓")
    else:
        try:
            bg_photo = download_nature_photo(weekday, week_number)
            print(f"     Stil: Naturfoto geladen ✓")
        except Exception as e:
            print(f"     Foto-Download fehlgeschlagen ({e}), nutze Volltonfarbe")
            bg_color = WEEKDAY_PALETTES[weekday]["bg"]
            bg_photo = Image.new("RGB", (W, H), bg_color)

    total = len(slides_text)
    slides_imgs = []
    for i, text in enumerate(slides_text, 1):
        img = create_slide(text, bg_photo.copy(), weekday, i, total, use_clean=use_clean)
        slides_imgs.append(img)
        print(f"     Karte {i}/{total} erstellt ✓")

    print("3/4  Bild + Caption werden hochgeladen …")
    image_urls = []
    for i, img in enumerate(slides_imgs, 1):
        url = upload_slide(img, date_str, i)
        image_urls.append(url)
        print(f"     Karte {i} hochgeladen: {url}")
    upload_caption(caption, date_str)

    print("4/4  Vorschau-E-Mail wird gesendet …")
    send_preview_email(image_urls, caption, date_str, post_type)

    print("✓ Fertig! Lisa erhält jetzt die Vorschau-E-Mail zur Freigabe.")


if __name__ == "__main__":
    main()
