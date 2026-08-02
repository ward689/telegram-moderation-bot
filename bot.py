import asyncio
import re
import json
import os
import time
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

TOKEN = "8430168047:AAG0ZnQkWmVGNIsSx-qaPYQbieSwc41nnao"
GEMINI_API_KEY = "AQ.Ab8RN6LmyqpA9V_Kky3m-Zj71j-OW2Bb1AbmUI19utcy9nKohA"

OWNER_ID = "7823802800"
ADMINS_FILE = "admins.json"
WARNS_FILE = "warns.json"
MUTED_FILE = "muted.json"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"temperature": 0.0, "top_p": 0.9},
    system_instruction="""
Ты — модератор чата. Отвечай ТОЛЬКО JSON.

ПРАВИЛА:
1. НЕ СЧИТАЙ буллингом обычный мат: сука, бля, блять, блядь, хуй, хер, пизда, ебать, иди нахуй, пошёл нахуй, нахуй.
2. СЧИТАЙ буллингом ТОЛЬКО ЭТО:
   - Личные оскорбления: ты бесполезен, ты никчёмный, ты ничтожество, ты тупой, ты дебил (как личное оскорбление)
   - Угрозы: сдохни, умри, убейся, я тебя убью, ты покойник
   - Унижения: тварь, шлюха, сукин сын (как личное оскорбление)

Формат ответа:
{"is_bullying": true/false, "reason": "причина"}
"""
)

def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

admins = load_json(ADMINS_FILE)
if OWNER_ID not in admins:
    admins[OWNER_ID] = 7
    save_json(ADMINS_FILE, admins)

warns = load_json(WARNS_FILE)
muted = load_json(MUTED_FILE)

def clean_muted():
    now = time.time()
    for user, until in list(muted.items()):
        if now > until:
            del muted[user]
    save_json(MUTED_FILE, muted)

LEVEL_RIGHTS = {
    1: "🔹 Удалять сообщения\n🔹 Следить за чатом",
    2: "🔹 Удалять сообщения\n🔹 Выдавать предупреждения",
    3: "🔹 Удалять сообщения\n🔹 Выдавать предупреждения\n🔹 Мутить",
    4: "🔹 Удалять сообщения\n🔹 Выдавать предупреждения\n🔹 Мутить\n🔹 Размучивать",
    5: "🔹 Удалять сообщения\n🔹 Выдавать предупреждения\n🔹 Мутить\n🔹 Размучивать\n🔹 Кикать",
    6: "🔹 Удалять сообщения\n🔹 Выдавать предупреждения\n🔹 Мутить\n🔹 Размучивать\n🔹 Кикать\n🔹 Банить",
    7: "🔹 Удалять сообщения\n🔹 Выдавать предупреждения\n🔹 Мутить\n🔹 Размучивать\n🔹 Кикать\n🔹 Банить\n🔹 Назначать/снимать админов"
}

LEVEL_NAMES = {
    1: "🟢 Младший модератор",
    2: "🟢 Модератор",
    3: "🟡 Старший модератор",
    4: "🟡 Заместитель",
    5: "🟠 Старший администратор",
    6: "🔴 Заместитель владельца",
    7: "👑 Владелец"
}

# ========== ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ ==========
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
        
        welcome_text = (
            f"👋 Добро пожаловать, {member.first_name}!\n\n"
            f"Этот чат модерируется ботом с ИИ.\n"
            f"Пожалуйста, ознакомься с правилами сообщества."
        )
        
        keyboard = [
            [InlineKeyboardButton("📜 Правила сообщества", url="https://telegra.ph/Pravila-soobshchestva-03-13-6")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "Пользователь"
    text = (
        f"👋 Привет, {first_name}!\n\n"
        f"🔹 Отличаю буллинг от обычного мата\n"
        f"🔹 Выдаю предупреждения за буллинг\n"
        f"🔹 Автоматически мучу за 3 варна\n"
        f"🔹 Есть система администраторов (уровни 1–7)\n\n"
        f"📌 Для админов: /giveadmin, /removeadmin, /admins"
    )
    await update.message.reply_text(text)

async def give_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if admins.get(user_id, 0) < 7:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ /giveadmin @user 7")
        return
    target = None
    level = None
    for arg in context.args:
        if arg.startswith("@"):
            target = arg.replace("@", "")
        elif arg.isdigit():
            level = int(arg)
    if not target:
        target = context.args[0].replace("@", "")
    if level is None and len(context.args) > 1:
        try:
            level = int(context.args[1])
        except:
            pass
    if not target:
        await update.message.reply_text("❌ Не найден username.")
        return
    if level is None:
        await update.message.reply_text("❌ Не найден уровень.")
        return
    if level < 1 or level > 7:
        await update.message.reply_text("❌ Уровень 1-7.")
        return
    admins[target] = level
    save_json(ADMINS_FILE, admins)
    level_name = LEVEL_NAMES.get(level, f"Уровень {level}")
    await update.message.reply_text(f"✅ @{target} назначен администратором уровня {level} — {level_name}.")
    
    if level >= 5:
        keyboard = [[InlineKeyboardButton("📋 Мои права", callback_data=f"rights|{target}|{level}")]]
        await update.message.reply_text(
            f"🎉 @{target}, вы назначены администратором уровня {level}!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if admins.get(user_id, 0) < 7:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    if not context.args:
        await update.message.reply_text("❌ /removeadmin @user")
        return
    target = context.args[0].replace("@", "")
    if target in admins:
        del admins[target]
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text(f"✅ @{target} снят с админки.")
    else:
        await update.message.reply_text(f"❌ @{target} не админ.")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admins:
        await update.message.reply_text("📋 Список пуст.")
        return
    text = "📋 Список администраторов:\n"
    for user, level in admins.items():
        level_name = LEVEL_NAMES.get(level, f"Уровень {level}")
        text += f"  @{user} — {level_name}\n"
    await update.message.reply_text(text)

async def show_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|")
    if len(data) < 3:
        await query.answer("❌ Ошибка.", show_alert=True)
        return
    
    target_username = data[1]
    level = int(data[2])
    user_id = str(query.from_user.id)
    
    if user_id != target_username and user_id != OWNER_ID:
        await query.answer("⛔ Это не ваша кнопка!", show_alert=True)
        return
    
    level_name = LEVEL_NAMES.get(level, f"Уровень {level}")
    rights = LEVEL_RIGHTS.get(level, "Права не определены")
    
    short_alert = f"📋 {level_name}\n{rights[:100]}"
    await query.answer(short_alert, show_alert=True)
    
    full_text = (
        f"📋 ВАША ДОЛЖНОСТЬ: {level_name}\n\n"
        f"🔹 Ваши права:\n{rights}\n\n"
        f"⚙️ КАКИЕ ПРАВА ВЫДАТЬ В TELEGRAM:\n"
        f"{rights}"
    )
    await query.message.reply_text(full_text)

async def check_with_gemini(text):
    try:
        prompt = f"Сообщение: {text}"
        response = model.generate_content(prompt)
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_str:
            return json.loads(json_str.group())
        return {"is_bullying": False}
    except Exception as e:
        print(f"[GEMINI ОШИБКА] {e}")
        return {"is_bullying": False}

async def mute_user(chat_id, user_id, duration_minutes, reason="буллинг"):
    until = time.time() + duration_minutes * 60
    muted[str(user_id)] = until
    save_json(MUTED_FILE, muted)
    try:
        await app.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions={"can_send_messages": False},
            until_date=until
        )
        await app.bot.send_message(chat_id, f"🔇 @{user_id} замучен на {duration_minutes} минут. Причина: {reason}")
        print(f"[МУТ] {user_id} на {duration_minutes} мин ({reason})")
    except Exception as e:
        print(f"Ошибка мута: {e}")

async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)

    if user_id in admins:
        return
    clean_muted()
    if user_id in muted:
        await update.message.delete()
        return

    text = update.message.text.lower()
    result = await check_with_gemini(text)
    if result.get("is_bullying"):
        try:
            await update.message.delete()
            print(f"[УДАЛЕНО] {update.message.text} (причина: {result.get('reason', 'неизвестна')})")
            warns[user_id] = warns.get(user_id, 0) + 1
            save_json(WARNS_FILE, warns)
            count = warns[user_id]
            await update.message.reply_text(
                f"⚠️ ВАРН {count}/3 за буллинг!\n"
                f"Сообщение: {update.message.text}\n"
                f"Причина: {result.get('reason', 'неизвестна')}"
            )
            if count >= 3:
                await mute_user(chat_id, int(user_id), 30, "3 варна за буллинг")
                warns[user_id] = 0
                save_json(WARNS_FILE, warns)
        except Exception as e:
            print(f"Ошибка: {e}")

async def send_owner_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != OWNER_ID:
        return
    keyboard = [[InlineKeyboardButton("📋 Мои права", callback_data=f"rights|{OWNER_ID}|7")]]
    await update.message.reply_text(
        f"👑 Привет, Владелец!\nТы автоматически назначен администратором уровня 7.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    global app
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("giveadmin", give_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("admins", list_admins))

    app.add_handler(CallbackQueryHandler(show_rights, pattern="^rights\\|"))

    # ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(OWNER_ID), send_owner_welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))

    print("Бот запущен. Ожидание сообщений...")
    app.run_polling()

if __name__ == "__main__":
    main()