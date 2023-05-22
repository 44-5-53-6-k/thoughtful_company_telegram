"""Create a ChatVectorDBChain for question/answering."""
from typing import Optional

from langchain.callbacks import StdOutCallbackHandler
# from langchain.callbacks.base import AsyncCallbackManager
from langchain.callbacks.base import CallbackManager
from langchain.callbacks.tracers import LangChainTracer
from langchain.chains import ChatVectorDBChain
from langchain.chains.chat_vector_db.prompts import (CONDENSE_QUESTION_PROMPT,
                                                     QA_PROMPT)
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from langchain.llms import OpenAIChat
from langchain.vectorstores.base import VectorStore
from langchain.prompts.prompt import PromptTemplate

# from callback import DebuggingCallbackHandler

_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""
CUSTOM_PROMPT_1 = PromptTemplate.from_template(_template)

prompt_template = """Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

{context}

Question: {question}
Helpful Answer:"""
CUSTOM_PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)

_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""
STANDALONE_QUESTION = PromptTemplate.from_template(_template)

prompt_template = """
Your name is Margulan. You're a spiritual mentor to help me better understand my inner self and your philosophy. 
You should reply in a professional yet educative manner. You should provide lots of detail and use everyday life examples.
You should not make information up. If you can't answer because you don't have the information, output a clarifying question and allow me to respond by providing the information. 

Question: {question}
Context from Margulan's knowledge: {context}
Helpful Answer:"""
MARGULAN_ANSWERS = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)


def get_chain(
        vectorstore: VectorStore,
        debugging_callback_handler: Optional[DebuggingCallbackHandler]
) -> ChatVectorDBChain:
    """Create a ChatVectorDBChain for question/answering."""
    # Construct a ChatVectorDBChain with a streaming llm for combine docs
    # and a separate, non-streaming llm for question generation
    manager = CallbackManager([StdOutCallbackHandler()])
    if debugging_callback_handler is not None:
        manager.add_handler(debugging_callback_handler)

    question_gen_llm = OpenAIChat(
        verbose=True,
        callback_manager=manager,
        model_name="gpt-3.5-turbo",
        max_tokens=516,
        temperature=0.2,
    )
    streaming_llm = OpenAIChat(
        callback_manager=manager,
        verbose=True,
        model_name="gpt-4",
        max_tokens=516,
        temperature=0.2,
    )

    question_generator = LLMChain(
        llm=question_gen_llm,
        prompt=STANDALONE_QUESTION,
        callback_manager=manager,
        verbose=True,
    )

    # investigate stuff
    doc_chain = load_qa_chain(
        streaming_llm,
        chain_type="stuff",
        prompt=MARGULAN_ANSWERS,
        callback_manager=manager,
        verbose=True,
    )

    qa = ChatVectorDBChain(
        vectorstore=vectorstore,
        combine_docs_chain=doc_chain,
        question_generator=question_generator,
        callback_manager=manager,
        verbose=True,
    )
    return qa