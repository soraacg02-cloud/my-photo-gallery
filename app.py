import streamlit as st
from PIL import Image
import datetime
import json
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO
import time

# 設定網頁標題
st.set_page_config(page_title="雲端相簿 (永久免費版)", layout="wide")
st.title("☁️ 雲端相簿 Pro (防快取修正版)")

# --- 1. Cloudinary 連線設定 ---
cloudinary.config(
    cloud_name = st.secrets["cloudinary"]["cloud_name"],
    api_key = st.secrets["cloudinary"]["api_key"],
    api_secret = st.secrets["cloudinary"]["api_secret"],
    secure = True
)

DB_FILENAME = "photo_db.json"

# --- 2. 核心功能函數 ---

def load_db():
    """從雲端下載資料庫"""
    try:
        # 產生檔案的下載連結
        url, options = cloudinary.utils.cloudinary_url(DB_FILENAME, resource_type="raw")
        
        # [修正點 1] 加入時間戳記 (?t=...)
        # 這會強迫程式去抓「這一秒」的最新檔案，而不是抓快取裡的舊檔案
        no_cache_url = f"{url}?t={time.time()}"
        
        # 下載內容
        response = requests.get(no_cache_url)
        
        if response.status_code == 200:
            data = response.json()
            # 轉換日期
            for item in data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
            return data
        else:
            # 如果是 404，代表還沒建立過檔案，回傳空清單
            return []
    except Exception as e:
        # 如果出錯，在終端機印出來方便除錯
        print(f"讀取資料庫失敗: {e}")
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
            "tags": item['tags']
        })
    
    json_str = json.dumps(save_list, ensure_ascii=False, indent=4)
    
    # [修正點 2] 加入 invalidate=True
    # 這會告訴 Cloudinary 的伺服器：這個檔案更新了，請把舊的快取清除！
    cloudinary.uploader.upload(
        BytesIO(json_str.encode('utf-8')), 
        public_id=DB_FILENAME, 
        resource_type="raw", 
        overwrite=True,
        invalidate=True 
    )

def upload_image(file_obj):
    """上傳圖片"""
    response = cloudinary.uploader.upload(file_obj)
    return response['public_id'], response['secure_url']

def delete_image(public_id):
    """刪除圖片"""
    cloudinary.uploader.destroy(public_id)

# --- 3. 應用程式主邏輯 ---

# 初始化
if 'gallery' not in st.session_state:
    with st.spinner('正在連線到雲端資料庫...'):
        st.session_state.gallery = load_db()

TAG_OPTIONS = ["線搞", "上色", "單人", "雙人", "背景"]

# === 側邊欄：上傳區 ===
with st.sidebar:
    st.header("📤 上傳照片")
    uploaded_files = st.file_uploader("選擇照片...", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳"):
        progress_bar = st.progress(0)
        
        for i, uploaded_file in enumerate(uploaded_files):
            fname = uploaded_file.name
            try:
                # A. 上傳圖片
                pid, url = upload_image(uploaded_file)
                
                # B. 自動抓取日期
                try:
                    date_str = fname[:8]
                    img_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                except:
                    img_date = datetime.date.today()
                
                # C. 記錄到記憶體
                st.session_state.gallery.append({
                    "public_id": pid,
                    "url": url,
                    "name": fname,
                    "date": img_date,
                    "tags": []
                })
            except Exception as e:
                st.error(f"上傳失敗: {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        # D. 存檔
        save_db(st.session_state.gallery)
        st.success("上傳成功！")
        
        # [修正點 3] 等待 1 秒再重新整理，讓雲端有時間反應
        time.sleep(1)
        st.rerun()

# === 主畫面：瀏覽與篩選 ===
st.divider()

col1, col2 = st.columns(2)
with col1:
    filter_date = st.date_input("📅 篩選日期", value=None)
with col2:
    filter_tags = st.multiselect("🏷️ 篩選標籤", TAG_OPTIONS)

displayed_count = 0

# 檢查是否有資料
if not st.session_state.gallery:
    st.info("資料庫目前是空的。請上傳照片，它們會被記錄在 Cloudinary 的 photo_db.json 中。")
else:
    for photo in reversed(st.session_state.gallery):
        date_match = (filter_date is None) or (photo['date'] == filter_date)
        tag_match = not filter_tags or all(tag in photo['tags'] for tag in filter_tags)
        
        if date_match and tag_match:
            displayed_count += 1
            with st.container(border=True):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(photo['url'], use_container_width=True)
                
                with c2:
                    st.subheader(photo['name'])
                    st.caption(f"📅 {photo['date']}")
                    
                    new_tags = st.multiselect("標籤", TAG_OPTIONS, default=photo['tags'], key=f"t_{photo['public_id']}")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    if col_btn1.button("💾 儲存", key=f"s_{photo['public_id']}"):
                        photo['tags'] = new_tags
                        save_db(st.session_state.gallery)
                        st.toast("標籤已更新！")
                    
                    if col_btn2.button("🗑️ 刪除", key=f"d_{photo['public_id']}"):
                        delete_image(photo['public_id'])
                        st.session_state.gallery.remove(photo)
                        save_db(st.session_state.gallery)
                        st.rerun()

    if displayed_count == 0 and st.session_state.gallery:
        st.warning("有照片資料，但被篩選條件過濾掉了。")
