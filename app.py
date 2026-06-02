from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
import threading
import time
import random
from datetime import datetime, timedelta
from models import Normalizer
from scrapers import CrawlerService, CellphoneSScraper, TheGioiDiDongScraper, FPTShopScraper

app = Flask(__name__)
DB_FILE = "database.db"
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, url TEXT, image_path TEXT,
                name_pattern TEXT, price_pattern TEXT, status TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, normalized_name TEXT, price REAL,
                rating REAL, url TEXT, provider_id INTEGER, status TEXT, image_url TEXT,
                FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER, price REAL, recorded_at TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')
        
        if not conn.execute("SELECT id FROM providers WHERE name='CellphoneS'").fetchone():
            conn.execute("INSERT INTO providers (name, url, image_path, status) VALUES ('CellphoneS', 'https://cellphones.com.vn', '', 'Hoạt động')")
            conn.execute("INSERT INTO providers (name, url, image_path, status) VALUES ('Thế Giới Di Động', 'https://thegioididong.com', '', 'Hoạt động')")
            conn.execute("INSERT INTO providers (name, url, image_path, status) VALUES ('FPT Shop', 'https://fptshop.com.vn', '', 'Hoạt động')")
init_db()

crawler_service = CrawlerService()
crawler_service.register_scraper(CellphoneSScraper())
crawler_service.register_scraper(TheGioiDiDongScraper())
crawler_service.register_scraper(FPTShopScraper())

def save_product_and_history(name, price, rating, url, provider_id, status="Hoạt động", image_url=""):
    norm_name = Normalizer.normalize(name)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, price FROM products WHERE url = ?", (url,))
        existing = cursor.fetchone()
        
        if existing:
            pid = existing[0]
            if image_url:
                cursor.execute("UPDATE products SET price=?, rating=?, image_url=? WHERE id=?", (price, rating, image_url, pid))
            else:
                cursor.execute("UPDATE products SET price=?, rating=? WHERE id=?", (price, rating, pid))
                
            if existing[1] != price:
                cursor.execute("INSERT INTO price_history (product_id, price, recorded_at) VALUES (?,?,?)", (pid, price, now_str))
        else:
            cursor.execute('''
                INSERT INTO products (name, normalized_name, price, rating, url, provider_id, status, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, norm_name, price, rating, url, provider_id, status, image_url))
            pid = cursor.lastrowid
            for i in range(4, -1, -1):
                p_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
                m_price = price * random.uniform(0.96, 1.04) if i > 0 else price
                cursor.execute("INSERT INTO price_history (product_id, price, recorded_at) VALUES (?,?,?)", (pid, int(m_price), p_date))
        conn.commit()

def cron_worker():
    while True:
        time.sleep(60)
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                all_prods = conn.execute("SELECT DISTINCT name, provider_id, rating, url FROM products").fetchall()
            for r in all_prods:
                save_product_and_history(r['name'], r['price'], r['rating'], r['url'], r['provider_id'])
        except Exception as e: 
            print(f"Cron execution error: {e}")

threading.Thread(target=cron_worker, daemon=True).start()

@app.route('/')
def index():
    keyword = request.args.get('keyword', '').strip()
    min_p = request.args.get('min_price', 0, type=float)
    max_p = request.args.get('max_price', 200, type=float)
    
    if keyword:
        scraped = crawler_service.crawlAll(keyword)
        with sqlite3.connect(DB_FILE) as conn:
            cps_id = (conn.execute("SELECT id FROM providers WHERE name='CellphoneS'").fetchone() or [1])[0]
            tgdd_id = (conn.execute("SELECT id FROM providers WHERE name='Thế Giới Di Động'").fetchone() or [2])[0]
            fpt_id = (conn.execute("SELECT id FROM providers WHERE name='FPT Shop'").fetchone() or [3])[0]
            
            for item in scraped:
                url_lower = item['url'].lower()
                if "cellphones" in url_lower:
                    prov_id = cps_id
                elif "thegioididong" in url_lower or "dienmayxanh" in url_lower:
                    prov_id = tgdd_id
                else:
                    prov_id = fpt_id
                save_product_and_history(item['name'], item['price'], item['rating'], item['url'], prov_id)

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        query = '''
            SELECT p.*, MIN(p.price) as min_price, p.image_url as image_url 
            FROM products p
            WHERE p.status='Hoạt động'
        '''
        params = []
        if keyword:
            query += " AND p.normalized_name LIKE ?"
            params.append(f"%{Normalizer.normalize(keyword)}%")
        query += " GROUP BY p.normalized_name"
        
        if min_p > 0 or max_p < 200:
            query = f"SELECT * FROM ({query}) WHERE min_price >= ? AND min_price <= ?"
            params.extend([min_p * 1000000, max_p * 1000000])
            
        products = conn.execute(query, params).fetchall()
    return render_template('index.html', products=products, keyword=keyword)

@app.route('/compare/<normalized_name>')
def compare(normalized_name):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        offers = conn.execute('''
            SELECT p.*, prov.name as provider_name, prov.image_path as provider_logo 
            FROM products p
            LEFT JOIN providers prov ON p.provider_id = prov.id
            WHERE p.normalized_name=? AND p.status='Hoạt động' ORDER BY p.price ASC
        ''', (normalized_name,)).fetchall()
        
    if not offers: 
        return "Data not found.", 404
    
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        history = conn.execute("SELECT price, recorded_at FROM price_history WHERE product_id=? ORDER BY recorded_at ASC", (offers[0]['id'],)).fetchall()
        
    labels = [h['recorded_at'][:10] for h in history]
    prices = [h['price'] for h in history]
    return render_template('detail.html', offers=offers, main=offers[0], labels=labels, prices=prices)

@app.route('/admin/providers')
def admin_providers():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        providers = conn.execute("SELECT * FROM providers").fetchall()
    return render_template('admin_providers.html', providers=providers)

@app.route('/admin/provider/add', methods=['GET', 'POST'])
@app.route('/admin/provider/edit/<int:prov_id>', methods=['GET', 'POST'])
def admin_provider_form(prov_id=None):
    provider = None
    if prov_id:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            provider = conn.execute("SELECT * FROM providers WHERE id=?", (prov_id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        url = request.form['url']
        name_pattern = request.form['name_pattern']
        price_pattern = request.form['price_pattern']
        status = request.form['status']
        
        file = request.files['image_file']
        image_path = provider['image_path'] if provider else ""
        if file and file.filename != '':
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_path = '/' + filepath.replace('\\', '/')

        with sqlite3.connect(DB_FILE) as conn:
            if provider:
                conn.execute("UPDATE providers SET name=?, url=?, image_path=?, name_pattern=?, price_pattern=?, status=? WHERE id=?", (name, url, image_path, name_pattern, price_pattern, status, prov_id))
            else:
                conn.execute("INSERT INTO providers (name, url, image_path, name_pattern, price_pattern, status) VALUES (?,?,?,?,?,?)", (name, url, image_path, name_pattern, price_pattern, status))
        return redirect(url_for('admin_providers'))
    return render_template('admin_provider_edit.html', provider=provider)

@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        rating = float(request.form['rating'])
        url = request.form['url']
        provider_id = int(request.form['provider_id'])
        status = request.form['status']
        
        file = request.files.get('product_image')
        image_url = ""
        if file and file.filename != '':
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_url = '/' + filepath.replace('\\', '/')

        save_product_and_history(name, price, rating, url, provider_id, status, image_url)
        return redirect(url_for('admin_products'))

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        products = conn.execute("SELECT p.*, prov.name as provider_name, prov.image_path as provider_logo FROM products p LEFT JOIN providers prov ON p.provider_id = prov.id ORDER BY p.id DESC").fetchall()
        providers = conn.execute("SELECT id, name FROM providers WHERE status='Hoạt động'").fetchall()
    return render_template('admin_products.html', products=products, providers=providers)

@app.route('/admin/product/delete/<int:pid>')
def admin_product_delete(pid):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
    return redirect(url_for('admin_products'))

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)