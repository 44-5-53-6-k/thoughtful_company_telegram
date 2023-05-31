import asyncio
from threading import Thread

from callback import TelegramStreamingCallbackHandler

import telegram
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    MessageHandler,
    filters
)
from langchain.chat_models import ChatOpenAI
from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import HumanMessage, BaseMessage, SystemMessage, LLMResult

from telegram.constants import ParseMode
import ai_api

import config
from callback import DebuggingCallbackHandler

import yaml
import os

# Load the YAML file
with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

# get the key from config/config.yml and set it to OPENAI_API_KEY
OPENAI_API_KEY = config_data['openai_api_key']
COHERE_API_KEY = config_data['cohere_api_key']
# set os environment variable
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
print(os.getenv("OPENAI_API_KEY"))
import cohere

co = cohere.Client(COHERE_API_KEY)

user_semaphores = {}

vectorstore = ai_api.init_vectorstore()
print("init vectorstore")
import pyrogram

api_id = "20282180"
api_hash = "a1264d4ca1cc770ed1ed1bee674ab46a"

# TODO add on startup and on shotdown handlers

file_queue = asyncio.Queue()
is_downloading = False

# Add a file to the queue


async def download_file(file_id, file_name, chat_id):
    global is_downloading
    async def progress(current, total):
        if total > 0:
            print(f"{current * 100 / total:.1f}%")
        else:
            print(f"{current} of unknown")

    pyro_app = pyrogram.Client("my_account", api_id=api_id, api_hash=api_hash,
                               bot_token="5899466534:AAF3LVMo2a5ybcjVv5TMo2Je0BSl2smyKX8")

    async with pyro_app:
        file = await pyro_app.download_media(file_id, file_name=file_name, progress=progress)
        await pyro_app.send_message(chat_id, f"File {file_name} downloaded, id {file_id}")


async def media_handler(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    print(f"Handling media from {update.effective_user}")
    global is_downloading

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        chat_id = message.chat_id

        await file_queue.put((file_id, file_name, chat_id))

        if not is_downloading:
            is_downloading = True
            context.bot.loop.create_task(download_files(context))

        await message.reply_text(f"File {file_name} added to queue")


async def message_handle(update: Update, context: CallbackContext, message=None, use_new_dialog_timeout=True):
    _message = message or update.message.text

    print(f"Handling message from {update.effective_user}")

    if update.message.chat.type != "private":
        _message = _message.replace("@" + context.bot.username, "").strip()

    user_id = update.message.from_user.id

    async def message_handle_fn():
        n_input_tokens, n_output_tokens = 0, 0

        try:
            await update.message.chat.send_action(action="typing")

            if _message is None or len(_message) == 0:
                await update.message.reply_text("🥲 You sent <b>empty message</b>. Please, try again!",
                                                parse_mode=ParseMode.HTML)
                return

            # parse_mode = {
            #     "html": ParseMode.HTML,
            #     "markdown": ParseMode.MARKDOWN
            # }

            vector = co.embed(
                texts=[_message],
                model="embed-multilingual-v2.0",
            ).embeddings[0]
            docs = vectorstore.similarity_search_by_vector(vector)
            # filter docs with empty page content
            docs = [doc for doc in docs if doc.page_content is not None and len(doc.page_content) > 0]

            callback_handler = TelegramStreamingCallbackHandler(context.bot, update.message.chat_id)
            # streaming_flag = config.enable_message_streaming and len(dialog_messages) > 0
            streaming_flag = True
            # get 5 most similar documents and put it to $context
            # reduce them to a string
            # Each doc should start with "Document N", where N is the number of the document
            max_docs = 5
            docs_length = len(docs)
            range_value = min(max_docs, docs_length)
            print(docs)
            knowledge_context = "\n".join([f"Document {i + 1}: {docs[i].page_content}" for i in range(0, range_value)])
            print('here')

            prompt_template = f"""
            Your name is Margulan Seissembai. You're a spiritual mentor to help me better understand my inner self and your philosophy. 
            You should reply in a professional yet educative manner. You should provide lots of detail and use everyday life examples.
            You should not make information up. If you can't answer because you don't have the information, output a clarifying question and allow me to respond by providing the information. 

            Question: {_message}
            Context from Margulan's knowledge: {knowledge_context}
            Helpful Answer:"""
            # prompt_template = 'Use the following portion of a long document to see if any of the text is relevant to answer the question. Document: \n\n' + docs[0].page_content

            if streaming_flag:
                chat = ChatOpenAI(temperature=0.2, openai_api_key=os.environ.get("OPENAI_API_KEY"),
                                  callbacks=[callback_handler], streaming=streaming_flag)
                # Create your list of messages.
                # Here we're just sending a single message from a hypothetical user "Alice".

                # Asynchronously generate a chat response.
                batch_messages = [
                    [
                        SystemMessage(content=prompt_template),
                        HumanMessage(content=_message)
                    ],
                ]
                result = await chat.agenerate(batch_messages)
                # print(result)

            else:
                # get type of docs[0]

                # answer with docs
                await update.message.reply_text(docs[0].page_content, parse_mode=ParseMode.HTML)

                # answer = qa_chain.run(
                #     {"question": _message, "chat_history": []}
                # )
                # chat = ChatOpenAI(temperature=0.2, openai_api_key="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",
                #                   streaming=streaming_flag)
                # memory = ConversationBufferMemory()
                # llm_chain = ConversationChain(
                #     llm=chat,
                #     prompt=prompt_template,
                #     memory=memory,
                # )
                # resp = chat_instance([HumanMessage(content=_message)])
                # answer = resp[-1].content  # get the content of the last message, which should be the bot's response
                #
                # async def fake_gen():
                #     yield "finished", answer, (n_input_tokens, n_output_tokens), n_first_dialog_messages_removed
                #
                # gen = fake_gen()


        except asyncio.CancelledError:
            # note: intermediate token updates only work when enable_message_streaming=True (config.yml)
            raise

        except Exception as e:
            error_text = f"Something went wrong during completion. Reason: {e}"
            print(error_text)
            await update.message.reply_text(error_text)
            return

        # send message if some messages were removed from the context
        # if n_first_dialog_messages_removed > 0:
        #     if n_first_dialog_messages_removed == 1:
        #         text = "✍️ <i>Note:</i> Your current dialog is too long, so your <b>first message</b> was removed from the context.\n Send /new command to start new dialog"
        #     else:
        #         text = f"✍️ <i>Note:</i> Your current dialog is too long, so <b>{n_first_dialog_messages_removed} first messages</b> were removed from the context.\n Send /new command to start new dialog"
        #     await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    await message_handle_fn()


async def run_bot() -> None:
    application = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .concurrent_updates(True)
        # .rate_limiter(AIORateLimiter(max_retries=5))
        # .post_init(post_init)
        .build()
    )

    document_handler = MessageHandler(filters.ATTACHMENT, media_handler)
    application.add_handler(document_handler)

    application.run_polling()

if __name__ == "__main__":
    run_bot()
    # run_pyrogram()
