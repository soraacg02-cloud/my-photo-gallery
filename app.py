import streamlit as st
from PIL import Image
import datetime

# 設定網頁標題與佈局
st.set_page_config(page_title="我的隨身相簿", layout="wide")

st.title("📱 我的隨身相簿")

# --- 第一部分：初始化資料結構 ---
# 這是為了讓網頁在互動時不會「忘記」我們上傳的圖片
# 我們使用 st.session_state 來模擬一個暫時的資料庫
if 'gallery' not in st.session_state:
    st.session_state.gallery = []

# --- 第二部分：側邊欄 (上傳與控制) ---
with st.sidebar:
    st.header("📸 新增照片")
    uploaded_file = st.file_uploader("選擇一張照片...", type=['jpg', 'png', 'jpeg'])
    
    # 用戶輸入照片資訊
    img_date = st.date_input("拍攝日期", datetime.date.today())
    img_category = st.selectbox("選擇分類", ["生活", "工作", "旅遊", "美食", "其他"])
    
    if uploaded_file is not None:
        if st.button("確認上傳"):
            # 將圖片與資訊打包成一個字典 (Dictionary)
            photo_data = {
                "image": Image.open(uploaded_file),
                "name": uploaded_file.name,
                "date": img_date,
                "category": img_category
            }
            # 存入我們的暫存清單
            st.session_state.gallery.append(photo_data)
            st.success(f"已新增一張 [{img_category}] 照片！")

# --- 第三部分：篩選區域 ---
st.divider()
st.subheader("🔍 篩選與瀏覽")

# 獲取目前所有已有的分類
all_categories = ["全部"] + list(set([item['category'] for item in st.session_state.gallery]))
selected_filter = st.selectbox("依分類篩選", all_categories)

# --- 第四部分：邏輯與顯示 (手機介面風格) ---
# 根據使用者的選擇進行篩選
if selected_filter == "全部":
    filtered_photos = st.session_state.gallery
else:
    # 這裡使用了 Python 的列表推導式 (List Comprehension)
    filtered_photos = [p for p in st.session_state.gallery if p['category'] == selected_filter]

# 顯示照片 (使用多欄位佈局模擬相簿牆)
if filtered_photos:
    # 在手機上 st.columns 會自動堆疊，看起來就像手機 App 的介面
    cols = st.columns(3) 
    
    for idx, photo in enumerate(filtered_photos):
        # 讓照片依序放入 0, 1, 2 的欄位中
        with cols[idx % 3]:
            st.image(photo['image'], use_container_width=True)
            st.caption(f"📅 {photo['date']} | 🏷️ {photo['category']}")
            st.text(photo['name'])
else:
    st.info("目前沒有符合條件的照片，請從側邊欄上傳！")
