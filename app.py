import streamlit as st
import pandas as pd
import json
import os
import time
import plotly.express as px
from db import get_all_coupons
from crawler import run_crawler

# Page Configuration
st.set_page_config(
    page_title="Revolv - Smart Coupon Aggregator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
DB_PATH = os.environ.get('DB_PATH', 'coupons.db')

# Language Dictionaries (Localization)
LOCALIZATION = {
    "English": {
        "title": "⚡ Revolv Coupon Hub",
        "subtitle": "Multi-Source AI-Powered Coupon Intelligence Platform",
        "lang_selector": "Language / اللغة",
        "search_store": "Search Store",
        "search_code": "Search Code",
        "filter_category": "Filter Category",
        "filter_source": "Filter Source",
        "all": "All",
        "show_expired": "Show Expired Coupons",
        "update_button": "🔄 Sync & Recrawl Now",
        "pages_to_crawl": "Mahally pages to crawl",
        "loading_crawling": "Crawling coupon feeds and classifying categories with Gemini AI...",
        "success_sync": "Sync Complete! Synced {} coupons.",
        "no_data_title": "No coupon data available yet.",
        "no_data_desc": "Click 'Sync & Recrawl Now' in the sidebar to populate the database.",
        "kpi_total": "Total Coupons",
        "kpi_stores": "Unique Stores",
        "kpi_categorized": "AI Categorized",
        "kpi_uncategorized": "Uncategorized",
        "tab_coupons": "🏷️ Coupons Feed",
        "tab_analytics": "📊 Analytics Dashboard",
        "analytics_title": "📊 Coupon Aggregator Analytics",
        "cat_dist_chart": "Distribution by Category",
        "store_dist_chart": "Top 10 Stores by Coupon Count",
        "source_ratio_chart": "Breakdown by Source (Mahally vs Qasimah)",
        "raw_data_title": "📄 Raw Coupons Data Table",
        "download_csv": "Download as CSV",
        "included_products": "Included Products:",
        "direct_discount": "Direct Discount (No Code)",
        "expires": "Expires:",
        "source": "Source",
        "category": "Category",
        "active": "Active",
        "expired": "Expired",
        "reasoning": "Reasoning",
        "other": "Other",
        "view_mode": "View Layout",
        "grid_view": "Grid Columns",
        "list_view": "Horizontal Rows"
    },
    "العربية": {
        "title": "⚡ ريـفـولـف (Revolv)",
        "subtitle": "المنصة الذكية لتجميع وتحليل كوبونات الخصم من مصادر متعددة",
        "lang_selector": "Language / اللغة",
        "search_store": "اسم المتجر",
        "search_code": "كود الكوبون",
        "filter_category": "التصنيف",
        "filter_source": "المصدر",
        "all": "الكل",
        "show_expired": "عرض الكوبونات المنتهية",
        "update_button": "🔄 تحديث وسحب البيانات الآن",
        "pages_to_crawl": "عدد صفحات محلي للسحب",
        "loading_crawling": "جاري سحب الكوبونات وتصنيفها بالذكاء الاصطناعي (Gemini)...",
        "success_sync": "تم بنجاح! تم جلب وتحديث {} كوبون.",
        "no_data_title": "لا توجد بيانات كوبونات حالياً.",
        "no_data_desc": "اضغط على 'تحديث وسحب البيانات الآن' في القائمة الجانبية لجلب البيانات.",
        "kpi_total": "إجمالي الكوبونات",
        "kpi_stores": "عدد المتاجر الفريدة",
        "kpi_categorized": "مصنفة بالذكاء الاصطناعي",
        "kpi_uncategorized": "غير مصنفة",
        "tab_coupons": "🏷️ تغذية الكوبونات",
        "tab_analytics": "📊 لوحة التحليلات",
        "analytics_title": "📊 تحليلات ومؤشرات الكوبونات",
        "cat_dist_chart": "توزيع الكوبونات حسب التصنيفات",
        "store_dist_chart": "أعلى 10 متاجر حسب عدد الكوبونات",
        "source_ratio_chart": "توزيع الكوبونات حسب المصدر (محلي وقسيمة)",
        "raw_data_title": "📄 جدول البيانات الخام للكوبونات",
        "download_csv": "تحميل كـ CSV",
        "included_products": "المنتجات المشمولة:",
        "direct_discount": "خصم مباشر (لا يوجد كود)",
        "expires": "ينتهي:",
        "source": "المصدر",
        "category": "التصنيف",
        "active": "نشط",
        "expired": "منتهي",
        "reasoning": "التبرير",
        "other": "أخرى",
        "view_mode": "طريقة العرض",
        "grid_view": "أعمدة شبكية",
        "list_view": "صفوف أفقية"
    }
}

# Category translations for English mode
CATEGORY_TRANSLATIONS = {
    "مستحضرات التجميل والعناية": "Cosmetics & Care",
    "مستحضر التجميل والعناية": "Cosmetics & Care",
    "ازياء": "Fashion",
    "الكترونيات": "Electronics",
    "منتجات رقمية": "Digital Products",
    "أغذية وتموينات": "Food & Groceries",
    "مستلزمات المنزل": "Home Essentials",
    "الاكسسوارات و الهدايا": "Accessories & Gifts",
    "الكتب والتعليم": "Books & Education",
    "مجوهرات": "Jewelry",
    "صحة ولياقة": "Health & Fitness",
    "سيارات": "Cars",
    "خدمات": "Services",
    "المطاعم والمقاهي": "Restaurants & Cafes",
    "العاب": "Games",
    "حيوانات": "Pets",
    "الفنون والموسيقى": "Arts & Music",
    "عيادة طبية": "Medical Clinic",
    "أخرى": "Other"
}

# Setup Sidebar - Logo
if os.path.exists("revolv_logo.png"):
    st.sidebar.image("revolv_logo.png", use_container_width=True)
else:
    st.sidebar.markdown(
        f"<h3 style='text-align: center; color:#10B981;'>⚡ REVOLV</h3>", 
        unsafe_allow_html=True
    )
st.sidebar.markdown("---")

lang = st.sidebar.selectbox("🌐 Choose Language / اختر اللغة", ["English", "العربية"])
texts = LOCALIZATION[lang]

# Custom CSS matching Revolv brand (navy/electric teal & green accents)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Tajawal:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Tajawal', sans-serif;
    }
    
    h1, h2, h3 {
        font-family: 'Outfit', 'Tajawal', sans-serif;
        font-weight: 700;
        color: #0F172A;
    }
    
    /* Revolv Brand Card Header */
    .revolv-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: white;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        margin-bottom: 25px;
        border-left: 6px solid #10B981;
    }
    
    /* KPI Card styling */
    .metric-card {
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
    }
    
    /* Coupon Card styling */
    .coupon-card {
        background: white;
        border-radius: 20px;
        border: 1px solid #E2E8F0;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
        overflow: hidden;
    }
    
    .coupon-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        border-color: #10B981;
    }
    
    /* Source Badge styling */
    .source-badge {
        font-size: 11px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 6px;
        color: white;
        display: inline-block;
        margin-bottom: 10px;
    }
    
    .badge-mahally {
        background-color: #69BE4B;
    }
    
    .badge-qasimah {
        background-color: #2563EB;
    }
    
    /* Card badge */
    .category-badge {
        background-color: #F1F5F9;
        color: #475569;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
        display: inline-block;
        margin-bottom: 12px;
        margin-left: 5px;
    }
    
    .value-tag {
        font-size: 22px;
        font-weight: 700;
        color: #0F172A;
        margin-top: 8px;
        margin-bottom: 4px;
    }
    
    .expiry-tag {
        font-size: 12px;
        color: #10B981;
        font-weight: 500;
        margin-top: 8px;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    
    .store-name {
        font-size: 16px;
        font-weight: 600;
        color: #0F172A;
    }
    
    .details-text {
        font-size: 13px;
        color: #64748B;
        margin-top: 6px;
        margin-bottom: 12px;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to localize categories
def get_localized_category(cat_name):
    if not cat_name:
        return texts["other"]
    if lang == "English":
        return CATEGORY_TRANSLATIONS.get(cat_name, cat_name)
    return cat_name

# Header Layout
if os.path.exists("revolv_logo.png"):
    col_l, col_t = st.columns([1.5, 8])
    with col_l:
        st.image("revolv_logo.png", width=180)
    with col_t:
        st.markdown(f"<p style='color: #64748B; font-size: 15px; margin-top: 15px; margin-bottom: 0; font-weight: 500;'>{texts['subtitle']}</p>", unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="revolv-header">
        <h1 style='color: white; margin: 0; font-size: 32px;'>{texts["title"]}</h1>
        <p style='color: #94A3B8; margin: 8px 0 0 0; font-size: 16px;'>{texts["subtitle"]}</p>
    </div>
    """, unsafe_allow_html=True)

# Verify database exists
if not os.path.exists(DB_PATH):
    from db import init_db
    init_db(DB_PATH)

coupons = get_all_coupons(DB_PATH)

# Sidebar Filter Panel
st.sidebar.header(f"🔍 {texts['filter_category']}")
search_store = st.sidebar.text_input(texts['search_store'], "")
search_code = st.sidebar.text_input(texts['search_code'], "")

# Source selector
source_options = [texts["all"], "Mahally", "Qasimah"]
selected_source = st.sidebar.selectbox(texts["filter_source"], source_options)

# Category selector
categories_list = [texts["all"]]
if coupons:
    cats_in_db = set(c['category'] for c in coupons if c['category'])
    categories_list.extend(sorted(list(cats_in_db)))

selected_category = st.sidebar.selectbox(texts["filter_category"], categories_list)

st.sidebar.markdown("---")
st.sidebar.header(f"👁️ {texts['view_mode']}")
view_options = [texts["grid_view"], texts["list_view"]]
selected_view = st.sidebar.radio("", view_options)

st.sidebar.markdown("---")

# Sync & Trigger panel
st.sidebar.header(f"⚙️ {texts['update_button']}")
max_pages = st.sidebar.slider(texts['pages_to_crawl'], min_value=1, max_value=20, value=3)

if st.sidebar.button(texts["update_button"], use_container_width=True):
    with st.spinner(texts["loading_crawling"]):
        scraped, uncategorized = run_crawler(max_pages=max_pages, page_delay=0.5)
        st.sidebar.success(texts["success_sync"].format(scraped))
        time.sleep(1)
        st.rerun()

# Build DataFrame and apply filters
if coupons:
    df = pd.DataFrame(coupons)
    
    # Store Name Filter
    if search_store:
        df = df[df['store_name'].str.contains(search_store, case=False, na=False)]
        
    # Coupon Code Filter
    if search_code:
        df = df[df['coupon_code'].str.contains(search_code, case=False, na=False)]
        
    # Source Filter
    if selected_source != texts["all"]:
        source_val = "mahally" if selected_source == "Mahally" else "qasimah"
        df = df[df['source'] == source_val]
        
    # Category Filter
    if selected_category != texts["all"]:
        df = df[df['category'] == selected_category]
        
    # Tabs layout
    tab_list, tab_stats = st.tabs([texts["tab_coupons"], texts["tab_analytics"]])
    
    # --- Tab 1: Coupons Feed ---
    with tab_list:
        total_coupons = len(df)
        unique_stores = df['store_name'].nunique()
        uncategorized_count = df['category'].isna().sum() + (df['category'] == '').sum()
        categorized_count = total_coupons - uncategorized_count
        
        # KPI widgets
        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            st.markdown(f"<div class='metric-card'><div style='font-size:14px;color:#64748B;'>{texts['kpi_total']}</div><div style='font-size:28px;font-weight:700;color:#0F172A;'>{total_coupons}</div></div>", unsafe_allow_html=True)
        with kpi_cols[1]:
            st.markdown(f"<div class='metric-card'><div style='font-size:14px;color:#64748B;'>{texts['kpi_stores']}</div><div style='font-size:28px;font-weight:700;color:#0F172A;'>{unique_stores}</div></div>", unsafe_allow_html=True)
        with kpi_cols[2]:
            st.markdown(f"<div class='metric-card'><div style='font-size:14px;color:#64748B;'>{texts['kpi_categorized']}</div><div style='font-size:28px;font-weight:700;color:#10B981;'>{categorized_count}</div></div>", unsafe_allow_html=True)
        with kpi_cols[3]:
            st.markdown(f"<div class='metric-card'><div style='font-size:14px;color:#64748B;'>{texts['kpi_uncategorized']}</div><div style='font-size:28px;font-weight:700;color:#EF4444;'>{uncategorized_count}</div></div>", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        coupon_records = df.to_dict('records')
        
        if selected_view == texts["grid_view"]:
            # Grid layout
            cols_per_row = 3
            for idx in range(0, len(coupon_records), cols_per_row):
                grid_cols = st.columns(cols_per_row)
                for col_idx in range(cols_per_row):
                    item_idx = idx + col_idx
                    if item_idx >= len(coupon_records):
                        break
                    
                    c = coupon_records[item_idx]
                    with grid_cols[col_idx]:
                        cat_display = get_localized_category(c.get('category'))
                        src_badge = "badge-mahally" if c.get('source') == "mahally" else "badge-qasimah"
                        src_display = "Mahally" if c.get('source') == "mahally" else "Qasimah"
                        logo = c.get('store_logo') or "https://cdn.salla.network/images/logo/mahly/logo-wide.png"
                        
                        st.markdown(f"""
                        <div class="coupon-card">
                            <div>
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span class="source-badge {src_badge}">{src_display}</span>
                                    <span class="category-badge">{cat_display}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                    <img src="{logo}" style="width: 48px; height: 48px; border-radius: 50%; object-fit: contain; border: 1px solid #E2E8F0;"/>
                                    <div class="store-name"><a href="{c.get('store_url')}" target="_blank" style="color: inherit; text-decoration: none;">{c.get('store_name')}</a></div>
                                </div>
                                <div class="value-tag">{c.get('coupon_value')}</div>
                                <div class="details-text">{c.get('coupon_details')}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Code field
                        if c.get('coupon_code'):
                            st.code(c.get('coupon_code'), language="")
                        else:
                            st.caption(texts["direct_discount"])
                            
                        # Included product images (for mahally)
                        prod_imgs = c.get('product_images', [])
                        if prod_imgs:
                            st.markdown(f"<p style='font-size: 11px; margin-bottom: 4px; color: #64748B;'>{texts['included_products']}</p>", unsafe_allow_html=True)
                            img_cols = st.columns(min(len(prod_imgs), 4))
                            for img_idx, img_col in enumerate(img_cols):
                                if img_idx < len(prod_imgs):
                                    img_col.image(prod_imgs[img_idx], use_container_width=True)
                                    
                        if c.get('expiry_date'):
                            st.markdown(f"<div class='expiry-tag'>📅 {texts['expires']} {c.get('expiry_date')}</div>", unsafe_allow_html=True)
                            
                        st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
        else:
            # List layout (Horizontal layout)
            for c in coupon_records:
                cat_display = get_localized_category(c.get('category'))
                src_badge = "badge-mahally" if c.get('source') == "mahally" else "badge-qasimah"
                src_display = "Mahally" if c.get('source') == "mahally" else "Qasimah"
                logo = c.get('store_logo') or "https://cdn.salla.network/images/logo/mahly/logo-wide.png"
                
                with st.container(border=True):
                    col_logo, col_desc, col_code_exp = st.columns([1.2, 5, 2.3])
                    
                    with col_logo:
                        st.markdown(f"""
                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; gap: 8px;">
                            <img src="{logo}" style="width: 64px; height: 64px; border-radius: 50%; object-fit: contain; border: 1px solid #E2E8F0;"/>
                            <span class="source-badge {src_badge}" style="margin-bottom: 0;">{src_display}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with col_desc:
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                            <span class="store-name" style="font-size: 18px;"><a href="{c.get('store_url')}" target="_blank" style="color: inherit; text-decoration: none;">{c.get('store_name')}</a></span>
                            <span class="category-badge" style="margin-bottom: 0;">{cat_display}</span>
                        </div>
                        <div class="value-tag" style="font-size: 20px; margin-top: 4px; margin-bottom: 4px;">{c.get('coupon_value')}</div>
                        <div class="details-text" style="margin-top: 0; margin-bottom: 0;">{c.get('coupon_details')}</div>
                        """, unsafe_allow_html=True)
                        
                        # Included product images (for mahally)
                        prod_imgs = c.get('product_images', [])
                        if prod_imgs:
                            st.markdown(f"<p style='font-size: 11px; margin-bottom: 4px; margin-top: 6px; color: #64748B;'>{texts['included_products']}</p>", unsafe_allow_html=True)
                            img_cols = st.columns(min(len(prod_imgs), 6))
                            for img_idx, img_col in enumerate(img_cols):
                                if img_idx < len(prod_imgs):
                                    img_col.image(prod_imgs[img_idx], use_container_width=True)
                                    
                    with col_code_exp:
                        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
                        if c.get('coupon_code'):
                            st.code(c.get('coupon_code'), language="")
                        else:
                            st.caption(texts["direct_discount"])
                            
                        if c.get('expiry_date'):
                            st.markdown(f"<div class='expiry-tag' style='margin-top: 4px;'>📅 {texts['expires']} {c.get('expiry_date')}</div>", unsafe_allow_html=True)
                    
    # --- Tab 2: Analytics Dashboard ---
    with tab_stats:
        st.markdown(f"### {texts['analytics_title']}")
        
        # 3 Metrics plots
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            # Category Breakdown
            st.markdown(f"#### 📊 {texts['cat_dist_chart']}")
            cat_df = df[df['category'].notna() & (df['category'] != '')].copy()
            if not cat_df.empty:
                cat_df['localized_cat'] = cat_df['category'].apply(get_localized_category)
                cat_counts = cat_df['localized_cat'].value_counts().reset_index()
                cat_counts.columns = [texts['category'], texts['kpi_total']]
                fig_cat = px.bar(cat_counts, x=texts['category'], y=texts['kpi_total'], color=texts['category'],
                                 color_discrete_sequence=px.colors.qualitative.Plotly)
                fig_cat.update_layout(showlegend=False, height=350, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.caption("No categorized data.")
                
        with col_c2:
            # Source Distribution Donut Chart
            st.markdown(f"#### 🍕 {texts['source_ratio_chart']}")
            src_counts = df['source'].value_counts().reset_index()
            src_counts.columns = [texts['source'], texts['kpi_total']]
            # Localize source strings
            src_counts[texts['source']] = src_counts[texts['source']].map({"mahally": "Mahally", "qasimah": "Qasimah"})
            fig_src = px.pie(src_counts, values=texts['kpi_total'], names=texts['source'], hole=0.4,
                             color_discrete_sequence=['#69BE4B', '#2563EB'])
            fig_src.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig_src, use_container_width=True)
            
        # Top Stores plot
        st.markdown(f"#### 🏢 {texts['store_dist_chart']}")
        store_counts = df['store_name'].value_counts().head(10).reset_index()
        store_counts.columns = [texts['search_store'], texts['kpi_total']]
        fig_store = px.bar(store_counts, x=texts['kpi_total'], y=texts['search_store'], orientation='h',
                           color=texts['search_store'], color_discrete_sequence=px.colors.sequential.Teal)
        fig_store.update_layout(showlegend=False, height=400, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_store, use_container_width=True)
        
        # Raw Data Section
        st.markdown("---")
        st.markdown(f"### {texts['raw_data_title']}")
        raw_df = df[['source', 'store_name', 'coupon_value', 'coupon_code', 'category', 'expiry_date', 'store_url']].copy()
        # Localize headers and category contents for raw table
        raw_df['category'] = raw_df['category'].apply(get_localized_category)
        raw_df['source'] = raw_df['source'].map({"mahally": "Mahally", "qasimah": "Qasimah"})
        
        st.dataframe(raw_df, use_container_width=True)
        
        # Export CSV option
        csv = raw_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 {texts['download_csv']}",
            data=csv,
            file_name="revolv_coupons.csv",
            mime="text/csv",
        )
else:
    st.info(texts["no_data_desc"])
