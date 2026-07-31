import os
import asyncio
import telebot
import edge_tts
from flask import Flask
from threading import Thread

# --- إعدادات السيرفر الوهمي (لخداع ريندر وإبقاء البوت يعمل) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "VONE Bot is running perfectly! 🚀"

def run_server():
    # ريندر يحدد المنفذ تلقائياً عبر متغير PORT، وإلا سيستخدم 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.start()
# -------------------------------------------------------------

# جلب التوكن من متغيرات البيئة في ريندر
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على BOT_TOKEN.")

bot = telebot.TeleBot(BOT_TOKEN)
VOICE_NAME = "ar-SA-HamedNeural"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "مرحباً بك في **VONE** 🎙️\n\n"
                 "المنصة الأولى لتحويل النصوص إلى أصوات طبيعية.\n"
                 "أرسل لي أي نص الآن وسأحوله لك فوراً!")

async def generate_audio(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    await communicate.save(output_file)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    chat_id = message.chat.id
    message_id = message.message_id
    
    processing_msg = bot.reply_to(message, "⏳ جاري التوليد، لحظات...")
    audio_file = f"vone_{chat_id}_{message_id}.mp3"
    
    try:
        asyncio.run(generate_audio(text, audio_file))
        
        with open(audio_file, 'rb') as audio:
            bot.send_voice(
                chat_id, 
                audio, 
                caption="✨ تم التوليد بواسطة **VONE**",
                reply_to_message_id=message_id
            )
            
        os.remove(audio_file)
        bot.delete_message(chat_id, processing_msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ عذراً، حدث خطأ أثناء المعالجة: {str(e)}", chat_id, processing_msg.message_id)

if __name__ == '__main__':
    # تشغيل السيرفر الوهمي أولاً
    keep_alive()
    
    print("🚀 البوت يعمل الآن بنجاح ومستعد لاستقبال الرسائل...")
    # تشغيل البوت
    bot.infinity_polling()


