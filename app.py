import streamlit as st
import datetime
import json
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO
import time

# 設定網頁標題
st.set_page_config(page_title="雲端相簿 Pro+", layout="wide")
st.title("☁️ 雲端相簿 Pro+ (相簿管理版)")

# --- 1. Cloudinary 連線設定 ---
# 請確保 .streamlit/secrets.toml 設定正確
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

DB_FILENAME = "photo_db_v2.json" # 升級檔名以區隔舊版

# --- 2. 核心功能函數 ---

def load_db():
    """從雲端下載資料庫"""
    try:
        url, options = cloudinary.utils.cloudinary_url(DB_FILENAME, resource_type="raw")
        no_cache_url = f"{url}?t={time.time()}"
        response = requests.get(no_cache_url)
        
        if response.status_code == 200:
            data = response.json()
            # 資料轉換與修復 (確保舊資料有 album 欄位)
            for item in data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
                if 'album' not in item:
                    item['album'] = "未分類" # 舊資料預設歸類
            return data
        else:
            return []
    except Exception as e:
        return []

def save_db(data):
    """把資料庫存回雲端"""
    save_list = []
    for item in data:
        save_list.append({
            "public_id": item['public_id'],
            "url": item['url'],
            "name": item['name'],
            "date_str": item['date'].strftime("%Y-%m-%d"),
            "tags": item['tags'],
            "album": item.get('album', '未分類') # 新增儲存相簿欄位
        })
    
    json_str = json.dumps(save_list, ensure_ascii=False, indent=4)
    cloudinary.uploader.upload(
        BytesIO(json_str.encode('utf-8')), 
        public_id=DB_FILENAME, 
        resource_type="raw", 
        overwrite=True,
        invalidate=True 
    )

def delete_image_from_cloud(public_id):
    """刪除雲端圖片"""
    cloudinary.uploader.destroy(public_id)

# --- 3. 應用程式主邏輯 ---

# 初始化 Session State
if 'gallery' not in st.session_state:
    with st.spinner('正在連線到雲端資料庫...'):
        st.session_state.gallery = load_db()

# 取得所有現有的相簿名稱
existing_albums = sorted(list(set([item['album'] for item in st.session_state.gallery])))
if "未分類" not in existing_albums:
    existing_albums.append("未分類")

TAG_OPTIONS = ["人像", "風景", "美食", "工作", "回憶"]

# === 側邊欄：相簿與上傳區 ===
with st.sidebar:
    st.header("📂 1. 選擇或建立相簿")
    
    # 讓使用者選擇現有相簿或輸入新名稱
    album_mode = st.radio("模式", ["選擇現有相簿", "建立新相簿"])
    
    if album_mode == "建立新相簿":
        current_album = st.text_input("輸入新相簿名稱")
    else:
        current_album = st.selectbox("選擇相簿", existing_albums)

    st.divider()
    st.header("📤 2. 上傳照片")
    st.info(f"即將上傳至：**{current_album}**")
    
    uploaded_files = st.file_uploader("選擇照片...", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳", type="primary"):
        if not current_album:
            st.error("請先輸入或選擇相簿名稱！")
        else:
            progress_bar = st.progress(0)
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    # A. 上傳
                    res = cloudinary.uploader.upload(uploaded_file)
                    pid, url = res['public_id'], res['secure_url']
                    
                    # B. 處理日期
                    fname = uploaded_file.name
                    try:
                        date_str = fname[:8] # 嘗試從檔名抓日期 ex: 20231201.jpg
                        img_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                    except:
                        img_date = datetime.date.today()
                    
                    # C. 加入資料庫 (包含 album)
                    st.session_state.gallery.append({
                        "public_id": pid,
                        "url": url,
                        "name": fname,
                        "date": img_date,
                        "tags": [],
                        "album": current_album 
                    })
                except Exception as e:
                    st.error(f"上傳失敗: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            # D. 存檔
            save_db(st.session_state.gallery)
            st.success("上傳完成！")
            time.sleep(1)
            st.rerun()

# === 主畫面：瀏覽與管理 ===

# 1. 頂部篩選區 (Filter)
st.subheader("🔍 篩選與檢視")
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    filter_album = st.selectbox("相簿分類", ["全部"] + existing_albums)

# 準備年份與月份資料
all_years = sorted(list(set([d['date'].year for d in st.session_state.gallery])), reverse=True)
all_months = list(range(1, 13))

with col_f2:
    filter_year = st.selectbox("年份", ["全部"] + all_years)

with col_f3:
    filter_month = st.selectbox("月份", ["全部"] + all_months)

# 執行篩選邏輯
filtered_gallery = []
for photo in st.session_state.gallery:
    # 相簿篩選
    match_album = (filter_album == "全部") or (photo['album'] == filter_album)
    # 年份篩選
    match_year = (filter_year == "全部") or (photo['date'].year == filter_year)
    # 月份篩選
    match_month = (filter_month == "全部") or (photo['date'].month == filter_month)
    
    if match_album and match_year and match_month:
        filtered_gallery.append(photo)

st.caption(f"共找到 {len(filtered_gallery)} 張照片")

# 2. 批次處理區 (Batch Actions)
st.divider()
st.subheader("🛠️ 批次管理")

if filtered_gallery:
    # 產生多選單，讓使用者選擇要處理的照片
    # 使用 format_func 讓選項顯示 "檔名 (相簿)"
    selected_photos = st.multiselect(
        "勾選要 **修改標籤** 或 **刪除** 的照片：",
        filtered_gallery,
        format_func=lambda x: f"{x['name']} ({x['album']})"
    )

    if selected_photos:
        b_col1, b_col2 = st.columns(2)
        
        # 批次修改標籤
        with b_col1:
            st.write("Tag 設定")
            batch_tags = st.multiselect("設定新標籤", TAG_OPTIONS)
            if st.button("套用標籤到選取照片"):
                for p in selected_photos:
                    # 找到原始資料並更新 (避免只更新到篩選後的副本)
                    for origin_p in st.session_state.gallery:
                        if origin_p['public_id'] == p['public_id']:
                            origin_p['tags'] = batch_tags
                save_db(st.session_state.gallery)
                st.success("標籤已批次更新！")
                time.sleep(1)
                st.rerun()

        # 批次刪除
        with b_col2:
            st.write("危險操作")
            if st.button("🗑️ 刪除選取的照片", type="primary"):
                progress = st.progress(0)
                for idx, p in enumerate(selected_photos):
                    # 1. 刪除雲端圖檔
                    delete_image_from_cloud(p['public_id'])
                    # 2. 從記憶體移除
                    st.session_state.gallery = [x for x in st.session_state.gallery if x['public_id'] != p['public_id']]
                    progress.progress((idx + 1) / len(selected_photos))
                
                # 3. 存檔更新 JSON
                save_db(st.session_state.gallery)
                st.success("照片已批次刪除！")
                time.sleep(1)
                st.rerun()

# 3. 照片展示區 (Gallery)
st.divider()
if filtered_gallery:
    # 簡單的 Grid 排版
    cols = st.columns(4)
    for idx, photo in enumerate(filtered_gallery):
        with cols[idx % 4]:
            st.image(photo['url'], use_container_width=True)
            st.caption(f"📁 {photo['album']}")
            st.caption(f"📅 {photo['date']}")
            if photo['tags']:
                st.write(f"🏷️ {','.join(photo['tags'])}")
else:
    st.info("沒有符合條件的照片。")
