import telebot
from telebot import types
import yt_dlp
import os
import html
import time
import json
import random
import google.generativeai as genai
from dotenv import load_dotenv
from pptx import Presentation
from docx import Document
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

# Xabarlarni darhol chiqarish uchun funksiya (Hugging Face Logs uchun)
def log(msg):
    print(msg, flush=True)

# ==========================================
# HEALTH CHECK SERVER (Hugging Face uchun)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online and healthy!")

def run_health_check():
    try:
        # Hugging Face 7860-portni talab qiladi
        server = HTTPServer(('0.0.0.0', 7860), HealthCheckHandler)
        log("✅ Health check server 7860-portda ishga tushdi")
        server.serve_forever()
    except Exception as e:
        log(f"❌ Serverda xato: {e}")

# Serverni birinchi bo'lib alohida oqimda ishga tushiramiz
threading.Thread(target=run_health_check, daemon=True).start()

# ==========================================
# INTERNETNI KUTISH (Cloud hosting uchun)
# ==========================================
def wait_for_internet():
    log("⏳ Internet va DNS bog'lanishi kutilmoqda...")
    while True:
        try:
            socket.gethostbyname("api.telegram.org")
            log("🌐 Internet va DNS bog'landi!")
            return
        except Exception:
            time.sleep(5)

wait_for_internet()

# .env faylini script joylashgan joydan yuklashga harakat qiladi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# ==========================================
# SOZLAMALAR (Environment Variables)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

# Xatolikni tekshirish
if not BOT_TOKEN:
    log("❌ Xato: BOT_TOKEN topilmadi! Server 'Secrets' bo'limini tekshiring.")
if not GEMINI_API_KEY:
    log("⚠️ Ogohlantirish: GEMINI_API_KEY topilmadi!")

# Gemini AI sozlash
genai.configure(api_key=GEMINI_API_KEY)

AVAILABLE_MODELS = []
CURRENT_MODEL_INDEX = 0

def get_available_models_list():
    global AVAILABLE_MODELS
    try:
        log("🔍 Mavjud modellarni tekshirish...")
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        targets = [
            'gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-pro'
        ]
        
        found_models = []
        for target in targets:
            match = [m for m in all_models if target in m]
            if match: found_models.append(match[0])
        
        if not found_models: found_models = all_models
        AVAILABLE_MODELS = found_models
        log(f"✅ Tanlangan modellar: {AVAILABLE_MODELS}")
        return found_models
    except Exception as e:
        log(f"❌ Modellarda xato: {e}")
        AVAILABLE_MODELS = ['models/gemini-1.5-flash']
        return AVAILABLE_MODELS

SYS_INSTR = (
    "Sizning ismingiz Toparchik AI. Sizni 'Vibe Coder' (Hacker) yaratgan. "
    "Siz aqlli va do'stona yordamchisiz."
)

def get_current_model():
    global CURRENT_MODEL_INDEX
    if not AVAILABLE_MODELS: get_available_models_list()
    idx = CURRENT_MODEL_INDEX % len(AVAILABLE_MODELS)
    return genai.GenerativeModel(AVAILABLE_MODELS[idx], system_instruction=SYS_INSTR)

get_available_models_list()

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# DOIMIY XOTIRA (PERSISTENCE)
# ==========================================
SEARCH_DATA_FILE = os.path.join(BASE_DIR, "user_searches.json")

def load_user_searches():
    if os.path.exists(SEARCH_DATA_FILE):
        try:
            with open(SEARCH_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except: return {}
    return {}

def save_user_searches():
    try:
        with open(SEARCH_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_searches, f, ensure_ascii=False, indent=4)
    except: pass

user_searches = load_user_searches()
user_states = {}
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ------------------------------------------
# YORDAMCHI FUNKSIYALAR
# ------------------------------------------
def format_duration(seconds):
    try:
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"
    except: return "0:00"

def retry_gemini(func):
    def wrapper(*args, **kwargs):
        global CURRENT_MODEL_INDEX
        for i in range(5):
            try:
                get_current_model()
                return func(*args, **kwargs)
            except Exception as e:
                if "429" in str(e).lower():
                    CURRENT_MODEL_INDEX += 1
                    time.sleep(2)
                    continue
                break
        return "😔 Bo'sh model topilmadi."
    return wrapper

@retry_gemini
def ask_gemini(query):
    m = get_current_model()
    response = m.generate_content(query)
    return response.text + "\n\n🌟 @toparchik_bot"

@retry_gemini
def generate_presentation(topic):
    prompt = f"Mavzu: {topic}. 8 ta slaydli JSON qaytaring: [{{\"title\": \"...\", \"content\": \"...\"}}]"
    m = get_current_model()
    res = m.generate_content(prompt)
    text = res.text.strip()
    # JSON Parsing...
    # (Bu qismlar boyagi kodingizda bor edi, soddalashtirib ko'rsatyapman)
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = topic
    path = os.path.join(DOWNLOAD_DIR, f"pptx_{int(time.time())}.pptx")
    prs.save(path)
    return path

def download_audio(video_id, chat_id):
    path_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_{video_id}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': path_template,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
        return f"{path_template}.mp3", info

# ... (Menu, Nav va boshqa handlerlar kodingizdagidek qoladi)

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎵 Musiqa qidirish", "🤖 AI Savol-javob")
    markup.add("📊 Prezentatsiya yaratish", "🏠 Asosiy menyu")
    return markup

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Toparchik AI botga xush kelibsiz!", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def text_handle(m):
    t = m.text
    if t == "🎵 Musiqa qidirish":
        user_states[m.chat.id] = 'music'
        bot.send_message(m.chat.id, "Musiqa nomini yozing:")
    elif user_states.get(m.chat.id) == 'music':
        # Qidiruv...
        bot.send_message(m.chat.id, f"'{t}' qidirilmoqda...")

if __name__ == "__main__":
    log("🤖 Bot polling rejimida ishga tushdi!")
    while True:
        try:
            bot.infinity_polling(timeout=90, long_polling_timeout=40)
        except Exception as e:
            log(f"⚠️ Polling'da xato: {e}")
            time.sleep(10)