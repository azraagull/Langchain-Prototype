from langchain_community.llms import Ollama

def get_chat_model():
    return Ollama(model="llama3", base_url="http://localhost:11434")
