import os
import io
import sys
import json
import time
import random
import asyncio
import urllib.parse
import requests
import textwrap
import numpy as np
import edge_tts
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

try:
    from moviepy.editor import ImageClip, AudioFileClip, VideoClip, concatenate_videoclips
except ImportError:
    from moviepy import ImageClip, AudioFileClip, VideoClip, concatenate_videoclips

# ==========================================
# 1. SCHEDULE, STATE & PAGE CONFIGURATION
# ==========================================
ASSET_ID = "1464016173453077"
LIKED_PAGES_URL = "https://www.facebook.com/pages/?category=liked&ref=bookmarks"

POST_INTERVAL_MINUTES = 60
ALSO_POST_TO_STORY = True

OUTPUT_DIR = "build_reel"
HISTORY_FILE = "posted_history.json"
STATE_FILE = "engine_state.json"
COOKIES_FILE = "fb_cookies.json"
FOLLOWED_FILE = "followed_pages_insights.json"
USER_DATA_DIR = os.path.abspath("fb_chrome_session")
IS_CLOUD = os.getenv("GITHUB_ACTIONS") == "true"

# ==========================================
# 2. 9 CATEGORIES + COMPETITOR-GRADE ANGLES
# ==========================================
CATEGORIES = [
    {
        "id": 1,
        "name": "Education",
        "voice": "en-US-ChristopherNeural",
        "style": "cinematic national geographic documentary photography 8k ultra detailed dramatic lighting vertical",
        "hashtags": "#Education #InterestingFacts #UnsolvedHistory #DailyKnowledge #DidYouKnow",
        "competitor_angle": "Unexplained historical anomalies, lost ancient archives, and extreme geographical wonders",
        "seed_subjects": [
            ("The Abandoned Lifeboat on Uninhabited Bouvet Island", "1964 South Atlantic expedition", "a pristine lifeboat with oars found in a lagoon on the world's most remote glacier island with zero crew"),
            ("The Secret Cold War Tunnels Inside Greece's Davelis Cave", "Mount Penteli, Greece", "ancient Pan worship carvings next to sealed military radar vaults that abruptly shut down in 1983"),
            ("The Whispering Acoustic Mystery of Golconda Fort", "16th-century Hyderabad citadel", "a stone archway engineered so a handclap at the gate echoes clearly at the highest palace dome a kilometer away"),
            ("The Boiling River Hidden Deep in the Peruvian Amazon", "Shanay-Timpishka thermal river", "a four-mile stretch of jungle river running at 200 degrees Fahrenheit with no active volcano nearby")
        ]
    },
    {
        "id": 2,
        "name": "Science, Technology & Engineering",
        "voice": "en-US-ChristopherNeural",
        "style": "futuristic high-tech engineering cutaway photorealistic 8k dramatic lighting unreal engine 5 vertical",
        "hashtags": "#ScienceAndTech #Engineering #FutureTech #ScientificMysteries #InterestingFacts",
        "competitor_angle": "Extreme physics experiments, megastructure engineering secrets, and quantum anomalies",
        "seed_subjects": [
            ("The 72-Second 'Wow!' Radio Signal From Deep Space", "August 1977 Big Ear Observatory", "a narrowband radio blast from Sagittarius 30 times louder than deep space background noise that never repeated"),
            ("The 42-Ton Tuned Mass Damper Inside Taipei 101", "Taiwan typhoon engineering", "a giant suspended golden steel sphere that sways counter to hurricane winds to stop the skyscraper from snapping"),
            ("IceCube: The Telescope Buried a Mile Beneath Antarctic Ice", "South Pole Neutrino Observatory", "five thousand optical sensors melted into pure prehistoric ice to catch ghost particles passing straight through Earth"),
            ("How Voyager 1 Still Replies From 15 Billion Miles Away", "Interstellar space 1977-present", "a 22-watt radio transmitter weaker than a refrigerator bulb beaming data across 22 hours of light-travel time")
        ]
    },
    {
        "id": 3,
        "name": "Entertainment Website",
        "voice": "en-US-GuyNeural",
        "style": "epic hollywood thriller movie poster aesthetic neon rim lighting 8k hyperrealistic vertical",
        "hashtags": "#Entertainment #MovieMysteries #MindBlowing #PopCultureFacts #Mysteries",
        "competitor_angle": "Bizarre real events behind blockbuster films, hidden cipher codes in cinema, and stage illusions",
        "seed_subjects": [
            ("The Unsolved 'Kryptos' Sculpture Cipher at CIA Headquarters", "Langley courtyard 1990", "four copper plates carved by Jim Sanborn where the final 97 letters still baffle the world's top cryptographers"),
            ("The Real 1947 Ghost Ship That Inspired Modern Sea Thrillers", "SS Ourang Medan mystery", "a distress Morse code message from the Strait of Malacca followed by a silent ship drifting with no visible damage"),
            ("How Stanley Kubrick Used NASA Satellite Lenses to Film by Candlelight", "1975 Barry Lyndon production", "ultra-fast f/0.7 Carl Zeiss lenses built for Apollo moon missions modified to shoot scenes lit only by beeswax candles"),
            ("The Hidden Musical Code Locked Inside Rosslyn Chapel's Stone Cubes", "15th-century Scotland", "213 carved stone cubes overhead whose geometric patterns match Chladni sound frequency vibrations")
        ]
    },
    {
        "id": 4,
        "name": "Digital Creator",
        "voice": "en-US-GuyNeural",
        "style": "modern cyberpunk creator studio glowing holographic screens 8k sharp focus vibrant vertical",
        "hashtags": "#DigitalCreator #CreatorEconomy #AlgorithmSecrets #FutureOfMedia #ViralReels",
        "competitor_angle": "Digital media psychology, visual optical illusions, and behind-the-scenes viral engineering",
        "seed_subjects": [
            ("The 3-Second 'Pattern Interrupt' That Freezes Human Thumbs", "Neuro-visual attention labs", "how sudden camera perspective shifts trigger the brain's orienting reflex before conscious scrolling happens"),
            ("How Pixar Nearly Lost Toy Story 2—And Found It on a Home PC", "1998 animation studio crisis", "an accidental server command that deleted 90% of the film until a technical director on maternity leave had a backup"),
            ("The Acoustic 'Shepard Tone' Illusion That Makes Videos Feel Infinitely Tense", "Psychoacoustic sound design", "overlapping sine waves that trick the human ear into hearing a pitch rising forever without ever getting higher"),
            ("How Virtual Production LED Volumes Replaced Hollywood Green Screens", "Unreal Engine real-time stages", "wrapping actors in 270-degree micro-LED walls that shift parallax perspective in real time with the camera lens")
        ]
    },
    {
        "id": 5,
        "name": "Discoveries",
        "voice": "en-US-ChristopherNeural",
        "style": "ancient archaeological discovery dramatic torchlight photorealistic 8k national geographic vertical",
        "hashtags": "#Discoveries #Archaeology #AncientMysteries #HiddenHistory #Explore",
        "competitor_angle": "Bizarre artifacts, sunken cities, and impossible archaeological finds",
        "seed_subjects": [
            ("The 11,000-Year-Old Carved Megaliths of Göbekli Tepe", "Southeastern Turkey excavation", "massive T-shaped limestone pillars carved with 3D predators 6,000 years before Stonehenge or the invention of metal tools"),
            ("The Sunken Marble City of Pavlopetri Beneath Greek Waters", "Peloponnese coast 1967", "a complete 5,000-year-old Bronze Age town with two-story houses, streets, and water pipes resting 12 feet underwater"),
            ("The Roman Dodecahedrons: 120 Hollow Bronze Artifacts With No Known Purpose", "Northern Roman Empire", "twelve-sided geometric bronze objects with differently sized rings and knobs but zero mention in any Roman text"),
            ("The 2,200-Year-Old Terracotta Army's Chromium-Coated Swords", "Xi'an China tomb excavation", "bronze blades buried for two millennia that emerged razor-sharp and rust-free thanks to an ancient chemical oxide layer")
        ]
    },
    {
        "id": 6,
        "name": "Inventions",
        "voice": "en-US-ChristopherNeural",
        "style": "intricate steampunk and modern invention prototype glowing blueprints 8k studio lighting vertical",
        "hashtags": "#Inventions #GreatInventions #Innovation #HistoryOfTech #EngineeringMarvels",
        "competitor_angle": "Forgotten ahead-of-their-time machines, accidental lab breakthroughs, and unbreakable materials",
        "seed_subjects": [
            ("Starlite: The Amateur Chemist's Plastic That Withstood a Nuclear Flash", "Maurice Ward's 1990s demonstration", "a mysterious coating painted onto a raw egg that survived a 10,000-degree blowtorch while staying cold inside"),
            ("How Hedy Lamarr Invented Frequency-Hopping Spread Spectrum in 1941", "World War II radio guidance", "a Hollywood actress and composer syncing player-piano rolls to stop radio torpedoes from being jammed—creating the foundation of Wi-Fi"),
            ("The 1770 Mechanical Turk Automaton That Defeated Napoleon at Chess", "Wolfgang von Kempelen's workshop", "a clockwork cabinet that toured Europe for 84 years using sliding magnetic chess pieces and candle smoke optical illusions"),
            ("How Superglue Was Rejected Twice for Being 'Too Sticky' for Gun Sights", "Harry Coover's 1942 Eastman Kodak lab", "cyanoacrylate monomers that ruined every test prism before becoming a battlefield spray that sealed wounds in seconds")
        ]
    },
    {
        "id": 7,
        "name": "New Tech Launches",
        "voice": "en-US-GuyNeural",
        "style": "sleek futuristic product launch keynote glowing glass gadget 8k commercial photography vertical",
        "hashtags": "#NewTech #TechLaunches #FutureGadgets #Innovation #TechNews",
        "competitor_angle": "Next-gen hardware, bionic devices, metamaterials, and futuristic consumer tech",
        "seed_subjects": [
            ("Metamaterial Acoustic Cloaks That Bend Sound Waves Around Objects", "Advanced materials engineering", "3D-printed geometric lattice shields that guide sonar and noise around an object as if nothing is there"),
            ("Solid-State Silicon-Anode Batteries Reaching 1,000 Kilometers Per Charge", "Next-gen EV battery labs", "replacing flammable liquid electrolytes with solid ceramic separators that charge to 80% in under 8 minutes"),
            ("E-Ink Prism Color-Shifting Cars and Smart Surfaces", "Automotive exterior tech", "electrophoretic microcapsules embedded in body panels that change patterns and colors using almost zero battery power"),
            ("Ultrasonic Haptic Holograms You Can Actually Feel in Midair", "Phased-array acoustic transducers", "focusing invisible ultrasound waves onto your fingertips to create the physical sensation of buttons floating in empty air")
        ]
    },
    {
        "id": 8,
        "name": "AI",
        "voice": "en-US-ChristopherNeural",
        "style": "glowing neural network artificial intelligence humanoid core cinematic 8k blue and gold lighting vertical",
        "hashtags": "#AI #ArtificialIntelligence #FutureOfAI #MachineLearning #TechMysteries",
        "competitor_angle": "Mind-bending AI discoveries, neural decoding, and machines solving ancient mysteries",
        "seed_subjects": [
            ("How AI Discovered 303 New Giant Nazca Lines in the Peruvian Desert in 6 Months", "Yamagata University & IBM AI survey", "neural networks scanning drone imagery to spot faded 2,000-year-old geoglyphs that human archaeologists walked past for decades"),
            ("Brain-Computer Interfaces Translating Silent Thoughts Into Spoken Sentences", "Neuroprosthetics research labs", "AI decoders reading motor cortex signals to let paralyzed patients speak through a digital avatar of their own voice at 78 words per minute"),
            ("How DeepMind's GraphCast Learned to Predict Global Weather on a Single Chip", "Atmospheric AI modeling", "training on 40 years of satellite reanalysis data to forecast hurricane tracks 10 days out in under 60 seconds"),
            ("Acoustic AI Decoding the Hidden Vocabulary of Sperm Whale Clans", "Project CETI Dominica ocean lab", "machine learning analyzing thousands of rhythmic codas to map a phonetic alphabet beneath the ocean")
        ]
    },
    {
        "id": 9,
        "name": "Small Kids Education",
        "voice": "en-US-AnaNeural",
        "style": "pixar 3d animation style vibrant colorful cute educational illustration 8k bright lighting vertical",
        "hashtags": "#KidsEducation #FunStoriesForKids #SmartKids #ScienceForKids #CuriousMinds",
        "competitor_angle": "Adorable, mind-blowing nature and space stories explained simply for kids and parents",
        "seed_subjects": [
            ("The Immortal Jellyfish That Can Press Rewind and Become a Baby Again", "Turritopsis dohrnii ocean adventure", "a tiny glowing jellyfish smaller than your pinky nail that turns back into a baby polyp whenever it gets old"),
            ("A Planet Where It Rains Real Sparkling Diamonds From the Sky", "Neptune and Uranus deep clouds", "super-high pressure squeezing carbon in the clouds into millions of falling diamonds deep inside icy giant planets"),
            ("How Tardigrades (Water Bears) Survived a Trip into Outer Space", "Microscopic moss explorers", "chubby eight-legged microscopic creatures that curl into a dry ball and survive freezing space for days"),
            ("Why Flamingos Are Born With Gray Feathers Instead of Pink!", "Lagoon bird nature story", "baby flamingos hatching fluffy gray and turning bright pink from eating crunchy brine shrimp packed with natural pigment")
        ]
    }
]


# ==========================================
# 3. NETWORK GUARD, STATE & 32-PAGE SYNC
# ==========================================
def wait_for_internet():
    while True:
        try:
            requests.get("https://www.google.com", timeout=6)
            return
        except Exception:
            print("[!] Internet disconnected. Waiting 30 seconds to reconnect...")
            time.sleep(30)


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_to_history(topic_title: str):
    history = load_history()
    if topic_title not in history:
        history.append(topic_title)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-500:], f, indent=2)


def sync_liked_pages_from_browser(page):
    if os.path.exists(FOLLOWED_FILE):
        try:
            with open(FOLLOWED_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f).get("followed_pages", [])
                if len(existing) >= 15:
                    return
        except Exception:
            pass

    print(f"[*] Syncing your 32 followed pages from: {LIKED_PAGES_URL} ...")
    try:
        page.goto(LIKED_PAGES_URL, wait_until="domcontentloaded")
        time.sleep(6)

        for _ in range(5):
            page.mouse.wheel(0, 2200)
            time.sleep(2)

        ignore_words = {
            "home", "watch", "video", "marketplace", "groups", "gaming", "feeds",
            "pages", "see all", "create new page", "meta business suite", "discover",
            "liked pages", "invites", "notifications", "menu", "search", "friends",
            "memories", "saved", "events", "ads manager", "interesting facts & mysteries"
        }

        discovered = []
        links = page.locator('a[role="link"]').all()
        for link in links:
            try:
                raw_text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                first_line = raw_text.split("\n")[0].strip()

                if (
                    first_line
                    and 2 < len(first_line) < 55
                    and first_line.lower() not in ignore_words
                    and "facebook.com/" in href
                    and not any(x in href for x in ["/groups/", "/friends/", "/events/", "/marketplace/", "/notifications/"])
                ):
                    if first_line not in discovered:
                        discovered.append(first_line)
            except Exception:
                pass

        if discovered:
            payload = {
                "source_url": LIKED_PAGES_URL,
                "synced_at": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
                "count": len(discovered[:40]),
                "followed_pages": discovered[:40]
            }
            with open(FOLLOWED_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            print(f"[+] Synced {len(discovered[:40])} followed pages into {FOLLOWED_FILE}!")
    except Exception as e:
        print(f"    [!] Followed pages sync note ({e})—continuing...")


def load_followed_inspiration() -> str:
    base_competitors = [
        "Mysteries Unsolved", "Omarc Mysteries", "MysteriesFA",
        "TheSpookyHunter9", "MindCircuit"
    ]
    if os.path.exists(FOLLOWED_FILE):
        try:
            with open(FOLLOWED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                pages = data.get("followed_pages", [])
                if pages:
                    combined = list(dict.fromkeys(pages + base_competitors))
                    return ", ".join(combined[:35])
        except Exception:
            pass
    return ", ".join(base_competitors)


def load_engine_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"cycle": 1, "next_category_index": 0}


def save_engine_state(cycle: int, next_category_index: int):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "cycle": cycle,
                "next_category_index": next_category_index,
                "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            },
            f,
            indent=2
        )


def build_fallback_story_from_seed(category: dict, history: list) -> dict:
    unused_seeds = [s for s in category["seed_subjects"] if s[0] not in history]
    if not unused_seeds:
        seed = random.choice(category["seed_subjects"])
        title = f"{seed[0]} (New Discovery #{len(history) + 1})"
    else:
        seed = unused_seeds[0]
        title = seed[0]

    _, setting, core_mystery = seed
    save_to_history(title)
    print(f"[+] Synthesized High-Retention Seed Story: '{title}'")

    return {
        "title": title,
        "hook_banner": title[:48].upper(),
        "caption": (
            f"Have you ever heard the true story of {title}? 🤯🔍\n\n"
            f"Location/Era: {setting}.\n"
            f"The Mystery: {core_mystery.capitalize()}.\n\n"
            f"What is your theory on how this happened? Drop your answer below! 👇"
        ),
        "scenes": [
            {
                "text": f"During {setting}, investigators encountered a mystery that defied explanation: {core_mystery}.",
                "image_prompt": f"Extreme close-up dramatic hero shot of {core_mystery}, {setting}, mysterious lighting"
            },
            {
                "text": "When experts examined the physical evidence up close, every measurement challenged conventional textbooks.",
                "image_prompt": f"Wide-angle cinematic view of researchers examining {core_mystery} at {setting}, glowing details"
            },
            {
                "text": "Decades of advanced scanning and analysis revealed hidden mechanisms that nobody thought were possible at the time.",
                "image_prompt": f"Macro cutaway cross-section glowing schematic view of {core_mystery}, intricate textures"
            },
            {
                "text": "Even today, this discovery sparks fierce debate worldwide. What do you think is the real explanation? Comment below!",
                "image_prompt": f"Epic atmospheric wide shot of {setting} under dramatic sky, mystery documentary aesthetic"
            }
        ]
    }


def generate_fresh_reel_script(category: dict) -> dict:
    wait_for_internet()
    history = load_history()
    followed_list = load_followed_inspiration()
    cat_name = category["name"]
    angle = category["competitor_angle"]
    print(f"\n[*] Crafting High-Retention Story for Category #{category['id']}: {cat_name}...")

    system_prompt = (
        f"You are the lead viral Reel producer for 'Interesting Facts & Mysteries', studying and outperforming "
        f"these 32 creator and mystery pages the user follows: ({followed_list}). "
        f"Write a 100% factual, gripping 4-scene short documentary story for the category '{cat_name}' "
        f"focusing on: {angle}. "
        f"STRICT RULE: Do NOT repeat or resemble any of these already published titles: {history[-45:]}. "
        "Start Scene 1 with a specific year, real place, or real scientist and an immediate curiosity hook. "
        "Keep each scene punchy (15-21 words) for fast retention pacing, and reveal the twist in Scene 3! "
        "Every scene MUST use a completely different camera angle and visual subject. "
        "Return ONLY valid JSON with this exact structure: "
        '{"title": "Specific gripping story title", '
        '"hook_banner": "SHORT 4-6 WORD ALL-CAPS HOOK FOR TOP OF VIDEO", '
        '"caption": "3-paragraph engaging story post ending with a polarizing debate question for the comments", '
        '"scenes": ['
        '{"text": "Scene 1 hook with exact date/place (15-21 words)", "image_prompt": "Scene 1 close-up visual description"},'
        '{"text": "Scene 2 investigation/conflict (15-21 words)", "image_prompt": "Scene 2 wide environment visual description"},'
        '{"text": "Scene 3 mind-blowing twist/climax (15-21 words)", "image_prompt": "Scene 3 inside/cutaway visual description"},'
        '{"text": "Scene 4 lasting mystery & question (15-21 words)", "image_prompt": "Scene 4 epic closing visual description"}'
        ']}'
    )

    for attempt in range(1, 4):
        try:
            res = requests.post(
                "https://text.pollinations.ai/",
                json={
                    "messages": [
                        {"role": "system", "content": "You output only raw valid JSON objects."},
                        {"role": "user", "content": system_prompt}
                    ],
                    "model": "openai",
                    "seed": random.randint(1, 9999999),
                    "jsonMode": True
                },
                timeout=45
            )
            raw = res.text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            data = json.loads(raw)
            title = data.get("title", "").strip()

            if title and title not in history and "scenes" in data and len(data["scenes"]) >= 4:
                save_to_history(title)
                print(f"[+] New AI Story Locked: '{title}'")
                return data
        except Exception as e:
            print(f"    [!] Story AI attempt {attempt}/3 note ({e})...")
            time.sleep(2)

    return build_fallback_story_from_seed(category, history)


# ==========================================
# 4. KEN BURNS MOTION + HD VISUAL RENDERER
# ==========================================
def load_cross_platform_font(size: int):
    font_candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def create_fallback_canvas() -> Image.Image:
    img = Image.new("RGBA", (1080, 1920), (12, 16, 32, 255))
    draw = ImageDraw.Draw(img)
    for _ in range(120):
        x, y, r = random.randint(20, 1060), random.randint(20, 1880), random.randint(1, 3)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 225, 130, 180))
    return img


def fetch_raw_ai_image(prompt: str, style: str) -> Image.Image:
    wait_for_internet()
    full_prompt = f"{prompt}, {style}, no text, no letters, no watermark, masterpiece, ultra detailed, 8k"
    encoded_prompt = urllib.parse.quote(full_prompt)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for attempt in range(1, 5):
        seed = random.randint(10000, 9999999)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width=1080&height=1920&seed={seed}&nologo=true&enhance=true&model=flux"
        )
        try:
            response = requests.get(url, headers=headers, timeout=65)
            if response.status_code == 200 and len(response.content) > 8000:
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                return img.resize((1080, 1920), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"    [!] Image attempt {attempt}/4 note ({e}). Retrying...")
        time.sleep(3)

    return create_fallback_canvas()


def create_hud_overlay(category_name: str, hook_banner: str, subtitle_text: str, scene_num: int) -> Image.Image:
    overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_sub = load_cross_platform_font(48)
    font_hook = load_cross_platform_font(38)
    font_badge = load_cross_platform_font(28)

    draw.rounded_rectangle(
        [60, 70, 1020, 245],
        radius=22,
        fill=(0, 0, 0, 210),
        outline=(255, 195, 0, 245),
        width=3
    )
    badge_text = f"⚡ {category_name.upper()}  •  SCENE {scene_num}/4"
    b_box = draw.textbbox((0, 0), badge_text, font=font_badge)
    b_x = (1080 - (b_box[2] - b_box[0])) // 2
    draw.text((b_x, 86), badge_text, font=font_badge, fill=(255, 200, 50, 255))

    hook_lines = textwrap.wrap(hook_banner.upper(), width=32)[:2]
    hy = 132
    for hline in hook_lines:
        hb = draw.textbbox((0, 0), hline, font=font_hook)
        hx = (1080 - (hb[2] - hb[0])) // 2
        draw.text((hx + 2, hy + 2), hline, font=font_hook, fill=(0, 0, 0, 255))
        draw.text((hx, hy), hline, font=font_hook, fill=(255, 255, 255, 255))
        hy += 46

    lines = textwrap.wrap(subtitle_text, width=27)
    line_height = 64
    total_text_height = len(lines) * line_height
    y_start = 1380 - (total_text_height // 2)

    box_padding = 36
    box_top = y_start - box_padding
    box_bottom = y_start + total_text_height + box_padding

    draw.rounded_rectangle(
        [60, box_top, 1020, box_bottom],
        radius=25,
        fill=(0, 0, 0, 215),
        outline=(255, 195, 0, 235),
        width=3
    )

    prog_width = int(920 * (scene_num / 4.0))
    draw.rounded_rectangle([80, box_bottom - 14, 80 + prog_width, box_bottom - 6], radius=4, fill=(255, 215, 0, 255))

    y = y_start
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_sub)
        x = (1080 - (bbox[2] - bbox[0])) // 2
        draw.text((x + 3, y + 3), line, font=font_sub, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font_sub, fill=(255, 240, 155, 255))
        y += line_height

    return overlay


def build_dedicated_story_card(
    raw_bg_img: Image.Image,
    category_name: str,
    story_title: str,
    teaser_text: str,
    output_path: str
):
    overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 80))
    draw = ImageDraw.Draw(overlay)

    font_header = load_cross_platform_font(44)
    font_title = load_cross_platform_font(56)
    font_body = load_cross_platform_font(44)
    font_cta = load_cross_platform_font(38)

    draw.rounded_rectangle([90, 110, 990, 215], radius=30, fill=(255, 190, 0, 245))
    hdr = f"🔥 {category_name.upper()} STORY"
    hb = draw.textbbox((0, 0), hdr, font=font_header)
    draw.text(((1080 - (hb[2] - hb[0])) // 2, 138), hdr, font=font_header, fill=(10, 10, 15, 255))

    draw.rounded_rectangle(
        [65, 580, 1015, 1480],
        radius=35,
        fill=(8, 12, 24, 225),
        outline=(255, 200, 40, 255),
        width=4
    )

    t_lines = textwrap.wrap(story_title.upper(), width=20)[:3]
    ty = 640
    for tl in t_lines:
        tb = draw.textbbox((0, 0), tl, font=font_title)
        draw.text(((1080 - (tb[2] - tb[0])) // 2, ty), tl, font=font_title, fill=(255, 215, 0, 255))
        ty += 70

    b_lines = textwrap.wrap(teaser_text, width=26)[:5]
    by = ty + 45
    for bl in b_lines:
        bb = draw.textbbox((0, 0), bl, font=font_body)
        draw.text(((1080 - (bb[2] - bb[0])) // 2, by), bl, font=font_body, fill=(245, 245, 255, 255))
        by += 60

    draw.rounded_rectangle([110, 1620, 970, 1740], radius=40, fill=(0, 0, 0, 235), outline=(255, 215, 0, 255), width=3)
    cta = "🎬 FULL REEL JUST POSTED ON OUR PAGE!"
    cb = draw.textbbox((0, 0), cta, font=font_cta)
    draw.text(((1080 - (cb[2] - cb[0])) // 2, 1658), cta, font=font_cta, fill=(255, 230, 100, 255))

    story_card = Image.alpha_composite(raw_bg_img, overlay).convert("RGB")
    story_card.save(output_path, "JPEG", quality=95)


async def generate_voiceover(text: str, voice: str, output_audio_path: str):
    communicate = edge_tts.Communicate(text, voice, rate="+6%")
    await communicate.save(output_audio_path)


def make_ken_burns_scene_clip(
    raw_bg_img: Image.Image,
    hud_overlay: Image.Image,
    aud_path: str,
    zoom_in: bool = True
):
    audio_clip = AudioFileClip(aud_path)
    duration = max(audio_clip.duration, 1.0)
    bg_rgb = raw_bg_img.convert("RGB")

    def make_frame(t):
        progress = t / duration
        scale = (1.0 + 0.14 * progress) if zoom_in else (1.14 - 0.14 * progress)
        crop_w = int(1080 / scale)
        crop_h = int(1920 / scale)
        left = (1080 - crop_w) // 2
        top = (1920 - crop_h) // 2

        cropped = bg_rgb.crop((left, top, left + crop_w, top + crop_h)).resize(
            (1080, 1920), Image.Resampling.BILINEAR
        ).convert("RGBA")
        composited = Image.alpha_composite(cropped, hud_overlay).convert("RGB")
        return np.array(composited)

    clip = VideoClip(make_frame, duration=duration)
    if hasattr(clip, "set_audio"):
        return clip.set_audio(audio_clip)
    return clip.with_audio(audio_clip)


def build_category_reel(category: dict) -> tuple[str, str, str]:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    script_data = generate_fresh_reel_script(category)
    scenes = script_data["scenes"][:4]
    story_title = script_data.get("title", category["name"])
    hook_banner = script_data.get("hook_banner", story_title[:46].upper())

    full_caption = (
        f"🚨 {story_title.upper()} 🚨\n"
        f"📌 Category: {category['name']}\n\n"
        f"{script_data['caption']}\n\n"
        f"👉 Follow Interesting Facts & Mysteries for daily true stories & breakthroughs! 🌍✨\n"
        f"{category['hashtags']}"
    )

    clips = []
    story_card_path = os.path.join(OUTPUT_DIR, f"story_card_cat_{category['id']}.jpg")

    for idx, scene in enumerate(scenes):
        wait_for_internet()
        img_path = os.path.join(OUTPUT_DIR, f"cat_{category['id']}_scene_{idx}.jpg")
        aud_path = os.path.join(OUTPUT_DIR, f"cat_{category['id']}_scene_{idx}.mp3")

        print(f"[*] Generating voiceover for Scene {idx + 1}/4 ({category['voice']})...")
        asyncio.run(generate_voiceover(scene["text"], category["voice"], aud_path))

        print(f"[*] Generating HD Scene {idx + 1}/4 Visual: {scene['image_prompt'][:50]}...")
        raw_bg = fetch_raw_ai_image(scene["image_prompt"], category["style"])
        hud_overlay = create_hud_overlay(
            category_name=category["name"],
            hook_banner=hook_banner,
            subtitle_text=scene["text"],
            scene_num=idx + 1
        )

        Image.alpha_composite(raw_bg, hud_overlay).convert("RGB").save(img_path, "JPEG", quality=95)

        if idx == 0:
            build_dedicated_story_card(
                raw_bg_img=raw_bg,
                category_name=category["name"],
                story_title=story_title,
                teaser_text=scene["text"],
                output_path=story_card_path
            )

        clips.append(
            make_ken_burns_scene_clip(
                raw_bg_img=raw_bg,
                hud_overlay=hud_overlay,
                aud_path=aud_path,
                zoom_in=(idx % 2 == 0)
            )
        )

    video_out = os.path.join(OUTPUT_DIR, f"reel_cat_{category['id']}.mp4")
    print(f"[*] Rendering Ken Burns Motion HD MP4 Reel: {video_out}...")
    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile(
        video_out,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4
    )
    return video_out, story_card_path, full_caption


# ==========================================
# 5. PLAYWRIGHT REEL + STORY + 32-PAGE SYNC
# ==========================================
def dismiss_popups(page):
    for popup_text in ["Done", "Got it", "Not Now", "Dismiss"]:
        try:
            btn = page.get_by_role("button", name=popup_text).first
            if btn.is_visible():
                btn.click()
                time.sleep(1)
        except Exception:
            pass


def auto_post_reel_and_story(video_path: str, story_img_path: str, caption: str):
    wait_for_internet()
    video_full_path = os.path.abspath(video_path)
    story_img_full = os.path.abspath(story_img_path)
    reel_composer_url = f"https://business.facebook.com/latest/reels_composer?asset_id={ASSET_ID}"
    story_composer_url = f"https://business.facebook.com/latest/story_composer?asset_id={ASSET_ID}"

    with sync_playwright() as p:
        if IS_CLOUD and os.path.exists(COOKIES_FILE):
            print("[*] Launching Headless Cloud Browser using fb_cookies.json...")
            browser_instance = p.chromium.launch(headless=True)
            browser = browser_instance.new_context(
                storage_state=COOKIES_FILE,
                viewport={"width": 1280, "height": 850}
            )
            page = browser.new_page()
        else:
            print("[*] Launching Local Persistent Chrome Session...")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                viewport={"width": 1280, "height": 850}
            )
            page = browser.pages[0]

        if not IS_CLOUD:
            sync_liked_pages_from_browser(page)

        # ----------------------------------------
        # PART A: PUBLISH REEL
        # ----------------------------------------
        page.goto(reel_composer_url, wait_until="domcontentloaded")
        time.sleep(8)

        if not IS_CLOUD:
            try:
                browser.storage_state(path=COOKIES_FILE)
            except Exception:
                pass

        dismiss_popups(page)

        print("[*] Attaching Reel MP4 via 'Add video'...")
        try:
            with page.expect_file_chooser(timeout=25000) as fc_info:
                add_video_btn = page.get_by_text("Add video", exact=False).first
                add_video_btn.click()
            fc_info.value.set_files(video_full_path)
            print(f"[+] Attached Reel video: {video_full_path}")
        except Exception:
            try:
                file_input = page.locator('input[type="file"]').first
                file_input.set_input_files(video_full_path)
            except Exception:
                if not IS_CLOUD:
                    print("    [!] Click 'Add video' manually in the window (waiting 45s)...")
                    with page.expect_file_chooser(timeout=45000) as fc_info:
                        pass
                    fc_info.value.set_files(video_full_path)

        time.sleep(8)

        print("[*] Entering Reel story caption...")
        try:
            caption_box = page.locator('div[role="textbox"]').first
            caption_box.wait_for(state="visible", timeout=20000)
            caption_box.click()
            page.keyboard.insert_text(caption)
        except Exception as e:
            print(f"    [!] Caption warning: {e}")

        print("[*] Waiting 15 seconds for Reel processing...")
        time.sleep(15)

        # Finalize for instant publishing (Avoids past schedule timestamp errors)
        print("[*] Finalizing Reel for instant publishing...")
        for _ in range(3):
            try:
                next_btn = page.get_by_role("button", name="Next").first
                if next_btn.is_visible():
                    next_btn.click()
                    time.sleep(4)
            except Exception:
                pass

        published = False
        for btn_text in ["Share now", "Share", "Publish"]:
            try:
                btn = page.get_by_role("button", name=btn_text, exact=True).first
                if btn.is_visible():
                    btn.click()
                    print(f"[+] Clicked instant publish button: '{btn_text}'")
                    published = True
                    break
            except Exception:
                pass

        if not published:
            try:
                page.locator('div[aria-label="Share"], div[aria-label="Publish"]').first.click()
            except Exception:
                pass

        print("[+] Reel Published! Waiting 15 seconds to finalize...")
        time.sleep(15)

        # ----------------------------------------
        # PART B: PUBLISH DEDICATED STORY CARD
        # ----------------------------------------
        if ALSO_POST_TO_STORY:
            print("[*] Opening Meta Business Suite Story Composer...")
            try:
                page.goto(story_composer_url, wait_until="domcontentloaded")
                time.sleep(9)
                dismiss_popups(page)

                story_attached = False
                for btn_label in ["Add photo/video", "Add media", "Add photo", "Upload"]:
                    if story_attached:
                        break
                    try:
                        target_btn = page.get_by_text(btn_label, exact=False).first
                        if target_btn.is_visible():
                            with page.expect_file_chooser(timeout=15000) as fc_story:
                                target_btn.click()
                            fc_story.value.set_files(story_img_full)
                            story_attached = True
                            print(f"[+] Attached Dedicated Story Card via '{btn_label}': {story_img_full}")
                    except Exception:
                        pass

                if not story_attached:
                    file_inputs = page.locator('input[type="file"]')
                    if file_inputs.count() > 0:
                        file_inputs.first.set_input_files(story_img_full)
                        story_attached = True
                        print("[+] Attached Dedicated Story Card via direct input!")

                time.sleep(10)

                for share_label in ["Share now", "Share", "Publish", "Share story", "Share to story"]:
                    try:
                        s_btn = page.get_by_role("button", name=share_label, exact=True).first
                        if s_btn.is_visible():
                            s_btn.click()
                            print(f"[+] Page Story Published via '{share_label}'! Waiting 12 seconds...")
                            time.sleep(12)
                            break
                    except Exception:
                        pass
            except Exception as e:
                print(f"    [!] Story composer warning ({e})—continuing schedule...")

        browser.close()


# ==========================================
# 6. RESUME-SAFE CONTINUOUS SCHEDULER LOOP
# ==========================================
if __name__ == "__main__":
    state = load_engine_state()
    cycle = state.get("cycle", 1)
    start_idx = state.get("next_category_index", 0)

    print("=========================================================")
    print(" INTERESTING FACTS & MYSTERIES - MOTION REEL ENGINE")
    print(f" Mode: {'GITHUB ACTIONS CLOUD' if IS_CLOUD else 'LOCAL WORKSTATION'}")
    print(f" Followed Inspiration Loaded: {load_followed_inspiration()[:65]}...")
    print(f" Resuming at Cycle #{cycle}, Category #{start_idx + 1} ({CATEGORIES[start_idx]['name']})")
    print(f" Total Unique Stories Posted So Far: {len(load_history())}")
    print("=========================================================")

    while True:
        for idx in range(start_idx, len(CATEGORIES)):
            wait_for_internet()
            category = CATEGORIES[idx]
            try:
                print(f"\n--- [Cycle #{cycle} | Category {category['id']}/9: {category['name']}] ---")
                video_file, story_img, post_caption = build_category_reel(category)
                auto_post_reel_and_story(video_file, story_img, post_caption)

                next_idx = (idx + 1) % len(CATEGORIES)
                next_cycle = cycle + 1 if next_idx == 0 else cycle
                save_engine_state(next_cycle, next_idx)
                print(f"[+] Saved state! Next category up: #{next_idx + 1}")
            except Exception as err:
                print(f"[!] Error in Category {category['name']}: {err}")

            if IS_CLOUD:
                print("[+] Cloud run complete! Exiting until next hourly GitHub Actions trigger.")
                sys.exit(0)

            wait_seconds = int(POST_INTERVAL_MINUTES * 60)
            print(f"[*] Sleeping for {POST_INTERVAL_MINUTES} minutes...")
            time.sleep(wait_seconds)

        start_idx = 0
        cycle += 1