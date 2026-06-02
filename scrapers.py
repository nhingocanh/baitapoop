from abc import ABC, abstractmethod
import sqlite3
from models import Product, Normalizer

class Scraper(ABC):
    @abstractmethod
    def fetch_products(self, keyword: str) -> list:
        pass

class CellphoneSScraper(Scraper):
    def fetch_products(self, keyword: str) -> list:
        results = []
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            provider = conn.execute("SELECT id FROM providers WHERE name='CellphoneS' AND status='Hoạt động'").fetchone()
            if not provider: 
                return results
            
            db_products = conn.execute(
                "SELECT * FROM products WHERE provider_id=? AND normalized_name LIKE ?", 
                (provider['id'], f"%{Normalizer.normalize(keyword)}%")
            ).fetchall()
            
            for p in db_products:
                results.append({"name": p['name'], "price": p['price'], "rating": p['rating'], "url": p['url']})
        return results

class TheGioiDiDongScraper(Scraper):
    def fetch_products(self, keyword: str) -> list:
        results = []
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            provider = conn.execute("SELECT id FROM providers WHERE name='Thế Giới Di Động' AND status='Hoạt động'").fetchone()
            if not provider: 
                return results
            
            db_products = conn.execute(
                "SELECT * FROM products WHERE provider_id=? AND normalized_name LIKE ?", 
                (provider['id'], f"%{Normalizer.normalize(keyword)}%")
            ).fetchall()
            
            for p in db_products:
                results.append({"name": p['name'], "price": p['price'], "rating": p['rating'], "url": p['url']})
        return results

class FPTShopScraper(Scraper):
    def fetch_products(self, keyword: str) -> list:
        results = []
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            provider = conn.execute("SELECT id FROM providers WHERE name='FPT Shop' AND status='Hoạt động'").fetchone()
            if not provider: 
                return results
            
            db_products = conn.execute(
                "SELECT * FROM products WHERE provider_id=? AND normalized_name LIKE ?", 
                (provider['id'], f"%{Normalizer.normalize(keyword)}%")
            ).fetchall()
            
            for p in db_products:
                results.append({"name": p['name'], "price": p['price'], "rating": p['rating'], "url": p['url']})
        return results

class CrawlerService:
    def __init__(self):
        self.scrapers = []
        
    def register_scraper(self, scraper: Scraper):
        self.scrapers.append(scraper)
        
    def crawlAll(self, keyword: str) -> list:
        all_data = []
        for s in self.scrapers:
            try: 
                all_data.extend(s.fetch_products(keyword))
            except Exception as e: 
                print(f"Error execution at {type(s).__name__}: {e}")
        return all_data