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
st.set_page_config(page_title="雲端相簿 Ultimate", layout="wide")
st.title("☁️ 雲端相簿 Ultimate (全選+切換視圖)")

# --- 1. Cloudinary 連線設定 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

DB_FILENAME = "photo_db_v2.json"

# --- 2. 核心功能函數 ---
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

# --- 3. 應用程式主邏輯 ---
if 'gallery' not in st.session_state:
    with st.spinner('載入資料庫...'):
        st.session_state.gallery = load_db()

existing_albums = sorted(list(set([item['album'] for item in st.session_state.gallery])))
if "未分類" not in existing_albums: existing_albums.append("未分類")
TAG_OPTIONS = ["人像", "風景", "美食", "工作", "回憶"]

# === 側邊欄：上傳與設定 ===
with st.sidebar:
    st.header("📂 上傳照片")
    album_mode = st.radio("模式", ["選擇現有相簿", "建立新相簿"])
    if album_mode == "建立新相簿":
        current_album = st.text_input("輸入新相簿名稱")
    else:
        current_album = st.selectbox("選擇相簿", existing_albums)

    uploaded_files = st.file_uploader("選擇照片 (可多選)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳", type="primary"):
        if not current_album: st.error("請輸入相簿名稱")
        else:
            progress = st.progress(0)
            for i, f in enumerate(uploaded_files):
                try:
                    res = cloudinary.uploader.upload(f)
                    try: 
                        d = datetime.datetime.strptime(f.name[:8], "%Y%m%d").date()
                    except: 
                        d = datetime.date.today()
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

# === 主畫面：篩選、控制與展示 ===

# 1. 篩選工具列 (Filter Toolbar)
st.subheader("🔍 篩選條件")
c1, c2, c3 = st.columns(3)

with c1:
    filter_album = st.selectbox("相簿", ["全部"] + existing_albums)

# 準備年月資料
all_years = sorted(list(set([p['date'].year for p in st.session_state.gallery])), reverse=True)
all_months = list(range(1, 13))

with c2:
    filter_year = st.selectbox("年份", ["全部"] + all_years)
with c3:
    filter_month = st.selectbox("月份", ["全部"] + all_months)

# 執行篩選
filtered_photos = [
    p for p in st.session_state.gallery 
    if ((filter_album == "全部") or (p['album'] == filter_album)) and
       ((filter_year == "全部") or (p['date'].year == filter_year)) and
       ((filter_month == "全部") or (p['date'].month == filter_month))
]

st.divider()

# 2. 檢視與選取控制列 (View & Selection Control)
ctrl_c1, ctrl_c2 = st.columns([1, 1])

with ctrl_c1:
    # 瀏覽模式切換
    view_mode = st.radio("👀 瀏覽模式", ["網格 (3欄)", "大圖 (1欄)"], horizontal=True)
    if view_mode == "網格 (3欄)":
        num_columns = 3
    else:
        num_columns = 1

with ctrl_c2:
    # 全選/取消全選按鈕
    st.write("批次選取")
    sel_c1, sel_c2 = st.columns(2)
    if sel_c1.button("✅ 全選本頁"):
        for p in filtered_photos:
            st.session_state[f"sel_{p['public_id']}"] = True
        st.rerun()
    
    if sel_c2.button("❎ 取消全選"):
        for p in filtered_photos:
            st.session_state[f"sel_{p['public_id']}"] = False
        st.rerun()

# 3. 照片展示區 (Gallery)
selected_photos = [] 

if filtered_photos:
    cols = st.columns(num_columns)
    
    for idx, photo in enumerate(filtered_photos):
        with cols[idx % num_columns]:
            # 決定顯示尺寸
            use_width = True # 網格模式自動調整
            
            st.image(photo['url'], use_container_width=use_width)
            
            # 檢查 Checkbox 狀態
            key = f"sel_{photo['public_id']}"
            # 如果 key 不在 session_state，初始化為 False
            if key not in st.session_state:
                st.session_state[key] = False
            
            is_selected = st.checkbox(
                f"{photo['name']}", 
                key=key
            )
            
            if photo['tags']:
                st.caption(f"🏷️ {','.join(photo['tags'])}")
            
            # 只有在大圖模式才顯示詳細日期，避免網格太擠
            if num_columns == 1:
                st.text(f"相簿: {photo['album']} | 日期: {photo['date']}")
            
            st.write("---")
            
            if is_selected:
                selected_photos.append(photo)

# 4. 批次操作區 (Batch Actions)
# 使用 fixed container 讓操作區在照片很多時也能容易看到 (Streamlit 原生不支援 sticky footer，這裡放底部)
if selected_photos:
    st.warning(f"⚡ 目前已選取 {len(selected_photos)} 張照片")
    
    act_c1, act_c2 = st.columns(2)
    with act_c1:
        new_tags = st.multiselect("批次標籤", TAG_OPTIONS)
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
        if st.button("🗑️ 刪除選取項目", type="primary"):
            for p in selected_photos:
                delete_image_from_cloud(p['public_id'])
                st.session_state.gallery = [x for x in st.session_state.gallery if x['public_id'] != p['public_id']]
            save_db(st.session_state.gallery)
            st.success("已刪除！")
            time.sleep(1)
            st.rerun()
else:
    if filtered_photos:
        st.info("💡 勾選上方照片進行操作")
    else:
        st.warning("沒有符合篩選條件的照片")
