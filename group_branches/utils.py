import logging

from bson import ObjectId
from pymongo import MongoClient
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

notion_token = os.getenv("NOTION_TOKEN")

from telegram import Update
from telegram.ext import ContextTypes

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["MONGO_DB_URL"] = config_data['mongo_margulan_db_url']

client = MongoClient(os.getenv("MONGO_DB_URL"))
db = client['topics_db']
user_threads = db['threads']
user_prompt = db['user_prompts']


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

def store_user_prompt(user_id, title, prompt):
    thread_id = user_prompt.insert_one({
        "user_id": user_id,
        "title": title,
        "prompt": prompt,
    }).inserted_id

def get_user_prompts(user_id):
    result =  user_prompt.find({"user_id": user_id})
    # get 10 prompts for this user
    return result

def get_user_prompt(user_id, prompt_id):
    return user_prompt.find_one({"user_id": user_id, "_id": ObjectId(prompt_id)})


# When a new thread is created
def chat_memory_to_dict(chat_memory):
    """Convert chat history to dictionary format."""
    return [message.__dict__ for message in chat_memory.chat_memory.messages]
def on_new_thread(chat_data):
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
    thread_id = user_threads.insert_one(new_thread).inserted_id
    print(f"Conversation saved. Thread id: {thread_id}.")
    return thread_id

# When a new message arrives
def update_chat_history(topic_id, chat_history):
    chat_history = messages_to_dict(chat_history)
    # update in mongo
    user_threads.update_one({'thread_id': topic_id}, {"$set": {"chat_history": chat_history}})

def get_thread_data(thread_id):
    thread = user_threads.find_one({'thread_id': thread_id})
    # if chat_history is None make it []
    if thread['chat_history'] is None:
        thread['chat_history'] = []
    chat_history = messages_from_dict(thread['chat_history'])
    thread['chat_history'] = chat_history

    return thread

def get_chat_history(thread_id):
    topic_details = user_threads.find_one({'thread_id': thread_id})
    chat_history = messages_from_dict(topic_details['chat_history'])
    return chat_history