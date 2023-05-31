import logging
from pymongo import MongoClient
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, BaseMessage, SystemMessage, LLMResult
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import yaml
import os


# Load the YAML file
with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["OPENAI_API_KEY"] = config_data['openai_api_key']
os.environ["TELEGRAM_BOT_TOKEN"] = config_data['telegram_token']

import dialogues
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Connect to MongoDB
client = MongoClient('mongodb+srv://doadmin:GE42t0U6s85w1M9g@margulan-db-89944bc8.mongo.ondigitalocean.com/admin?replicaSet=margulan-db&tls=true&authSource=admin')
db = client['thoughtful_company']
user_habits = db['user_habits']
users = db['users']

chat_openai = ChatOpenAI()
prompt = PromptTemplate(
    input_variables=['habit_name'],
    template="I want to {habit_name}.",
)

# Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your habit tracker bot.")


async def list_habits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    habits = [doc['habit'] for doc in user_habits.find({'chat_id': chat_id})]
    if habits:
        habits_text = '\n'.join(habits)
        await context.bot.send_message(chat_id=chat_id, text=f"Your habits:\n{habits_text}")
    else:
        await context.bot.send_message(chat_id=chat_id, text="You have no habits yet.")

# Main function
if __name__ == '__main__':
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    start_handler = CommandHandler('start', start)
    list_habits_handler = CommandHandler('list_habits', list_habits)

    add_habit_handler = dialogues.add_habit_dialogue(user_habits)

    application.add_handler(start_handler)
    application.add_handler(add_habit_handler)
    application.add_handler(list_habits_handler)

    application.run_polling()
