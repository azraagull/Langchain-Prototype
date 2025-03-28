import sys
import os
from typing import List, Tuple
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bs4 import BeautifulSoup
import requests
from lxml import html
from config import DB_HOST, DB_PORT, DB_USERNAME_SCRAPER, DB_PASSWORD_SCRAPER, DB_NAME_SCRAPER, PAGINATION
import mysql.connector
from datetime import datetime
import dateparser
import urllib.parse
import logging
import chardet
import concurrent.futures
import threading

# -*- coding:utf-8 -*-

# Loglama ayarları
LOG_FILE = 'scraper.log'
LOG_LEVEL = logging.INFO  # Hata ayıklama için DEBUG, normal çalışma için INFO
logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')
PROJECT_DIR = os.path.dirname(os.path.abspath(__name__))

thread_local = threading.local()

def get_db_connection():
    """
    Thread-local veritabanı bağlantısı döndürür.
    Bu fonksiyon, her thread için ayrı bir veritabanı bağlantısı sağlar.
    Bu, çoklu thread'li uygulamalarda eş zamanlı erişim sorunlarını önler.
    """
    if not hasattr(thread_local, "db"):
        try:
            thread_local.db = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USERNAME_SCRAPER,
                password=DB_PASSWORD_SCRAPER,
                database=DB_NAME_SCRAPER
            )
            logging.info(f"Thread {threading.current_thread().name} için veritabanı bağlantısı oluşturuldu.")
        except mysql.connector.Error as e:
            logging.error(f"Thread {threading.current_thread().name} için veritabanı bağlantı hatası: {e}")
            return None  # Bağlantı başarısız olursa None döndür
    return thread_local.db

def get_db_cursor(db):
    """
    Verilen veritabanı bağlantısı için thread-local cursor döndürür.
    Her thread için ayrı bir cursor oluşturarak, veritabanı işlemlerinin
    eş zamanlı ve güvenli bir şekilde yapılmasını sağlar.
    """
    if db and not hasattr(thread_local, "cursor"):
        try:
            thread_local.cursor = db.cursor()
            logging.info(f"Thread {threading.current_thread().name} için cursor oluşturuldu.")
        except mysql.connector.Error as e:
            logging.error(f"Thread {threading.current_thread().name} için cursor oluşturma hatası: {e}")
            return None
    return thread_local.cursor

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
        return (f"PageContent(\n"
            f"  title='{self.title}',\n"
            f"  url='{self.url}',\n"
            f"  department='{self.department}',\n"
            f"  author='{self.author}',\n"
            f"  date='{self.date}',\n"
            f"  content='{self.content[:100]}...'\n"  # İçeriğin tamamını yazdırmak yerine ilk 100 karakteri gösteriyoruz.
            f")")
        
    
page_urls = {}
paginated_urls = {}
suffix = '/haberler/'
   
def create_paginated_url(url, page):
    """
    Verilen URL ve sayfa numarası ile sayfalama (pagination) URL'si oluşturur.
    Örneğin, bir web sitesinin haberler bölümündeki farklı sayfaları belirtmek için kullanılır.
    """
    return f"{url}{suffix}page:{page}"

def fill_paginated_urls(department, url):
    """
    Belirli bir bölüm için sayfalama URL'lerini oluşturur ve saklar.
    Bu fonksiyon, bir bölümün haberler sayfalarının tüm sayfalarına ait URL'leri oluşturur.
    """
    paginated_urls[department] = []
    for i in range(1, PAGINATION + 1):
        paginated_urls[department].append(create_paginated_url(url, i))
        
        
def get_page_urls(department, urls):
    """
    Verilen URL'lerden sayfa URL'lerini alır.
    Belirli bir bölüm için, belirtilen URL'lerdeki haber bağlantılarını (article etiketleri içindeki a etiketleri) bulur.
    """
    logging.info(f"{department} için sayfa URL'leri alınıyor...")
    session = requests.Session()
    department_page_urls = []
    for url in urls:
        try:
            response = session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for link in soup.find_all('article', class_='news-item'):
                if link and link.find('a'):
                    page_url = link.find('a')['href'].strip()
                    department_page_urls.append(f"{url_list[department]}{page_url}") # Tam URL olarak kaydet
                else:
                    logging.warning(f"'{url}' adresindeki sayfada haber bağlantısı bulunamadı.")
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Hata oluştu ({url}): {e}")
        except Exception as e:
            logging.exception(f"Hata oluştu ({url}): {e}")
    department_page_urls = list(dict.fromkeys(department_page_urls)) # Tekrar eden sayfa URL'lerini temizle
    logging.info(f"{department} için sayfa URL'leri alındı.")
    return department_page_urls

def fetch_page_content(url):
    """
    Belirtilen URL'den sayfa içeriğini getirir ve BeautifulSoup nesnesi döndürür.
    Bu fonksiyon, verilen URL'deki HTML içeriğini alır, karakter kodlamasını otomatik olarak tespit eder
    ve içeriği BeautifulSoup nesnesine dönüştürerek ayrıştırma için hazırlar.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        bytes_data = response.content

        # PDF dosyası kontrolü
        if bytes_data.startswith(b'%PDF'):
            logging.warning(f"PDF dosyası bulundu, içerik ayrıştırılamıyor: {url}")
            return None

        # Karakter kodlamasını otomatik olarak tespit et
        encoding = chardet.detect(bytes_data)['encoding']

        # Kodlama None ise varsayılan bir değer kullan
        if encoding is None:
            encoding = 'utf-8'  # veya başka bir uygun varsayılan değer

        text = bytes_data.decode(encoding)
        return BeautifulSoup(text, 'html.parser')
    except requests.exceptions.RequestException as e:
        logging.error(f"Sayfa içeriği getirilirken hata oluştu ({url}): {e}")
        return None
    except Exception as e:
        logging.error(f"Karakter kodlaması tespit edilirken veya çözülürken hata oluştu ({url}): {e}")
        return None

def parse_title(soup, url):
    """
    BeautifulSoup nesnesinden başlığı ayrıştırır.
    Verilen BeautifulSoup nesnesi içindeki 'h1' etiketini bulur ve başlığı elde eder.
    """
    try:
        title_element = soup.find('h1', class_='heading-title')
        return title_element.text.strip() if title_element else "Başlık Bulunamadı"
    except AttributeError:
        logging.warning(f"Başlık ayrıştırılırken hata oluştu: {url}")
        return "Başlık Bulunamadı"

def parse_content(soup, url):
    """
    BeautifulSoup nesnesinden içeriği ayrıştırır.
    Verilen BeautifulSoup nesnesi içindeki metin içeriğini bulur ve temizler.
    """
    content = "İçerik Bulunamadı"
    try:
        content_element = soup.find('div', class_='news-wrapper')
        if content_element:
            content_array = content_element.find_all('span')
            content_array = [span.text.strip() for span in content_array if span.text.strip()]
            content_array = list(dict.fromkeys(content_array))
            content = "".join(content_array)

            if not content:
                content_array = content_element.find_all('p')
                if content_array:
                    content_array = [p.text.strip() for p in content_array if p.text.strip()]
                    if content_array:
                        if len(content_array) > 0:
                            content_array.pop(0)
                        content_array = list(dict.fromkeys(content_array))
                        content = "".join(content_array)
    except Exception as e:
        content = "Ayrıştırma Hatası"
        logging.error(f"İçerik ayrıştırılırken hata oluştu: {url} - {e}")
    return content

def parse_author_and_date(soup, url):
    """
    BeautifulSoup nesnesinden yazar ve tarih bilgilerini ayrıştırır.
    Verilen BeautifulSoup nesnesi içindeki yazar ve tarih bilgilerini bulur ve düzenler.
    """
    author = "Yazar Bulunamadı"
    date = "1000-01-01"
    try:
        meta = soup.find('p', class_='meta text-muted')
        if meta:
            author_text = meta.text.strip()
            author = author_text.split('|')[0].replace("Yazar:", "").strip()
            date = author_text.split('|')[1].replace("Tarih:", "").strip()
            date = convert_date_string_to_date(date)
    except (AttributeError, IndexError) as e:
        logging.warning(f"Yazar veya tarih bilgisi ayrıştırılırken hata oluştu: {url} - {e}")
    return author, date

def convert_date_string_to_date(date_string):
    """
    Tarih stringini tarih formatına dönüştürür.
    Verilen tarih stringini 'YYYY-MM-DD' formatına dönüştürür.
    """
    try:
        date = dateparser.parse(date_string, languages=['tr'])
        formatted_date = date.strftime("%Y-%m-%d") if date else None
        return formatted_date
    except Exception as e:
        logging.error(f"Tarih dönüştürme hatası: {e}")
        formatted_date = None
        return formatted_date

      
def save_page_content_to_db(page_data):
    """
    Veritabanına sayfa içeriğini kaydeder (thread-safe).
    Veritabanında UNIQUE kısıtlaması olduğu için, aynı başlık, departman ve içeriğe sahip
    kayıtlar veritabanı seviyesinde engellenir.
    """
    db = get_db_connection()
    if not db:
        logging.error("Veritabanı bağlantısı yok, kaydetme işlemi atlanıyor.")
        return None
    cursor = get_db_cursor(db)
    if not cursor:
        logging.error("Cursor oluşturulamadı, kaydetme işlemi atlanıyor.")
        return None
    try:
        sql = "INSERT INTO PageContent(title, content, author, date, department, url) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (
            page_data.title, page_data.content, page_data.author, page_data.date, page_data.department, page_data.url
        )
        cursor.execute(sql, val)
        db.commit()
        page_id = cursor.lastrowid
        logging.info(f"Başlık: {page_data.title} - ID: {page_id} olarak kaydedildi (Thread: {threading.current_thread().name}).")
        return page_id
    except mysql.connector.errors.IntegrityError as e:
        logging.warning(f"Aynı URL'ye sahip kayıt zaten var, ekleme yapılamadı: {page_data.title} - {page_data.url} (Thread: {threading.current_thread().name}).")
        # Burada isteğe bağlı olarak varolan kaydın ID'sini bulup döndürebilirsiniz.
        # Ancak bu durumda, varolan kaydın ID'sini bulmak için ek bir sorgu çalıştırmanız gerekir.
        return None  # Veya hata durumunda None döndürmeye devam edebilirsiniz.
    except mysql.connector.Error as e:
        logging.error(f"Veritabanına kaydetme hatası (Thread: {threading.current_thread().name}): {e}")
        return None
    except Exception as e:
        logging.exception(f"Beklenmedik hata (Thread: {threading.current_thread().name}): {e}")
        return None

def save_attachments_to_db(soup, department, page_content_id, year):
    """
    Ek dosyaları veritabanına kaydeder (thread-safe).
    Bu fonksiyon, bir sayfa içeriğine ait ek dosyaları (PDF, DOC, DOCX, XLS, XLSX)
    veritabanına kaydeder ve dosyaları yerel diske indirir.
    """
    db = get_db_connection()
    if not db:
        logging.error("Veritabanı bağlantısı yok, ek dosya kaydetme işlemi atlanıyor.")
        return
    cursor = get_db_cursor(db)
    if not cursor:
        logging.error("Cursor oluşturulamadı, ek dosya kaydetme işlemi atlanıyor.")
        return
    attachment_data: List[Tuple] = []

    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')) and 'oidb' not in href and 'https://' not in href:
            absolute_url = urllib.parse.urljoin(url_list[department], href)
        else:
            continue

        try:
            file_name = os.path.basename(absolute_url)
            file_name, file_extension = os.path.splitext(file_name)
            file_extension = file_extension[1:]

            try:
                os.makedirs(f"{PROJECT_DIR}/assets/{year}/{department}/{file_extension}", exist_ok=True)
            except OSError as e:
                logging.error(f"Dizin oluşturma hatası (Thread: {threading.current_thread().name}): {e}")
                attachment_data.append((page_content_id, "Dizin Oluşturulamadı".encode('utf-8'), "Hata".encode('utf-8'), "Yok".encode('utf-8')))
            file_path = f"{PROJECT_DIR}/assets/{year}/{department}/{file_extension}/{file_name}.{file_extension}"

            response = requests.get(absolute_url, stream=True)
            response.raise_for_status()
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            attachment_data.append((page_content_id, file_name.encode('utf-8'), file_extension.encode('utf-8'), file_path.encode('utf-8')))
            logging.info(f"Ek dosya indirildi ve kaydedildi: {file_path} (Thread: {threading.current_thread().name})")

        except requests.exceptions.RequestException as e:
            logging.error(f"Dosya indirme hatası (Thread: {threading.current_thread().name}): {e}")
            attachment_data.append((page_content_id, "İndirilemedi".encode('utf-8'), "Hata".encode('utf-8'), "Yok".encode('utf-8')))

    if attachment_data:
        try:
            sql = "INSERT INTO Attachments (page_content_id, file_name, file_type, file_path) VALUES (%s, %s, %s, %s)"
            cursor.executemany(sql, attachment_data)
            db.commit()
            logging.info(f"{len(attachment_data)} adet ek dosya veritabanına kaydedildi (Thread: {threading.current_thread().name}).")
        except mysql.connector.Error as e:
            logging.error(f"Toplu ekleme hatası (Thread: {threading.current_thread().name}): {e}")
        except Exception as e:
            logging.exception(f"Beklenmedik Toplu ekleme hatası (Thread: {threading.current_thread().name}): {e}")

def get_data_from_page(url, department):
    """
    Sayfa içeriğini getirir, ayrıştırır ve veritabanına kaydeder.
    Bu fonksiyon, bir URL'den sayfa içeriğini çeker, başlık, içerik, yazar ve tarih bilgilerini ayrıştırır
    ve bu bilgileri veritabanına kaydeder. Ayrıca, sayfadaki ek dosyaları da indirir ve veritabanına kaydeder.
    """
    soup = fetch_page_content(url)
    if not soup:
        return None

    title = parse_title(soup, url)
    content = parse_content(soup, url)
    author, date = parse_author_and_date(soup, url)

    title = title.encode('utf-8', 'ignore').decode('utf-8') if title else "Başlık Bulunamadı"
    content = content.encode('utf-8', 'ignore').decode('utf-8') if content else "İçerik Bulunamadı"
    year = date.split('-')[0] if date else "1000"

    page_data = PageContent(title=title, content=content, author=author, date=date, department=department, url=url)
    page_id = save_page_content_to_db(page_data)
    save_attachments_to_db(soup=soup, department=department, page_content_id=page_id, year=year)

    return page_data

def scrape_department(department, urls):
    """
    Bir bölüm için scraping işlemini gerçekleştirir.
    Bu fonksiyon, belirli bir bölümdeki URL'leri tarayarak her bir sayfadan veri çeker
    ve sonuçları konsola yazdırır. Başarılı ve başarısız işlemler hakkında log kaydı tutar.
    """
    success_count = 0
    for url in urls:
        page_data = get_data_from_page(url=url, department=department)
        if page_data:
            print(page_data)
            print("\n" + "="*50 + "\n")
            success_count += 1
        else:
            logging.error(f"{department} bölümündeki {url} adresi için veri alınamadı.")

    logging.info(f"{department} bölümündeki sayfalar için işlem tamamlandı. Başarılı: {success_count}, Toplam: {len(urls)}")

def prepare_urls(url_list, pagination=1):
    """
    URL listesini hazırlar.
    Verilen URL listesi ve sayfalama sayısı ile her bölüm için sayfalama URL'lerini oluşturur.
    """
    paginated_urls = {}
    for department, url in url_list.items():
        paginated_urls[department] = []
        for i in range(1, pagination + 1):
            paginated_urls[department].append(create_paginated_url(url, i))
    return paginated_urls

def main(url_list, pagination=PAGINATION, num_threads=len(url_list)):
    """
    Ana scraping işlemini gerçekleştirir.
    Bu fonksiyon, belirtilen URL listesi için scraping işlemini başlatır.
    Her bölüm için sayfa URL'lerini alır ve her bir sayfadan veri çekmek için çoklu thread kullanır.
    """
    logging.info("Scraping işlemi başladı.")

    # URL'leri hazırla
    paginated_urls = prepare_urls(url_list, pagination)

    # Her bölüm için sayfa URL'lerini al
    page_urls = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_department = {executor.submit(get_page_urls, department, urls): department for department, urls in paginated_urls.items()}
        for future in concurrent.futures.as_completed(future_to_department):
            department = future_to_department[future]
            try:
                page_urls[department] = future.result()
            except Exception as exc:
                logging.error(f'{department} için URL alma hatası: {exc}')
                page_urls[department] = []

    # Her bölüm için scraping işlemini çoklu thread ile gerçekleştir
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(scrape_department, department, urls) for department, urls in page_urls.items()]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logging.error(f'Bir bölüm için scraping hatası: {exc}')

    logging.info("Scraping işlemi tamamlandı.")
    logging.info("İndirilen toplam sayfa sayısı: %d", sum(len(urls) for urls in page_urls.values()))
    logging.info("Başarıyla kaydedilen sayfa sayısı: %d", sum(len(urls) for urls in page_urls.values()) - sum(1 for urls in page_urls.values() if not urls))

if __name__ == "__main__":
    main(url_list, int(PAGINATION))