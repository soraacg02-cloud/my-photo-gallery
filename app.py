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
st.set_page_config(page_title="雲端相簿 Pro (手機修復版)", layout="wide")
st.title("☁️ 雲端相簿 Pro (排序與手機優化)")

# --- 1. Cloudinary 連線設定 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

DB_FILENAME = "photo_db_v2.json"

# --- 2. CSS 強力修正 (針對手機版網格) ---
def inject_custom_css():
    st.markdown("""
    <style>
    /* 1. 標籤樣式優化 */
    span[data-baseweb="tag"] {
        background-color: #ff4b4b !important;
    }
    
    /* 2. 手機版強制網格 (Mobile Grid Fix) 
       我們針對螢幕寬度小於 640px 的裝置
    */
    @media (max-width: 640px) {
        /* 針對 Streamlit 的列 (Column) 進行強制縮減 */
        [data-testid="column"] {
            width: 50% !important;
            flex: 1 1 50% !important;
            min-width: 50% !important;
        }
        
        /* 修正圖片在窄欄位中的顯示 */
        [data-testid="column"] img {
            max-width: 100% !important;
            height: auto !important;
        }
        
        /* 讓按鈕在手機上也比較好按，稍微縮小一點 margin */
        .stButton button {
            width: 100%;
            padding: 0.25rem 0.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- 3. 核心功能函數 ---
def load_db():
    try:
        url, options = cloudinary.utils.cloudinary_url(DB_FILENAME, resource_type="raw")
        no_cache_url = f"{url}?t={time.time()}"
        response = requests.get(no_cache_url)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
                if 'album' not in item: item['album'] = "未分類"
            return data
        else: return []
    except: return []

def save_db(data):
    save_list = []
    for item in data:
        save_list.append({
            "public_id": item['public_id'], "url": item['url'], "name": item['name'],
            "date_str": item['date'].strftime("%Y-%m-%d"), "tags": item['tags'],
            "album": item.get('album', '未分類')
        })
    json_str = json.dumps(save_list, ensure_ascii=False, indent=4)
    cloudinary.uploader.upload(
        BytesIO(json_str.encode('utf-8')), public_id=DB_FILENAME, 
        resource_type="raw", overwrite=True, invalidate=True 
    )

def delete_image_from_cloud(public_id):
    cloudinary.uploader.destroy(public_id)

# --- 4. 應用程式主邏輯 ---
if 'gallery' not in st.session_state:
    with st.spinner('載入資料庫...'):
        st.session_state.gallery = load_db()

# 資料整理
existing_albums = sorted(list(set([item['album'] for item in st.session_state.gallery])))
if "未分類" not in existing_albums: existing_albums.append("未分類")

existing_tags = sorted(list(set([tag for item in st.session_state.gallery for tag in item['tags']])))
DEFAULT_TAGS = ["人像", "風景", "美食", "工作", "回憶"]
ALL_TAG_OPTIONS = sorted(list(set(DEFAULT_TAGS + existing_tags)))

# === 側邊欄：上傳 ===
with st.sidebar:
    st.header("📂 上傳照片")
    album_mode = st.radio("模式", ["選擇現有相簿", "建立新相簿"])
    if album_mode == "建立新相簿":
        current_album = st.text_input("輸入新相簿名稱")
    else:
        current_album = st.selectbox("選擇上傳相簿", existing_albums)

    uploaded_files = st.file_uploader("選擇照片 (可多選)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳", type="primary"):
        if not current_album: st.error("請輸入相簿名稱")
        else:
            progress = st.progress(0)
            for i, f in enumerate(uploaded_files):
                try:
                    res = cloudinary.uploader.upload(f)
                    try: d = datetime.datetime.strptime(f.name[:8], "%Y%m%d").date()
                    except: d = datetime.date.today()
                    st.session_state.gallery.append({
                        "public_id": res['public_id'], "url": res['secure_url'], 
                        "name": f.name, "date": d, "tags": [], "album": current_album
                    })
                except: pass
                progress.progress((i+1)/len(uploaded_files))
            save_db(st.session_state.gallery)
            st.success("完成！")
            time.sleep(1)
            st.rerun()

# === 主畫面 ===

# 1. 篩選與排序工具列
st.subheader("🔍 瀏覽設定")

# 第一排：相簿 + 標籤
f_c1, f_c2 = st.columns([1, 2])
with f_c1:
    filter_album = st.selectbox("📂 相簿", ["全部"] + existing_albums)
with f_c2:
    filter_tags = st.multiselect("🏷️ 標籤篩選 (同時符合)", existing_tags)

# 第二排：排序 + 年份
f_c3, f_c4 = st.columns(2)
with f_c3:
    # [需求 2 & 3] 排序功能
    # 設定預設順序：日期 (舊→新)
    sort_option = st.selectbox(
        "🔃 排序方式", 
        ["日期 (舊→新)", "日期 (新→舊)", "檔名 (A→Z)", "檔名 (Z→A)", "標籤 (A→Z)"],
        index=0 # 預設選第一個
    )

with f_c4:
    all_years = sorted(list(set([p['date'].year for p in st.session_state.gallery])), reverse=True)
    filter_year = st.selectbox("📅 年份", ["全部"] + all_years)

# 執行篩選
filtered_photos = []
for p in st.session_state.gallery:
    match_album = (filter_album == "全部") or (p['album'] == filter_album)
    match_year = (filter_year == "全部") or (p['date'].year == filter_year)
    
    match_tags = True
    if filter_tags:
        match_tags = all(tag in p['tags'] for tag in filter_tags)
    
    if match_album and match_year and match_tags:
        filtered_photos.append(p)

# [需求 2 & 3] 執行排序邏輯
if sort_option == "日期 (舊→新)":
    # 使用 Python 的 sort, key 指定要比對的欄位
    filtered_photos.sort(key=lambda x: x['date']) 
elif sort_option == "日期 (新→舊)":
    filtered_photos.sort(key=lambda x: x['date'], reverse=True)
elif sort_option == "檔名 (A→Z)":
    filtered_photos.sort(key=lambda x: x['name'])
elif sort_option == "檔名 (Z→A)":
    filtered_photos.sort(key=lambda x: x['name'], reverse=True)
elif sort_option == "標籤 (A→Z)":
    # 如果沒標籤就排最後，有的話取第一個標籤來排序
    filtered_photos.sort(key=lambda x: x['tags'][0] if x['tags'] else "zzzz")

st.divider()

# 2. 檢視與操作列
ctrl_c1, ctrl_c2 = st.columns([1, 1])
with ctrl_c1:
    view_mode = st.radio("👀 模式", ["網格", "大圖"], horizontal=True, label_visibility="collapsed")
    num_columns = 3 if view_mode == "網格" else 1

with ctrl_c2:
    sel_c1, sel_c2 = st.columns(2)
    if sel_c1.button("✅ 全選"):
        for p in filtered_photos: st.session_state[f"sel_{p['public_id']}"] = True
        st.rerun()
    if sel_c2.button("❎ 取消"):
        for p in filtered_photos: st.session_state[f"sel_{p['public_id']}"] = False
        st.rerun()

# 3. 照片展示區
selected_photos = [] 

if filtered_photos:
    # 這裡會受到上方 CSS 影響，手機版會強制變成 2 欄
    cols = st.columns(num_columns)
    
    for idx, photo in enumerate(filtered_photos):
        with cols[idx % num_columns]:
            st.image(photo['url'], use_container_width=True)
            
            key = f"sel_{photo['public_id']}"
            if key not in st.session_state: st.session_state[key] = False
            
            is_selected = st.checkbox(f"{photo['name']}", key=key)
            
            if photo['tags']:
                st.caption(f"🏷️ {','.join(photo['tags'])}")
            
            if num_columns == 1:
                 st.text(f"相簿: {photo['album']} | 日期: {photo['date']}")
            
            st.write("") # 間距
            
            if is_selected:
                selected_photos.append(photo)

# 4. 批次操作區
if selected_photos:
    st.markdown("---")
    st.info(f"⚡ 已選取 {len(selected_photos)} 張照片")
    
    act_c1, act_c2 = st.columns(2)
    with act_c1:
        new_tags = st.multiselect("批次設定標籤", ALL_TAG_OPTIONS)
        if st.button("更新標籤"):
            for p in selected_photos:
                for origin in st.session_state.gallery:
                    if origin['public_id'] == p['public_id']:
                        origin['tags'] = new_tags
            save_db(st.session_state.gallery)
            st.toast("更新完成！")
            time.sleep(1)
            st.rerun()
            
    with act_c2:
        if st.button("🗑️ 刪除照片", type="primary"):
            for p in selected_photos:
                delete_image_from_cloud(p['public_id'])
                st.session_state.gallery = [x for x in st.session_state.gallery if x['public_id'] != p['public_id']]
            save_db(st.session_state.gallery)
            st.success("已刪除！")
            time.sleep(1)
            st.rerun()
else:
    if not filtered_photos:
        st.warning("沒有符合篩選條件的照片")
