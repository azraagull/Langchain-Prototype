import json

def evaluate_responses(results, output_path):
    def serialize_document(doc):
        return {
            "page_content": doc.page_content,  # Belgenin içeriği
            "metadata": doc.metadata           # Belgeye ait metadata
        }
    
    # `source_documents` içindeki `Document` nesnelerini serileştirilebilir hale getir
    for result in results:
        if "source_documents" in result["response"]:
            result["response"]["source_documents"] = [
                serialize_document(doc) for doc in result["response"]["source_documents"]
            ]
    
    # Sonuçları JSON dosyasına yaz
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

    print(f"Results saved to {output_path}")
