from lxml import html
import requests
from dataclasses import dataclass
import sys
from pathlib import Path

# Define data structures
@dataclass
class NewsItem:
    title: str
    url: str

@dataclass
class PDFDocument:
    title: str
    url: str

# Constants
MAIN_URL = "https://bil-muhendislik.omu.edu.tr"
NEWS_URL = f"{MAIN_URL}/tr/haberler"
DOWNLOAD_DIR = Path("data/exam_dates")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

def fetch_page(url):
    """Fetch and return the content of a webpage."""
    response = requests.get(url)
    response.encoding = 'utf-8'
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.content

def parse_news_items(tree):
    """Parse news items from the HTML tree."""
    news_elements = tree.xpath("/html/body/div[1]/div/div/div/div/div/article/div/h3/a")
    return [
        NewsItem(
            title=item.text_content().strip().encode('latin1').decode('utf-8'),  # Encoding fix
            url=f"{MAIN_URL}{item.get('href')}".encode('latin1').decode('utf-8')  # Encoding fix
        )
        for item in news_elements
    ]

def filter_news_items(news_items, keyword):
    """Filter news items by a keyword in the title."""
    return [item for item in news_items if keyword.lower() in item.title.lower()]

def extract_pdf_info(page_content):
    """Extract PDF title and URL from a news page."""
    tree = html.fromstring(page_content)
    title = tree.xpath("/html/body/div[1]/div/div/header/h1")[0].text_content().strip().encode('latin1').decode('utf-8')  # Encoding fix
    pdf_url = tree.xpath("/html/body/div[1]/div/div/div/div/div/article/p[4]/a")[0].get('href').encode('latin1').decode('utf-8')  # Encoding fix
    return PDFDocument(title, f"{MAIN_URL}{pdf_url}")

def download_pdf(pdf):
    """Download a PDF file and save it to the specified directory."""
    response = requests.get(pdf.url)
    response.raise_for_status()
    file_path = DOWNLOAD_DIR / f"{pdf.title}.pdf"
    with open(file_path, 'wb') as f:
        f.write(response.content)
    print(f"{pdf.title} indirildi")

def main():
    try:
        # Fetch and parse the news page
        news_page_content = fetch_page(NEWS_URL)
        tree = html.fromstring(news_page_content)
        news_items = parse_news_items(tree)

        # Filter news items for exam schedules
        filtered_news_items = filter_news_items(news_items, "sınav programı")

        # Extract and download PDFs
        for news_item in filtered_news_items:
            page_content = fetch_page(news_item.url)
            pdf = extract_pdf_info(page_content)
            download_pdf(pdf)

        print("İşlem tamamlandı")
    except Exception as e:
        print(f"Hata oluştu: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()