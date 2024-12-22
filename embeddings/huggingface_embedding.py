from langchain_huggingface import HuggingFaceEmbeddings
from config import HUGGINGFACE_API_KEY

def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
