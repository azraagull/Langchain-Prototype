from langchain.text_splitter import RecursiveCharacterTextSplitter

def get_text_splitter(chunk_size=500, chunk_overlap=40):
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
