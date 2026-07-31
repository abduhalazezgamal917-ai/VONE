import os
import asyncio
import sqlite3
import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import edge_tts
from flask import Flask
from threading import Thread
from mutagen.mp3 import MP3

# ================= إعدادات السيرفر الوهمي =================
app = Flask(__name__)
@app.route('/')
def home():
    return "VONE Bot & Database are running perfectly! 🚀"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.start()
# =========================================================

# جلب المتغيرات
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ID") # الايدي الخاص بك الذي وضعته في ريندر لتعطيك صلاحيات لا نهائية
CHANNEL_USERNAME = "@ZenoX_Tools"
BOT_USERNAME = "VONE_BOT" # استبدله بيوزر البوت الفعلي بدون @

if not BOT_TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على التوكن.")

bot = telebot.TeleBot(BOT_TOKEN)

# ================= قاعدة البيانات =================
def init_db():
    conn = sqlite3.connect('vone_database.sqlite')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  free_seconds INTEGER DEFAULT 100, 
                  paid_seconds INTEGER DEFAULT 0, 
                  last_reset TEXT, 
                  voice TEXT DEFAULT 'ar-SA-HamedNeural')''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('vone_database.sqlite')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    today = datetime.date.today().isoformat()
    
    # إذا كان مستخدم جديد
    if row is None:
        c.execute("INSERT INTO users (user_id, last_reset) VALUES (?, ?)", (user_id, today))
        conn.commit()
        row = {'user_id': user_id, 'free_seconds': 100, 'paid_seconds': 0, 'last_reset': today, 'voice': 'ar-SA-HamedNeural'}
    
    # تجديد الثواني المجانية يومياً (100 ثانية)
    elif row['last_reset'] != today:
        c.execute("UPDATE users SET free_seconds = 100, last_reset = ? WHERE user_id = ?", (today, user_id))
        conn.commit()
        row = dict(row)
        row['free_seconds'] = 100
        row['last_reset'] = today
        
    conn.close()
    return dict(row)

def update_balance(user_id, free_used, paid_used):
    conn = sqlite3.connect('vone_database.sqlite')
    c = conn.cursor()
    c.execute("UPDATE users SET free_seconds = free_seconds - ?, paid_seconds = paid_seconds - ? WHERE user_id = ?", 
              (free_used, paid_used, user_id))
    conn.commit()
    conn.close()

def update_voice(user_id, voice_name):
    conn = sqlite3.connect('vone_database.sqlite')
    c = conn.cursor()
    c.execute("UPDATE users SET voice = ? WHERE user_id = ?", (voice_name, user_id))
    conn.commit()
    conn.close()

def add_paid_seconds(user_id, seconds):
    conn = sqlite3.connect('vone_database.sqlite')
    c = conn.cursor()
    c.execute("UPDATE users SET paid_seconds = paid_seconds + ? WHERE user_id = ?", (seconds, user_id))
    conn.commit()
    conn.close()
# =========================================================

# ================= الاشتراك الإجباري =================
def check_sub(user_id):
    try:
        if str(user_id) == str(ADMIN_ID): return True
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def sub_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 الاشتراك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
    markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub"))
    return markup
# =========================================================

# ================= القوائم والأزرار =================
def main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎙️ عرض الأصوات المتاحة", callback_data="voices_menu"),
        InlineKeyboardButton("⭐ شراء رصيد إضافي (بالنجوم)", callback_data="buy_menu"),
        InlineKeyboardButton("🎁 رصيدي و رابط الدعوة", callback_data="my_balance")
    )
    return markup

def voices_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    # أصوات مايكروسوفت العربية
    markup.add(
        InlineKeyboardButton("👨 حامد (سعودي - رسمي)", callback_data="setvoice_ar-SA-HamedNeural"),
        InlineKeyboardButton("👩 زارية (سعودية - هادئ)", callback_data="setvoice_ar-SA-ZariyahNeural"),
        InlineKeyboardButton("👨 حمدان (إماراتي - وثائقي)", callback_data="setvoice_ar-AE-HamdanNeural"),
        InlineKeyboardButton("👩 سلمى (مصري - حيوي)", callback_data="setvoice_ar-EG-SalmaNeural"),
        InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return markup

def buy_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("⭐ 50 نجمة (1000 ثانية)", callback_data="buy_1000"),
        InlineKeyboardButton("⭐ 100 نجمة (2500 ثانية)", callback_data="buy_2500"),
        InlineKeyboardButton("⭐ 250 نجمة (7500 ثانية)", callback_data="buy_7500"),
        InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return markup

# ================= أوامر البداية =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    text = message.text
    
    # نظام الإحالة (الدعوات)
    if " " in text:
        referrer_id = text.split(" ")[1]
        try:
            if int(referrer_id) != user_id:
                conn = sqlite3.connect('vone_database.sqlite')
                c = conn.cursor()
                # التأكد أن المستخدم جديد تماماً
                c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                if c.fetchone() is None:
                    # إضافة 50 ثانية مدفوعة للداعي مكافأة
                    c.execute("UPDATE users SET paid_seconds = paid_seconds + 50 WHERE user_id = ?", (int(referrer_id),))
                    conn.commit()
                    bot.send_message(int(referrer_id), f"🎉 مبروك! قام شخص بالدخول عبر رابطك، تمت إضافة 50 ثانية لرصيدك.")
                conn.close()
        except: pass

    get_user(user_id) # تهيئة المستخدم في القاعدة
    
    if not check_sub(user_id):
        bot.reply_to(message, f"عذراً عزيزي ✋\nعليك الاشتراك في القناة الرسمية للبوت أولاً لتتمكن من استخدامه.\n\nاشترك ثم اضغط تحقق:", reply_markup=sub_markup())
        return

    bot.reply_to(message, 
                 "مرحباً بك في **VONE** 🎙️\n\n"
                 "منصتك الذكية لتحويل النصوص إلى أصوات طبيعية نابضة بالحياة.\n"
                 "اختر من القائمة أدناه أو أرسل لي أي نص مباشرة لبدء التوليد!", 
                 reply_markup=main_menu_markup())

# ================= استجابة الأزرار (Callback) =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "check_sub":
        if check_sub(user_id):
            bot.edit_message_text("✅ شكراً لاشتراكك! يمكنك الآن استخدام البوت.\n\nأرسل /start لفتح القائمة الرئيسية.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ لم تقم بالاشتراك بعد!", show_alert=True)
            
    elif not check_sub(user_id):
        bot.answer_callback_query(call.id, "عليك الاشتراك في القناة أولاً!", show_alert=True)
        return

    elif data == "voices_menu":
        bot.edit_message_text("اختر الصوت الذي تفضله:", call.message.chat.id, call.message.message_id, reply_markup=voices_markup())
        
    elif data.startswith("setvoice_"):
        voice_id = data.split("_")[1]
        update_voice(user_id, voice_id)
        bot.answer_callback_query(call.id, "✅ تم تعيين الصوت بنجاح!", show_alert=True)
        bot.edit_message_text("مرحباً بك في **VONE** 🎙️\n\nأرسل نصك الآن:", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

    elif data == "buy_menu":
        bot.edit_message_text("اختر الباقة المناسبة لك (الدفع آمن ومباشر عبر نجوم تيليجرام):", call.message.chat.id, call.message.message_id, reply_markup=buy_markup())

    elif data == "back_main":
        bot.edit_message_text("مرحباً بك في **VONE** 🎙️\n\nاختر من القائمة أدناه:", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

    elif data == "my_balance":
        u = get_user(user_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        msg = (f"📊 **رصيدك الحالي:**\n\n"
               f"⏱️ الثواني المجانية (تتجدد يومياً): {u['free_seconds']} ثانية\n"
               f"💰 الثواني المشتراة (دائمة): {u['paid_seconds']} ثانية\n\n"
               f"🎁 **اربح المزيد:**\nشارك رابطك مع أصدقائك، وعلى كل مستخدم جديد يدخل عبر رابطك ستحصل على **50 ثانية دائمة** مجاناً!\n\n"
               f"🔗 رابطك:\n`{ref_link}`")
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup(), parse_mode="Markdown")

    # معالجة الشراء بالنجوم
    elif data.startswith("buy_"):
        amount = int(data.split("_")[1])
        prices_map = {1000: 50, 2500: 100, 7500: 250} # عدد الثواني: عدد النجوم
        stars = prices_map[amount]
        
        prices = [LabeledPrice(label=f"{amount} ثانية", amount=stars)]
        bot.send_invoice(
            call.message.chat.id,
            title="شراء رصيد VONE",
            description=f"باقة {amount} ثانية لتوليد الصوت.",
            invoice_payload=f"buy_{amount}",
            provider_token="", # يترك فارغاً لأن النجوم هي عملة تيليجرام الأصلية
            currency="XTR",
            prices=prices
        )

# تأكيد عملية الدفع
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# عند نجاح الدفع
@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    seconds_bought = int(payload.split("_")[1])
    add_paid_seconds(message.chat.id, seconds_bought)
    bot.reply_to(message, f"🎉 شكراً لك! تم استلام الدفع بنجاح. تمت إضافة {seconds_bought} ثانية لرصيدك الدائم.")

# ================= توليد الصوت (الذكاء) =================
async def generate_audio(text, output_file, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    
    if not check_sub(user_id):
        bot.reply_to(message, "عذراً، عليك الاشتراك في القناة أولاً.", reply_markup=sub_markup())
        return

    text = message.text
    u = get_user(user_id)
    total_balance = u['free_seconds'] + u['paid_seconds']
    
    # الإدمن (أنت) له رصيد لا نهائي ولا يخضع للقيود
    is_admin = str(user_id) == str(ADMIN_ID)
    
    if total_balance <= 0 and not is_admin:
        bot.reply_to(message, "❌ لقد نفد رصيدك من الثواني لهذا اليوم.\nيمكنك شراء المزيد من النجوم أو انتظار التجديد اليومي.", reply_markup=main_menu_markup())
        return

    processing_msg = bot.reply_to(message, "⏳ جاري تحليل النص وتوليد الصوت...")
    audio_file = f"vone_{user_id}_{message.message_id}.mp3"
    
    try:
        # التوليد
        asyncio.run(generate_audio(text, audio_file, u['voice']))
        
        # حساب مدة الصوت الفعلي بالثواني بدقة
        audio_meta = MP3(audio_file)
        duration = int(audio_meta.info.length)
        if duration == 0: duration = 1 # حد أدنى
        
        if duration > total_balance and not is_admin:
            os.remove(audio_file)
            bot.edit_message_text(f"❌ النص طويل جداً! سيستغرق {duration} ثانية، بينما رصيدك الكلي {total_balance} ثانية فقط.", message.chat.id, processing_msg.message_id)
            return

        # الخصم الذكي (يخصم من المجاني أولاً، ثم المدفوع)
        free_used = 0
        paid_used = 0
        
        if not is_admin:
            if u['free_seconds'] >= duration:
                free_used = duration
            else:
                free_used = u['free_seconds']
                paid_used = duration - free_used
            
            update_balance(user_id, free_used, paid_used)
            u = get_user(user_id) # تحديث البيانات بعد الخصم
        
        rem_total = (u['free_seconds'] + u['paid_seconds']) if not is_admin else "∞ (أنت الأدمن 👑)"
        
        caption_text = (f"✨ تم التوليد بنجاح!\n"
                        f"⏱️ مدة المقطع: {duration} ثانية\n"
                        f"📊 المتبقي من رصيدك: {rem_total} ثانية\n\n"
                        f"🤖 صُنع بواسطة: @{BOT_USERNAME}")

        with open(audio_file, 'rb') as audio:
            bot.send_voice(message.chat.id, audio, caption=caption_text, reply_to_message_id=message.message_id)
            
        os.remove(audio_file)
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ عذراً، حدث خطأ: {str(e)}", message.chat.id, processing_msg.message_id)
        if os.path.exists(audio_file):
            os.remove(audio_file)

if __name__ == '__main__':
    init_db()
    keep_alive()
    print("🚀 البوت وقاعدة البيانات يعملان بنجاح...")
    bot.infinity_polling()


