import logging

from bson import ObjectId
import motor.motor_asyncio
import datetime
import os

from langchain.schema import (
    AIMessage,
    BaseChatMessageHistory,
    BaseMessage,
    HumanMessage,
    messages_to_dict,
    messages_from_dict,
)

import requests
import yaml


from telegram import Update
from telegram.ext import ContextTypes

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

database_id = config_data['notion_prompts_database_id']
os.environ["MONGO_DB_URL"] = config_data['mongo_margulan_db_url']
notion_token = config_data['notion_thoughtful_company']
database_name = config_data['database_name']

# client = MongoClient(os.getenv("MONGO_DB_URL"))
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_DB_URL"))
db = client[database_name]
user_threads = db['threads']
user_prompt = db['user_prompts']
usage_logs = db['usage_logs']
users = db['users']

def get_data_from_notion(database_id):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"

    payload = {"page_size": 100}
    headers = {
        "accept": "application/json",
        "Notion-Version": "2022-06-28",
        "Authorization": f"Bearer {notion_token}",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    dict_result = response.json()['results']

    resulting_pages = []
    for page in dict_result:
        title = ""
        for title_part in page['properties']['Name']['title']:
            title += title_part['text']['content']

        prompt = ""
        for prompt_part in page['properties']['Prompt']['rich_text']:
            prompt += prompt_part['text']['content']

        new_page = {
            "id": page['id'],
            "title": title,
            "prompt": prompt,
        }

        resulting_pages.append(new_page)

    return {
        "prompts": resulting_pages
    }


data = get_data_from_notion(database_id)

def get_prompt_by_id(prompt_id):
    for prompt in data['prompts']:
        if prompt['id'] == prompt_id:
            return prompt

    return None


async def choose_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompts = data['prompts']
    # show keyboard with prompts to user
    # keyboard = [[prompt] for prompt in prompts]
    keyboard = []
    for prompt in prompts:
        keyboard_item = {
            "text": prompt['title'],
            "callback_data": f"prompt_{prompt['id']}"
        }
        keyboard.append([keyboard_item])

    reply_markup = {
        "inline_keyboard": keyboard
    }
    await update.message.reply_text('Выберите тему, которую хотите изучить', reply_markup=reply_markup)

async def choose_private_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompts = get_user_prompts(update.message.from_user.id)
    # show keyboard with prompts to user
    # keyboard = [[prompt] for prompt in prompts]
    keyboard = []
    for prompt in prompts:
        keyboard_item = {
            "text": prompt['title'],
            "callback_data": f"prompt_{prompt['_id']}"
        }
        keyboard.append([keyboard_item])

    reply_markup = {
        "inline_keyboard": keyboard
    }
    await update.message.reply_text('Выберите тему, которую хотите изучить', reply_markup=reply_markup)
def save_conversation(conversation_id, context, chat_history):
    if "conversations" not in context.chat_data:
        context.chat_data["conversations"] = {}
    if conversation_id not in context.chat_data["conversations"]:
        context.chat_data["conversations"][conversation_id] = {}
    context.chat_data["conversations"][conversation_id]["chat_history"] = chat_history

def retreive_conversation(conversation_id, context):
    chat_history = None

    if context.chat_data and context.chat_data["conversations"] and (
            conversation_id in context.chat_data["conversations"]):
        chat_history = context.chat_data["conversations"][conversation_id]["chat_history"]
    else:
        print(f"Session memory is empty, retrieving from database")
        chat_history = get_chat_history(conversation_id)

    print(f"Retrieved chat history: {chat_history}")
    return chat_history


def generate_topic_name(update):
    time = datetime.datetime.now()
    adequate_time = f"{time.hour}:{time.minute} {time.day}.{time.month}.{time.year}"
    topic_name = adequate_time

    if update.message:
        topic_name = update.message.text.split(' ', 1)[1] if len(update.message.text.split(' ', 1)) > 1 else str(
            adequate_time)

    return topic_name

async def store_user_prompt(user_id, title, prompt):
    thread = await user_prompt.insert_one({
        "user_id": user_id,
        "title": title,
        "prompt": prompt,
    })
    return thread.inserted_id

async def get_user_prompts(user_id):
    result =  await user_prompt.find({"user_id": user_id})
    # get 10 prompts for this user
    return result

async def get_user_prompt(user_id, prompt_id):
    return await user_prompt.find_one({"user_id": user_id, "_id": ObjectId(prompt_id)})


# When a new thread is created
def chat_memory_to_dict(chat_memory):
    """Convert chat history to dictionary format."""
    return [message.__dict__ for message in chat_memory.chat_memory.messages]
async def on_new_thread(chat_data):
    print("Logging new thread")
    # Get user details from update
    # destruct chat_dat

    new_thread = {
        'user_id': chat_data['user_id'],
        'chat_id': chat_data['chat_id'],
        'thread_id': chat_data['thread_id'],
        'thread_name': chat_data['thread_name'],
        'hello_message_id': chat_data['hello_message_id'],
        'created_at': datetime.datetime.utcnow(),
        "chat_history": None,
        "prompt_data": chat_data['prompt_data'],
    }


    # Insert the new thread into the collection
    thread = await user_threads.insert_one(new_thread)
    thread_id = thread.inserted_id
    print(f"Conversation saved. Thread id: {thread_id}.")
    return thread_id

# When a new message arrives
async def update_chat_history(topic_id, chat_history):
    chat_history = messages_to_dict(chat_history)
    # update in mongo
    await user_threads.update_one({'thread_id': topic_id}, {"$set": {"chat_history": chat_history}})

async def reset_daily_usage():
   await users.update_many({}, {"$set": {"daily_usage": 0}})


async def reset_weekly_usage():
    await users.update_many({}, {"$set": {"weekly_usage": 0}})

async def create_user(user_id):
    user = {
            "telegram_id": user_id,
            "daily_usage": 0,
            "weekly_usage": 0,
            "all_time_usage": 0,
        }
    result = await users.insert_one(user)
    print(f"Created user {user_id} with result: {result}")
    return result


async def log_costs(update, costs):
    user_id = update.effective_user.id
    user = await users.find_one({"telegram_id": user_id})

    if not user:
        print(f"User {user_id} not found.")
        await create_user(user_id)

    # Updating the usage data
    user['daily_usage'] += costs
    user['weekly_usage'] += costs
    user['all_time_usage'] += costs

    # Updating the user data in MongoDB
    log_result = await users.update_one({"telegram_id": user_id}, {"$set": user})
    print(f"Updated user {user_id} with result: {log_result}")

    # Adding a usage log
    usage_log = {"user_id": user_id, "cost": costs, "timestamp": datetime.datetime.utcnow()}
    await usage_logs.insert_one(usage_log)

    # Checking against limits and taking appropriate action
    if user['daily_usage'] > 0.75:
        print(f"User {user_id} has exceeded the daily limit.")
        await update.message.reply_text("Ваш дневной лимит сообщений исчерпан.Приходите завтра.")
        # Code to lock the user out goes here
    elif user['daily_usage'] > 0.5:
        await update.message.reply_text("Ваш дневной лимит сообщений подходит к концу.")
        print(f"User {user_id} has exceeded the daily warning limit.")
        # Code to send warning to the user goes here
    elif user['weekly_usage'] > 4:
        print(f"User {user_id} has exceeded the weekly limit.")
        await update.message.reply_text("Ваш недельный лимит сообщений исчерпан.Приходите на следующей неделе.")
        # Code to lock the user out for the week goes here

    print(
        f"Updated costs for user {user_id}. Daily: {user['daily_usage']}, Weekly: {user['weekly_usage']}, All time: {user['all_time_usage']}")

async def has_access(user_id):
    user = await users.find_one({"telegram_id": user_id})

    if not user:
        print(f"User {user_id} not found.")
        await create_user(user_id)
        return True

    # check daily limits
    if user['daily_usage'] > 0.75:
        return False
    elif user['weekly_usage'] > 4:
        return False

    return True


async def get_thread_data(thread_id):
    thread = await user_threads.find_one({'thread_id': thread_id})
    # if chat_history is None make it []
    if thread['chat_history'] is None:
        thread['chat_history'] = []
    chat_history = messages_from_dict(thread['chat_history'])
    thread['chat_history'] = chat_history

    return thread

async def get_chat_history(thread_id):
    topic_details = await user_threads.find_one({'thread_id': thread_id})
    chat_history = messages_from_dict(topic_details['chat_history'])
    return chat_history