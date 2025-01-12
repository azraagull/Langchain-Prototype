import google.generativeai as gemini
import os
import dotenv
import pandas as pd
from csv2pdf import convert

dotenv.load_dotenv()

directory_path = "data/exam_dates"


gemini.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = gemini.GenerativeModel("gemini-1.5-pro")

import os
import dotenv
import pandas as pd
from csv2pdf import convert

dotenv.load_dotenv()

gemini.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = gemini.GenerativeModel("gemini-1.5-pro")

directory_path = "data/exam_dates"

for filename in os.listdir(directory_path):
    file_path = os.path.join(directory_path, filename)
    if os.path.isfile(file_path):
        sample_file = gemini.upload_file(path=file_path, display_name=filename)
        print(f"File {filename} uploaded successfully")

        response = model.generate_content([sample_file, "Senden bu dosyayı CSV formatında vermeni istiyorum. Tarih, Gün, Saat, Sınav, Yer  başlıkları altında düzenle. Eğer boş olan alanlar var ise boş bırak ve CSV dosyasına ekleme. Eğer yer kısmında birden fazla yer varsa bunları virgül ile değil boşluk ile ayır. Ayrıca bu çıktıyı direkt olarak kaydedececğim için herhangi bir yorum ekleme sadece CSV formatını ver."])
        output_file_path_csv = f"data/tables/CSV/{filename}.csv"
        output_file_path_pdf = f"data/tables/PDF/{filename}.pdf"
        with open(output_file_path_csv, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        f.close()
        if f.closed:
            pd.read_csv(output_file_path_csv,encoding='utf-8').dropna().to_csv(output_file_path_csv, index=False, encoding='utf-8')
            convert(source=output_file_path_csv, destination=output_file_path_pdf, font="fonts/Roboto-Regular.ttf")

        


