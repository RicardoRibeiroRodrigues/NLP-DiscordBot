import aiohttp
from bs4 import BeautifulSoup
import os
import pickle
import re


class Scrapper:
    DOCS_PATH = "data/Docs/"
    URLS_PATH = "data/urls.pickle"
    TITLES_PATH = "data/titles.pickle"
    CONTENTS_PATH = "data/contents.pickle"

    def __init__(self, max_downloads: int = 50) -> None:
        self.MAX_DOWNLOADS = max_downloads

        if not os.path.exists(self.DOCS_PATH):
            os.mkdir(self.DOCS_PATH)
        
        if not os.path.exists(self.URLS_PATH):
            self.urls: list = []
        else:
            print("[INFO] Loading urls...")
            self.load_urls()
        
        if not os.path.exists(self.CONTENTS_PATH):
            self.contents: list = []
        else:
            print("[INFO] Loading contents...")
            self.load_contents()
        
        if not os.path.exists(self.TITLES_PATH):
            self.titles: list = []
        else:
            print("[INFO] Loading titles...")
            self.load_titles()
        

    def save_urls(self) -> None:
        with open(self.URLS_PATH, "wb") as f:
            pickle.dump(self.urls, f)


    def load_contents(self) -> None:
        with open(self.CONTENTS_PATH, "rb") as f:
            self.contents = pickle.load(f)

    
    def save_contents(self) -> None:
        with open(self.CONTENTS_PATH, "wb") as f:
            pickle.dump(self.contents, f)


    def load_urls(self) -> None:
        with open(self.URLS_PATH, "rb") as f:
            self.urls = pickle.load(f)
    
    def load_titles(self) -> None:
        with open(self.TITLES_PATH, 'rb') as f:
            self.titles = pickle.load(f)
    
    def save_titles(self) -> None:
        with open(self.TITLES_PATH, 'wb') as f:
            pickle.dump(self.titles, f)


    def url_to_filename(self, url: str) -> str:
        filename = re.sub(r"(https://)|(http://)", "", url)
        filename = re.sub(r"\W+", "_", filename)
        if len(filename) > 255:
            filename = filename[:250]
        return filename + ".txt"


    def save_doc(self, filename: str, content: str) -> None:
        with open(f"{self.DOCS_PATH}{filename}", "w") as f:
            f.write(content)


    def valid_url(self, url: str) -> bool:
        forbidden_file_formats = r".+\.(pptx|docx|jpg|jpeg|png|gif|bmp|pdf|mp4|mp3|wav)$"
        if (not url) or re.match(forbidden_file_formats, url) or (not re.match(r"(https://)|(http://)", url)):
            return False
        # Prevent equal urls with only the # in the end of difference (sections of the same page).
        return "#".join(url.rsplit('#', 1)[:-1])
        

    def url_in_db(self, url: str) -> bool:
        return url in self.urls


    def extract_from_soup(self, url: str, soup: BeautifulSoup) -> tuple:
        text = soup.get_text()
        title = soup.title.string
        self.save_doc(self.url_to_filename(url), text.lower())
        self.contents.append(text.lower())
        self.titles.append(str(title))
        return title, text
    

    async def scrape(self, url: str) -> tuple:
        url_queue = [url]
        download_count = 0
        # Using only in this function for its O(1) in func.
        urls_set = set(self.urls)

        async with aiohttp.ClientSession() as session:
            while url_queue and download_count < self.MAX_DOWNLOADS: 
                curr_link = url_queue.pop(0)
                try:
                    # print(f"[INFO] Downloading {curr_link}")
                    soup = await self.get_content(curr_link, session)

                    if not soup:
                        print("Failed to download:", curr_link)
                        continue
                    download_count += 1
                    self.urls.append(curr_link)

                    for a_tag in soup.find_all('a'):
                        url = a_tag.get('href')
                        url = self.valid_url(url)
                        if url and (url not in urls_set):
                            # Set prevents downloading duplicates.
                            urls_set.add(url)
                            url_queue.append(url)

                    yield self.extract_from_soup(curr_link, soup)
                except Exception as e:
                    print(e)
                    if curr_link in self.urls:
                        self.urls.remove(curr_link)
                        if len(self.contents) > len(self.urls):
                            self.contents.pop()
                        if len(self.titles) > len(self.urls):
                            self.titles.pop()
                    
                    
        # Data persistence -> Save urls and contents in pickle files
        self.save_urls()
        self.save_contents()
        self.save_titles()


    async def get_content(self, url: str, session) -> BeautifulSoup:
        async with session.get(url) as response:
            content = await response.text()
            if response.status != 200 or not content:
                return None
        
        soup = BeautifulSoup(content, "html.parser")
        if not soup.title:
            return None

        return soup

