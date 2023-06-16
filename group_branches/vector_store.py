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
    return Weaviate(client, "NotionPage", "answer", attributes=["source"])
