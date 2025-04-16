from multiprocessing import Process
from typing import Union

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

import cfg
from cfg import QUEUE_OUT, QUEUE_IN
from listener import MailListener
from mail_handle import mail_add, mail_remove, mail_info
from mail_handle import message_handler as mail_message_handler
from mail_handle import button_handler as mail_button_handler

application: Union[Application, None] = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="Запускаюсь...")

    QUEUE_IN.put({"type": "new", "chat_id": chat_id})

    context.user_data[chat_id] = {}

    keyboard = [
        [KeyboardButton("Добавить почту")],
        [KeyboardButton("Удалить почту")],
        [KeyboardButton("Мои почты")]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await context.bot.send_message(chat_id=chat_id, text="Привет! Добавь почту, чтобы начать!", reply_markup=reply_markup)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    QUEUE_IN.put({"type": "append", "chat_id": chat_id})


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    QUEUE_IN.put({"type": "remove", "chat_id": chat_id, "email": "pussy.kek@yandex.ru"})


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id

    if user_message == "Добавить почту":
        return await mail_add(update, context)
    elif user_message == "Удалить почту":
        return await mail_remove(update, context)
    elif user_message == "Мои почты":
        return await mail_info(update, context)

    work = context.user_data[chat_id].get("work")
    if work is not None:
        if work == "mail":
            return await mail_message_handler(update, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    work = context.user_data[chat_id].get('work')

    if work is not None:
        if work == "mail":
            return await mail_button_handler(update, context)


MAILLISTENER = MailListener(queue_in=QUEUE_IN, queue_out=QUEUE_OUT, token=cfg.TOKEN)


PROCESS = Process(target=MAILLISTENER.listen)


def main():
    global application
    global PROCESS
    application = Application.builder().token(cfg.TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    PROCESS.start()
    application.run_polling()
    PROCESS.join()


if __name__ == '__main__':
    main()
