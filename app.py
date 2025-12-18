import streamlit as st
from PIL import Image
import datetime
import os
import json

# 設定網頁標題與佈局
st.set_page_config(page_title="我的隨身相簿 Pro (存檔版)", layout="wide")
st.title("📱 我的隨身相簿 Pro (自動存檔版)")

# 定義檔案儲存路徑
DB_FILE = 'photo_db.json'
TAG_OPTIONS = ["線搞", "上色", "單人", "雙人"]

# --- 函數：讀取與寫入資料 ---
def load_data():
    """從 JSON 檔案讀取資料"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # JSON 存的是字串，轉回 Python 的日期物件
            for item in data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
                # 注意：真實環境中圖片通常存路徑，這裡為了教學簡化，
                # 我們假設圖片還是暫時性的，重整後需要重新上傳，
                # 但我們會保留「資料記錄」。
                # *進階提示：要永久保存圖片檔案需要更複雜的檔案系統操作*
            return data
    return []

def save_data(data_list):
    """將資料寫入 JSON 檔案"""
    # 準備要存檔的資料 (移除 Image 物件，只存文字資訊，因為 JSON 不能存圖片)
    save_list = []
    for item in data_list:
        save_item = {
            "name": item['name'],
            "date_str": item['date'].strftime("%Y-%m-%d"), # 把日期轉文字
            "tags": item['tags']
        }
        save_list.append(save_item)
    
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(save_list, f, ensure_ascii=False, indent=4)

# --- 初始化 ---
# 只有在第一次載入時讀取檔案
if 'gallery' not in st.session_state:
    st.session_state.gallery = load_data()

# --- 側邊欄：批次上傳 ---
with st.sidebar:
    st.header("📸 批次新增照片")
    uploaded_files = st.file_uploader("選擇照片...", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button(f"確認上傳 {len(uploaded_files)} 張"):
            for uploaded_file in uploaded_files:
                filename = uploaded_file.name
                # 自動抓取日期
                try:
                    date_str = filename[:8]
                    img_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                except ValueError:
                    img_date = datetime.date.today()
                
                new_photo = {
                    "image": Image.open(uploaded_file), # 注意：圖片本身在重整後仍會遺失(記憶體限制)
                    "name": filename,
                    "date": img_date,
                    "tags": []
                }
                st.session_state.gallery.append(new_photo)
            
            # 上傳完立刻存檔！
            save_data(st.session_state.gallery)
            st.success("上傳並存檔成功！")
            st.rerun()

# --- 提醒視窗 ---
st.warning("⚠️ 注意：此版本會將「照片資訊（日期、標籤）」永久存在 photo_db.json 檔案中。但因為圖片檔案較大，目前僅存在記憶體中，重新整理後圖片會顯示失效，但標籤資料還在。")

# --- 主畫面：篩選與瀏覽 ---
st.divider()
col1, col2 = st.columns(2)
with col1:
    filter_date = st.date_input("📅 篩選日期", value=None)
with col2:
    filter_tags = st.multiselect("🏷️ 篩選標籤", TAG_OPTIONS)

# 顯示邏輯
displayed_photos = []
for photo in st.session_state.gallery:
    date_match = (filter_date is None) or (photo['date'] == filter_date)
    tag_match = not filter_tags or all(tag in photo['tags'] for tag in filter_tags)
    
    if date_match and tag_match:
        displayed_photos.append(photo)

if displayed_photos:
    cols = st.columns(3)
    for idx, photo in enumerate(displayed_photos):
        with cols[idx % 3]:
            # 檢查圖片物件是否存在 (因為重整後圖片物件會消失)
            if 'image' in photo:
                st.image(photo['image'], use_container_width=True)
            else:
                st.info(f"🖼️ 圖片已過期: {photo['name']}")
            
            st.caption(f"📅 {photo['date']}")
            
            # 編輯標籤
            current_tags = st.multiselect(
                "編輯標籤", 
                options=TAG_OPTIONS, 
                default=photo['tags'],
                key=f"tags_{idx}"
            )
            
            # 如果標籤有變動，就存檔
            if current_tags != photo['tags']:
                photo['tags'] = current_tags
                save_data(st.session_state.gallery) # 變更後立刻存檔
                st.rerun()

            # 刪除功能
            if st.button("🗑️ 刪除", key=f"del_{idx}"):
                st.session_state.gallery.remove(photo)
                save_data(st.session_state.gallery) # 刪除後立刻存檔
                st.rerun()
            st.divider()
else:
    st.info("沒有符合條件的照片。")
