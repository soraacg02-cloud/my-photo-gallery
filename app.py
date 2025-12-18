import streamlit as st
from PIL import Image
import datetime

# 設定網頁標題與佈局
st.set_page_config(page_title="我的隨身相簿 Pro", layout="wide")
st.title("📱 我的隨身相簿 Pro")

# --- 初始化資料結構 ---
if 'gallery' not in st.session_state:
    st.session_state.gallery = []

# 定義我們新的分類標籤
TAG_OPTIONS = ["線搞", "上色", "單人", "雙人"]

# --- 側邊欄：批次上傳區 ---
with st.sidebar:
    st.header("📸 批次新增照片")
    # 1. 修改：accept_multiple_files=True 允許一次選多張
    uploaded_files = st.file_uploader("選擇照片 (可多選)...", 
                                      type=['jpg', 'png', 'jpeg'], 
                                      accept_multiple_files=True)
    
    # 這裡只做一個簡單的上傳按鈕，按下後才開始處理檔案
    if uploaded_files:
        if st.button(f"確認上傳 {len(uploaded_files)} 張照片"):
            for uploaded_file in uploaded_files:
                # 2. 邏輯：自動讀取檔名日期 (檔名格式預設為: 20251011.jpg)
                filename = uploaded_file.name
                try:
                    # 抓取檔名前 8 碼，並嘗試轉換成日期格式
                    date_str = filename[:8] 
                    img_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                except ValueError:
                    # 如果檔名不符合格式，預設為今天
                    img_date = datetime.date.today()
                
                # 建立新照片資料
                new_photo = {
                    "image": Image.open(uploaded_file),
                    "name": filename,
                    "date": img_date,
                    "tags": [] # 3. 修改：現在這是一個列表，可以放多個標籤
                }
                st.session_state.gallery.append(new_photo)
            
            st.success(f"成功上傳 {len(uploaded_files)} 張照片！")
            st.rerun() # 重新整理頁面以顯示新照片

# --- 主畫面：篩選與瀏覽 ---
st.divider()

# 建立兩欄的篩選器
col1, col2 = st.columns(2)
with col1:
    # 4. 篩選功能：日期篩選
    filter_date = st.date_input("📅 篩選日期 (選填)", value=None)
with col2:
    # 4. 篩選功能：標籤篩選
    filter_tags = st.multiselect("🏷️ 篩選標籤", TAG_OPTIONS)

# --- 顯示與編輯區域 ---
# 根據條件過濾照片
displayed_photos = []
for photo in st.session_state.gallery:
    # 日期檢查：如果使用者沒選日期，或是日期相符
    date_match = (filter_date is None) or (photo['date'] == filter_date)
    # 標籤檢查：如果使用者沒選標籤，或是照片包含了使用者選的所有標籤
    # (這裡邏輯是：選了"單人"和"上色"，必須這張照片同時有這兩個標籤才顯示)
    tag_match = not filter_tags or all(tag in photo['tags'] for tag in filter_tags)
    
    if date_match and tag_match:
        displayed_photos.append(photo)

# 顯示照片網格
if displayed_photos:
    cols = st.columns(3) # 手機版面風格
    for idx, photo in enumerate(displayed_photos):
        with cols[idx % 3]:
            # 顯示圖片
            st.image(photo['image'], use_container_width=True)
            
            # 顯示檔名與日期
            st.caption(f"📄 {photo['name']} | 📅 {photo['date']}")
            
            # 3. 編輯功能：直接在這裡編輯標籤 (Multiselect)
            # key 是必要的，讓 Streamlit 知道這是哪張照片的選單
            current_tags = st.multiselect(
                "編輯標籤", 
                options=TAG_OPTIONS, 
                default=photo['tags'],
                key=f"tags_{photo['name']}_{idx}"
            )
            # 當使用者改變選項時，即時更新資料
            photo['tags'] = current_tags

            # 4. 刪除功能
            if st.button("🗑️ 刪除", key=f"del_{photo['name']}_{idx}"):
                st.session_state.gallery.remove(photo)
                st.rerun() # 刪除後立刻刷新頁面
            
            st.divider() # 分隔線
else:
    st.info("沒有符合條件的照片。")
