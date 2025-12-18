import streamlit as st
from PIL import Image
import datetime
import json
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO

# 設定網頁標題
st.set_page_config(page_title="雲端相簿 (永久免費版)", layout="wide")
st.title("☁️ 雲端相簿 Pro (Cloudinary 加速版)")

# --- 1. Cloudinary 連線設定 ---
# 程式會自動去 Secrets 抓取您設定好的帳號密碼
cloudinary.config(
    cloud_name = st.secrets["cloudinary"]["cloud_name"],
    api_key = st.secrets["cloudinary"]["api_key"],
    api_secret = st.secrets["cloudinary"]["api_secret"],
    secure = True
)

# 資料庫檔案名稱
DB_FILENAME = "photo_db.json"

# --- 2. 核心功能函數 ---

def load_db():
    """從雲端下載資料庫 (JSON檔)"""
    try:
        # 產生檔案的下載連結
        url, options = cloudinary.utils.cloudinary_url(DB_FILENAME, resource_type="raw")
        # 下載內容
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            # 把文字日轉回日期物件，方便程式處理
            for item in data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
            return data
        else:
            return [] # 如果是第一次使用，檔案還不存在，回傳空清單
    except Exception:
        return []

def save_db(data):
    """把資料庫存回雲端"""
    # 轉換資料格式 (因為 JSON 不能直接存日期物件)
    save_list = []
    for item in data:
        save_list.append({
            "public_id": item['public_id'],
            "url": item['url'],
            "name": item['name'],
            "date_str": item['date'].strftime("%Y-%m-%d"),
            "tags": item['tags']
        })
    
    # 轉成文字
    json_str = json.dumps(save_list, ensure_ascii=False, indent=4)
    
    # 上傳覆蓋舊檔 (resource_type="raw" 代表它是純檔案，不是圖片)
    cloudinary.uploader.upload(
        BytesIO(json_str.encode('utf-8')), 
        public_id=DB_FILENAME, 
        resource_type="raw", 
        overwrite=True
    )

def upload_image(file_obj):
    """上傳圖片到 Cloudinary"""
    # 這行指令會自動把圖片傳上去，並回傳圖片的資訊
    response = cloudinary.uploader.upload(file_obj)
    return response['public_id'], response['secure_url']

def delete_image(public_id):
    """從雲端刪除圖片"""
    cloudinary.uploader.destroy(public_id)

# --- 3. 應用程式主邏輯 ---

# 初始化：如果記憶體是空的，就去雲端載入資料
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
                    "public_id": pid, # Cloudinary 的身分證 ID
                    "url": url,       # 圖片網址 (速度很快)
                    "name": fname,
                    "date": img_date,
                    "tags": []
                })
            except Exception as e:
                st.error(f"上傳失敗: {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        # D. 全部傳完後，立刻存檔資料庫
        save_db(st.session_state.gallery)
        st.success("上傳成功！")
        st.rerun()

# === 主畫面：瀏覽與篩選 ===
st.divider()

col1, col2 = st.columns(2)
with col1:
    filter_date = st.date_input("📅 篩選日期", value=None)
with col2:
    filter_tags = st.multiselect("🏷️ 篩選標籤", TAG_OPTIONS)

displayed_count = 0

# 反轉列表 (reversed)，讓最新的照片顯示在最前面
for photo in reversed(st.session_state.gallery):
    # 篩選邏輯
    date_match = (filter_date is None) or (photo['date'] == filter_date)
    tag_match = not filter_tags or all(tag in photo['tags'] for tag in filter_tags)
    
    if date_match and tag_match:
        displayed_count += 1
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                # 顯示圖片 (直接使用 Cloudinary 網址)
                st.image(photo['url'], use_container_width=True)
            
            with c2:
                st.subheader(photo['name'])
                st.caption(f"📅 {photo['date']}")
                
                # 編輯標籤
                # key 加上 public_id 確保每個選單都是獨立的
                new_tags = st.multiselect("標籤", TAG_OPTIONS, default=photo['tags'], key=f"t_{photo['public_id']}")
                
                col_btn1, col_btn2 = st.columns(2)
                
                # 按鈕：儲存標籤
                if col_btn1.button("💾 儲存", key=f"s_{photo['public_id']}"):
                    # 更新記憶體中的資料
                    photo['tags'] = new_tags
                    # 更新雲端資料庫
                    save_db(st.session_state.gallery)
                    st.toast("標籤已更新！")
                
                # 按鈕：刪除照片
                if col_btn2.button("🗑️ 刪除", key=f"d_{photo['public_id']}"):
                    # 1. 刪除雲端圖片
                    delete_image(photo['public_id'])
                    # 2. 從清單中移除
                    st.session_state.gallery.remove(photo)
                    # 3. 更新資料庫
                    save_db(st.session_state.gallery)
                    st.rerun()

if displayed_count == 0:
    st.info("目前沒有照片。請從側邊欄上傳第一張照片吧！(第一次上傳會自動建立資料庫)")
