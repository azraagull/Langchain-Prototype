from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

def setup_retriever(documents, embedding_model, db_name="chroma_db"):
    """
    Optimize edilmiş Chroma retriever setup.
    - Veritabanı zaten varsa, yeniden oluşturmaz.
    - Yeni belgeler eklenirse, sadece bu belgeleri ekler.
    """
    # Veritabanı dizinini belirle
    chroma_db_path = f"{db_name}_db"

    # Eğer veritabanı dizini yoksa veya boşsa, yeni bir veritabanı oluştur
    if not os.path.exists(chroma_db_path) or not os.listdir(chroma_db_path):
        # Text splitter ile metinleri böl
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=40)
        texts = text_splitter.split_documents(documents)

        # Chroma vektör veri tabanı oluştur
        vectorstore = Chroma.from_documents(
            texts, embedding_model, persist_directory=chroma_db_path
        )
    else:
        # Mevcut veritabanını yükle
        vectorstore = Chroma(persist_directory=chroma_db_path, embedding_function=embedding_model)

    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})