import os
import asyncio
import telebot
import edge_tts

# جلب التوكن من متغيرات البيئة في ريندر (لن يكون مكشوفاً في الكود)
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# التأكد من وجود التوكن لتفادي الأخطاء عند التشغيل
if not BOT_TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على BOT_TOKEN. تأكد من إضافته في إعدادات Environment Variables في ريندر.")

bot = telebot.TeleBot(BOT_TOKEN)

# تحديد الصوت الافتراضي (صوت 'حامد' من مايكروسوفت - ذكاء اصطناعي طبيعي وواضح)
VOICE_NAME = "ar-SA-HamedNeural"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "مرحباً بك في **VONE** 🎙️\n\n"
                 "المنصة الأولى لتحويل النصوص إلى أصوات طبيعية.\n"
                 "أرسل لي أي نص الآن وسأحوله لك فوراً!")

# دالة توليد الصوت (غير متزامنة)
async def generate_audio(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    await communicate.save(output_file)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    chat_id = message.chat.id
    message_id = message.message_id
    
    # إرسال رسالة للمستخدم لمعرفة أن البوت يستجيب
    processing_msg = bot.reply_to(message, "⏳ جاري التوليد، لحظات...")
    
    # إنشاء اسم ملف فريد لكل عملية لتجنب تداخل الملفات إذا استخدم البوت أكثر من شخص في نفس اللحظة
    audio_file = f"vone_{chat_id}_{message_id}.mp3"
    
    try:
        # تشغيل دالة توليد الصوت
        asyncio.run(generate_audio(text, audio_file))
        
        # قراءة الملف الصوتي وإرساله
        with open(audio_file, 'rb') as audio:
            bot.send_voice(
                chat_id, 
                audio, 
                caption="✨ تم التوليد بواسطة **VONE**",
                reply_to_message_id=message_id
            )
            
        # التنظيف: حذف الملف من سيرفر ريندر وحذف رسالة الانتظار
        os.remove(audio_file)
        bot.delete_message(chat_id, processing_msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ عذراً، حدث خطأ أثناء المعالجة: {str(e)}", chat_id, processing_msg.message_id)

if __name__ == '__main__':
    print("🚀 البوت يعمل الآن بنجاح ومستعد لاستقبال الرسائل...")
    bot.infinity_polling()

