from langchain_huggingface import HuggingFaceEmbeddings
from config import HUGGINGFACE_API_KEY

def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="emrecan/bert-base-turkish-cased-mean-nli-stsb-tr")
