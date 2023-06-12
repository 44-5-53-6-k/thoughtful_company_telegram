from telegram import Update, ReplyKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler
from telegram.constants import ChatAction

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, BaseMessage, SystemMessage, LLMResult
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import uuid
import yaml
import os
import datetime

from group_branches.scenes import add_prompt_scene

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["MONGO_DB_URL"] = config_data['mongo_margulan_db_url']
print(config_data['mongo_margulan_db_url'])
os.environ["COHERE_API_KEY"] = config_data['cohere_api_key']
os.environ["TELEGRAM_BOT_TOKEN"] = config_data['telegram_token_1']
os.environ["NOTION_TOKEN"] = config_data['notion_thoughtful_company']

import utils
from utils import get_data_from_notion
from chat_handlers import init_memory, create_agent_from_memory


database_id = "5af5ce3becee4dbabdd8ed22d6955c2f"
data = utils.get_data_from_notion(database_id)

def get_prompt_by_id(prompt_id):
    for prompt in data['prompts']:
        if prompt['id'] == prompt_id:
            return prompt

    return None


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
        chat_history = utils.get_chat_history(conversation_id)

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.message.chat.type == 'group' or update.message.chat.type == 'supergroup'
    if is_group:
        await update.message.reply_text("Привет! Я - бот образовательной платформы Margulan AI. У меня есть малая крупица знаний Маргулана Сейсембая, но я постоянно учусь! Спросите у меня вопрос на тему того, что учит Маргулан Калиевич и я постараюсь ответить на ваш вопрос используя его знание. \n\n Чтобы начать новый диалог, нажми /new_topic")
    else:
        await update.message.reply_text("Привет! Я - бот образовательной платформы Margulan AI. У меня есть малая крупица знаний Маргулана, но я постоянно учусь! Спросите у меня вопрос на тему того, что учит Маргулан и я постараюсь ответить на него используя знание Маргулана")

    # delete_my_commands at bot
    await context.bot.delete_my_commands()

    # # List of commands and descriptions
    command_list = [
        ('new_chat', 'Start a new chat'),
        ('choose_prompt', 'Choose a prompt'),
        ('choose_private_prompt', 'Choose a private prompt'),
        ('new_topic', 'Create a new topic'),
        ('delete_topic', 'Delete a topic'),
        ('delete_all_topics', 'Delete all topics')
    ]

    bot_commands_objects = []
    for command, description in command_list:
        # use BotCommand class
        bot_command = BotCommand(command=command, description=description)
        bot_commands_objects.append(bot_command)

    # set my commands
    await context.bot.set_my_commands(commands=bot_commands_objects)

    # Generate the message with command list and descriptions
    message = 'Available commands:\n\n'
    for command, description in command_list:
        message += f'/{command}: {description}\n'

    # Send the message to the user
    await update.message.reply_text(text=message)

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
    prompts = utils.get_user_prompts(update.message.from_user.id)
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

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("creating new chat branch")
    # generate id for new converation, it should be unique, it should not be chat id. use datetime for that purpose
    conversation_id = str(uuid.uuid4())
    # it could be update.message or update.callback_query
    user = None
    chat = None
    if update.message:
        user = update.message.from_user
        chat = update.message.chat
    elif update.callback_query:
        user = update.callback_query.from_user
        chat = update.callback_query.message.chat
    else:
        print("Error: unsupported update type")
        return

    topic_name = generate_topic_name(update)

    default_message = """
        Hello! How may I assist you?\n\n<b>Commands</b>:\n/new_topic - create a new topic\n/delete_topic - delete the current topic\n/delete_all_topics - delete all the topics
    """

    current_prompt = None
    prompt_text = None
    if "current_prompt" in context.chat_data:
        current_prompt = context.chat_data["current_prompt"]
        prompt_text = current_prompt['prompt']
    else:
        current_prompt = {
            "id": "1",
            "prompt": "What is the meaning of life?",
            "title": "Brainfuck"
        }
        prompt_text = current_prompt['prompt']

    context.chat_data["current_conversation"] = conversation_id
    print(f"Current conversation: {context.chat_data['current_conversation']}")
    # TODO conversation should live for 60 minutes by default

    try:
        hello_message = await chat.send_message(text=default_message,
                                                               parse_mode="HTML")

        # CRETING NEW AGENT
        memory = init_memory(conversation_id)
        save_conversation(conversation_id, context, memory.buffer)

        chat_data = {
            "user_id": user.id,
            "thread_id": conversation_id,
            "thread_name": topic_name,
            "hello_message_id": hello_message.message_id,
            "chat_id": chat.id,
            "prompt_data": current_prompt
        }
        utils.on_new_thread(chat_data)

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
        Привет! Что бы тебе хотелось узнать?\n\n<b>Команды</b>:\n/new_topic - Начать новый диалог\n/delete_topic - удалить текущий диалог
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
        utils.on_new_thread(user, update.message.chat.id, topic_id, topic_name, hello_message.message_id)

        await update.message.reply_text(
            f"<code>Новый диалог создан!\n</code>Нажмите чтобы открыть чат: <a href='{link_to_newly_created_topic}'>{topic_name}</a>",
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

    # for now every operation is loaded from mongo and saved to it
    thread_data = utils.get_thread_data(conversation_id)

    agent_chain = create_agent_from_memory(thread_data["chat_history"], thread_data["prompt_data"]['prompt'])
    message = agent_chain.run(input=message_text)

    utils.update_chat_history(conversation_id, agent_chain.memory.buffer)

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
    utils.update_chat_history(conversation_id, agent_chain.memory.buffer)

    await update.message.reply_text(message)

    return

async def new_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # set message status typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
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

async def prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prompt_id = query.data.split("_")[1]
    prompt = get_prompt_by_id(prompt_id)

    user_id = update.effective_user.id

    if prompt is None:
        print("Searching inside user prompt")
        prompt = utils.get_user_prompt(user_id, prompt_id)

    # set prompt to chat data
    context.chat_data["current_prompt"] = prompt

    query_answer = f"You've selected: {prompt['title']}"

    await query.answer(query_answer)
    await new_chat(update, context)


# Main function
if __name__ == '__main__':
    # get data from notion

    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    new_chat_handler = CommandHandler('new_chat', new_chat)
    application.add_handler(new_chat_handler)

    choose_prompt_handler = CommandHandler('choose_prompt', choose_prompt)
    application.add_handler(choose_prompt_handler)

    choose_private_prompt_handler = CommandHandler('choose_private_prompt', choose_private_prompt)
    application.add_handler(choose_private_prompt_handler)

    prompt_handler = CallbackQueryHandler(prompt_handler, 'prompt_')
    application.add_handler(prompt_handler)

    new_topic_handler = CommandHandler('new_topic', new_topic)
    application.add_handler(new_topic_handler)

    delete_topic_handler = CommandHandler('delete_topic', delete_topic)
    application.add_handler(delete_topic_handler)

    delete_all_topics_handler = CommandHandler('delete_all_topics', delete_all_topics)
    application.add_handler(delete_all_topics_handler)

    add_prompt = add_prompt_scene()
    application.add_handler(add_prompt)


    # should be last
    chat_handler = MessageHandler(filters.TEXT, new_message_router)
    application.add_handler(chat_handler)


    application.run_polling()
