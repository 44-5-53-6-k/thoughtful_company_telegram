from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, BaseMessage, SystemMessage, LLMResult
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import uuid
import yaml
import os
import datetime

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["MONGO_DB_URL"] = config_data['mongo_margulan_db_url']
os.environ["COHERE_API_KEY"] = config_data['cohere_api_key']

import mongo_utils
from chat_handlers import init_memory, create_agent_from_memory


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
        chat_history = mongo_utils.get_chat_history(conversation_id)

    print(f"Retrieved chat history: {chat_history}")
    return chat_history


def generate_topic_name(update):
    time = datetime.datetime.now()
    adequate_time = f"{time.hour}:{time.minute} {time.day}.{time.month}.{time.year}"

    topic_name = update.message.text.split(' ', 1)[1] if len(update.message.text.split(' ', 1)) > 1 else str(
        adequate_time)
    return topic_name


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.message.chat.type == 'group' or update.message.chat.type == 'supergroup'
    if is_group:
        await update.message.reply_text("Hello! I'm your habit tracker bot.")

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your habit tracker bot.")


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("creating new chat branch")
    # generate id for new converation, it should be unique, it should not be chat id. use datetime for that purpose
    conversation_id = str(uuid.uuid4())
    user = update.message.from_user
    topic_name = generate_topic_name(update)

    default_message = """
        Hello! How may I assist you?\n\n<b>Commands</b>:\n/new_topic - create a new topic\n/delete_topic - delete the current topic\n/delete_all_topics - delete all the topics
    """

    context.chat_data["current_conversation"] = conversation_id
    # TODO conversation should live for 60 minutes by default

    try:
        hello_message = await update.message.chat.send_message(text=default_message,
                                                               parse_mode="HTML")

        # CRETING NEW AGENT
        memory = init_memory(conversation_id)
        save_conversation(conversation_id, context, memory.buffer)
        mongo_utils.on_new_thread(user, update.message.chat.id, conversation_id, topic_name, hello_message.message_id)

    except Exception as e:
        print(e)
        return
    # create new conversation


async def new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NOT TESTED

    is_group = update.message.chat.type == 'group' or update.message.chat.type == 'supergroup'
    topic_name = generate_topic_name(update)

    if not is_group:
        await update.message.reply_text("This command is only available in a forum mode.")
        return

    print("Creating new topic")
    default_message = """
        Hello! How may I assist you?\n\n<b>Commands</b>:\n/new_topic - create a new topic\n/delete_topic - delete the current topic\n/delete_all_topics - delete all the topics
    """

    try:
        newly_created_topic = await update.message.chat.create_forum_topic(name=topic_name)
        topic_id = newly_created_topic.message_thread_id
        hello_message = await update.message.chat.send_message(text=default_message,
                                                               message_thread_id=newly_created_topic.message_thread_id,
                                                               parse_mode="HTML")
        chat_id = update.message.chat.id
        chat_id = str(chat_id)[4:]
        link_to_newly_created_topic = f"https://t.me/c/{chat_id}/{topic_id}"
        user = update.effective_user

        print("Trying to start the conversation")
        # CREATING AGENT
        agent_memory = init_memory(topic_id)

        # SAVING AGENT to session memory
        # TODO #1 switch saving history to saving agent
        # Warning: If chat migrates to supergroup, chat_data will still be linked to previous chat id
        chat_history = agent_memory.buffer
        save_conversation(topic_id, context, agent_memory.buffer)
        mongo_utils.on_new_thread(user, update.message.chat.id, topic_id, topic_name, hello_message.message_id)

        await update.message.reply_text(
            f"<code>Announcement!\n</code>New topic created: <a href='{link_to_newly_created_topic}'>{topic_name}</a>",
            parse_mode="HTML")

    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {e}")


async def new_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    print(f"New message received: {message_text}")
    conversation_id = None

    if "current_conversation" in context.chat_data:
        conversation_id = context.chat_data["current_conversation"]
    else:
        print(f"No active conversations found for {update.message.from_user.id}")
        await update.message.reply_text("You don't have any active conversations. Start one with /new_chat")
        return

    chat_history = retreive_conversation(conversation_id, context)
    agent_chain = create_agent_from_memory(chat_history)
    message = agent_chain.run(input=message_text)

    mongo_utils.update_chat_history(conversation_id, agent_chain.memory.buffer)

    await update.message.reply_text(message)

    return


async def new_forum_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # todo consider feature of resetting chat history
    message_text = update.message.text
    print(f"New message received: {message_text}")

    if update.message.is_topic_message is False:
        # answer that chat could be started only in a group with topics
        await update.message.reply_text("Chat could be started only in a group with topics")
        return

    conversation_id = update.message.message_thread_id
    chat_history = retreive_conversation(conversation_id, context)

    agent_chain = create_agent_from_memory(chat_history)
    message = agent_chain.run(input=message_text)

    # UPDATE CHAT HISTORY IN MONGO
    mongo_utils.update_chat_history(conversation_id, agent_chain.memory.buffer)

    await update.message.reply_text(message)

    return


async def new_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.message.chat.type == 'group' or update.message.chat.type == 'supergroup'
    is_private_message = update.message.chat.type == 'private'

    if is_private_message:
        await new_private_message(update, context)
        return
    else:
        await new_forum_message(update, context)
        return


async def delete_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_thread_id = update.message.reply_to_message.message_thread_id if update.message.reply_to_message else None

    if message_thread_id is None:
        # reply to the message with the topic to delete
        await update.message.reply_text("This topic cannot be deleted.")
        return

    try:
        await update.message.chat.delete_forum_topic(message_thread_id=message_thread_id)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {e}")


async def delete_all_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # get all the topics
    # delete all the topics
    # answer that this feature is not done yet
    await update.message.reply_text("This feature is not done yet.")
    pass


# Main function
if __name__ == '__main__':
    application = ApplicationBuilder().token("6011659848:AAEicZv8J0S3ywzagPNejqolqlD3lstYuBk").build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    new_chat_handler = CommandHandler('new_chat', new_chat)
    application.add_handler(new_chat_handler)

    new_topic_handler = CommandHandler('new_topic', new_topic)
    application.add_handler(new_topic_handler)

    delete_topic_handler = CommandHandler('delete_topic', delete_topic)
    application.add_handler(delete_topic_handler)

    delete_all_topics_handler = CommandHandler('delete_all_topics', delete_all_topics)
    application.add_handler(delete_all_topics_handler)

    chat_handler = MessageHandler(filters.TEXT, new_message_router)
    application.add_handler(chat_handler)

    application.run_polling()
