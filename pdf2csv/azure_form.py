from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import os
import dotenv
import csv
import pathlib
dotenv.load_dotenv()
endpoint = os.getenv("AZURE_ENDPOINT")
key = os.getenv("AZURE_API_KEY")


pdf_path = "data/exam_dates/tablo.pdf"

document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

with open(pdf_path, "rb") as f:
     poller = document_analysis_client.begin_analyze_document("prebuilt-receipt", f)
     result = poller.result()
tables = result.tables
print(result.tables)

csv_path = "data/exam_dates/tablo.csv"

with open(csv_path, "w", newline="", encoding='utf-8') as f:
         writer = csv.writer(f)
         writer.writerow(["Tarih", "Gün", "Saat", "Ders", "Yer"])  # Başlık satırı
         for table in tables:
             for row in table.rows:
                 row_data = [cell.content for cell in row.cells]
                 writer.writerow(row_data)
               
               
print(f"Tablo verileri {csv_path} dosyasına kaydedildi.")