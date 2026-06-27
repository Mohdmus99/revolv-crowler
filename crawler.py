import os
import re
import json
import datetime
import time
import argparse
import requests
import lxml.html
import concurrent.futures
from openai import OpenAI
from db import save_coupons, get_uncategorized_coupons, update_coupon_category, update_coupon_category_and_expiry, get_all_coupons

# Load environment variables manually
def load_env(file_path=".env"):
    if not os.path.exists(file_path):
        return
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

load_env()

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
DB_PATH = os.environ.get('DB_PATH', 'coupons.db')

ALLOWED_CATEGORIES = [
    "مستحضر التجميل والعناية", # Normalized beauty name or standard match
    "مستحضرات التجميل والعناية",
    "ازياء",
    "الكترونيات",
    "منتجات رقمية",
    "أغذية وتموينات",
    "مستلزمات المنزل",
    "الاكسسوارات و الهدايا",
    "الكتب والتعليم",
    "مجوهرات",
    "صحة ولياقة",
    "سيارات",
    "خدمات",
    "المطاعم والمقاهي",
    "العاب",
    "حيوانات",
    "الفنون والموسيقى",
    "عيادة طبية",
    "أخرى"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

# --- Mahally Scraper ---

def fetch_mahally_page(page_number):
    url = f"https://mahally.com/ar/coupons/?coupons[page]={page_number}"
    print(f"Fetching Mahally page: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error fetching Mahally page {page_number}: HTTP Status {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception fetching Mahally page {page_number}: {e}")
        return None

def parse_mahally_coupons(html_content):
    if not html_content:
        return []
    
    doc = lxml.html.fromstring(html_content)
    li_elements = doc.xpath('//li[descendant::div[contains(@class, "couponCard")]]')
    
    coupons = []
    for li in li_elements:
        details_link = li.xpath('.//a[contains(@class, "abs-size")]/@href')
        coupon_id = ''
        coupon_url = ''
        if details_link:
            coupon_url = 'https://mahally.com' + details_link[0]
            m = re.search(r'/coupons/(\d+)', details_link[0])
            if m:
                coupon_id = m.group(1)
        
        if not coupon_id:
            continue
            
        store_name_el = li.xpath('.//h2[@aria-label="Store Name"]/a')
        store_name = store_name_el[0].text_content().strip() if store_name_el else ''
        store_url = 'https://mahally.com' + store_name_el[0].get('href') if store_name_el else ''
        
        logo_el = li.xpath('.//a[contains(@class, "rounded-full")]//img')
        store_logo = logo_el[0].get('src') if logo_el else ''
        
        info_div = li.xpath('.//div[contains(@class, "couponCardInfo")]')
        coupon_value = ''
        expiry_date = ''
        details_parts = []
        
        if info_div:
            val_el = info_div[0].xpath('.//span[@aria-label="Coupon Value"]')
            coupon_value = val_el[0].text_content().strip() if val_el else ''
            coupon_value = re.sub(r'\s+', ' ', coupon_value)
            
            spans = info_div[0].xpath('./span')
            for s in spans:
                text = s.text_content().strip()
                text = re.sub(r'\s+', ' ', text)
                if not text:
                    continue
                if 'ينتهي' in text:
                    expiry_date = text
                details_parts.append(text)
        
        coupon_details = ' | '.join(details_parts)
        
        prod_imgs = li.xpath('.//div[contains(@class, "h-15")]//img/@src')
        
        code_el = li.xpath('.//div[@aria-label="coupon code"]/span')
        coupon_code = code_el[0].text_content().strip() if code_el else ''
        
        coupons.append({
            'id': f"mahally_{coupon_id}",
            'source': 'mahally',
            'store_name': store_name,
            'store_url': store_url,
            'store_logo': store_logo,
            'coupon_value': coupon_value,
            'coupon_details': coupon_details,
            'expiry_date': expiry_date,
            'product_images': prod_imgs,
            'coupon_code': coupon_code,
            'category': None
        })
        
    return coupons

def scrape_mahally(max_pages=5, page_delay=0.5):
    print("Starting Mahally Scraper...")
    mahally_coupons = []
    for page in range(1, max_pages + 1):
        html = fetch_mahally_page(page)
        if not html:
            break
        coupons = parse_mahally_coupons(html)
        if not coupons:
            break
        print(f"Scraped {len(coupons)} coupons from Mahally page {page}.")
        mahally_coupons.extend(coupons)
        if page < max_pages:
            time.sleep(page_delay)
    return mahally_coupons

# --- Qasimah Scraper ---

def scrape_qasimah():
    print("Starting Qasimah Scraper...")
    url = "https://qasimahapp.com/coupons"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"Error fetching Qasimah list page: Status {res.status_code}")
            return []
            
        doc = lxml.html.fromstring(res.content)
        coupon_cards = doc.xpath('//div[@class="couponCard"]')
        print(f"Found {len(coupon_cards)} Qasimah coupon cards.")
        
        def fetch_card_details(card):
            # Extract Logo
            logo_el = card.xpath('.//img[contains(@class, "couponLogo")]')
            logo_url = logo_el[0].get('src') if logo_el else ''
            if logo_url and not logo_url.startswith('http'):
                logo_url = 'https://qasimahapp.com' + logo_url
                
            # Extract Store Name
            title_el = card.xpath('.//span[@class="couponTitle"]')
            store_name = title_el[0].text_content().strip() if title_el else ''
            
            # Extract Brand Link
            link_el = card.xpath('.//a[contains(@class, "couponLink")]')
            brand_href = link_el[0].get('href') if link_el else ''
            brand_url = 'https://qasimahapp.com' + brand_href if brand_href else ''
            
            # Extract Coupon Value
            val_el = card.xpath('.//span[@class="discountPercent"]')
            coupon_value = val_el[0].text_content().strip() if val_el else ''
            
            # Brand ID
            brand_id = ''
            if brand_href:
                m = re.search(r'/brands/(\d+)', brand_href)
                if m:
                    brand_id = m.group(1)
            
            coupon_code = ''
            coupon_details = ''
            if brand_url:
                try:
                    d_res = requests.get(brand_url, headers=HEADERS, timeout=10)
                    d_doc = lxml.html.fromstring(d_res.content)
                    
                    code_el = d_doc.xpath('//span[@class="couponInlineCodeValue"]/text()')
                    if code_el:
                        coupon_code = code_el[0].strip()
                        
                    details_el = d_doc.xpath('//div[contains(@class, "cardDetails")]/text()')
                    if details_el:
                        coupon_details = ' '.join([t.strip() for t in details_el if t.strip()])
                except Exception:
                    pass
            
            return {
                'id': f'qasimah_{brand_id}' if brand_id else '',
                'source': 'qasimah',
                'store_name': store_name,
                'store_url': brand_url,
                'store_logo': logo_url,
                'coupon_value': coupon_value,
                'coupon_details': coupon_details or coupon_value,
                'expiry_date': '',
                'product_images': [],
                'coupon_code': coupon_code,
                'category': None
            }
            
        qasimah_coupons = []
        # Fetch detailed brand pages concurrently to save time
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(fetch_card_details, coupon_cards))
            qasimah_coupons = [r for r in results if r['id']]
            
        print(f"Scraped {len(qasimah_coupons)} coupons from Qasimah.")
        return qasimah_coupons
        
    except Exception as e:
        print(f"Exception scraping Qasimah: {e}")
        return []

# --- AI & Rule-based Categorization ---

def parse_arabic_date(text):
    if not text:
        return None
    
    text = text.strip()
    
    # Define mapping of Arabic months
    months_map = {
        "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4,
        "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
        "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12
    }
    
    # Target date reference is 2026-06-26 as current date
    base_date = datetime.date(2026, 6, 26)
    
    # Handle "اليوم" (today)
    if "اليوم" in text:
        return base_date.strftime("%Y-%m-%d")
        
    # Handle "غداً" or "غدا" (tomorrow)
    if "غدا" in text or "غداً" in text:
        tomorrow = base_date + datetime.timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
        
    # Match pattern: number followed by month name
    # e.g., "3 يوليو" or "ينتهي 3 يوليو" or "ينتهي في 3 يوليو"
    match = re.search(r'(\d+)\s+([أا]?[ببتثجحخدذرزسشصضطظعغفقكلمنهوي]+)', text)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        
        # Check if the word is in months_map
        month = None
        for m_name, m_num in months_map.items():
            if m_name in month_name:
                month = m_num
                break
                
        if month:
            year = base_date.year
            if month < base_date.month:
                year += 1
            try:
                dt = datetime.date(year, month, day)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
                
    return None

def rule_based_categorize(store_name, coupon_value, coupon_details):
    text = f"{store_name} {coupon_value} {coupon_details}".lower()
    
    # Beauty & Cosmetics
    if any(kw in text for kw in ["عود", "بخور", "عطور", "تجميل", "عناية", "مكياج", "درعة", "نخبة", "مسك", "عطر", "لوشن", "بشرة", "جمال"]):
        return "مستحضرات التجميل والعناية"
    # Fashion
    if any(kw in text for kw in ["ملابس", "ازياء", "أزياء", "فستان", "نعومي", "حذاء", "حقيبة", "شنطة", "شوز", "بوتيك", "عباية", "طرحة", "توب", "بشات"]):
        return "ازياء"
    # Electronics
    if any(kw in text for kw in ["جوال", "ايفون", "إلكترونيات", "كمبيوتر", "لابتوب", "شاحن", "سماعة", "أجهزة", "شاشة", "كيبل", "آيباد"]):
        return "الكترونيات"
    # Food & Groceries
    if any(kw in text for kw in ["تموينات", "أغذية", "خضار", "لحوم", "سوبرماركت", "بقالة", "عسل", "قهوة", "شوكولاته", "حلويات", "مخبز", "تعبئة", "شاي", "عسالون"]):
        return "أغذية وتموينات"
    # Restaurants & Cafes
    if any(kw in text for kw in ["مطعم", "كافيه", "مقهى", "شاورما", "برجر", "وجبة", "بيتزا", "فطور", "مأكولات"]):
        return "المطاعم والمقاهي"
    # Home Essentials
    if any(kw in text for kw in ["منزل", "منظفات", "مفارش", "كنب", "سجاد", "أثاث", "إنارة", "مطبخ", "غسيل", "أواني", "ويكس", "ممسحة", "ديكور", "نايس"]):
        return "مستلزمات المنزل"
    # Games
    if any(kw in text for kw in ["ألعاب", "العاب", "بلاستيشن", "سوني", "تويز", "دمى"]):
        return "العاب"
    # Pets
    if any(kw in text for kw in ["حيوان", "قطط", "طعام قطط", "كلاب", "أليف"]):
        return "حيوانات"
    # Jewelry
    if any(kw in text for kw in ["مجوهرات", "ذهب", "فضة", "خاتم", "سوار", "سلاسل", "قلادة", "ساعة", "ساعات", "لادون"]):
        return "مجوهرات"
    # Health & Fitness
    if any(kw in text for kw in ["صحة", "صيدلية", "لياقة", "فيتامينات", "بروتين", "نادي", "رياضة"]):
        return "صحة ولياقة"
    # Cars
    if any(kw in text for kw in ["سيارة", "سيارات", "إطارات", "زيت", "قطع غيار"]):
        return "سيارات"
    # Books & Education
    if any(kw in text for kw in ["كتب", "مكتبة", "قرطاسية", "تعليم", "دورة", "كتاب"]):
        return "الكتب والتعليم"
    # Accessories & Gifts
    if any(kw in text for kw in ["هدية", "هدايا", "ورد", "زهور", "اكسسوار", "نظارات", "بوكيه"]):
        return "الاكسسوارات و الهدايا"
    # Services
    if any(kw in text for kw in ["خدمة", "تصميم", "برمجة", "اشتراك", "خدمات", "غسيل سيارات"]):
        return "خدمات"
    # Digital Products
    if any(kw in text for kw in ["رقمي", "منتجات رقمية", "ملف", "بطاقة شحن", "بطاقات"]):
        return "منتجات رقمية"
        
    return "أخرى"

def categorize_coupons_batch_gemini(coupons_batch, api_key):
    """
    Sends a batch of coupons to Gemini 2.5 Flash to categorize them and calculate expiry dates.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    batch_data = []
    for c in coupons_batch:
        batch_data.append({
            'id': c['id'],
            'store_name': c['store_name'],
            'coupon_value': c['coupon_value'],
            'coupon_details': c['coupon_details']
        })
        
    system_prompt = f"""You are a smart e-commerce categorizer and expiration date parsing assistant.
Your task is to analyze coupon details and:
1. Categorize the store/brand into exactly ONE of the following Arabic categories:
{json.dumps(ALLOWED_CATEGORIES, ensure_ascii=False)}

2. Calculate/parse the coupon's expiration date.
The CURRENT DATE IS 2026-06-26. Use this to resolve relative dates (e.g., 'ينتهي 3 يوليو' means '2026-07-03' because July is after June, 'ينتهي اليوم' means '2026-06-26', etc.).

Rules:
1. You must respond with a JSON object containing a "classifications" array.
2. Each item in the array must contain:
   - "id": The coupon ID string matching the input.
   - "category": The selected Arabic category string (MUST be an exact match from the allowed list).
   - "expiry_date": The parsed/calculated standardized ISO expiration date string in format 'YYYY-MM-DD' (e.g., '2026-07-03'). If no expiration date is mentioned or it is a lifetime/infinite coupon, set this field to null.
   - "confidence": Float between 0.0 and 1.0.
   - "reasoning": A brief explanation in Arabic (1 sentence) for your classification and date calculation.
3. Make intelligent assumptions based on the store name and value description.
"""
    
    user_prompt = f"Please classify and parse dates for the following batch of coupons:\n{json.dumps(batch_data, ensure_ascii=False)}"
    prompt_text = f"{system_prompt}\n\nInput data to classify:\n{user_prompt}"
    
    data = {
        'contents': [{'parts': [{'text': prompt_text}]}],
        'generationConfig': {
            'responseMimeType': 'application/json'
        }
    }
    
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, json=data, timeout=30)
        if res.status_code == 200:
            res_json = res.json()
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            result_json = json.loads(text)
            return result_json.get('classifications', [])
        else:
            print(f"Gemini API Error: HTTP Status {res.status_code} - {res.text}")
            raise Exception(f"HTTP Status {res.status_code}")
    except Exception as e:
        print(f"Gemini API Exception: {e}. Falling back to rule-based categorization.")
        classifications = []
        for c in coupons_batch:
            cat = rule_based_categorize(c['store_name'], c['coupon_value'], c['coupon_details'])
            classifications.append({
                'id': c['id'],
                'category': cat,
                'expiry_date': parse_arabic_date(c.get('expiry_date')),
                'confidence': 0.5,
                'reasoning': f"Rule-based categorization fallback (Gemini error: {str(e)})"
            })
        return classifications

def categorize_coupons_batch(coupons_batch, api_key, model="gpt-4o-mini"):
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if gemini_key:
        return categorize_coupons_batch_gemini(coupons_batch, gemini_key)
        
    if not api_key:
        print("OpenAI API key missing. Falling back to rule-based categorization.")
        classifications = []
        for c in coupons_batch:
            cat = rule_based_categorize(c['store_name'], c['coupon_value'], c['coupon_details'])
            classifications.append({
                'id': c['id'],
                'category': cat,
                'expiry_date': parse_arabic_date(c.get('expiry_date')),
                'confidence': 0.5,
                'reasoning': 'Rule-based categorization (No API Key)'
            })
        return classifications
    
    client = OpenAI(api_key=api_key)
    
    batch_data = []
    for c in coupons_batch:
        batch_data.append({
            'id': c['id'],
            'store_name': c['store_name'],
            'coupon_value': c['coupon_value'],
            'coupon_details': c['coupon_details']
        })
        
    system_prompt = f"""You are a smart e-commerce categorizer assistant.
Your task is to analyze coupon details and categorize the coupon's store/brand into exactly ONE of the following Arabic categories:
{json.dumps(ALLOWED_CATEGORIES, ensure_ascii=False)}

Rules:
1. You must respond with a JSON object containing a "classifications" array.
2. Each item in the array must contain:
   - "id": The coupon ID string matching the input.
   - "category": The selected Arabic category string (MUST be an exact match from the allowed list).
   - "confidence": Float between 0.0 and 1.0.
   - "reasoning": A brief explanation in Arabic (1 sentence) for your classification.
"""
    
    user_prompt = f"Please classify the following batch of coupons:\n{json.dumps(batch_data, ensure_ascii=False)}"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return result_json.get('classifications', [])
    except Exception as e:
        print(f"OpenAI API Error: {e}. Falling back to rule-based categorization.")
        classifications = []
        for c in coupons_batch:
            cat = rule_based_categorize(c['store_name'], c['coupon_value'], c['coupon_details'])
            classifications.append({
                'id': c['id'],
                'category': cat,
                'expiry_date': parse_arabic_date(c.get('expiry_date')),
                'confidence': 0.5,
                'reasoning': f"Rule-based categorization fallback (OpenAI error: {str(e)})"
            })
        return classifications

# --- Master Crawler Runner ---

def run_crawler(max_pages=5, page_delay=0.5):
    print("Starting master crawler engine for Revolv...")
    
    # 1. Scrape Mahally
    mahally_list = scrape_mahally(max_pages=max_pages, page_delay=page_delay)
    
    # 2. Scrape Qasimah
    qasimah_list = scrape_qasimah()
    
    # Combine lists
    all_scraped_coupons = mahally_list + qasimah_list
    print(f"Total coupons parsed from all sources: {len(all_scraped_coupons)}")
    
    if not all_scraped_coupons:
        return 0, 0
        
    # 3. Save to database (preserves category if exists)
    saved_new, updated_existing = save_coupons(all_scraped_coupons, DB_PATH)
    print(f"Database sync complete: {saved_new} new coupons saved, {updated_existing} existing updated.")
    
    # 4. Categorize any missing categories
    uncategorized = get_uncategorized_coupons(DB_PATH)
    print(f"Found {len(uncategorized)} uncategorized coupons in the database.")
    
    if uncategorized and (GEMINI_API_KEY or OPENAI_API_KEY):
        batch_size = 15
        categorized_count = 0
        
        for i in range(0, len(uncategorized), batch_size):
            batch = uncategorized[i:i+batch_size]
            print(f"Categorizing batch {i//batch_size + 1} of {-(len(uncategorized)//-batch_size)} (Size: {len(batch)})...")
            
            classifications = categorize_coupons_batch(batch, OPENAI_API_KEY, OPENAI_MODEL)
            
            # Map classifications back to DB
            for item in classifications:
                cid = item.get('id')
                cat = item.get('category')
                exp = item.get('expiry_date')
                # Normalize mapping (sometimes Gemini outputs slight variants like 'مستحضر' instead of 'مستحضرات')
                if cat == "مستحضر التجميل والعناية":
                    cat = "مستحضرات التجميل والعناية"
                if cid and cat in ALLOWED_CATEGORIES:
                    update_coupon_category_and_expiry(cid, cat, exp, DB_PATH)
                    categorized_count += 1
                    
            print(f"Successfully categorized {len(classifications)} coupons in this batch.")
            time.sleep(0.5)
            
        print(f"AI categorization complete. Categorized {categorized_count} coupons.")
    elif uncategorized:
        print("AI API keys not configured. Coupons will remain uncategorized.")
        
    return len(all_scraped_coupons), len(uncategorized)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Revolv Aggregator: Smart AI Coupon Crawler")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum Mahally pages to scrape (default 5)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay in seconds between pages (default 0.5)")
    args = parser.parse_args()
    
    run_crawler(max_pages=args.max_pages, page_delay=args.delay)
