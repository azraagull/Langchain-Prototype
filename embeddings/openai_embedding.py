from langchain_openai import OpenAIEmbeddings
from config import OPENAI_API_KEY

def get_embedding_model():
    return OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
