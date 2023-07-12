from datetime import datetime

import motor.motor_asyncio
import os
import httpx

import requests
from bson import ObjectId
from langchain.schema import messages_from_dict, messages_to_dict

import logging

logger = logging.getLogger(__name__)

motor_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_MARGULAN_DB_URL"))

db = motor_client[os.getenv("MONGO_GPT_USER_DB_NAME")]

user_threads = db['threads']
user_prompt = db['user_prompts']
usage_logs = db['usage_logs']
users = db['users']

async def get_data_from_notion(database_id):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"

    payload = {"page_size": 100}
    headers = {
        "accept": "application/json",
        "Notion-Version": "2022-06-28",
        "Authorization": f"Bearer {os.getenv('NOTION_THOUGHTFUL_COMPANY')}",
        "content-type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

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
async def save_prompt(user_id, title, prompt):
    thread = await user_prompt.insert_one({
        "user_id": user_id,
        "title": title,
        "prompt": prompt,
    })
    return thread.inserted_id

async def get_all_prompts(user_id):
    result =  await user_prompt.find({"user_id": user_id})
    # get 10 prompts for this user
    return result

async def get_user_prompt(user_id, prompt_id):
    return await user_prompt.find_one({"user_id": user_id, "_id": ObjectId(prompt_id)})

async def save_thread(chat_data):
    logger.info(f"Saving new thread with ID {chat_data['thread_id']} for user {chat_data['user_id']}")

    try:
        thread = await user_threads.update_one(
            {"thread_id": chat_data['thread_id']},
            {"$set": chat_data},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error saving thread {chat_data['thread_id']} in mongo: {e}")
        return None
    logger.info(f"Conversation saved. User id: {chat_data['user_id']}. Thread id: {thread_id}.")

    return


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
    usage_log = {"user_id": user_id, "cost": costs, "timestamp": datetime.utcnow()}
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
