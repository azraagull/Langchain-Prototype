from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY

def get_chat_model():
    return ChatOpenAI(model="gpt-4", openai_api_key=OPENAI_API_KEY)
