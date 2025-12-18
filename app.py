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
st.set_page_config(page_title="雲端相簿 Pro (視覺選取版)", layout="wide")
st.title("☁️ 雲端相簿 (視覺選取版)")

# --- 1. Cloudinary 連線設定 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

DB_FILENAME = "photo_db_v2.json"

# --- 2. 核心功能函數 (保持不變) ---

def load_db():
    """從雲端下載資料庫"""
    try:
        url, options = cloudinary.utils.cloudinary_url(DB_FILENAME, resource_type="raw")
        no_cache_url = f"{url}?t={time.time()}"
        response = requests.get(no_cache_url)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
                if 'album' not in item:
                    item['album'] = "未分類"
            return data
        else:
            return []
    except:
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
            "album": item.get('album', '未分類')
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
    cloudinary.uploader.destroy(public_id)

# --- 3. 應用程式主邏輯 ---

if 'gallery' not in st.session_state:
    with st.spinner('連線中...'):
        st.session_state.gallery = load_db()

# 取得相簿與標籤清單
existing_albums = sorted(list(set([item['album'] for item in st.session_state.gallery])))
if "未分類" not in existing_albums: existing_albums.append("未分類")
TAG_OPTIONS = ["人像", "風景", "美食", "工作", "回憶"]

# === 側邊欄：上傳區 (支援手機多選) ===
with st.sidebar:
    st.header("📂 上傳照片")
    album_mode = st.radio("模式", ["選擇現有相簿", "建立新相簿"])
    if album_mode == "建立新相簿":
        current_album = st.text_input("輸入新相簿名稱")
    else:
        current_album = st.selectbox("選擇相簿", existing_albums)

    # 這裡的 accept_multiple_files=True 就是支援手機多選的關鍵
    uploaded_files = st.file_uploader("選擇照片 (手機可長按多選)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳", type="primary"):
        if not current_album:
            st.error("請輸入相簿名稱")
        else:
            progress = st.progress(0)
            for i, f in enumerate(uploaded_files):
                try:
                    res = cloudinary.uploader.upload(f)
                    pid, url = res['public_id'], res['secure_url']
                    try:
                        d_str = f.name[:8]
                        img_date = datetime.datetime.strptime(d_str, "%Y%m%d").date()
                    except:
                        img_date = datetime.date.today()
                    
                    st.session_state.gallery.append({
                        "public_id": pid, "url": url, "name": f.name,
                        "date": img_date, "tags": [], "album": current_album
                    })
                except: pass
                progress.progress((i+1)/len(uploaded_files))
            save_db(st.session_state.gallery)
            st.success("上傳完成！")
            time.sleep(1)
            st.rerun()

# === 主畫面：瀏覽與視覺化選取 ===

# 1. 篩選
col1, col2 = st.columns(2)
with col1:
    filter_album = st.selectbox("📂 相簿分類", ["全部"] + existing_albums)
with col2:
    # 簡化日期篩選，只用年份
    years = sorted(list(set([p['date'].year for p in st.session_state.gallery])), reverse=True)
    filter_year = st.selectbox("📅 年份", ["全部"] + years)

# 執行篩選
filtered_photos = [
    p for p in st.session_state.gallery 
    if ((filter_album == "全部") or (p['album'] == filter_album)) and
       ((filter_year == "全部") or (p['date'].year == filter_year))
]

st.divider()

# 2. 照片展示與勾選 (Visual Selection)
selected_photos = [] # 用來存被勾選的照片

if filtered_photos:
    # 設定每行顯示 3 張照片 (手機上會自動變窄，還是建議 2-3 張比較剛好)
    cols = st.columns(3) 
    
    for idx, photo in enumerate(filtered_photos):
        # 使用餘數運算 % 來決定這張照片要放在第幾個欄位
        with cols[idx % 3]:
            # 顯示圖片
            st.image(photo['url'], use_container_width=True)
            
            # 顯示 Checkbox (關鍵修改)
            # key 必須是唯一的，所以我們加上 photo['public_id']
            is_selected = st.checkbox(
                f"選取: {photo['name']}", 
                key=f"sel_{photo['public_id']}" 
            )
            
            # 顯示當前標籤
            if photo['tags']:
                st.caption(f"🏷️ {','.join(photo['tags'])}")
            else:
                st.caption("無標籤")
            
            st.write("---") # 分隔線
            
            # 如果使用者勾選了，就把這張照片加入待處理清單
            if is_selected:
                selected_photos.append(photo)

# 3. 批次操作動作列 (如果有照片被選取才顯示)
if selected_photos:
    st.markdown(f"### ✅ 已選取 {len(selected_photos)} 張照片")
    
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        # 修改標籤區
        new_tags = st.multiselect("批次增加/修改標籤", TAG_OPTIONS)
        if st.button("更新標籤"):
            for p in selected_photos:
                # 更新原始資料
                for origin in st.session_state.gallery:
                    if origin['public_id'] == p['public_id']:
                        origin['tags'] = new_tags
            save_db(st.session_state.gallery)
            st.success("標籤更新成功！")
            time.sleep(1)
            st.rerun()

    with action_col2:
        # 刪除區
        st.write("危險區域")
        if st.button("🗑️ 刪除選取照片", type="primary"):
            for p in selected_photos:
                delete_image_from_cloud(p['public_id'])
                # 從清單移除
                st.session_state.gallery = [x for x in st.session_state.gallery if x['public_id'] != p['public_id']]
            save_db(st.session_state.gallery)
            st.success("刪除成功！")
            time.sleep(1)
            st.rerun()

elif filtered_photos:
    st.info("💡 勾選照片下方的方塊即可進行編輯或刪除。")
else:
    st.warning("沒有符合條件的照片。")
