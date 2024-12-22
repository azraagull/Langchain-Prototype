from langchain_anthropic import ChatAnthropic
from config import ANTHROPIC_API_KEY

def get_chat_model():
    return ChatAnthropic(model="claude-2", anthropic_api_key=ANTHROPIC_API_KEY)
