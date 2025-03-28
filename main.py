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

def setup_models():
    """
    Retriever ve chat modelini başlatır.
    """
    # PDF ve Soru Yükleme
    pdf_path = "data/yonetmelik.pdf"
    pdf_documents = load_pdf(pdf_path)

    # Retriever'ı kur
    retriever = setup_retriever(
        pdf_documents,
        embedding_models["bert"](),
        db_name="chroma_bert"
    )

    # Chat modelini yükle
    chat_model = chat_models["deepseek"]()

    return retriever, chat_model

def main():
    # Retriever ve chat modelini başlat
    retriever, chat_model = setup_models()

    # Soruları yükle
    questions = load_questions("data/questions.json")

    # Sonuçları Toplamak İçin
    results = []

    for question in questions:
        # RetrievalQA
        qa_chain = RetrievalQA.from_chain_type(
            llm=chat_model,
            retriever=retriever,
            return_source_documents=True
        )

        # Soruyu çalıştır
        response = qa_chain.invoke({"query": question["query"]})
        results.append({
            "embedding_model": "bert",
            "chat_model": "deepseek",
            "question": question["query"],
            "response": response,
        })

    # Sonuçları Kaydet
    evaluate_responses(results, "results/output.json")
if __name__ == "__main__":
    main()
