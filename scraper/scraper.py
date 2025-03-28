import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bs4 import BeautifulSoup
import requests
from lxml import html
from config import DB_HOST, DB_PORT, DB_USERNAME_SCRAPER, DB_PASSWORD_SCRAPER, DB_NAME_SCRAPER
import mysql.connector
from datetime import datetime
import dateparser
import urllib.parse
import logging  # Logging modülünü ekledik

#TODO: Multithreading ile hızlandır, eem-makine-end için veri çekme sorunlarına göz at, asenkron hale getir

# -*- coding:utf-8 -*-

# Loglama ayarları
LOG_FILE = 'scraper.log'
LOG_LEVEL = logging.INFO  # Hata ayıklama için DEBUG, normal çalışma için INFO
logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')
PROJECT_DIR = os.path.dirname(os.path.abspath(__name__))
PAGINATION = 1

try:
    db = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USERNAME_SCRAPER,
        password=DB_PASSWORD_SCRAPER,
        database=DB_NAME_SCRAPER
    );
    cursor = db.cursor()
    logging.info("Veritabanı bağlantısı başarılı.")
except mysql.connector.Error as e:
    logging.error(f"Veritabanı bağlantı hatası: {e}")
    sys.exit(1) # Veritabanına bağlanamazsak programı durdur

url_list = {
    'bilgisayar-muhendisligi': 'https://bil-muhendislik.omu.edu.tr', # Bilgisayar Mühendisliği
    'cevre-muhendisligi': 'https://cev-muhendislik.omu.edu.tr', # Çevre Mühendisliği
    'elektrik-elektronik-muhendisligi': 'https://eem-muhendislik.omu.edu.tr', # Elektrik Elektronik Mühendisliği
    'insaat-muhendisligi': 'https://ins-muhendislik.omu.edu.tr', # İnşaat Mühendisliği
    'endustri-muhendisligi': 'https://end-muhendislik.omu.edu.tr', # Endüstri Mühendisliği
    'gida-muhendisligi': 'https://gida-muhendislik.omu.edu.tr', # Gıda Mühendisliği
    'harita-muhendisligi': 'https://hrt-muhendislik.omu.edu.tr', # Harita Mühendisliği
    'kimya-muhendisligi': 'https://kim-muhendislik.omu.edu.tr', # Kimya Mühendisliği
    'makine-muhendisligi': 'https://mak-muhendislik.omu.edu.tr', # Makine Mühendisliği
    'metalurji-ve-malzeme-muhendisligi': 'https://mlz-muhendislik.omu.edu.tr', # Metalurji ve Malzeme Mühendisliği
} 

class PageContent:
    def __init__(self, title="", content="", author="", date="", department="", url=""):
        self.title = title
        self.content = content
        self.author = author
        self.date = date
        self.department = department
        self.url = url
    def __str__(self):
        return f"Title: {self.title}\nURL: {self.url}\nDepartment: {self.department}\nAuthor: {self.author}\nDate: {self.date}\nContent: {self.content}"

page_urls = {}
paginated_urls = {}
suffix = '/haberler/'
   
def create_paginated_url(url, page):
    return f"{url}{suffix}page:{page}"

def fill_paginated_urls(department, url):
    paginated_urls[department] = []
    for i in range(1, PAGINATION + 1):
        paginated_urls[department].append(create_paginated_url(url, i))
        
        
def get_page_urls():
    global page_urls
    logging.info("Sayfa URL'leri alınıyor...")
    for department, urls in paginated_urls.items():
        page_urls[department] = []  # Her bölüm için URL listesini sıfırla
        for url in urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                for link in soup.find_all('article', class_='news-item'):
                    if link and link.find('a'):
                        page_url = link.find('a')['href'].strip()
                        page_urls[department].append(f"{url_list[department]}{page_url}") # Tam URL olarak kaydet
                    else:
                        logging.warning(f"'{url}' adresindeki sayfada haber bağlantısı bulunamadı.")
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Hata oluştu ({url}): {e}")
            except Exception as e:
                logging.exception(f"Hata oluştu ({url}): {e}")
    page_urls = {k: list(dict.fromkeys(v)) for k, v in page_urls.items()} # Tekrar eden sayfa URL'lerini temizle
    logging.info("Sayfa URL'leri alındı.")
    
def get_data_from_page(url, department):
    try:
        response = requests.get(url)
        response.raise_for_status()  # HTTP hatalarını kontrol et
        soup = BeautifulSoup(response.text, 'html.parser')

        # Başlık
        title = soup.find('h1', class_='heading-title').text.strip() if soup.find('h1', class_='heading-title') else "Başlık Bulunamadı"
        
        # İçerik
        try:
            content_element = soup.find('div', class_='news-wrapper')
            content_array = content_element.find_all('span') 
            content_array = [span.text.strip() for span in content_array if span.text.strip() != '']  # Boş olmayan span'ları al
            content_array = list(dict.fromkeys(content_array)) # Tekrar eden paragrafları temizle

            content = "".join(content_array)  # Listeyi birleştir
            if content == "" or content is None or content == " " or content == "\n":
                content_array = content_element.find_all('p')  # Eğer içerik boşsa p etiketlerini al
                content_array = [p.text.strip() for p in content_array if (p.text.strip() != '')] 
                content_array.pop(0) # Yazar bilgisi olan ilk paragrafı çıkar
                # remove duplicate paragraphs
                content_array = list(dict.fromkeys(content_array)) # Tekrar eden paragrafları temizle
                content = "".join(content_array)  # Listeyi birleştir
            print(content)
        except Exception as e:
            logging.error(f"İçerik alma hatası ({url}): {e}")
            content = "İçerik Bulunamadı"
            
        # Yazar ve Tarih
        meta = soup.find('p', class_='meta text-muted')
        if meta:
            author_text = meta.text.strip()
            author = author_text.split('|')[0].replace("Yazar:", "").strip()
            date = author_text.split('|')[1].replace("Tarih:", "").strip()
            date = convert_date_string_to_date(date)
            year = date.split('-')[0] if date else "0000"
        else:
            author = "Yazar Bulunamadı"
            date = "0000-00-00"  # Tarih bilgisi yoksa varsayılan bir tarih kullan
            logging.warning(f"Yazar veya tarih bilgisi bulunamadı: {url}")

        title = title.encode('utf-8', 'ignore').decode('utf-8') if title else "Başlık Bulunamadı"
        content = content.encode('utf-8', 'ignore').decode('utf-8') if content else "İçerik Bulunamadı"
        

        # PageContent nesnesi oluştur
        page_data = PageContent(title=title, content=content, author=author, date=date, department=department, url=url)
        # Veritabanına kaydet
        page_id = save_page_content_to_db(page_data) # Sayfa içeriğini veritabanına kaydet
        # Ekleri veritabanına kaydet
        save_attachments_to_db(soup=soup, department=department, page_content_id = page_id, year = year) # Ekleri veritabanına kaydet
        return page_data
    except requests.exceptions.RequestException as e:
        logging.error(f"Hata oluştu ({url}): {e}")
        return None  # Hata durumunda None döndür

    except Exception as e:
        logging.exception(f"Beklenmedik bir hata oluştu ({url}): {e}")
        return None
    
def convert_date_string_to_date(date_string):
    try:
        date = dateparser.parse(date_string, languages=['tr'])
        formatted_date = date.strftime("%Y-%m-%d") if date else None
        return formatted_date
    except Exception as e:
        logging.error(f"Tarih dönüştürme hatası: {e}")
        formatted_date = None
        return formatted_date

def save_page_content_to_db(page_data):
    try:
        sql = "INSERT INTO PageContent(title, content, author, date, department, url) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (
            page_data.title, page_data.content, page_data.author, page_data.date, page_data.department, page_data.url
        )
        cursor.execute(sql, val)
        db.commit()
        page_id = cursor.lastrowid
        logging.info(f"Başlık: {page_data.title} - ID: {page_id} olarak kaydedildi.")
        return page_id
    except Exception as e:
        logging.error(f"Veritabanına kaydetme hatası: {e}")
        return None

def save_attachments_to_db(soup, department, page_content_id, year):
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')):
            absolute_url = f"{url_list[department]}{href}"
        else:
            continue
        try:
            # Dosya adını ve uzantısını ayrıştır
            
            file_name = os.path.basename(absolute_url)
            file_name, file_extension = os.path.splitext(file_name)
            file_extension = file_extension[1:]
            # Dosyanın kaydedileceği yolu belirle
            os.makedirs(f"{PROJECT_DIR}/assets/{year}/{department}/{file_extension}", exist_ok=True)  # Dizin oluştur
            file_path = f"{PROJECT_DIR}/assets/{year}/{department}/{file_extension}/{file_name}.{file_extension}"  # Dosya yolu
            # Dosyayı indir ve kaydet
            response = requests.get(absolute_url, stream=True) #stream=True ile büyük dosyaları indirirken bellek kullanımını azaltırız.
            response.raise_for_status()  # HTTP hatalarını kontrol et
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192): #8192, chunk size'ı temsil eder (8KB).
                    file.write(chunk) #Dosyayı parça parça yazarak bellek verimliliğini artırırız.
            # Veritabanına kaydet
            sql = "INSERT INTO Attachments (page_content_id, file_name, file_type, file_path) VALUES (%s, %s, %s, %s)"
            val = (page_content_id, file_name.encode('utf-8'), file_extension.encode('utf-8'), file_path.encode('utf-8'))
            cursor.execute(sql, val)  #Cursor nesnesini kullan
            db.commit() # Bağlantı nesnesini kullan
            logging.info(f"Ek dosya indirildi ve kaydedildi: {file_path}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Dosya indirme hatası: {e}")
        except Exception as e:
            logging.exception(f"Ek dosya işleme hatası: {e}")
                    


def main():
    # URL'leri doldur
    for department, url in url_list.items():
        fill_paginated_urls(department, url)
    
    # Başlıkları ve sayfa URL'lerini al
    get_page_urls()
    
    # Her sayfa için verileri al ve veritabanına kaydet
    for department, urls in page_urls.items():
        for url in urls:
            page_data = get_data_from_page(url, department)
            if page_data:
                print(page_data)  # Sayfa içeriğini yazdır
                print("\n" + "="*50 + "\n")  # Ayırıcı
            logging.info(f"{department} bölümündeki sayfalar için işlem tamamlandı.")
                
if __name__ == "__main__":
    main()
    #get_data_from_page("https://bil-muhendislik.omu.edu.tr/tr/haberler/duyuru-tbfiz124-fizik-ii-ve-tbfiz122-fizik-ii-dersini-alan-ogrencilerin-dikkatine", "bilgisayar-muhendisligi")