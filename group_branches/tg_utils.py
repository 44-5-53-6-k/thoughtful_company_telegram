import logging

from bson import ObjectId
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

import group_branches.db_utils as db_utils

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

# todo rewrite so I can store this data in bot session storage
def get_prompt_by_id(prompt_id):
    for prompt in data['prompts']:
        if prompt['id'] == prompt_id:
            return prompt

    return None

def load_data(application):
    # todo test this
    try:
        data_from_notion = await db_utils.get_data_from_notion(os.getenv("NOTION_PROMPTS_DATABASE_ID"))
    except Exception as e:
        print(f"Error while loading data from notion: {e}")
        return None

    if "notion" not in application.context.bot_data:
        application.context.bot_data["notion"] = {}
    for datum in data_from_notion:
        application.context.bot_data[datum] = data_from_notion[datum]

    return True

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
    prompts = await db_utils.get_all_prompts(update.message.from_user.id)
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


def save_conversation(chat_data, context):
    conversation_id = chat_data["thread_id"]
    if "conversations" not in context.chat_data:
        context.chat_data["conversations"] = {}

    if conversation_id not in context.chat_data["conversations"]:
        context.chat_data["conversations"][conversation_id] = chat_data

def get_user_and_chat(update):
    if update.message:
        user = update.message.from_user
        chat = update.message.chat
    elif update.callback_query:
        user = update.callback_query.from_user
        chat = update.callback_query.message.chat
    else:
        print("Error: unsupported update type")
        return

    return user, chat

async def get_thread(update,  context):
    if "current_conversation" in context.chat_data:
        conversation_id = context.chat_data["current_conversation"]

        if context.chat_data and context.chat_data["conversations"] and (
                conversation_id in context.chat_data["conversations"]):
            return context.chat_data["conversations"][conversation_id]
    else:
        print(f"No active conversations found for {update.message.from_user.id}")
        # todo check in the database
        await update.message.reply_text("You don't have any active conversations. Start one with /new_chat")
        return

async def retreive_conversation(conversation_id, context):
    chat_history = None

    if context.chat_data and context.chat_data["conversations"] and (
            conversation_id in context.chat_data["conversations"]):
        chat_history = context.chat_data["conversations"][conversation_id]["chat_history"]
    else:
        print(f"Session memory is empty, retrieving from database")
        chat_history = await db_utils.get_chat_history(conversation_id)

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

# for deletion
# def chat_memory_to_dict(chat_memory):
#     """Convert chat history to dictionary format."""
#     return [message.__dict__ for message in chat_memory.chat_memory.messages]
