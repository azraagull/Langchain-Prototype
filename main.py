from langchain.chains import RetrievalQA
from embeddings import (
    openai_embedding, huggingface_embedding, sentence_transformer_embedding,
    cohere_embedding, instructor_embedding, bert_embedding
)
from chat_models import (
    openai_chat, huggingface_chat, anthropic_chat, deepseek_chat
)
from retriever.retriever import setup_retriever
from utils.loader import load_pdf, load_questions
from utils.evaluator import evaluate_responses

# Embedding ve Chat Modelleri
embedding_models = {
    "bert": bert_embedding.get_embedding_model,
    # "openai": openai_embedding.get_embedding_model,
    # "huggingface": huggingface_embedding.get_embedding_model,
    # "sentence_transformer": sentence_transformer_embedding.get_embedding_model,
    # "cohere": cohere_embedding.get_embedding_model,
    # "instructor": instructor_embedding.get_embedding_model,
}

chat_models = {
    # "anthropic": anthropic_chat.get_chat_model,
    "deepseek": deepseek_chat.get_chat_model,
    # "openai": openai_chat.get_chat_model,
    # "huggingface": huggingface_chat.get_chat_model,
}

def main():
    # PDF ve Soru Yükleme
    pdf_path = "data/yonetmelik.pdf"
    pdf_documents = load_pdf(pdf_path)

    questions = load_questions("data/questions.json")

    # Sistem Mesajı
    system_message = {
        "role": "system",
        "content": "Sen bir öğrenci destek platformu için yapılan sohbet botusun. Sadece sana verilen veriler üzerinden yorumlama yap ve halüsinasyon veri oluşturma."
    }

    # Sonuçları Toplamak İçin
    results = []

    # Her embedding modeli için ayrı koleksiyon
    for emb_name, emb_model_func in embedding_models.items():
        embedding_model = emb_model_func()
        retriever = setup_retriever(
            pdf_documents,
            embedding_model,
            db_name=f"chroma_{emb_name}"
        )

        for chat_name, chat_model_func in chat_models.items():
            chat_model = chat_model_func()

            for question in questions:
                # RetrievalQA
                qa_chain = RetrievalQA.from_chain_type(
                    llm=chat_model,
                    retriever=retriever,
                    return_source_documents=True
                )

                # Soruyu ve sistem mesajını birleştirerek çalıştır
                combined_query = {
                    "messages": [
                        system_message,
                        {"role": "user", "content": question["query"]}
                    ]
                }
                response = qa_chain.invoke(combined_query)

                # Sonuçları kaydet
                results.append({
                    "embedding_model": emb_name,
                    "chat_model": chat_name,
                    "question": question["query"],
                    "response": response,
                })

    # Sonuçları Kaydet
    evaluate_responses(results, "results/output.json")

if __name__ == "__main__":
    main()