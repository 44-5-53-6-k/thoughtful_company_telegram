"""Main api point."""
from typing import Optional

from langchain.chains import ChatVectorDBChain
from langchain.vectorstores import VectorStore

# from callback import DebuggingCallbackHandler
# from query_data import get_chain
from callback import DebuggingCallbackHandler
from query_data import get_chain
import weaviate
from langchain.vectorstores import Weaviate
import os



def init_vectorstore():
    WEAVIATE_URL = "https://6mvrfnrrtdgvrb40m7uqjw.gcp.weaviate.cloud"
    client = weaviate.Client(
        url=WEAVIATE_URL,
        additional_headers={
            'X-OpenAI-Api-Key': os.environ['OPENAI_API_KEY'],
            'X-Cohere-Api-Key': "8b18i6iTWMmFAQIdb8QY61ge8U8Q8iRwMVad8H1S",
        },
        auth_client_secret=weaviate.AuthApiKey("VkEhJ9R00YBnpgvmhqnx8kwbT1TNOKJBFzAw")
    )
    # global vectorstore
    return Weaviate(client, "NotionPage", "answer")


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
    qa_chain = get_chain(vectorstore)
    return qa_chain