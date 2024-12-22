from langchain_cohere import CohereEmbeddings
from config import COHERE_API_KEY

def get_embedding_model():
    return CohereEmbeddings(cohere_api_key=COHERE_API_KEY, model="embed-english-light-v2.0")
