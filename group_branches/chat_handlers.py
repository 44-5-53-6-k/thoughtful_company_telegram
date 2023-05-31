from langchain.agents import Tool
from langchain.memory import ConversationBufferMemory, MongoDBChatMessageHistory
from langchain.chat_models import ChatOpenAI
from langchain.utilities import SerpAPIWrapper
from langchain.agents import initialize_agent
from langchain.agents import AgentType
from getpass import getpass

import yaml
import os
import datetime
import cohere

from telegram import Update
from telegram.ext import ContextTypes

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["OPENAI_API_KEY"] = config_data['openai_api_key']
os.environ["COHERE_API_KEY"] = config_data['cohere_api_key']

llm = ChatOpenAI(openai_api_key=os.getenv("OPENAI_API_KEY"), temperature=0, model_name="gpt-4")
co = cohere.Client(os.getenv("COHERE_API_KEY"))

from vector_store import init_vectorstore
vectorstore = init_vectorstore()
print("init vectorstore")

def embed_message(message):
    vector = co.embed(
        texts=[message],
        model="embed-multilingual-v2.0",
    ).embeddings[0]

    return vector


def retreive_search_results(search_term):
    vector = embed_message(search_term)

    docs = vectorstore.similarity_search_by_vector(vector)
    docs = [doc for doc in docs if doc.page_content is not None and len(doc.page_content) > 0]

    max_docs = 5
    docs_length = len(docs)
    range_value = min(max_docs, docs_length)
    knowledge_context = "\n".join([f"Document {i + 1}: {docs[i].page_content}" for i in range(0, range_value)])

    return knowledge_context


tools = [
    Tool(
        name="Search Margulan's knowledge base",
        func=retreive_search_results,
        description="Provides search results from Margulan's knowledge base"
    ),
]

def init_memory(conversation_id):
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    agent_chain = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, verbose=True,
                                   memory=memory)

    print("Agent created for topic: ", conversation_id)
    return memory

def create_agent_from_memory(chat_history):
    chat_memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    chat_memory.chat_memory.messages = chat_history
    # chat_memory.chat_memory.messages = [ChatMessage(**message) for message in data['chat_history']]
    agent_chain = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, verbose=True,
                                   memory=chat_memory)

    return agent_chain
