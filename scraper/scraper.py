import sys
import os
from typing import List, Optional, Tuple

import pymongo

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bs4 import BeautifulSoup
import requests
from lxml import html
from config import PAGINATION, MONGO_DB_URI
from datetime import datetime
import dateparser
import urllib.parse
import logging
import chardet
import concurrent.futures
import threading
from pymongo import MongoClient

# -*- coding:utf-8 -*-

# Loglama ayarları
LOG_FILE = 'scraper.log'
LOG_LEVEL = logging.INFO  # Hata ayıklama için DEBUG, normal çalışma için INFO
PROJECT_DIR = os.path.dirname(os.path.abspath(__name__))
MONGO_DB_NAME = 'scraped_data'
ATTACHMENTS_COLLECTION = 'page_attachments'
logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')

thread_local = threading.local()

def get_db_connection():
    """
    Thread-local veritabanı bağlantısı döndürür.
    Bu fonksiyon, her thread için ayrı bir veritabanı bağlantısı sağlar.
    Bu, çoklu thread'li uygulamalarda eş zamanlı erişim sorunlarını önler.
    """
    if not hasattr(thread_local, "db_client"):
        try:
            thread_local.db_client = MongoClient(MONGO_DB_URI, serverSelectionTimeoutMS=5000) # Add timeout
            thread_local.db_client.admin.command('ismaster')
            logging.info(f"Thread {threading.current_thread().name} için MongoDB bağlantısı oluşturuldu.")
        except pymongo.errors.ConnectionFailure as e:
            logging.error(f"Thread {threading.current_thread().name} için MongoDB bağlantı hatası: {e}")
            thread_local.db_client = None
            return None
        except Exception as e:
            logging.error(f"Beklenmedik hata (Thread: {threading.current_thread().name}): {e}")
            thread_local.db_client = None
            return None
    return thread_local.db_client


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
        # Format date nicely for printing if it's a datetime object
        date_str = self.date.strftime("%Y-%m-%d") if isinstance(self.date, datetime) else str(self.date)
        return (f"PageContent(\n"
            f"  title='{self.title}',\n"
            f"  url='{self.url}',\n"
            f"  department='{self.department}',\n"
            f"  author='{self.author}',\n"
            f"  date='{date_str}',\n" # Use formatted date string
            f"  content='{self.content[:100]}...'\n"
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
    department_page_urls = set()
    base_url = url_list[department]
    
    for url in urls:
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for link in soup.find_all('article', class_='news-item'):
                a_tag = link.find('a', href=True) # Ensure href exists
                if a_tag:
                    page_url = a_tag['href'].strip()
                    # Ensure the URL is absolute
                    full_url = urllib.parse.urljoin(base_url, page_url)
                    department_page_urls.add(full_url) # Add absolute URL to set
                else:
                    logging.warning(f"'{url}' adresindeki bir 'article' içinde 'a' etiketi veya href bulunamadı.")
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Hata oluştu ({url}): {e}")
        except Exception as e:
            logging.exception(f"Beklenmedik Hata oluştu ({url}): {e}")
            
            
    department_page_urls_list = list(department_page_urls) # Convert set to list
    logging.info(f"{department} için {len(department_page_urls_list)} adet benzersiz sayfa URL'si alındı.")
    return department_page_urls

def fetch_page_content(url) -> Optional[BeautifulSoup]:
    """
    Belirtilen URL'den sayfa içeriğini getirir ve BeautifulSoup nesnesi döndürür.
    Bu fonksiyon, verilen URL'deki HTML içeriğini alır, karakter kodlamasını otomatik olarak tespit eder
    ve içeriği BeautifulSoup nesnesine dönüştürerek ayrıştırma için hazırlar.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        
        # PDF dosyası kontrolü
        if 'application/pdf' in content_type:
             logging.warning(f"PDF dosyası (Content-Type ile tespit edildi), içerik ayrıştırılamıyor: {url}")
             return None
         
        bytes_data = response.content

        # Karakter kodlamasını otomatik olarak tespit et
        encoding = response.apparent_encoding
        
        if not encoding:
            detected_encoding = chardet.detect(bytes_data)['encoding']
            encoding = detected_encoding if detected_encoding else 'utf-8'
            logging.debug(f"'{url}' için apparent_encoding bulunamadı, chardet kullandı: {encoding}")
        try:
            text = bytes_data.decode(encoding, errors='replace')
        except UnicodeDecodeError as decode_error:
            logging.error(f"'{url}' içeriği '{encoding}' ile çözümlenirken hata: {decode_error}. UTF-8 denenecek.")
            try:
                text = bytes_data.decode('utf-8', errors='replace')
            except Exception as fallback_decode_error:
                logging.error(f"'{url}' içeriği 'UTF-8' ile çözümlenirken hata: {fallback_decode_error}. UTF-8 denenecek.")
        
        return BeautifulSoup(text, 'html.parser')
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Sayfa içeriği getirilirken hata oluştu ({url}): {e}")
        return None
    except Exception as e:
        logging.error(f"Sayfa içeriği işlenirken beklenmedik hata ({url}): {e}")
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


# --- REVERTED FUNCTION ---
def convert_date_string_to_date(date_string) -> Optional[str]:
    """
    Tarih stringini 'YYYY-MM-DD' formatına dönüştürür.
    Başarısız olursa None döndürür.
    """
    if not date_string:
        return None
    try:
        # dateparser still useful for parsing various input formats
        date_obj = dateparser.parse(date_string, languages=['tr'])
        if date_obj:
            formatted_date = date_obj.strftime("%Y-%m-%d")
            return formatted_date
        else:
            logging.warning(f"'{date_string}' tarihi dateparser ile dönüştürülemedi.")
            return None # Return None if parsing fails
    except Exception as e:
        logging.error(f"Tarih ('{date_string}') dönüştürme hatası: {e}")
        return None # Return None on error

# --- REVERTED FUNCTION ---
def parse_author_and_date(soup, url) -> Tuple[str, str]: # Return type hint changed to str
    """
    BeautifulSoup nesnesinden yazar ve tarih bilgilerini ayrıştırır.
    Tarihi 'YYYY-MM-DD' string formatında veya default '1000-01-01' döndürür.
    """
    author = "Yazar Bulunamadı"
    date_str = "1000-01-01" # Default date string if parsing fails
    try:
        meta = soup.find('p', class_='meta text-muted')
        if meta:
            # Using get_text might be slightly more robust than splitting meta.text
            meta_text = meta.get_text(separator="|", strip=True)
            parts = meta_text.split('|')
            author_part = parts[0] if len(parts) > 0 else ""
            date_part = parts[1] if len(parts) > 1 else ""

            if "Yazar:" in author_part:
                author = author_part.replace("Yazar:", "").strip()
            if "Tarih:" in date_part:
                raw_date_str = date_part.replace("Tarih:", "").strip()
                # Try to convert to YYYY-MM-DD format
                formatted_date = convert_date_string_to_date(raw_date_str)
                if formatted_date: # If conversion successful, use it
                    date_str = formatted_date
                # Else, date_str remains '1000-01-01' (the default)

    except Exception as e: # Catch broader exceptions during parsing
        logging.warning(f"Yazar veya tarih bilgisi ayrıştırılırken hata oluştu: {url} - {e}")
        # Keep author and date_str as their current values (either default or parsed before error)
    return author, date_str
    

      
def save_page_content_to_db(page_data):
    """
    Veritabanına sayfa içeriğini kaydeder (thread-safe).
    Veritabanında UNIQUE kısıtlaması olduğu için, aynı başlık, departman ve içeriğe sahip
    kayıtlar veritabanı seviyesinde engellenir.
    """
    client = get_db_connection()
    if not client:
        logging.error(f"MongoDB bağlantısı yok, '{page_data.title}' kaydetme işlemi atlanıyor.")
        return None

    try:
        db = client[MONGO_DB_NAME]
        content_collection = db['page_contents']
        
        document = {
            "user_id": None,
            "model_id": None,
            "title": page_data.title,
            "content": page_data.content,
            "author": page_data.author,
            "date": page_data.date, # Store datetime object directly
            "department": page_data.department,
            "url": page_data.url,
            "scraped_at": datetime.now(), # Add timestamp for when it was scraped
        }
        
        result = content_collection.insert_one(document)
        page_id = result.inserted_id
        logging.info(f"'{page_data.title}' ID: {page_id} olarak kaydedildi (Thread: {threading.current_thread().name}).")
        
        return page_id
    except pymongo.errors.DuplicateKeyError:
        logging.warning(f"Aynı URL'ye sahip kayıt zaten var, ekleme yapılamadı: '{page_data.title}' - {page_data.url} (Thread: {threading.current_thread().name}).")
        # Optionally, find the existing document ID if needed
        # existing_doc = content_collection.find_one({"url": page_data.url}, {"_id": 1})
        # return existing_doc['_id'] if existing_doc else None
        return None
    except pymongo.errors.PyMongoError as e:
        logging.error(f"MongoDB'ye kaydetme hatası (Thread: {threading.current_thread().name}): {e}")
        return None
    except Exception as e:
        logging.exception(f"Beklenmedik MongoDB kaydetme hatası (Thread: {threading.current_thread().name}): {e}")
        return None

def save_attachments_to_db(soup: BeautifulSoup, department: str, page_content_id, base_url: str, year: str):
    """
    Ek dosyaları MongoDB'ye kaydeder ve indirir (thread-safe).
    page_content_id, ilgili PageContent belgesinin _id'sidir.
    """
    if not page_content_id: # Don't save attachments if the main page wasn't saved
        logging.warning(f"Ana sayfa kaydedilmediği için ekler kaydedilmiyor (department: {department}).")
        return

    client = get_db_connection()
    if not client:
        logging.error("MongoDB bağlantısı yok, ek dosya kaydetme işlemi atlanıyor.")
        return

    db = client[MONGO_DB_NAME]
    attachments_collection = db[ATTACHMENTS_COLLECTION]
    attachment_docs = []

    for link in soup.find_all('a', href=True):
        href = link['href']
        # Basic filtering for downloadable files - adjust extensions as needed
        if href and any(href.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.zip', '.rar']) and 'oidb' not in href:
            # Make URL absolute
            absolute_url = urllib.parse.urljoin(base_url, href)

            # Avoid re-downloading external links if not intended (simple check)
            if not absolute_url.startswith(base_url) and not absolute_url.startswith("http"):
                 # If it became absolute but doesn't share the base URL, double-check logic
                 # For now, we assume relative links are intended to be within the site
                 pass # Allow it if joined from relative path

            elif not absolute_url.startswith(base_url):
                logging.debug(f"Harici bağlantı atlanıyor: {absolute_url}")
                continue # Skip links clearly pointing to external domains

            try:
                file_name_from_url = os.path.basename(urllib.parse.urlparse(absolute_url).path)
                if not file_name_from_url: # Handle cases like domain.com/download/
                    file_name_from_url = absolute_url.split('/')[-1] or "downloaded_file"

                file_name, file_extension = os.path.splitext(file_name_from_url)
                file_extension = file_extension[1:].lower() # Get extension without dot, lower case

                # Create directory structure
                # Use department and year if available, otherwise use a general folder
                year_str = str(year) if year else "unknown_year"
                save_dir = os.path.join(PROJECT_DIR, "assets", year_str, department, file_extension)
                try:
                    os.makedirs(save_dir, exist_ok=True)
                except OSError as e:
                    logging.error(f"Dizin oluşturma hatası (Thread: {threading.current_thread().name}): {save_dir} - {e}")
                    # Decide whether to skip or try a fallback path
                    continue # Skip this file if directory fails

                # Clean file name for saving (remove invalid characters)
                safe_file_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
                if not safe_file_name: safe_file_name = "untitled" # Handle empty names after cleaning
                file_path = os.path.join(save_dir, f"{safe_file_name}.{file_extension}")

                # Avoid re-downloading if file exists (optional)
                if os.path.exists(file_path):
                    logging.info(f"Dosya zaten var, indirme atlanıyor: {file_path}")
                else:
                    logging.info(f"İndiriliyor: {absolute_url} -> {file_path}")
                    response = requests.get(absolute_url, stream=True, timeout=30) # Add timeout, stream
                    response.raise_for_status()
                    with open(file_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            file.write(chunk)
                    logging.info(f"Ek dosya indirildi: {file_path} (Thread: {threading.current_thread().name})")

                # Prepare document for MongoDB
                attachment_doc = {
                    "page_content_id": page_content_id, # Link to the main document's _id
                    "original_url": absolute_url,
                    "file_name": safe_file_name,
                    "file_type": file_extension,
                    "file_path": file_path, # Local path where it's saved
                    "downloaded_at": datetime.now()
                }
                attachment_docs.append(attachment_doc)

            except requests.exceptions.RequestException as e:
                logging.error(f"Dosya indirme hatası ({absolute_url}) (Thread: {threading.current_thread().name}): {e}")
            except IOError as e:
                 logging.error(f"Dosya yazma hatası ({file_path}) (Thread: {threading.current_thread().name}): {e}")
            except Exception as e:
                 logging.error(f"Ek işlenirken beklenmedik hata ({absolute_url}) (Thread: {threading.current_thread().name}): {e}")

    if attachment_docs:
        try:
            # Insert all documents for this page in one go
            result = attachments_collection.insert_many(attachment_docs, ordered=False) # ordered=False allows partial success
            logging.info(f"{len(result.inserted_ids)} adet ek dosya bilgisi MongoDB'ye kaydedildi (page_id: {page_content_id}, Thread: {threading.current_thread().name}).")
        except pymongo.errors.BulkWriteError as bwe:
            logging.error(f"Toplu ekleme sırasında MongoDB hatası (page_id: {page_content_id}, Thread: {threading.current_thread().name}): {bwe.details}")
        except pymongo.errors.PyMongoError as e:
            logging.error(f"Ekleri MongoDB'ye kaydederken hata (page_id: {page_content_id}, Thread: {threading.current_thread().name}): {e}")
        except Exception as e:
            logging.exception(f"Ekleri kaydederken beklenmedik hata (page_id: {page_content_id}, Thread: {threading.current_thread().name}): {e}")


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
    author, date_str = parse_author_and_date(soup, url)

    # Clean and prepare data
    title = title.strip() if title else "Başlık Bulunamadı"
    content = content.strip() if content else "İçerik Bulunamadı"
    author = author.strip() if author else "Yazar Bulunamadı"
    
    year = date_str.split('-')[0] if date_str and date_str != "1000-01-01" else "unknown_year"
    
    page_data = PageContent(title=title, content=content, author=author, date=date_str, department=department, url=url)
    page_id = save_page_content_to_db(page_data)
    if page_id:
        base_url = url_list[department] # Pass base URL for resolving relative attachment links
        save_attachments_to_db(soup=soup, department=department, page_content_id=page_id, base_url=base_url, year=year)
    else:
         logging.warning(f"Ana içerik kaydedilmediği için '{title}' ({url}) ekleri işlenmedi.")
         
    return page_data

def scrape_department(department, urls):
    """
    Bir bölüm için scraping işlemini gerçekleştirir.
    Bu fonksiyon, belirli bir bölümdeki URL'leri tarayarak her bir sayfadan veri çeker
    ve sonuçları konsola yazdırır. Başarılı ve başarısız işlemler hakkında log kaydı tutar.
    """
    success_count = 0
    fail_count = 0
    total_urls = len(urls)
    logging.info(f"'{department}' bölümü için {total_urls} URL işlenmeye başlanıyor...")
    
    for i, url in enumerate(urls):
        logging.debug(f"[{department} {i+1}/{total_urls}] İşleniyor: {url}")
        try:
            page_data = get_data_from_page(url=url, department=department)
            if page_data:
                # Optional: print(page_data) - Can be verbose
                # print("\n" + "="*50 + "\n")
                success_count += 1
            else:
                # Error already logged in get_data_from_page or its sub-functions
                fail_count += 1
        except Exception as e:
             logging.exception(f"'{department}' bölümündeki '{url}' işlenirken ana döngüde hata: {e}")
             fail_count += 1

    logging.info(f"'{department}' bölümü için işlem tamamlandı. Başarılı: {success_count}, Başarısız: {fail_count}, Toplam: {total_urls}")

def prepare_urls(url_list, pagination=1):
    """
    URL listesini hazırlar.
    Verilen URL listesi ve sayfalama sayısı ile her bölüm için sayfalama URL'lerini oluşturur.
    """
    paginated_urls = {}
    for department, url in url_list.items():
        paginated_urls[department] = []
        # Add the base /haberler/ page as well (page 1 often has no explicit page number)
        base_news_url = f"{url}{suffix}"
        paginated_urls[department].append(base_news_url)
        for i in range(1, pagination + 1): # Start from 1 for page:1
            paginated_urls[department].append(create_paginated_url(url, i))
        # Remove duplicates if base_news_url is same as page:1 (unlikely but possible)
        paginated_urls[department] = sorted(list(set(paginated_urls[department])))
    return paginated_urls

def main(url_list, pagination=PAGINATION, num_threads=len(url_list)):
    """
    Ana scraping işlemini gerçekleştirir.
    Bu fonksiyon, belirtilen URL listesi için scraping işlemini başlatır.
    Her bölüm için sayfa URL'lerini alır ve her bir sayfadan veri çekmek için çoklu thread kullanır.
    """
    
    if num_threads is None or num_threads <= 0:
        num_threads = len(url_list) 
        
    logging.info(f"Scraping işlemi {num_threads} thread ile başladı.")
    # URL'leri hazırla
    paginated_urls_map = prepare_urls(url_list, pagination)

    # Her bölüm için sayfa URL'lerini al
    all_page_urls = {}
    logging.info("Bölüm haber listesi sayfaları taranıyor...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="URL_Getter") as executor:
        future_to_department = {
            executor.submit(get_page_urls, department, urls): department
            for department, urls in paginated_urls_map.items()
        }
        for future in concurrent.futures.as_completed(future_to_department):
            department = future_to_department[future]
            try:
                department_urls = future.result()
                all_page_urls[department] = department_urls
                logging.info(f"'{department}' için {len(department_urls)} sayfa URL'si bulundu.")
            except Exception as exc:
                logging.error(f"'{department}' için URL alma işlemi başarısız: {exc}")
                all_page_urls[department] = [] # Ensure department exists in dict even on failure

    total_unique_urls = sum(len(urls) for urls in all_page_urls.values())
    logging.info(f"Toplam {total_unique_urls} adet benzersiz haber/duyuru URL'si bulundu.")

    if total_unique_urls == 0:
        logging.warning("Hiçbir haber URL'si bulunamadı. Scraping işlemi durduruluyor.")
        return

    # Her bölüm için scraping işlemini çoklu thread ile gerçekleştir
    logging.info("Sayfa içerikleri ve ekleri indirilip kaydediliyor...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="Scraper") as executor:
        # Submit scraping tasks
        scrape_futures = [
            executor.submit(scrape_department, department, urls)
            for department, urls in all_page_urls.items() if urls # Only submit if URLs were found
        ]
        # Wait for all scraping tasks to complete
        for future in concurrent.futures.as_completed(scrape_futures):
            try:
                future.result()  # Raise exceptions if any occurred within scrape_department threads
            except Exception as exc:
                # Log errors that might escape scrape_department's error handling (less likely now)
                logging.error(f'Bir bölümün scraping işlemi sırasında beklenmedik hata: {exc}')

    logging.info("Scraping işlemi tamamlandı.")
    # Note: Calculating success counts accurately across threads requires more complex state management
    # The logs within scrape_department provide per-department summaries.
if __name__ == "__main__":
    try:
        pagination_value = int(PAGINATION)
    except (ValueError, TypeError):
        logging.error(f"PAGINATION değeri ({PAGINATION}) geçerli bir tamsayı değil. Varsayılan olarak 1 kullanılıyor.")
        pagination_value = 1
        
    main(url_list, int(PAGINATION))