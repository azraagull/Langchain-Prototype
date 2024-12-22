from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
import shutil

def setup_retriever(documents, embedding_model, db_name="chroma_db"):
    """
    Dinamik Chroma retriever setup. Eski koleksiyonu temizler ve yeni bir koleksiyon oluşturur.
    """
    # Veritabanı dizinini dinamik belirleyin
    chroma_db_path = f"{db_name}_db"
    shutil.rmtree(chroma_db_path, ignore_errors=True)

    # Text splitter ile metinleri böl
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=40)
    texts = text_splitter.split_documents(documents)

    # Chroma vektör veri tabanı oluştur
    vectorstore = Chroma.from_documents(
        texts, embedding_model, persist_directory=chroma_db_path
    )

    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
