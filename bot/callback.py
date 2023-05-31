"""Callback handlers used in the app."""
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from langchain.callbacks.base import AsyncCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler
from langchain.input import print_text
from langchain.schema import AgentAction, AgentFinish, LLMResult, BaseMessage
import time

from pyrogram.enums import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram


# from schemas import ChatResponse


# class StreamingLLMCallbackHandler(AsyncCallbackHandler):
#     """Callback handler for streaming LLM responses."""
#
#     def __init__(self, websocket):
#         self.websocket = websocket
#
#     async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
#         resp = ChatResponse(sender="bot", message=token, type="stream")
#         await self.websocket.send_json(resp.dict())
#

# class QuestionGenCallbackHandler(AsyncCallbackHandler):
#     """Callback handler for question generation."""
#
#     def __init__(self, websocket):
#         self.websocket = websocket
#
#     async def on_llm_start(
#             self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
#     ) -> None:
#         """Run when LLM starts running."""
#         resp = ChatResponse(
#             sender="bot", message="Synthesizing question...", type="info"
#         )
#         await self.websocket.send_json(resp.dict())

class TelegramStreamingCallbackHandler(AsyncCallbackHandler):
    """Async callback handler that can be used to handle callbacks from langchain."""

    def __init__(self, bot, chat_id):
        self.bot = bot
        self.placeholder_message = None
        self.cancel_reply_markup = None
        self.prev_answer = ""
        self.tokens = []
        self.chat_id = chat_id
        self.last_update_time = time.time()

    async def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[BaseMessage]],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:

        self.last_update_time = time.time()
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

        if (len(message) > 4096):
            message = message[:4096]
        #     TODO imporve this to send new message instead

        if len(message) == 0 or message == self.prev_answer:
            return

        if time.time() - self.last_update_time < 2:
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

        self.prev_answer = message
        self.last_update_time = time.time()


class DebuggingCallbackHandler(BaseCallbackHandler):
    """Callback Handler that prints to std out."""
    data = []
    total_tokens: int = 0

    def get_data_and_reset(self):
        data = self.data
        self.data = []
        return data

    def get_tokens_and_reset(self):
        data = self.total_tokens
        self.total_tokens = 0
        return data

    def log_text(self, text):
        self.data.append(text)

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Print out the prompts."""
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Collect token usage."""
        if response.llm_output is not None:
            if "token_usage" in response.llm_output:
                token_usage = response.llm_output["token_usage"]
                if "total_tokens" in token_usage:
                    self.total_tokens += token_usage["total_tokens"]

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Do nothing."""
        pass

    def on_llm_error(
            self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Do nothing."""
        pass

    def on_chain_start(
            self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Print out that we are entering a chain."""
        class_name = serialized["name"]
        self.log_text(f"\n\n\033[1m> Entering new {class_name} chain...\033[0m")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Print out that we finished a chain."""
        self.log_text("\n\033[1m> Finished chain.\033[0m")

    def on_chain_error(
            self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Do nothing."""
        pass

    def on_tool_start(
            self,
            serialized: Dict[str, Any],
            input_str: str,
            **kwargs: Any,
    ) -> None:
        """Do nothing."""
        pass

    def on_agent_action(
            self, action: AgentAction, color: Optional[str] = None, **kwargs: Any
    ) -> Any:
        """Run on agent action."""
        self.log_text(action.log)

    def on_tool_end(
            self,
            output: str,
            color: Optional[str] = None,
            observation_prefix: Optional[str] = None,
            llm_prefix: Optional[str] = None,
            **kwargs: Any,
    ) -> None:
        """If not the final action, print out observation."""
        self.log_text(f"\n{observation_prefix}")
        self.log_text(output)
        self.log_text(f"\n{llm_prefix}")

    def on_tool_error(
            self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Do nothing."""
        pass

    def on_text(
            self,
            text: str,
            color: Optional[str] = None,
            end: str = "",
            **kwargs: Optional[str],
    ) -> None:
        """Run when agent ends."""
        self.log_text(text)

    def on_agent_finish(
            self, finish: AgentFinish, color: Optional[str] = None, **kwargs: Any
    ) -> None:
        """Run on agent end."""
        self.log_text(finish.log)