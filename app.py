from fastapi import FastAPI, Request, HTTPException
import httpx
from main import setup_models  # main.py'den setup_models fonksiyonunu içe aktar
from config import TELEGRAM_BOT_TOKEN
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

app = FastAPI()


# Telegram bot token ve API URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Modelleri ve retriever'ı kur
retriever, chat_model = setup_models()


# Telegram webhook endpoint'i
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text")
    pdf = message.get("document")  # TODO: PDF ve görsel dosyalar için destek sağla.

    # Hata döndürmek yerine kullanıcıyı bilgilendir!
    if not chat_id or not text:  # Text kontrolü önemli.
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": "Üzgünüm, şu anda sadece metin mesajlarına yanıt verebilirim."}
            )
        return {"status": "ok"}


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
        chain_type_kwargs={"prompt": PROMPT},  # System mesajını LLM'e ilet.
    )


    # LLM'e soru sor ve cevabı kullanıcıya ilet.
    response = qa_chain.invoke({"query": text})
    response_text = response["result"]

    # Telegram'a cevap gönder
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": response_text}
        )
    return {"status": "ok"}