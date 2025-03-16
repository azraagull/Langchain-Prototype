from fastapi import FastAPI, Request
import httpx
from main import setup_models
from config import TELEGRAM_BOT_TOKEN, UPLOAD_DIR_TG
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
import os
import tempfile
import uuid
from typing import List

app = FastAPI()

# Telegram bot token ve API URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Modelleri ve retriever'ı kur
retriever, chat_model = setup_models()

os.makedirs(UPLOAD_DIR_TG, exist_ok=True)

def load_documents_from_file(file_path: str) -> List:
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".docx":
        loader = Docx2txtLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path)
    else:
        raise ValueError(f"Desteklenmeyen dosya tipi: {ext}")
    
    return loader.load()

async def download_file(file_id: str, file_extension: str) -> str:
      async with httpx.AsyncClient() as client:
        response = await client.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}")
        response.raise_for_status()
        file_path_tg = response.json()["result"]["file_path"]
        
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path_tg}"    
        response = await client.get(download_url)
        response.raise_for_status()
        
        tempdir = tempfile.mkdtemp()
        file_path = os.path.join(tempdir, f"{uuid.uuid4()}{file_extension}")
        
        with open(file_path, "wb") as file:
            file.write(response.content)
        return file_path
        
# Telegram webhook endpoint'i
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text")
    document = message.get("document")

    if not chat_id:
        return {"status": "ok", "message": "Chat ID bulunamadı."}

    query = None  # Initialize query here

    if text:
        query = text
    elif document:
        file_id = document.get("file_id")
        file_name = document.get("file_name", "unknown")
        file_extension = os.path.splitext(file_name)[1]
        
        try:
            file_path = await download_file(file_id, file_extension)
            documents = load_documents_from_file(file_path)
            
            retriever.add_documents(documents)
            query = "Sana gönderdiğim bu dosyayı incele sana bu dosya üzerinden sorular soracağım ve bu dosyayı göz önüne alarak cevap vermeni istiyorum."
        except Exception as e:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{TELEGRAM_API_URL}/sendMessage",
                    json={"chat_id": chat_id, "text": f"Dosya yüklenirken bir hata oluştu: {e}"}
                )
                return {'status': "error", 'message': str(e)}
        finally:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
                os.rmdir(os.path.dirname(file_path))

    # This check should be OUTSIDE the elif document block
    if query is None:  
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "Lütfen yazı ya da bir doküman gönderin."}
            )
        return {'status': "ok"}

    # Sistem mesajını içeren bir prompt şablonu oluştur
    prompt_template = """
        Sen Ondokuz Mayıs Üniversitesi adına çalışan yardımcı bir sohbet robotusun. 
        İsmin OkAI. Sana sorulan sorulara doğru, hızlı ve dostane bir şekilde cevap ver. 
        Eğer doğru cevabı bilmiyorsan cevabı bilmediğini kullanıcıya bildir.
    {context}

    Soru: {question}
    Cevap:"""

    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    # RetrievalQA zincirini oluştururken, chain_type_kwargs ile prompt'u özelleştir.
    qa_chain = RetrievalQA.from_chain_type(
        llm=chat_model,
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT},
    )


    # LLM'e soru sor ve cevabı kullanıcıya ilet.
    response = qa_chain.invoke({"query": query})
    response_text = response["result"]

    # Telegram'a cevap gönder
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": f"{response_text} \ {response['source_documents']}"}
        )
    return {"status": "ok"}