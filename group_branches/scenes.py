from telegram import Update
from telegram.ext import ConversationHandler, CommandHandler, ContextTypes, MessageHandler, filters, BaseHandler

import datetime
import re

from group_branches import utils


def add_prompt_scene():
    NAME, PROMPT = range(2)

    async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_to_answer = "Provide me with a name for your system prompt. Example: 'Programmer prompt' or 'Psychologist prompt'"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_to_answer)
        return NAME

    async def add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
        title = update.message.text
        context.user_data['temp_prompt'] = {
            'title': title
        }

        message_to_answer = "Provide me with the full content of your priming prompt."
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=message_to_answer)
        return PROMPT

    async def confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
        prompt = update.message.text
        title = context.user_data['temp_prompt']['title']

        # delete temp_prompt from user_data
        del context.user_data['temp_prompt']

        message_to_answer = "Your prompt has been added to the database."

        # todo add to database
        user_id = update.effective_user.id

        utils.store_user_prompt(user_id, title, prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=message_to_answer)
        return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        print('cancelling ')

        await context.bot.send_message(chat_id=update.effective_chat.id, text="Prompt addition cancelled.")

    return ConversationHandler(
        entry_points=[CommandHandler('add_prompt', add_title)],
        states={
            NAME: [MessageHandler(filters.TEXT & (~ filters.COMMAND), add_prompt)],
            PROMPT: [MessageHandler(filters.TEXT & (~ filters.COMMAND), confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

