from config import HUGGINGFACE_API_KEY
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint, HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM

def get_chat_model():
        model_name = "Nexusflow/Athene-V2-Chat"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)

        # Hugging Face Pipeline oluşturma
        hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer, max_length=1024)

        # LangChain ile uyumlu hale getirme
        return HuggingFacePipeline(pipeline=hf_pipeline)