import logging

from bson import ObjectId
from pymongo import MongoClient
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from datetime import datetime

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, BaseMessage, SystemMessage, LLMResult
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import yaml
import os

I = 10 + "ss"

# Load the YAML file
with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["OPENAI_API_KEY"] = config_data['openai_api_key']
os.environ["TELEGRAM_BOT_TOKEN"] = config_data['telegram_token']
os.environ["MONGO_DB"] = config_data['mongo_margulan_db_url']

import dialogues
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Connect to MongoDB
client = MongoClient(os.getenv("MONGO_DB"))
db = client['thoughtful_company']
user_habits = db['user_habits']
users = db['users']

chat_openai = ChatOpenAI()
prompt = PromptTemplate(
    input_variables=['habit_name'],
    template="I want to {habit_name}.",
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()



async def send_reminder(user):
    return

async def fetch_users_and_habits_to_notify():
    current_time = datetime.utcnow().strftime('%H:%M')

    # Get all users
    all_users = users.find()

    users_and_habits_to_notify = []

    # For each user, check if there's a reminder with time equal to current time and status "active"
    for user in all_users:
        for reminder in user['reminders']:
            if reminder['time'] == current_time and reminder['status'] == "active":
                # Find the habit associated with this user
                habit = user_habits.find_one({'_id': user['habit_id']})
                users_and_habits_to_notify.append((user, habit))
                break

    return users_and_habits_to_notify



# Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('start handler')
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your habit tracker bot.")

    # set commands for the bot
    await context.bot.set_my_commands([
        ('/start', 'Start the bot'),
        ('/add_habit', 'Add a new habit'),
        ('/list_habits', 'List all habits'),
    ])

def mark_habit_complete(habit_id, completion_time=datetime.utcnow()):
    user_habits.update_one(
        {'_id': ObjectId(habit_id)},
        {'$push': {'completions': completion_time}}
    )

async def edit_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_data = update.callback_query.data
    habit_id = callback_data.split('_')[1]

    # get habit data
    habit_doc = user_habits.find_one({'_id': ObjectId(habit_id)})

    name = habit_doc['habit']


async def list_habits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    habit_docs = list(user_habits.find({'user_id': chat_id}))

    habits = [doc['habit'] for doc in habit_docs]
    habit_ids = [str(doc['_id']) for doc in habit_docs]

    if habits:
        keyboard = [[InlineKeyboardButton(habit, callback_data=f"edit_{habit_id}")]
                    for habit, habit_id in zip(habits, habit_ids)]
        reply_keyboard = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(chat_id=chat_id, text="Your habits", reply_markup=reply_keyboard)
    else:
        await context.bot.send_message(chat_id=chat_id, text="You have no habits yet.")

# Main function
if __name__ == '__main__':
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()


    async def check_and_send_reminders():
        # Fetch users to notify along with their habits
        users_and_habits_to_notify = await fetch_users_and_habits_to_notify()

        for user, habit in users_and_habits_to_notify:
            # Construct the reminder message
            message = f"It's time for your habit: {habit['name']}!"

            # Send reminder to the user
            await application.send_message(chat_id=user['telegram_id'], text=message)


            # Update the reminder's status in the user's document
            for reminder in user['reminders']:
                if reminder['time'] == datetime.utcnow().strftime('%H:%M') and reminder['status'] == "active":
                    reminder['status'] = "sent"
                    users.update_one({'_id': user['_id']}, {"$set": {"reminders": user['reminders']}})
                    break


    scheduler.add_job(check_and_send_reminders, 'interval', minutes=5)
    scheduler.start()

    start_handler = CommandHandler('start', start)
    list_habits_handler = CommandHandler('list_habits', list_habits)

    add_habit_handler = dialogues.add_habit_dialogue(user_habits)

    application.add_handler(start_handler)
    application.add_handler(add_habit_handler)
    application.add_handler(list_habits_handler)

    application.run_polling()
