# -*- coding:utf-8 -*-
import sys
import os
import time
from typing import List, Optional, Tuple, Union # Added Union

import pymongo

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bs4 import BeautifulSoup
import requests
from lxml import html # Keep lxml import if used elsewhere, although not directly in provided code
from config import PAGINATION, MONGO_DB_URI
from datetime import datetime
import dateparser
import urllib.parse
import logging
import chardet
import concurrent.futures
import threading
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi # Good practice for modern pymongo


# Loglama ayarları
LOG_FILE = 'scraper.log'
LOG_LEVEL = logging.INFO  # Hata ayıklama için DEBUG, normal çalışma için INFO
# --- Correct PROJECT_DIR detection ---
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__)) # Use __file__ for script location
# --- ---
MONGO_DB_NAME = 'scraped_data'
ATTACHMENTS_COLLECTION = 'page_attachments'
logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')

thread_local = threading.local()

def get_db_connection():
    """
    Thread-local veritabanı bağlantısı döndürür.
    """
    if not hasattr(thread_local, "db_client") or thread_local.db_client is None: # Check if None too
        try:
            # Use modern connection string handling and ServerApi
            thread_local.db_client = MongoClient(MONGO_DB_URI,
                                                 server_api=ServerApi('1'), # Recommended
                                                 serverSelectionTimeoutMS=5000)
            # The ismaster command is cheap and does not require auth.
            thread_local.db_client.admin.command('ping') # Use ping for modern checks
            logging.info(f"Thread {threading.current_thread().name} için MongoDB bağlantısı oluşturuldu.")
        except pymongo.errors.ConnectionFailure as e:
            logging.error(f"Thread {threading.current_thread().name} için MongoDB bağlantı hatası: {e}")
            thread_local.db_client = None # Ensure it's None on failure
            return None
        except Exception as e:
            logging.error(f"MongoDB bağlantısı kurulurken beklenmedik hata (Thread: {threading.current_thread().name}): {e}")
            thread_local.db_client = None # Ensure it's None on failure
            return None

    # Check connection validity before returning (optional, adds overhead)
    # try:
    #     thread_local.db_client.admin.command('ping')
    # except pymongo.errors.ConnectionFailure:
    #     logging.warning(f"Thread {threading.current_thread().name} için mevcut MongoDB bağlantısı geçersiz. Yeniden bağlanılıyor...")
    #     # Clear the old client and retry connection
    #     thread_local.db_client.close()
    #     thread_local.db_client = None
    #     return get_db_connection() # Recursive call to reconnect

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
    def __init__(self, title="", content="", author="", date="", department="",faculty="", url=""):
        self.title = title
        self.content = content
        self.author = author
        self.date = date # Keep as string YYYY-MM-DD or None
        self.department = department
        self.faculty = faculty
        self.url = url

    def __str__(self):
        date_str = self.date if self.date else "No Date"
        return (f"PageContent(\n"
            f"  title='{self.title}',\n"
            f"  url='{self.url}',\n"
            f"  department='{self.department}',\n"
            f"  faculty='{self.faculty}',\n"
            f"  author='{self.author}',\n"
            f"  date='{date_str}',\n"
            f"  content='{self.content[:100]}...'\n"
            f")")


page_urls = {}
paginated_urls = {}
suffix = '/haberler/'

def create_paginated_url(url, page):
    """
    Verilen URL ve sayfa numarası ile sayfalama (pagination) URL'si oluşturur.
    """
    return f"{url}{suffix}page:{page}"

def fill_paginated_urls(department, url):
    """
    Belirli bir bölüm için sayfalama URL'lerini oluşturur ve saklar.
    """
    paginated_urls[department] = []
    for i in range(1, PAGINATION + 1):
        paginated_urls[department].append(create_paginated_url(url, i))


def get_page_urls(department, urls):
    """
    Verilen URL'lerden sayfa URL'lerini alır.
    """
    logging.info(f"{department} için sayfa URL'leri alınıyor...")
    session = requests.Session()
    department_page_urls = set()
    base_url = url_list[department]

    for url in urls:
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()

             # --- Encoding handling for list pages ---
            bytes_data = response.content
            encoding = response.apparent_encoding
            if not encoding:
                detected_encoding = chardet.detect(bytes_data)['encoding']
                encoding = detected_encoding if detected_encoding else 'utf-8'
            try:
                text = bytes_data.decode(encoding, errors='replace')
            except UnicodeDecodeError:
                logging.warning(f"'{url}' listesi sayfası '{encoding}' ile çözümlenirken hata. UTF-8 denenecek.")
                text = bytes_data.decode('utf-8', errors='replace')
            # --- ---

            soup = BeautifulSoup(text, 'html.parser') # Use decoded text

            for link in soup.find_all('article', class_='news-item'):
                a_tag = link.find('a', href=True)
                if a_tag:
                    page_url = a_tag['href'].strip()
                    full_url = urllib.parse.urljoin(base_url, page_url)
                    department_page_urls.add(full_url)
                else:
                    logging.warning(f"'{url}' adresindeki bir 'article' içinde 'a' etiketi veya href bulunamadı.")

        except requests.exceptions.RequestException as e:
            logging.error(f"Hata oluştu ({url}): {e}")
        except Exception as e:
            logging.exception(f"Beklenmedik Hata oluştu ({url}): {e}")


    department_page_urls_list = list(department_page_urls)
    logging.info(f"{department} için {len(department_page_urls_list)} adet benzersiz sayfa URL'si alındı.")
    return department_page_urls_list # Return list here

# --- MODIFIED fetch_page_content ---
def fetch_page(url) -> Optional[requests.Response]:
    """
    Belirtilen URL'den içeriği getirir. Hata durumunda None döner.
    Content-Type kontrolünü veya parsing'i burada YAPMAZ.
    """
    try:
        response = requests.get(url, timeout=20) # Increased timeout slightly
        response.raise_for_status() # Check for HTTP errors like 404, 500
        return response
    except requests.exceptions.Timeout:
        logging.error(f"Timeout hatası ({url})")
        return None
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Hatası ({url}): {e.response.status_code} {e.response.reason}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Sayfa içeriği getirilirken istek hatası oluştu ({url}): {e}")
        return None
    except Exception as e:
        logging.error(f"Sayfa içeriği getirilirken beklenmedik hata ({url}): {e}")
        return None

# --- NEW HELPER: Decode response content ---
def decode_content(response: requests.Response) -> Optional[str]:
    """
    Attempts to decode response content using apparent_encoding or fallback to chardet/utf-8.
    Returns decoded text or None if decoding fails completely.
    """
    url = response.url
    bytes_data = response.content
    encoding = response.apparent_encoding

    if not encoding:
        try:
            detected_encoding = chardet.detect(bytes_data)['encoding']
            encoding = detected_encoding if detected_encoding else 'utf-8'
            logging.debug(f"'{url}' için apparent_encoding bulunamadı, chardet kullandı: {encoding}")
        except Exception as chardet_err:
             logging.warning(f"Chardet hatası ({url}): {chardet_err}. UTF-8 kullanılacak.")
             encoding = 'utf-8'

    try:
        text = bytes_data.decode(encoding, errors='replace')
        return text
    except (UnicodeDecodeError, LookupError) as decode_error: # LookupError for invalid encoding names
        logging.warning(f"'{url}' içeriği '{encoding}' ile çözümlenirken hata: {decode_error}. UTF-8 denenecek.")
        try:
            text = bytes_data.decode('utf-8', errors='replace')
            return text
        except Exception as fallback_decode_error:
            logging.error(f"'{url}' içeriği UTF-8 ile de çözümlenirken hata: {fallback_decode_error}.")
            return None


def parse_title(soup, url):
    """
    BeautifulSoup nesnesinden başlığı ayrıştırır.
    """
    try:
        title_element = soup.select_one('h1.heading-title') 
        if not title_element:
            title_element = soup.find('h1')
        return title_element.text.strip() if title_element else "Başlık Bulunamadı"
    except AttributeError:
        logging.warning(f"Başlık ayrıştırılırken hata oluştu (AttributeError): {url}")
        return "Başlık Bulunamadı"
    except Exception as e:
        logging.error(f"Başlık ayrıştırılırken beklenmedik hata: {url} - {e}")
        return "Başlık Ayrıştırma Hatası"

def parse_content(soup, url):
    """
    BeautifulSoup nesnesinden içeriği ayrıştırır.
    """
    content = "İçerik Bulunamadı"
    try:
        # --- Improved Content Parsing ---
        content_element = soup.find('div', class_='news-wrapper')
        if content_element:
            # Remove known non-content elements like metadata paragraph
            meta_p = content_element.find('p', class_='meta')
            if meta_p:
                meta_p.decompose() # Remove it from the tree

            # Get text from all relevant tags within the wrapper
            # Exclude script/style, handle paragraphs, lists, etc.
            text_parts = []
            for element in content_element.find_all(['p', 'span', 'div', 'ul', 'ol', 'li', 'strong', 'em', 'br']):
                 # Basic filtering: skip empty or purely whitespace elements
                element_text = element.get_text(separator=' ', strip=True)
                if element_text:
                    # Add paragraph breaks for block elements like p, div, li
                    if element.name in ['p', 'div', 'li', 'br']:
                         text_parts.append("\n") # Add a newline before block element text
                    text_parts.append(element_text)

            # Join parts, remove excessive whitespace/newlines
            full_text = " ".join(text_parts).strip()
            full_text = "\n".join([line.strip() for line in full_text.splitlines() if line.strip()]) # Consolidate newlines
            content = full_text if full_text else "İçerik Bulunamadı (Wrapper Boş)"
        else:
            # Fallback: Try getting content from body if specific wrapper fails
            body_content = soup.body.get_text(separator=' ', strip=True) if soup.body else ""
            if body_content:
                 content = body_content[:2000] # Limit fallback content length
                 logging.warning(f"'.news-wrapper' bulunamadı, body text kullanıldı (kısaltılmış): {url}")
            else:
                 logging.warning(f"'.news-wrapper' bulunamadı ve body text alınamadı: {url}")


        # --- Original Content Parsing (Less Robust) ---
        # content_element = soup.find('div', class_='news-wrapper')
        # if content_element:
        #     # Try getting text directly first, might be cleaner
        #     content = content_element.get_text(separator='\n', strip=True)
        #     if not content.strip(): # If get_text fails, fallback to span/p logic
        #         content_array = content_element.find_all('span')
        #         content_array = [span.text.strip() for span in content_array if span.text.strip()]
        #         content_array = list(dict.fromkeys(content_array)) # Remove duplicates
        #         content = "\n".join(content_array) # Join with newline

        #         if not content:
        #             content_array = content_element.find_all('p')
        #             if content_array:
        #                 # Remove meta paragraph if it exists
        #                 if content_array[0].find(class_='meta'):
        #                     content_array.pop(0)
        #                 content_array = [p.text.strip() for p in content_array if p.text.strip()]
        #                 content_array = list(dict.fromkeys(content_array))
        #                 content = "\n".join(content_array)


    except Exception as e:
        content = "Ayrıştırma Hatası"
        logging.error(f"İçerik ayrıştırılırken hata oluştu: {url} - {e}")
    return content if content else "İçerik Bulunamadı"

def parse_faculty_information(soup, url):
    """
    BeautifulSoup nesnesinden fakülte bilgilerini ayrıştırır.
    """
    try:
        faculty_element = soup.select_one('a:-soup-contains("Fakültesi")')
        if faculty_element:
            return faculty_element.text.strip()
    except AttributeError:
        logging.warning(f"Fakülte bilgisi ayrıştırılırken AttributeError oluştu: {url}")
        return "Fakülte Bilgisi Bulunamadı"
    except requests.exceptions.RequestException as e:
        logging.error(f"Fakülte bilgisi alınırken istek hatası oluştu: {url} - {e}")
        return "Fakülte Bilgisi Bulunamadı"
            
    
    except Exception as e:
        logging.error(f"Fakülte bilgisi ayrıştırılırken hata oluştu: {url} - {e}")
        return "Fakülte Bilgisi Bulunamadı"

def convert_date_string_to_date(date_string) -> Optional[str]:
    """
    Tarih stringini 'YYYY-MM-DD' formatına dönüştürür.
    Başarısız olursa None döndürür.
    """
    if not date_string:
        return None
    try:
        date_obj = dateparser.parse(date_string, languages=['tr'])
        if date_obj:
            if date_obj > datetime.now():
                 logging.warning(f"Gelecekteki tarih ayrıştırıldı '{date_string}' -> {date_obj}. Muhtemelen yanlış. None döndürülüyor.")
                 return None
            formatted_date = date_obj.strftime("%Y-%m-%d")
            return formatted_date
        else:
            logging.warning(f"'{date_string}' tarihi dateparser ile dönüştürülemedi.")
            return None # Return None if parsing fails
    except Exception as e:
        logging.error(f"Tarih ('{date_string}') dönüştürme hatası: {e}")
        return None # Return None on error


def parse_author_and_date(soup, url) -> Tuple[str, Optional[str]]:
    """
    BeautifulSoup nesnesinden yazar ve tarih bilgilerini ayrıştırır.
    """
    author = "Yazar Bulunamadı"
    date_str = None # Use None for date failure
    try:
        meta = soup.find('p', class_='meta text-muted')
        if meta:
            meta_text = meta.text.strip()
            parts = meta_text.split('|')
            if len(parts) >= 1:
                # Extract author, cleaning potential prefixes
                 author_part = parts[0].lower()
                 for prefix in ["yazar:", "author:"]:
                      if author_part.startswith(prefix):
                           author_part = author_part[len(prefix):]
                           break
                 author = author_part.strip().title() # Capitalize names

            if len(parts) >= 2:
                 # Extract date, cleaning potential prefixes
                 date_part = parts[1].lower()
                 for prefix in ["tarih:", "date:", "yayınlanma tarihi:"]:
                     if date_part.startswith(prefix):
                          date_part = date_part[len(prefix):]
                          break
                 raw_date = date_part.strip()
                 date_str = convert_date_string_to_date(raw_date) # Convert to YYYY-MM-DD

        if not meta: # Fallback if specific meta tag not found
             # Look for common date patterns elsewhere if needed (e.g., time tag)
             time_tag = soup.find('time', datetime=True)
             if time_tag and not date_str:
                  date_str = convert_date_string_to_date(time_tag['datetime'])
                  logging.debug(f"Tarih <time> etiketinden alındı: {url}")
             # Could add more fallbacks here if necessary

    except Exception as e: # Catch broader exceptions during parsing
        logging.warning(f"Yazar veya tarih bilgisi ayrıştırılırken hata oluştu: {url} - {e}")

    # Ensure author is not empty string, fallback if needed
    if not author:
        author = "Yazar Bulunamadı"

    return author, date_str


def save_page_content_to_db(page_data: PageContent) -> Optional[str]:
    """
    Veritabanına sayfa içeriğini kaydeder (thread-safe).
    Kaydedilen dokümanın id'sini döndürür.
    """
    client = get_db_connection()
    if not client:
        logging.error(f"MongoDB bağlantısı yok, '{page_data.title}' kaydetme işlemi atlanıyor.")
        return None

    try:
        db = client[MONGO_DB_NAME]
        content_collection = db['page_contents']

        # Ensure date is compatible with MongoDB (string or datetime, handle None)
        doc_date = None
        if page_data.date:
             try:
                 
                 doc_date = datetime.strptime(page_data.date, "%Y-%m-%d")
             except (ValueError, TypeError):
                 doc_date = page_data.date


        document = {
            "user_id": None,
            "model_id": None,
            "title": page_data.title,
            "content": page_data.content,
            "author": page_data.author,
            "date": doc_date,
            "department": page_data.department,
            "faculty": page_data.faculty,
            "url": page_data.url,
            "scraped_at": datetime.now(),
            "is_pdf_source": page_data.content == "[PDF Document]"
            
        }

        result = content_collection.insert_one(document)
        page_id = result.inserted_id
        logging.info(f"'{page_data.title}' ID: {page_id} olarak kaydedildi (Thread: {threading.current_thread().name}).")

        return str(page_id) # Return as string for consistency
    
    except pymongo.errors.PyMongoError as e:
        logging.error(f"MongoDB'ye kaydetme hatası (Thread: {threading.current_thread().name}): {e}")
        return None
    except Exception as e:
        logging.exception(f"Beklenmedik MongoDB kaydetme hatası (Thread: {threading.current_thread().name}): {e}")
        return None

def save_attachments_to_db(attachments_data: List[dict]) -> int:
    """
    İndirilen dosya bilgilerini MongoDB'ye kaydeder.
    """
    if not attachments_data:
        return 0

    client = get_db_connection()
    if not client:
        logging.error("MongoDB bağlantısı yok, ek dosya kaydetme işlemi atlanıyor.")
        return 0

    db = client[MONGO_DB_NAME]
    attachments_collection = db[ATTACHMENTS_COLLECTION]
    inserted_count = 0

    try:
        result = attachments_collection.insert_many(attachments_data, ordered=False)
        inserted_count = len(result.inserted_ids)
        logging.info(f"{inserted_count} adet ek dosya bilgisi MongoDB'ye kaydedildi (Thread: {threading.current_thread().name}).")
        if len(attachments_data) != inserted_count:
             logging.warning(f"Toplu ekleme sırasında bazı ekler kaydedilemedi (page_id: {attachments_data[0].get('page_content_id', 'N/A')}, Thread: {threading.current_thread().name}).")

    except pymongo.errors.BulkWriteError as bwe:
        inserted_count = bwe.details.get('nInserted', 0)
        logging.error(f"Toplu ekleme sırasında MongoDB hatası (page_id: {attachments_data[0].get('page_content_id', 'N/A')}, Thread: {threading.current_thread().name}): {bwe.details}")
    except pymongo.errors.PyMongoError as e:
        logging.error(f"Ekleri MongoDB'ye kaydederken hata (page_id: {attachments_data[0].get('page_content_id', 'N/A')}, Thread: {threading.current_thread().name}): {e}")
    except Exception as e:
        logging.exception(f"Ekleri kaydederken beklenmedik hata (page_id: {attachments_data[0].get('page_content_id', 'N/A')}, Thread: {threading.current_thread().name}): {e}")

    return inserted_count


def download_file(url: str, save_path: str) -> bool:
    """URL'den dosya indirir."""
    try:
        logging.info(f"İndiriliyor: {url} -> {save_path} (Thread: {threading.current_thread().name})")
        response = requests.get(url, stream=True, timeout=60) # Longer timeout for downloads
        response.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True) # Ensure directory exists
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logging.info(f"Dosya indirildi: {save_path}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Dosya indirme hatası ({url}) (Thread: {threading.current_thread().name}): {e}")
        return False
    except IOError as e:
        logging.error(f"Dosya yazma hatası ({save_path}) (Thread: {threading.current_thread().name}): {e}")
        return False
    except OSError as e:
        logging.error(f"Dizin oluşturma/Dosya sistemi hatası ({save_path}) (Thread: {threading.current_thread().name}): {e}")
        return False
    except Exception as e:
        logging.error(f"Dosya indirirken beklenmedik hata ({url}) (Thread: {threading.current_thread().name}): {e}")
        return False

def process_html_attachments(soup: BeautifulSoup, department: str, page_content_id: str, base_url: str, year: str):
    """
    HTML sayfasındaki ek dosyaları işler ve kaydeder.
    """
    if not page_content_id: # Don't save attachments if the main page wasn't saved
        logging.warning(f"Ana sayfa kaydedilmediği için ekler kaydedilmiyor (department: {department}, base_url: {base_url}).")
        return

    attachment_docs_to_save = []
    valid_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']

    for link in soup.find_all('a', href=True):
        href = link['href']
        if href and any(href.lower().endswith(ext) for ext in valid_extensions) and 'oidb' not in href.lower(): # Check lower case href
            absolute_url = urllib.parse.urljoin(base_url, href)

            if not absolute_url.startswith(base_url) and not absolute_url.startswith("http"):
                 pass 
            elif not absolute_url.startswith(base_url):
                logging.debug(f"Harici bağlantı atlanıyor: {absolute_url}")
                continue 

            try:
                parsed_url = urllib.parse.urlparse(absolute_url)
                file_name_from_url = os.path.basename(parsed_url.path)
                if not file_name_from_url:
                    file_name_from_url = absolute_url.split('/')[-1] or link.text.strip() or "downloaded_file"


                file_name, file_extension = os.path.splitext(file_name_from_url)
                file_extension = file_extension[1:].lower() # Get extension without dot, lower case

                if not file_extension: # Skip if no extension found
                     logging.warning(f"Uzantısız dosya bağlantısı atlanıyor: {absolute_url}")
                     continue

                year_str = str(year) if year else "unknown_year"
                save_dir = os.path.join(PROJECT_DIR, "assets", year_str, department, file_extension)
                os.makedirs(save_dir, exist_ok=True) 
                
                safe_file_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '_', '-')).strip()
                if not safe_file_name: safe_file_name = f"untitled_{int(time.time())}" # Handle empty names
                file_path = os.path.join(save_dir, f"{safe_file_name}.{file_extension}")

                # Zaten indirilmiş olan dosyaları indirme.
                if os.path.exists(file_path):
                    logging.info(f"Dosya zaten var, indirme atlanıyor: {file_path}")
                    download_successful = True
                else:
                    download_successful = download_file(absolute_url, file_path)

                if download_successful:
                    attachment_doc = {
                        "page_content_id": page_content_id, 
                        "original_url": absolute_url,
                        "file_name": safe_file_name,
                        "file_type": file_extension,
                        "file_path": file_path,
                        "department": department,
                        "downloaded_at": datetime.now()
                    }
                    attachment_docs_to_save.append(attachment_doc)

            except OSError as e:
                 logging.error(f"Dizin/Dosya sistemi hatası ({absolute_url}) (Thread: {threading.current_thread().name}): {e}")
            except Exception as e:
                 logging.error(f"HTML eki işlenirken beklenmedik hata ({absolute_url}) (Thread: {threading.current_thread().name}): {e}", exc_info=True) # Add traceback

    if attachment_docs_to_save:
        save_attachments_to_db(attachment_docs_to_save)


def handle_direct_pdf(response: requests.Response, department: str, url: str):
    """
    Doğrudan PDF dosyası tespit edildiğinde işleme alır.
    """
    logging.info(f"Doğrudan PDF dosyası tespit edildi: {url}. İndirme ve kaydetme işlemi başlatılıyor...")
    now = datetime.now()
    download_date_str = now.strftime("%Y-%m-%d")

    try:
        # 1. Extract Filename
        parsed_url = urllib.parse.urlparse(url)
        file_name_from_url = os.path.basename(parsed_url.path)
        # Try Content-Disposition header (more reliable)
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition:
            disp_parts = content_disposition.split(';')
            for part in disp_parts:
                if part.strip().lower().startswith('filename='):
                    file_name_from_url = part.split('=')[1].strip('" ')
                    break
        if not file_name_from_url:
            file_name_from_url = url.split('/')[-1] or f"downloaded_pdf_{int(now.timestamp())}"

        file_name, file_extension = os.path.splitext(file_name_from_url)
        file_extension = file_extension[1:].lower() if file_extension else 'pdf' # Assume pdf if no ext

        if file_extension not in ['pdf']:
            logging.warning(f"URL PDF olarak tespit edildi ancak dosya adı uzantısı farklı '{file_extension}'. 'pdf' olarak devam ediliyor: {url}")


        safe_title = "".join(c for c in file_name if c.isalnum() or c in (' ', '_', '-')).strip() or f"PDF Document {int(now.timestamp())}"
        pdf_page_data = PageContent(
            title=f"[PDF] {safe_title}", # Indicate it's a PDF in title
            content="[PDF Document]", 
            author="N/A",
            date=download_date_str, 
            department=department,
            url=url
        )

        # Sayfa verisini kaydet
        page_id = save_page_content_to_db(pdf_page_data)

        if not page_id:
            logging.error(f"Doğrudan PDF için ana içerik kaydı oluşturulamadı, ek kaydedilemiyor: {url}")
            return None # Indicate failure


        save_dir = os.path.join(PROJECT_DIR, "assets", "direct_downloads", department, file_extension)
        safe_file_name_for_path = "".join(c for c in file_name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not safe_file_name_for_path: safe_file_name_for_path = f"untitled_{int(now.timestamp())}"
        file_path = os.path.join(save_dir, f"{safe_file_name_for_path}.{file_extension}")

        # PDF indir
        download_successful = False
        if os.path.exists(file_path):
             logging.info(f"PDF dosyası zaten var, indirme atlanıyor: {file_path}")
             download_successful = True
        else:
            try:
                logging.info(f"PDF indiriliyor: {url} -> {file_path} (Thread: {threading.current_thread().name})")
                os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
                with open(file_path, 'wb') as file:
                    file.write(response.content) # Write content directly
                logging.info(f"PDF indirildi: {file_path}")
                download_successful = True
            except IOError as e:
                 logging.error(f"PDF dosya yazma hatası ({file_path}) (Thread: {threading.current_thread().name}): {e}")
            except OSError as e:
                 logging.error(f"PDF dizin oluşturma/Dosya sistemi hatası ({file_path}) (Thread: {threading.current_thread().name}): {e}")
            except Exception as e:
                 logging.error(f"PDF indirirken/yazarken beklenmedik hata ({url}) (Thread: {threading.current_thread().name}): {e}")



        if download_successful:
            attachment_doc = {
                "page_content_id": page_id, 
                "original_url": url,
                "file_name": safe_file_name_for_path,
                "file_type": file_extension,
                "file_path": file_path,
                "department": department,
                "downloaded_at": now
            }
            
            save_attachments_to_db([attachment_doc]) # Use the list-based saver
            return pdf_page_data # Return the created page data object on success
        else:
             logging.error(f"PDF indirme başarısız olduğu için ek kaydedilmedi: {url}")
             # Optionally: Delete the minimal PageContent entry if download fails?
             client = get_db_connection()
             if client: client[MONGO_DB_NAME]['page_contents'].delete_one({"_id": pymongo.ObjectId(page_id)})
             return None # Indicate failure


    except Exception as e:
        logging.error(f"Doğrudan PDF işlenirken genel hata ({url}): {e}", exc_info=True)
        return None


def get_data_from_page(url, department):
    """
    Sayfa içeriğini getirir, türüne göre işler (HTML/PDF) ve veritabanına kaydeder.
    """
    response = fetch_page(url)
    if not response:
        # Error logged in fetch_page
        return None # Indicate failure

    content_type = response.headers.get('Content-Type', '').lower()
    base_url = url_list[department] 

    is_pdf = 'application/pdf' in content_type or url.lower().endswith('.pdf')

    if is_pdf:
        logging.debug(f"PDF içeriği tespit edildi ({content_type or '.pdf uzantı'}): {url}")
        return handle_direct_pdf(response, department, url)

    else:
        logging.debug(f"HTML içeriği tespit edildi ({content_type}): {url}")
        html_text = decode_content(response)
        if not html_text:
             logging.error(f"HTML içerik çözümlenemedi (decode failed): {url}")
             return None 
        try:
             soup = BeautifulSoup(html_text, 'html.parser')
        except Exception as bs_error:
             logging.error(f"BeautifulSoup ayrıştırma hatası: {url} - {bs_error}")
             return None # Indicate failure


        # İçeriği parçala
        title = parse_title(soup, url)
        content = parse_content(soup, url)
        author, date_str = parse_author_and_date(soup, url)
        faculty = parse_faculty_information(soup, url) 

        # Veriyi temizle ve hazırla
        title = title.strip() if title else "Başlık Bulunamadı"
        content = content.strip() if content else "İçerik Bulunamadı"
        author = author.strip() if author else "Yazar Bulunamadı"
        faculty = faculty.strip() if faculty else "Fakülte Bilgisi Bulunamadı"

        # Determine year for saving attachments (use parsed date if available)
        year_for_attachments = "unknown_year"
        if date_str and date_str != "1000-01-01":
             try:
                  year_for_attachments = date_str.split('-')[0]
             except: pass # Ignore errors getting year

        page_data = PageContent(title=title, content=content, author=author, date=date_str, department=department, faculty=faculty, url=url)

        page_id = save_page_content_to_db(page_data) # Returns string ID or None

        if page_id:
             process_html_attachments(soup=soup,
                                      department=department,
                                      page_content_id=page_id,
                                      base_url=base_url,
                                      year=year_for_attachments)
        else:
             logging.warning(f"Ana içerik kaydedilmediği için '{title}' ({url}) HTML ekleri işlenmedi.")

        return page_data if page_id else None # Return page_data only if saved successfully


def scrape_department(department, department_urls): # Renamed urls to department_urls for clarity
    """
    Bir bölüm için scraping işlemini gerçekleştirir.
    """
    success_count = 0
    fail_count = 0
    total_urls = len(department_urls)
    logging.info(f"'{department}' bölümü için {total_urls} URL işlenmeye başlanıyor...")

    results = [] 

    for i, url in enumerate(department_urls):
        # Check if URL is valid before processing
        if not url or not url.startswith(('http://', 'https://')):
             logging.warning(f"[{department} {i+1}/{total_urls}] Geçersiz URL atlanıyor: {url}")
             fail_count += 1
             continue

        logging.debug(f"[{department} {i+1}/{total_urls}] İşleniyor: {url}")
        try:
            page_data = get_data_from_page(url=url, department=department)
            if page_data:
                
                results.append(page_data) 
                success_count += 1
            else:
                
                logging.warning(f"Başarısız işlem: {url}")
                fail_count += 1
        except Exception as e:
             
             logging.exception(f"'{department}' bölümündeki '{url}' işlenirken ana döngüde HATA: {e}")
             fail_count += 1
        
    logging.info(f"'{department}' bölümü için işlem tamamlandı. Başarılı: {success_count}, Başarısız: {fail_count}, Toplam: {total_urls}")
    return results 

def prepare_urls(url_map, pagination=1): # Renamed url_list to url_map
    """
    URL listesini hazırlar. pagination=0 /haberler/ 'i indir.
    """
    paginated_urls = {}
    for department, base_url in url_map.items():
        department_urls = set() # Use set to avoid duplicates initially
        # Add the base /haberler/ page
        base_news_url = urllib.parse.urljoin(base_url, suffix) # Use urljoin for safety
        department_urls.add(base_news_url)

        if pagination > 0:
            for i in range(1, pagination + 1):
                department_urls.add(create_paginated_url(base_url, i))

        paginated_urls[department] = sorted(list(department_urls)) # Convert to sorted list
        logging.debug(f"'{department}' için hazırlanmış haber listesi URL'leri: {paginated_urls[department]}")
    return paginated_urls


def main(base_url_list, pagination=PAGINATION, num_threads=None): # Renamed url_list
    """
    Ana scraping işlemini gerçekleştirir.
    """

    if num_threads is None or num_threads <= 0:
        num_threads = min(len(base_url_list), os.cpu_count() or 1) * 2 # Example: 2 threads per department/core
        num_threads = max(1, num_threads) # Ensure at least one thread
    logging.info(f"Scraping işlemi {num_threads} thread ile başladı.")

    paginated_urls_map = prepare_urls(base_url_list, pagination)

    all_page_urls = {}
    logging.info("Bölüm haber listesi sayfaları taranıyor...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="URL_Getter") as executor:
        future_to_department = {
            executor.submit(get_page_urls, department, urls): department
            for department, urls in paginated_urls_map.items() if urls 
        }
        for future in concurrent.futures.as_completed(future_to_department):
            department = future_to_department[future]
            try:
                department_urls = future.result() # This is now a list
                if department_urls:
                    all_page_urls[department] = department_urls # Store the list
                    logging.info(f"'{department}' için {len(department_urls)} sayfa URL'si bulundu.")
                else:
                    logging.warning(f"'{department}' için hiç sayfa URL'si bulunamadı.")
                    all_page_urls[department] = [] # Store empty list
            except Exception as exc:
                logging.error(f"'{department}' için URL alma işlemi başarısız: {exc}", exc_info=True)
                all_page_urls[department] = [] # Store empty list on error

    total_unique_urls = sum(len(urls) for urls in all_page_urls.values())
    logging.info(f"Toplam {total_unique_urls} adet benzersiz haber/duyuru URL'si bulundu.")

    if total_unique_urls == 0:
        logging.warning("Hiçbir haber URL'si bulunamadı. Scraping işlemi durduruluyor.")
        return

    # 3. Scrape individual pages concurrently
    logging.info("Sayfa içerikleri ve ekleri indirilip kaydediliyor...")
    all_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="Scraper") as executor:
        future_to_department_scrape = {
            executor.submit(scrape_department, department, urls): department
            for department, urls in all_page_urls.items() if urls # Only submit if URLs were found
        }
        for future in concurrent.futures.as_completed(future_to_department_scrape):
            department = future_to_department_scrape[future]
            try:
                 # scrape_department logs its own completion/stats
                 department_results = future.result() # Get results if scrape_department returns them
                 all_results[department] = department_results
            except Exception as exc:
                # Log errors from the scrape_department *task execution* itself
                logging.error(f"'{department}' bölümünün scraping görevi sırasında beklenmedik hata: {exc}", exc_info=True)

    if hasattr(thread_local, "db_client") and thread_local.db_client:
        try:
            thread_local.db_client.close()
            logging.info(f"Ana thread ({threading.current_thread().name}) MongoDB bağlantısı kapatıldı.")
        except Exception as e:
             logging.error(f"Ana thread MongoDB bağlantısı kapatılırken hata: {e}")


    logging.info("Scraping işlemi tamamlandı.")


if __name__ == "__main__":
    start_time = time.time()
    try:
        if not MONGO_DB_URI:
            raise ValueError("MONGO_DB_URI yapılandırma dosyasında tanımlı değil.")
        pagination_value = int(PAGINATION)
        if pagination_value < 0:
             logging.warning(f"PAGINATION ({PAGINATION}) negatif olamaz. 0 olarak ayarlandı (sadece ana haberler sayfası).")
             pagination_value = 0
    except (ValueError, TypeError) as config_error:
        logging.error(f"Yapılandırma hatası: {config_error}. Lütfen config.py dosyasını kontrol edin. Scraping durduruluyor.")
        sys.exit(1) # Exit if config is bad
    except NameError as config_missing:
        logging.error(f"Yapılandırma değişkeni bulunamadı: {config_missing}. Lütfen config.py dosyasını kontrol edin. Scraping durduruluyor.")
        sys.exit(1) # Exit if config is missing


    main(url_list, pagination_value)

    logging.info("Ana program tamamlandı.")
    logging.info(f"Toplam çalışma süresi: {time.time() - start_time:.2f} saniye")