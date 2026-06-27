import sqlite3
import json
import os

def get_db_connection(db_path='coupons.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path='coupons.db', drop_if_exists=False):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    if drop_if_exists:
        print("Dropping existing coupons table...")
        cursor.execute('DROP TABLE IF EXISTS coupons')
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            id TEXT PRIMARY KEY,
            source TEXT DEFAULT 'mahally',
            store_name TEXT,
            store_url TEXT,
            store_logo TEXT,
            coupon_value TEXT,
            coupon_details TEXT,
            expiry_date TEXT,
            product_images TEXT, -- JSON list of URLs
            coupon_code TEXT,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_coupons(coupons, db_path='coupons.db'):
    """
    Saves a list of coupons. Preserves existing categories to avoid redundant AI calls.
    Each coupon in coupons is a dict.
    """
    init_db(db_path) # ensure table exists
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    saved_count = 0
    updated_count = 0
    
    for c in coupons:
        cid = c['id']
        # Check if coupon already exists
        cursor.execute("SELECT category FROM coupons WHERE id = ?", (cid,))
        row = cursor.fetchone()
        
        category = c.get('category')
        if row:
            # Already exists in DB, preserve category if it was already assigned
            existing_category = row['category']
            if existing_category and not category:
                category = existing_category
            updated_count += 1
        else:
            saved_count += 1
            
        product_images_json = json.dumps(c.get('product_images', []))
        
        cursor.execute('''
            INSERT OR REPLACE INTO coupons (
                id, source, store_name, store_url, store_logo, coupon_value, 
                coupon_details, expiry_date, product_images, coupon_code, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cid,
            c.get('source', 'mahally'),
            c.get('store_name'),
            c.get('store_url'),
            c.get('store_logo'),
            c.get('coupon_value'),
            c.get('coupon_details'),
            c.get('expiry_date'),
            product_images_json,
            c.get('coupon_code'),
            category
        ))
        
    conn.commit()
    conn.close()
    return saved_count, updated_count

def get_uncategorized_coupons(db_path='coupons.db'):
    """
    Retrieves all coupons that have no category assigned.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons WHERE category IS NULL OR category = ''")
    rows = cursor.fetchall()
    
    uncategorized = []
    for r in rows:
        item = dict(r)
        item['product_images'] = json.loads(item['product_images']) if item['product_images'] else []
        uncategorized.append(item)
        
    conn.close()
    return uncategorized

def update_coupon_category(coupon_id, category, db_path='coupons.db'):
    """
    Updates the category of a single coupon.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE coupons SET category = ? WHERE id = ?", (category, coupon_id))
    conn.commit()
    conn.close()

def update_coupon_category_and_expiry(coupon_id, category, expiry_date, db_path='coupons.db'):
    """
    Updates the category and standardized expiry date of a single coupon.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE coupons SET category = ?, expiry_date = ? WHERE id = ?", (category, expiry_date, coupon_id))
    conn.commit()
    conn.close()

def get_all_coupons(db_path='coupons.db'):
    """
    Retrieves all coupons from the database.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    coupons = []
    for r in rows:
        item = dict(r)
        item['product_images'] = json.loads(item['product_images']) if item['product_images'] else []
        coupons.append(item)
        
    conn.close()
    return coupons
