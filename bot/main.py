import os
import logging
import asyncio
import traceback
import html
import json
import tempfile
from typing import Optional, Any, Dict, List, Union
from uuid import UUID
import uuid

from langchain import LLMChain
from langchain.chains.conversation.base import ConversationChain
from langchain.memory import ConversationBufferMemory
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import pydub
from pathlib import Path
from datetime import datetime
import openai


import telegram
from telegram import (
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    AIORateLimiter,
    filters
)
from langchain.chat_models import ChatOpenAI
from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import HumanMessage, BaseMessage, AIMessage, SystemMessage, LLMResult

from telegram.constants import ParseMode, ChatAction

import config
import database
import openai_utils

user_semaphores = {}


class MyCallbackHandler(AsyncCallbackHandler):
    """Async callback handler that can be used to handle callbacks from langchain."""

    def __init__(self, bot, chat_id):
        self.bot = bot
        self.placeholder_message = None
        self.cancel_reply_markup = None
        self.prev_answer = ""
        self.tokens = []
        self.chat_id = chat_id

    async def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[BaseMessage]],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        # placeholder_message = await update.message.reply_text("...")
        # change to self.bot
        placeholder_message = await self.bot.send_message(chat_id=self.chat_id, text="...")
        self.placeholder_message = placeholder_message

        cancel_button = InlineKeyboardButton("Cancel generation",
                                             callback_data=f"cancel_{placeholder_message.message_id}")
        self.cancel_reply_markup = InlineKeyboardMarkup([[cancel_button]])

        keyboard = [[cancel_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # send the message with the keyboard
        # update keyboard for the message with id = placeholder_message.message_id
        await placeholder_message.edit_text("...", reply_markup=reply_markup)
        return

    async def on_llm_end(
            self,
            response: LLMResult,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        # change reply markup to vote buttons
        keyboard = [[InlineKeyboardButton("👍", callback_data=f"like_{self.placeholder_message.message_id}"),
                     InlineKeyboardButton("👎", callback_data=f"dislike_{self.placeholder_message.message_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.bot.edit_message_reply_markup(chat_id=self.chat_id,
                                                 message_id=self.placeholder_message.message_id,
                                                 reply_markup=reply_markup)

    async def on_llm_error(
            self,
            error: Union[Exception, KeyboardInterrupt],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> None:
        print("on_llm_error")
        print(error)

    async def on_llm_new_token(self, token: str, *, run_id: UUID, parent_run_id: Optional[UUID] = None,
                               **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""

        self.tokens.append(token)  # add new token to the list
        message = ''.join(self.tokens)  # create a message from all gathered tokens

        gen_item = token  # assuming that gen_item is token
        # status, answer, (n_input_tokens, n_output_tokens), n_first_dialog_messages_removed = gen_item

        # answer = answer[:4096]  # telegram message limit
        if (len(message) > 4096):
            message = message[:4096]
        #     TODO imporve this to send new message instead

        # if message is empty or if it is the same, do not send
        if len(message) == 0 or message == self.prev_answer:
            return

        try:
            await self.bot.edit_message_text(message, chat_id=self.placeholder_message.chat_id,
                                             message_id=self.placeholder_message.message_id,
                                             parse_mode=ParseMode.HTML, reply_markup=self.cancel_reply_markup)
        except telegram.error.BadRequest as e:
            if str(e).startswith("Message is not modified"):
                pass
            else:
                await self.bot.edit_message_text(message, chat_id=self.placeholder_message.chat_id,
                                                 message_id=self.placeholder_message.message_id)

        await asyncio.sleep(0.005)  # wait a bit to avoid flooding

        self.prev_answer = message


async def message_handle(update: Update, context: CallbackContext, message=None, use_new_dialog_timeout=True):
    print("message_handle")
    # check if bot was mentioned (for group chats)

    # check if message is edited
    _message = message or update.message.text

    # remove bot mention (in group chats)
    if update.message.chat.type != "private":
        _message = _message.replace("@" + context.bot.username, "").strip()

    user_id = update.message.from_user.id

    async def message_handle_fn():
        # new dialog timeout

        # in case of CancelledError
        n_input_tokens, n_output_tokens = 0, 0

        try:
            await update.message.chat.send_action(action="typing")

            if _message is None or len(_message) == 0:
                await update.message.reply_text("🥲 You sent <b>empty message</b>. Please, try again!", parse_mode=ParseMode.HTML)
                return

            # parse_mode = {
            #     "html": ParseMode.HTML,
            #     "markdown": ParseMode.MARKDOWN
            # }

            callback_handler = MyCallbackHandler(context.bot, update.message.chat_id )
            # streaming_flag = config.enable_message_streaming and len(dialog_messages) > 0
            streaming_flag = True
            prompt_template = "Roleplay: Provide the dumbest and the most absurd answer to it."


            if streaming_flag:
                chat = ChatOpenAI(temperature=0.2, openai_api_key="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",
                                  callbacks=[callback_handler], streaming=streaming_flag)
                # Create your list of messages.
                # Here we're just sending a single message from a hypothetical user "Alice".

                # Asynchronously generate a chat response.
                batch_messages = [
                    [
                        SystemMessage(content="Roleplay: Provide the dumbest and the most absurd answer to it."),
                        HumanMessage(content=_message)
                    ],
                ]
                result = await chat.agenerate(batch_messages)
                # print(result)

            else:
                chat = ChatOpenAI(temperature=0.2, openai_api_key="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",
                                  streaming=streaming_flag)
                memory = ConversationBufferMemory()
                llm_chain = ConversationChain(
                    llm=chat,
                    prompt=prompt_template,
                    memory=memory,
                )
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


def run_bot() -> None:
    application = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .concurrent_updates(True)
        # .rate_limiter(AIORateLimiter(max_retries=5))
        # .post_init(post_init)
        .build()
    )

    # add handlers
    user_filter = filters.ALL
    # if len(config.allowed_telegram_usernames) > 0:
    #     usernames = [x for x in config.allowed_telegram_usernames if isinstance(x, str)]
    #     user_ids = [x for x in config.allowed_telegram_usernames if isinstance(x, int)]
    #     user_filter = filters.User(username=usernames) | filters.User(user_id=user_ids)

    # application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    # application.add_handler(CommandHandler("help", help_handle, filters=user_filter))
    # application.add_handler(CommandHandler("help_group_chat", help_group_chat_handle, filters=user_filter))
    #
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, message_handle))
    # add handler for callback buttons


    # application.add_handler(CommandHandler("retry", retry_handle, filters=user_filter))
    # application.add_handler(CommandHandler("new", new_dialog_handle, filters=user_filter))
    # application.add_handler(CommandHandler("cancel", cancel_handle, filters=user_filter))
    #
    # application.add_handler(MessageHandler(filters.VOICE & user_filter, voice_message_handle))

    # application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    # application.add_handler(CallbackQueryHandler(show_chat_modes_callback_handle, pattern="^show_chat_modes"))
    # application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))
    #
    # application.add_handler(CommandHandler("settings", settings_handle, filters=user_filter))
    # application.add_handler(CallbackQueryHandler(set_settings_handle, pattern="^set_settings"))
    #
    # application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))
    #
    # application.add_error_handler(error_handle)

    # start the bot
    application.run_polling()


if __name__ == "__main__":
    run_bot()
