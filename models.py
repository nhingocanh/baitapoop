import re
from datetime import datetime

class Normalizer:
    @staticmethod
    def normalize(name: str) -> str:
        if not name: 
            return ""
        name = name.lower()
        name = re.sub(r'[^a-zA-Z0-9\s]', ' ', name)
        return " ".join(name.split())

class Product:
    def __init__(self, product_id, name, normalized_name, price, rating, url, provider_id, status="Hoạt động"):
        self.id = product_id
        self.name = name
        self.normalized_name = normalized_name
        self.price = price
        self.rating = rating
        self.url = url
        self.provider_id = provider_id
        self.status = status

class PriceHistory:
    def __init__(self, product_id, price, recorded_at=None):
        self.product_id = product_id
        self.price = price
        self.recorded_at = recorded_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")