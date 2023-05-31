import logging
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

from telegram import Update
from telegram.ext import ContextTypes

client = MongoClient(os.getenv("MONGO_DB_URL"))
db = client['topics_db']
user_threads = db['threads']

# When a new thread is created
def chat_memory_to_dict(chat_memory):
    """Convert chat history to dictionary format."""
    return [message.__dict__ for message in chat_memory.chat_memory.messages]
def on_new_thread(user, chat_id, message_thread_id, topic_name, hello_message_id):
    print("Logging new thread")
    # Get user details from update

    # Create a new thread document
    new_thread = {
        'user_id': user.id,
        'chat_id': chat_id,
        'thread_id': message_thread_id,
        'thread_name': topic_name,
        'hello_message_id': hello_message_id,
        'created_at': datetime.datetime.utcnow(),
        "chat_history": None,
    }

    print(f"Conversation saved. Thread id: {message_thread_id}.")

    # Insert the new thread into the collection
    thread_id = user_threads.insert_one(new_thread).inserted_id
    return thread_id

# When a new message arrives
def update_chat_history(topic_id, chat_history):
    chat_history = messages_to_dict(chat_history)
    # update in mongo
    user_threads.update_one({'thread_id': topic_id}, {"$set": {"chat_history": chat_history}})

def get_chat_history(topic_id):
    topic_details = user_threads.find_one({'thread_id': topic_id})
    chat_history = messages_from_dict(topic_details['chat_history'])
    return chat_history