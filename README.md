# OkAI Sohbet Robotu Prototip Uygulaması

Bu proje, farklı dil modellerinin performansını değerlendirmek amacıyla oluşturulmuş bir prototiptir. Proje, çeşitli dil modellerini ve embedding modellerini kullanarak sorulara yanıt verir ve sonuçları değerlendirir.

## Gereksinimler

Projeyi çalıştırmak için aşağıdaki bağımlılıkların yüklü olması gerekmektedir:

- Python 3.7+ (Biz Python 3.11.9 Kullandık)
- `langchain`
- `langchain_anthropic`
- `langchain_chroma`
- `langchain_cohere`
- `langchain_community`
- `langchain_huggingface`
- `langchain_openai`
- `langchain_text_splitters`
- `python-dotenv`
- `transformers`

Bağımlılıkları yüklemek için aşağıdaki komutu çalıştırabilirsiniz:

```sh
pip install -r requirements.txt
```

## Kurulum

1. Projeyi İndirin ve Dizine Girin

```
git clone https://github.com/azraagull/Langchain-Prototype.git
cd Langchain-Prototype
```

2. Ortam Değişkeni Dosyasını Düzenleme

```
mv sample.env .env
Ardından gerekli olan API Anahtarlarını Giriniz.
```

3. Gerekli Kütüphanelerin Kurulması ve Sanal Ortam Oluşturma

```
python -m venv OkAI-Proto
scripts/activate # Windows
source OkAI-Proto/bin/activate # Linux & Mac
pip install -r requirements.txt
```

4. Projeyi Çalıştırmak

```
python main.py
```

## Dosya Yapısı

```
├── chat_models/
│   ├── anthropic_chat.py
│   ├── deepseek_chat.py
│   ├── huggingface_chat.py
│   ├── ollama_chat.py
│   └── openai_chat.py
├── chroma_bert_db/
│   └── chroma.sqlite3
├── config.py
├── data/               # PDF Dosylarını Buraya Yükleyin
│   └── questions.json
├── embeddings/
│   ├── bert_embedding.py
│   ├── cohere_embedding.py
│   ├── huggingface_embedding.py
│   ├── instructor_embedding.py
│   ├── openai_embedding.py
│   └── sentence_transformer_embedding.py
├── main.py
├── README.mdre
├── requirements.txt
├── results/          # LLM'den Gelen Cevaplar Tutulur
│   └── output.json
├── retriever/
│   └── retriever.py
├── sample.env
└── utils/
    ├── evaluator.py
    ├── loader.py
    └── splitter.py
```

## Notlar

Tasarım raporunda kullanılan GPT4-o ile DeepSeek V2.5'in karşılaştırmasında kullandığımız ve sonuçları içeren JSON dosyasına [buradan ulaşabilirsiniz.](https://github.com/azraagull/Langchain-Prototype/blob/main/results/OpenAI%20vs%20DeepSeek%20V2.5.json) \
Ayrıca soruları yanıtlamak için kullandığımız PDF dosyasına [bu bağlantıdan](https://kms.kaysis.gov.tr/Home/Goster/193844?AspxAutoDetectCookieSupport=1) ve [bu bağlantıdan](https://github.com/azraagull/Langchain-Prototype/blob/8fd92a84720e9eb914ad4d38aa99d7a245b376dd/data/yonetmelik.pdf) ulaşabilirsiniz.
