import uuid

from langchain.callbacks import get_openai_callback
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from telegram_bots import tg_utils, db_utils, chat_handlers, telethon_helper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_group = update.message.chat.type == 'group' or update.message.chat.type == 'supergroup'
    message_to_send = "Привет! Я - чат-бот образовательной платформы Margulan AI. У меня есть малая крупица знаний <b>Маргулана Сейсембая</b>, но я постоянно учусь! \n\nЗадайте мне вопрос на тему того, что учит Маргулан Калиевич и я постараюсь ответить на ваш вопрос используя его знание. Я стараюсь не придумывать ответ и сначала пробую искать информацию среди видео нашей платформы. Однако иногда я все равно ошибаюсь, поэтому лучше проверяйте мой ответ в источниках! \n\n<code>Пример запроса: 'Найди информацию про то, как управлять своим временем?'</code>\n\n Чтобы начать новый диалог, нажмите /new_chat"
    if is_group:
        await update.message.reply_text(message_to_send, parse_mode='HTML')
    else:
        await update.message.reply_text(message_to_send, parse_mode='HTML')

    # TODO send list of commands to bot
    # # delete_my_commands at bot
    # await context.bot.delete_my_commands()
    #
    # # # List of commands and descriptions
    # command_list = [
    #     ('new_chat', 'Start a new chat'),
    #     ('choose_prompt', 'Choose a prompt'),
    #     ('choose_private_prompt', 'Choose a private prompt'),
    #     ('new_topic', 'Create a new topic'),
    #     ('delete_topic', 'Delete a topic'),
    #     ('delete_all_topics', 'Delete all topics')
    # ]
    #
    # bot_commands_objects = []
    # for command, description in command_list:
    #     # use BotCommand class
    #     bot_command = BotCommand(command=command, description=description)
    #     bot_commands_objects.append(bot_command)
    #
    # # set my commands
    # await context.bot.set_my_commands(commands=bot_commands_objects)
    #
    # # Generate the message with command list and descriptions
    # message = 'Available commands:\n\n'
    # for command, description in command_list:
    #     message += f'/{command}: {description}\n'
    #
    # # Send the message to the user
    # await update.message.reply_text(text=message)




async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("creating new chat branch")
    conversation_id = str(uuid.uuid4())

    user, chat = tg_utils.get_user_and_chat(update)

    has_access = await db_utils.has_access(user.id)
    if not has_access:
        await update.message.reply_text("Упс. Ваши лимиты исчерпаны. Ждем вас в следующий раз!")
        return

    topic_name = tg_utils.generate_topic_name(update)

    # TODO conversation should live for 60 minutes by default
    hello_message = await chat.send_message(text="hey",
                                            parse_mode="HTML")

    chat_data = {
        "user_id": user.id,
        "thread_id": conversation_id,
        "thread_name": topic_name,
        "hello_message_id": hello_message.message_id,
        "chat_id": chat.id,
        "chat_history": [],
        "prompt_data": {
            "text": "You are the Devil"
        }
    }

    await db_utils.save_new_thread(chat_data)
    tg_utils.save_conversation(chat_data, context)


async def new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NOT TESTED

    is_group = update.message.chat.type == 'group' or update.message.chat.type == 'supergroup'
    topic_name = tg_utils.generate_topic_name(update)

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
        agent_memory = chat_handlers.init_memory(topic_id)

        # SAVING AGENT to session memory
        # TODO #1 switch saving history to saving agent
        # Warning: If chat migrates to supergroup, chat_data will still be linked to previous chat id
        chat_history = agent_memory.buffer
        tg_utils.save_conversation(topic_id, context, agent_memory.buffer)
        # TODO Rewrite
        # await tg_utils.on_new_thread(user, update.message.chat.id, topic_id, topic_name, hello_message.message_id)

        await update.message.reply_text(
            f"<code>Новый диалог создан!\n</code>Нажмите чтобы открыть чат: <a href='{link_to_newly_created_topic}'>{topic_name}</a>",
            parse_mode="HTML")

    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {e}")


async def new_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    target_message_id = await update.message.reply_text("🔎 Ищу ответ среди знаний Маргулана... 🕵️")

    message = await get_answer(update, context)

    await target_message_id.edit_text(message)
    return

async def get_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    conversation_id = None

    thread_data = await tg_utils.get_thread(update, context)
    if not thread_data:
        thread_data = await db_utils.get_thread_data(conversation_id)

    agent_chain = chat_handlers.create_agent_from_memory(thread_data["chat_history"], thread_data["prompt_data"]['prompt'])

    with get_openai_callback() as cb:
        try:
            message = agent_chain.run(input=message_text)
            await db_utils.log_costs(update, cb.total_cost)
        except Exception as e:
            print(e)
            message = "Что-то пошло не так. Начните новый чат и попробуйте сформулировать вопрос иначе.\n\n/new_chat"

    await db_utils.update_chat_history(conversation_id, agent_chain.memory.buffer)

    return message


async def new_forum_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # todo consider feature of resetting chat history
    message_text = update.message.text
    print(f"New message received: {message_text}")

    if update.message.is_topic_message is False:
        # answer that chat could be started only in a group with topics
        await update.message.reply_text("Chat could be started only in a group with topics")
        return

    conversation_id = update.message.message_thread_id
    chat_history = tg_utils.retreive_conversation(conversation_id, context)

    agent_chain = chat_handlers.create_agent_from_memory(chat_history)
    message = agent_chain.run(input=message_text)

    # UPDATE CHAT HISTORY IN MONGO
    await db_utils.update_chat_history(conversation_id, agent_chain.memory.buffer)

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
    prompt = tg_utils.get_prompt_by_id(prompt_id)

    user_id = update.effective_user.id

    if prompt is None:
        print("Searching inside user prompt")
        prompt = db_utils.get_user_prompt(user_id, prompt_id)

    # set prompt to chat data
    context.chat_data["current_prompt"] = prompt

    query_answer = f"You've selected: {prompt['title']}"

    await query.answer(query_answer)
    await new_chat(update, context)

async def authorization_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # todo add authorization
    pass
    # if update.effective_user.id in USERS_WITH_ACCESS:
    #     pass
    # else:
    #     await update.effective_message.reply_text(get_system_message("authorization/access_denied"))
    #     raise ApplicationHandlerStop



# def main():
#     # get data from notion
#
#     application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
#
#     auth_handler = TypeHandler(Update, authorization_user)
#     application.add_handler(auth_handler, -1)
#
#     start_handler = CommandHandler('start', start)
#     application.add_handler(start_handler)
#
#     new_chat_handler = CommandHandler('new_chat', new_chat)
#     application.add_handler(new_chat_handler)
#
#     #
#     # choose_private_prompt_handler = CommandHandler('choose_private_prompt', choose_private_prompt)
#     # application.add_handler(choose_private_prompt_handler)
#     #
#     #
#     # new_topic_handler = CommandHandler('new_topic', new_topic)
#     # application.add_handler(new_topic_handler)
#     #
#     # delete_topic_handler = CommandHandler('delete_topic', delete_topic)
#     # application.add_handler(delete_topic_handler)
#     #
#     # delete_all_topics_handler = CommandHandler('delete_all_topics', delete_all_topics)
#     # application.add_handler(delete_all_topics_handler)
#
#     # add_prompt = add_prompt_scene()
#     # application.add_handler(add_prompt)
#
#
#     # should be last
#     chat_handler = MessageHandler(filters.TEXT, new_message_router)
#     application.add_handler(chat_handler)
#
#
#     application.run_polling()

async def update_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_data_loaded = await tg_utils.load_data(context)
    # todo check admin
    username = update.effective_user.username


    if is_data_loaded is False:
        await update.message.reply_text("Data is not loaded. Exiting.")
        return
