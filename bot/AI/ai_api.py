"""Main api point."""
from typing import Optional

from langchain.chains import ChatVectorDBChain
from langchain.vectorstores import VectorStore

from bot.AI.callback import DebuggingCallbackHandler
from bot.AI.query_data import get_chain
import weaviate
from langchain.vectorstores import Weaviate
import os

os.environ['OPENAI_API_KEY'] = "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"
vectorstore: Optional[VectorStore] = None


def init_vectorstore():
    WEAVIATE_URL = "https://ownowfk-margo-ai-jn7jfpch.weaviate.network"
    client = weaviate.Client(
        url=WEAVIATE_URL,
        additional_headers={
            'X-OpenAI-Api-Key': os.environ["OPENAI_API_KEY"],
            'X-Cohere-Api-Key': "8b18i6iTWMmFAQIdb8QY61ge8U8Q8iRwMVad8H1S",
        }
    )
    global vectorstore
    vectorstore = Weaviate(client, "Page", "content")


def get_qa_chain(
        debugging_callback_handler: Optional[DebuggingCallbackHandler] = None
) -> ChatVectorDBChain:
    """
    :returns qa_chain used for question answering
    can be used bot sync and async. Async example:
    await qa_chain.acall(
        {"question": question, "chat_history": chat_history}
    )
    for more info see ChatVectorDBChain
    """
    qa_chain = get_chain(vectorstore, debugging_callback_handler)
    return qa_chain