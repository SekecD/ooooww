import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from cfg import QUEUE_IN, QUEUE_OUT


async def mail_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    context.user_data[chat_id]['work'] = "mail"
    context.user_data[chat_id]['subwork'] = "email_add"
    context.user_data[chat_id]['email'] = None
    context.user_data[chat_id]['password'] = None
    context.user_data[chat_id]['imap'] = None

    await context.bot.send_message(chat_id=chat_id, text="Введите почту:")


async def email_add(update: Update, context: ContextTypes.DEFAULT_TYPE, email):
    chat_id = update.effective_chat.id

    context.user_data[chat_id]['email'] = email
    context.user_data[chat_id]['subwork'] = "password_add"

    await context.bot.send_message(chat_id=chat_id, text="Введите пароль от почты:")


async def password_add(update: Update, context: ContextTypes.DEFAULT_TYPE, password):
    chat_id = update.effective_chat.id

    context.user_data[chat_id]['password'] = password
    context.user_data[chat_id]['subwork'] = "imap_add"

    await context.bot.send_message(chat_id=chat_id, text="Введите imap:")


async def imap_add(update: Update, context: ContextTypes.DEFAULT_TYPE, imap):
    chat_id = update.effective_chat.id

    context.user_data[chat_id]['imap'] = imap
    context.user_data[chat_id]['subwork'] = None

    return await mail_add_complete(update, context)


async def mail_add_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    QUEUE_IN.put(
        {
            "type": "append",
            "chat_id": chat_id,
            "kwargs": {
                "email": context.user_data[chat_id]['email'],
                "password": context.user_data[chat_id]['password'],
                "imap": context.user_data[chat_id]['imap']
            }
        }
    )

    context.user_data[chat_id]['work'] = None
    context.user_data[chat_id]['subwork'] = None
    context.user_data[chat_id]['email'] = None
    context.user_data[chat_id]['password'] = None
    context.user_data[chat_id]['imap'] = None

    await context.bot.send_message(chat_id=chat_id, text="Почта успешно добавлена!")


async def mail_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    context.user_data[chat_id]['work'] = "mail"
    context.user_data[chat_id]['subwork'] = "remove"

    QUEUE_IN.put({
        "type": "info",
        "chat_id": chat_id,
    })

    raw_info = None

    for _ in range(500):  # TODO ne bezopasno!
        if QUEUE_OUT.empty():
            await asyncio.sleep(0.01)
            continue

        raw_info = QUEUE_OUT.get()
        break

    if raw_info is None:
        context.user_data[chat_id]['work'] = None
        context.user_data[chat_id]['subwork'] = None
        return await context.bot.send_message(chat_id=chat_id, text="Ошибка получения списка почт!")

    if len(raw_info) == 0:
        context.user_data[chat_id]['work'] = None
        context.user_data[chat_id]['subwork'] = None
        await context.bot.send_message(chat_id=chat_id, text="Список пуст!")
    else:
        keyboard = [[InlineKeyboardButton(r['email'], callback_data=f"remove_{r['email']}")] for r in raw_info]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=chat_id, text="Выберите почту, которую хотите удалить:", reply_markup=reply_markup)


async def mail_remove_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, email):
    chat_id = update.effective_chat.id

    context.user_data[chat_id]['work'] = None
    context.user_data[chat_id]['subwork'] = None

    QUEUE_IN.put({
        "type": "remove",
        "chat_id": chat_id,
        "email": email
    })

    await context.bot.send_message(chat_id=chat_id, text="Почта успешно удалена!")


async def mail_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    QUEUE_IN.put({
        "type": "info",
        "chat_id": chat_id,
    })

    raw_info = None

    for _ in range(500):  # TODO ne bezopasno!
        if QUEUE_OUT.empty():
            await asyncio.sleep(0.01)
            continue

        raw_info = QUEUE_OUT.get()
        break

    info = ""

    if raw_info is None:
        return await context.bot.send_message(chat_id=chat_id, text="Ошибка получения списка почт!")

    for i in raw_info:
        info += f"email: {i['email']}; password: {i['password']}; imap: {i['imap']}\n"

    if info == "":
        await context.bot.send_message(chat_id=chat_id, text="Список пуст!")
    else:
        await context.bot.send_message(chat_id=chat_id, text=info)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id

    subwork = context.user_data[chat_id].get('subwork')

    if subwork is not None:
        if subwork == "email_add":
            return await email_add(update, context, user_message)
        elif subwork == "password_add":
            return await password_add(update, context, user_message)
        elif subwork == "imap_add":
            return await imap_add(update, context, user_message)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data.startswith("remove"):
        return await mail_remove_complete(update, context, query.data.replace("remove_", "", 1))
