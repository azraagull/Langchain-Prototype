from langchain_community.document_loaders import PyPDFLoader
import json

def load_pdf(pdf_path):
    loader = PyPDFLoader(pdf_path)
    return loader.load()

def load_questions(json_path):
    with open(json_path, "r") as file:
        return json.load(file)
