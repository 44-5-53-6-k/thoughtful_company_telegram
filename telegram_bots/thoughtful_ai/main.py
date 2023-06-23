import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from langchain.callbacks import get_openai_callback
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, \
    ApplicationHandlerStop, TypeHandler, CallbackQueryHandler
from telegram.constants import ChatAction


import uuid
import yaml
import os

from dotenv import load_dotenv
load_dotenv()


#load config yml. it is in the same folder as this file
with open('config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

from telegram_bots import tg_utils, db_utils, chat_handlers, telethon_helper
import handlers


USERS_WITH_ACCESS = telethon_helper.fetch_user_ids('main_session', 1789045052)

def get_system_message(path):
    # Split path by "/"
    path_parts = path.split('/')

    messages_data = None
    with open('system_messages/messages-en.json', 'r') as messages_file:
        messages_data = yaml.safe_load(messages_file)

    # Traverse through the dictionary
    data = messages_data
    for part in path_parts:
        data = data.get(part)

        # If at any point data is None, that means the path doesn't exist
        # So we return a default message or handle it in another way
        if data is None:
            return 'Path does not exist'

    # If we made it through the path without data being None, we return the found message
    return data



async def bot(application):
    # Initialize application
    await application.initialize()

    is_data_loaded = await tg_utils.load_data(application)
    if is_data_loaded is False:
        print("Data is not loaded. Exiting.")
        return
    else:
        print("Data is loaded.")

    # Register all handlers
    auth_handler = TypeHandler(Update, handlers.authorization_user)
    application.add_handler(auth_handler, -1)

    start_handler = CommandHandler('start', handlers.start)
    application.add_handler(start_handler)

    new_chat_handler = CommandHandler('new_chat', handlers.new_chat)
    application.add_handler(new_chat_handler)

    choose_prompt_handler = CommandHandler('choose_prompt', tg_utils.choose_predef_prompt)
    application.add_handler(choose_prompt_handler)

    application.add_handler(CallbackQueryHandler(handlers.prompt_handler, 'prompt_'))

    chat_handler = MessageHandler(filters.TEXT, handlers.new_message_router)
    application.add_handler(chat_handler)

    # Start the bot
    await application.start()
    await application.updater.start_polling()

    # Keep the program running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Stop the bot
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


# Define an async function for our scheduler
async def scheduler_tasks(scheduler):

    # Schedule the reset functions to run at appropriate times
    scheduler.add_job(db_utils.reset_daily_usage, 'cron', day_of_week='0-6', hour=0, minute=0)
    scheduler.add_job(db_utils.reset_weekly_usage, 'cron', day_of_week='0', hour=0, minute=0)
    scheduler.start()

    # Keep the program running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Shutdown the scheduler
        scheduler.shutdown()


# Define the main function
def main():
    # Create the bot application and the scheduler
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    scheduler = AsyncIOScheduler()

    # Run the bot and scheduler
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.gather(bot(application), scheduler_tasks(scheduler)))
    finally:
        loop.close()


# Main function
if __name__ == '__main__':
    main()