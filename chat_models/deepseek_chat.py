from langchain_openai import ChatOpenAI
from config import DEEPSEEK_API_KEY

def get_chat_model():
  return ChatOpenAI(
    model='deepseek-chat', 
    openai_api_key=DEEPSEEK_API_KEY, 
    openai_api_base='https://api.deepseek.com',
    max_tokens=1024
  )  