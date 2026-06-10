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

def generate_story_content(story_typ: str) -> tuple[str, str, str]:
    """Gibt (story_typ, bild_text, sticker) zurück."""
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    weekday = datetime.now().weekday()

    themen = {
        "frage": "Eine kurze, persönliche Frage die zum Nachdenken anregt — z.B. über den Körper, Stress, Wohlbefinden. Etwas das Follower gerne beantworten.",
        "tipp": "Ein konkreter Körper- oder Gesundheitstipp den man sofort umsetzen kann. Klein, alltagsnah, wirksam.",
        "zitat": "Ein inspirierendes Zitat aus der Naturheilkunde, Osteopathie oder Psychosomatik. Darf ruhig tiefgründig sein.",
    }

    prompt = f"""Du schreibst Instagram Stories für Lisa Goldschmidt (GOLDGESUND, Heilpraktikerin, Osteopathie & Psychosomatik, Berlin).

Wer Lisa ist — damit die Stories wirklich nach ihr klingen:
- Eigene Geschichte: Migräne, Burnout mit 27 — das macht sie authentisch
- Triggered wenn Patienten die Verantwortung abgeben ("der Arzt ist schuld") — übt sich in Annehmen und Loslassen
- Nach ihrem Retreat: will weg von "Symptome wegmachen" hin zu begleiten, ermächtigen, Eigenverantwortung stärken
- Tee und ätherische Öle sind ihr neu wichtig — fließen ins Business ein
- Was sie in der Praxis erlebt: trotz Internet wissen viele Menschen erstaunlich wenig über ihren Körper
- Das eigentliche Problem ist nicht fehlendes Wissen sondern die Integration ins echte Leben
- Mythen die sie täglich begegnen: "gerader Rücken ist gesund", "Psyche beeinflusst nicht Hormone", "ausgewogene Ernährung reicht"
- Persönlich: eigener Heilungsweg mit psychosomatischen Beschwerden — Annehmen und Loslassen sind ihre tägliche Praxis
- Tiefer Wunsch authentisch zu leben und eigene Schattenthemen zu integrieren
- Sinnsuche — Sinn in der Arbeit und im Leben finden beschäftigt sie sehr
- Sie lebt selbst was sie lehrt — das ist ihre Stärke und Glaubwürdigkeit
- Rituale: Kerze, Duftöle, Raum reinigen, Rassel, Meditation vor Behandlungen — das ist ihr echtes Leben
- Natur ist ihr Anker: zwei Hunde, barfuß laufen, Waldspaziergänge
- Liebt Fortbildungen leidenschaftlich — "dafür stehe ich Sonntagmorgen auf"
- Singt gerne, hört Musik mit vollem Fokus — durch Retreat wiederentdeckt
- Kaffee-Junkie mit Lieblingstassen aus dem Urlaub — entkoffeiniert mit Kokosmilch ist ihr Highlight des Jahres
- Summt beim Essen wenn es ihr schmeckt — Genuss und Süßes sind ihr wichtig
- Feiert kleine Dinge bewusst und mit Freude
- Berührende Momente aus der Praxis: Patientin deren Tinnitus kurz verschwand ("Wie wunderbar — das zeigt dass es wandelbar ist"); junge Mutter die nach Herzatmung weinte weil ihr Kopf endlich still war
- Diese Momente sind ihr Warum
- Haltung zu Selbstfürsorge: Atemmasken-Prinzip — erst sich, dann andere. Gesunder Egoismus ist keine Schwäche
- Business UND Träume — nicht entweder oder. Grautöne statt Schwarz-Weiß-Denken
- Kleine Schritte, Hilfe bitten, Träume machbar machen
- Eigene Erkenntnis: jahrelang versteckt hinter "ich rede über meine Gefühle" — aber Körper nicht mitgenommen
- Psychologin sagte fast "Kollegin" weil sie so kognitiv war — große Lektion in Demut
- Der Körper speichert alles — Emotionen sind Energie in Bewegung, nicht im Kopf
- Verstehen ist wichtig (Salutogenese) — aber eben nicht allein
- Praxis-Geschichte: hat sie durch einen Hundepopo auf einem Foto gefunden — Vermieterin war eine alte Hundetraining-Bekannte, Liebe auf den ersten Blick
- Liebt ihr buntes Klientel in Mariendorf — jung, alt, mit Tiefgang
- Vision: Praxis als Begegnungsort — Women's Circle, Mama Circle, Retreats, Workshops
- Kernbotschaft: Fokus auf das was DA ist statt auf Defizite — auch mit Diagnose ist Leben lebenswert und lebendig
- Selbst viele Krankheiten — und auf dem Retreat tiefe Selbstliebe und Lebendigkeit gefühlt
- Menschen langfristig begleiten: Körper, Seele, Tarot-Coaching, Kundalini, Gemeinschaft
- Ton: nahbar, ehrlich, aus dem echten Leben — nicht glatt oder perfekt, sondern menschlich und in Entwicklung

Story-Typ heute: {story_typ.upper()}
Kontext: {themen[story_typ]}

Die Story soll sich anfühlen als hätte Lisa sie selbst getippt — persönlich, direkt, warm.
Darf ruhig eine kleine persönliche Beobachtung aus dem Alltag enthalten (Natur, Körper, Praxis-Momente, Rituale).

Hier sind Beispiele die genau den richtigen Ton treffen — orientiere dich daran:

TIPP-Beispiele:
"Heute Morgen, Kaffee, Stille. / Bevor alles losgeht. / 5 Minuten nur für dich. / Das ist keine Kleinigkeit." → Sticker: Wie startest du in den Tag?
"Barfuß auf den Boden. / 2 Minuten. / Kein Witz — dein Nervensystem / dankt es dir sofort." → Sticker: Hast du es schon probiert?
"Gerader Rücken / ist nicht gesunder Rücken. / Dein Körper braucht / Bewegung — nicht Starre." → Sticker: Hat dich das überrascht?

FRAGE-Beispiele:
"Wann hast du zuletzt / auf deinen Körper gehört — / nicht auf Google, / sondern wirklich nach innen?" → Sticker: Schreib mir!
"Ich zünde vor jeder Behandlung / eine Kerze an. / Nicht für die Patienten — / für mich. Für den Übergang." → Sticker: Was sind deine Rituale?
"Heute beim Waldspaziergang / mit meinen Hunden / hab ich gemerkt: / Natur ist mein Reset-Knopf." → Sticker: Was ist deiner?

ZITAT-Beispiele:
"Annehmen ist keine Schwäche. / Es ist die schwerste / Übung die ich kenne. / Ich übe noch." → Sticker: Kennst du das?
"Symptome sind keine Feinde. / Sie sind Nachrichten. / Dein Körper spricht — / hörst du zu?" → Sticker: Was sagt dir deiner gerade?
"Eine Woche geht zu Ende. / Nicht perfekt. / Aber echt. / Das reicht." → Sticker: Was nimmst du mit?

BILD_TEXT: Max. 4 Zeilen, pro Zeile max. 28 Zeichen. Kurz und kraftvoll — wie die Beispiele oben.
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

    try:
        bild_text = raw.split("===BILD_TEXT===")[1].split("===STICKER===")[0].strip()
        sticker   = raw.split("===STICKER===")[1].strip()
    except IndexError:
        # Fallback: gesamten Text als Bild-Text verwenden
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("===")]
        bild_text = "\n".join(lines[:4]) if lines else "Dein Körper\nweiß den Weg."
        sticker   = "Was denkst du?"
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


def upload_story(img: Image.Image, date_str: str, nummer: int) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    content  = base64.b64encode(buf.getvalue()).decode()
    filename = f"posts/story_{date_str}_{nummer}.jpg"
    return upload_to_github(content, filename, f"Story {date_str} #{nummer}")


def send_stories_email(stories: list[dict], date_str: str) -> None:
    """Schickt alle 3 Stories des Tages in einer einzigen E-Mail."""
    typen_label = {"tipp": "🌿 Tipp für dich", "frage": "💬 Frage des Tages", "zitat": "✨ Gedanke"}

    karten_html = ""
    for s in stories:
        label = typen_label.get(s["typ"], s["typ"])
        karten_html += f"""
        <tr>
          <td style="padding:24px 40px;border-bottom:1px solid #e8e5de;text-align:center;">
            <p style="margin:0 0 8px;font-size:12px;color:#C8963E;letter-spacing:2px;text-transform:uppercase;font-weight:bold;">{label}</p>
            <img src="{s['url']}" width="220" alt="Story"
                 style="width:220px;border-radius:12px;border:1px solid #e0ddd5;display:block;margin:0 auto;">
            <p style="margin:12px 0 0;font-size:13px;color:#555;">
              <strong>Sticker:</strong> {s['sticker']}
            </p>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f0;padding:40px 0;">
    <tr><td align="center">
      <table width="540" cellpadding="0" cellspacing="0"
             style="background:#FAFAF7;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <tr>
          <td style="padding:28px 40px 16px;text-align:center;border-bottom:2px solid #C8963E;">
            <p style="margin:0;font-size:12px;color:#888;letter-spacing:2px;text-transform:uppercase;">Deine 3 Stories für heute</p>
            <h1 style="margin:8px 0 0;font-size:32px;color:#C8963E;font-weight:normal;font-style:italic;">goldgesund</h1>
            <p style="margin:4px 0 0;font-size:13px;color:#999;">{date_str}</p>
          </td>
        </tr>
        {karten_html}
        <tr>
          <td style="padding:24px 40px;background:#f8f6f0;">
            <p style="margin:0;font-size:13px;color:#555;line-height:1.7;">
              <strong>So postest du die Stories:</strong><br>
              1. Drück lange auf ein Bild → <em>Bild sichern</em><br>
              2. Öffne Instagram → tippe auf dein Profilbild<br>
              3. Bild auswählen und als Story posten ✓<br>
              4. Dasselbe Bild auch als WhatsApp Status nutzen 📱
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
        "subject": f"📱 Deine 3 Stories für {date_str}",
        "htmlContent": html,
    }
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    r.raise_for_status()
    print(f"  Alle 3 Stories per E-Mail gesendet ✓")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"GOLDGESUND Stories — {date_str} (alle 3 auf einmal)")

    typen = ["tipp", "frage", "zitat"]
    stories = []

    for i, story_typ in enumerate(typen, 1):
        print(f"{i}/3  Story '{story_typ}' wird generiert …")
        _, bild_text, sticker = generate_story_content(story_typ)
        print(f"     Text: {bild_text!r}")

        img = create_story_image(bild_text, story_typ, sticker)
        url = upload_story(img, date_str, i)
        time.sleep(2)
        stories.append({"typ": story_typ, "url": url, "sticker": sticker})
        print(f"     Hochgeladen ✓")

    print("4/4  E-Mail mit allen 3 Stories wird gesendet …")
    send_stories_email(stories, date_str)
    print("✓ Fertig!")


if __name__ == "__main__":
    main()
