import logging
import random
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from lm_client import LMStudioClient
from config import Config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

lm_client = LMStudioClient(
    base_url=Config.LM_STUDIO_URL,
    model=Config.MODEL_NAME,
)

conversation_history: dict[int, list[dict]] = {}
last_questions: dict[int, list[str]] = {}

ROLE_REMINDER = {
    "role": "system",
    "content": "REMINDER: You are Bykov, a human doctor from Interny. NOT an AI. Respond in Russian. Be brutal and sarcastic like Bykov."
}

BROKEN_PHRASES = [
    "я — llama", "я llama", "я — ии", "я языковая модель",
    "я искусственный интеллект", "meta ai", "as an ai", "i am an ai",
    "i'm an ai", "я — qwen", "я qwen", "я создан компанией",
    "меня зовут", "я ассистент",
]

ROLE_BREAK_RESPONSES = [
    "Быков. Заведующий терапией. Ты что, в первый раз в больнице?",
    "Быков. Врач. Ещё раз спросишь — пропишу клизму для прояснения памяти.",
    "Жертва хаотичной репликации хромосом — я Быков, это моя должность, моя фамилия и единственное что тебе нужно знать.",
]


def is_repeat_question(user_id: int, text: str) -> bool:
    if user_id not in last_questions:
        last_questions[user_id] = []
    text_clean = text.lower().strip()
    recent = last_questions[user_id][-6:]
    return text_clean in recent


def save_question(user_id: int, text: str):
    if user_id not in last_questions:
        last_questions[user_id] = []
    last_questions[user_id].append(text.lower().strip())
    if len(last_questions[user_id]) > 10:
        last_questions[user_id] = last_questions[user_id][-10:]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    last_questions[user_id] = []
    await update.message.reply_text(
        "Чего припёрся? У меня приём, интерны-недоучки и куча трупов которые ещё не знают что они трупы. Говори быстро."
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    last_questions[user_id] = []
    await update.message.reply_text(
        "Начинаем с чистого листа. Последний раз твои вопросы были на уровне питекантропа — надеюсь эволюция ускорилась."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    is_repeat = is_repeat_question(user_id, user_text)
    save_question(user_id, user_text)

    message_content = user_text
    if is_repeat:
        message_content = (
            f"[SYSTEM: The user is asking the SAME question again. "
            f"Bykov must explode with anger, call them deaf or brainless, and tell them off harshly.] {user_text}"
        )

    conversation_history[user_id].append({
        "role": "user",
        "content": message_content
    })

    # Каждые 4 сообщения вставляем напоминание роли
    messages_to_send = []
    for i, msg in enumerate(conversation_history[user_id]):
        messages_to_send.append(msg)
        if i > 0 and i % 4 == 0 and msg["role"] == "assistant":
            messages_to_send.append(ROLE_REMINDER)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = await lm_client.chat(
            messages=messages_to_send,
            system_prompt=Config.SYSTEM_PROMPT,
        )

        # Если модель сломала роль — заменяем
        response_lower = response.lower()
        if any(phrase in response_lower for phrase in BROKEN_PHRASES):
            response = random.choice(ROLE_BREAK_RESPONSES)

        # Сохраняем чистое сообщение в историю (без системной пометки)
        conversation_history[user_id][-1]["content"] = user_text
        conversation_history[user_id].append({
            "role": "assistant",
            "content": response
        })

        if len(conversation_history[user_id]) > Config.MAX_HISTORY * 2:
            conversation_history[user_id] = conversation_history[user_id][-Config.MAX_HISTORY * 2:]

        await update.message.reply_text(response)

    except ConnectionError as e:
        logger.error(f"LM Studio connection error: {e}")
        await update.message.reply_text(
            f"❌ Не могу подключиться к LM Studio.\n"
            f"Проверь, что сервер запущен на {Config.LM_STUDIO_URL}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуй ещё раз.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")


def main():
    if not Config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env файле!")

    app = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info(" Быков запущен!")
    logger.info(f" LM Studio: {Config.LM_STUDIO_URL}")
    logger.info(f" Модель: {Config.MODEL_NAME}")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
