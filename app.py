import streamlit as st
from PIL import Image
import datetime
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# 設定頁面
st.set_page_config(page_title="雲端相簿 Pro (Google Drive版)", layout="wide")
st.title("☁️ 雲端相簿 Pro (Google Drive 連動)")

# --- Google Drive 連線設定 ---
# 這是 Drive API 權限範圍
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = st.secrets["gdrive_folder_id"]
DB_FILENAME = "photo_db.json"

@st.cache_resource
def get_drive_service():
    """連線到 Google Drive"""
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_file_id_by_name(service, filename):
    """查詢檔案是否存在於指定資料夾，回傳 ID"""
    query = f"name = '{filename}' and '{FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

def download_db(service):
    """從 Drive 下載資料庫 JSON"""
    file_id = get_file_id_by_name(service, DB_FILENAME)
    if file_id:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return json.load(fh)
    return [] # 如果沒檔案，回傳空清單

def upload_db(service, data):
    """將資料庫 JSON 上傳回 Drive (覆蓋)"""
    # 將 list 轉為 json 字串
    json_str = json.dumps(data, ensure_ascii=False, indent=4)
    fh = io.BytesIO(json_str.encode('utf-8'))
    
    file_id = get_file_id_by_name(service, DB_FILENAME)
    media = MediaIoBaseUpload(fh, mimetype='application/json')
    
    if file_id:
        # 更新現有檔案
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        # 建立新檔案
        file_metadata = {'name': DB_FILENAME, 'parents': [FOLDER_ID]}
        service.files().create(body=file_metadata, media_body=media).execute()

def upload_image_to_drive(service, file_obj, filename):
    """上傳圖片到 Drive"""
    media = MediaIoBaseUpload(file_obj, mimetype=file_obj.type)
    file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- 應用程式邏輯 ---

# 1. 取得連線
try:
    drive_service = get_drive_service()
    # 2. 讀取資料庫 (只在第一次加載或強制重整時)
    if 'gallery' not in st.session_state:
        with st.spinner('正在從 Google Drive 下載資料庫...'):
            raw_data = download_db(drive_service)
            # 轉換日期格式
            for item in raw_data:
                item['date'] = datetime.datetime.strptime(item['date_str'], "%Y-%m-%d").date()
            st.session_state.gallery = raw_data
except Exception as e:
    st.error(f"連線失敗，請檢查 Secrets 設定: {e}")
    st.stop()

TAG_OPTIONS = ["線搞", "上色", "單人", "雙人"]

# --- 側邊欄 ---
with st.sidebar:
    st.header("📸 上傳至 Google Drive")
    uploaded_files = st.file_uploader("選擇照片...", type=['jpg', 'png'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳"):
        progress_bar = st.progress(0)
        for i, uploaded_file in enumerate(uploaded_files):
            # 處理日期
            fname = uploaded_file.name
            try:
                date_str = fname[:8]
                img_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
            except:
                img_date = datetime.date.today()
            
            # 上傳圖片實體
            img_id = upload_image_to_drive(drive_service, uploaded_file, fname)
            
            # 更新資料庫紀錄 (只存 ID 和 資訊，不存圖片本體)
            new_record = {
                "id": img_id, # Drive 檔案 ID
                "name": fname,
                "date": img_date,
                "tags": [],
                "date_str": img_date.strftime("%Y-%m-%d") # 方便存檔
            }
            st.session_state.gallery.append(new_record)
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        # 全部上傳完後，同步更新 DB 檔案
        save_list = []
        for item in st.session_state.gallery:
            # 準備要存檔的純文字資料
            save_list.append({
                "id": item['id'],
                "name": item['name'],
                "date_str": item['date'].strftime("%Y-%m-%d"),
                "tags": item['tags']
            })
        upload_db(drive_service, save_list)
        
        st.success("上傳完成！圖片已安全存入 Google Drive。")
        st.rerun()

# --- 主畫面：瀏覽 ---
# (為了效能，這裡我們只顯示資訊，圖片需要額外邏輯讀取，我們先做簡易版)
st.divider()
st.subheader("📂 雲端檔案列表")

# 篩選器
col1, col2 = st.columns(2)
with col1:
    filter_date = st.date_input("📅 篩選日期", value=None)
with col2:
    filter_tags = st.multiselect("🏷️ 篩選標籤", TAG_OPTIONS)

# 顯示
for idx, photo in enumerate(st.session_state.gallery):
    date_match = (filter_date is None) or (photo['date'] == filter_date)
    tag_match = not filter_tags or all(tag in photo['tags'] for tag in filter_tags)
    
    if date_match and tag_match:
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.info(f"🖼️ ID: {photo['id']}") 
                # 進階：這裡如果要顯示圖片，需要呼叫 API 下載，會比較慢
                # st.image(...) 
            with c2:
                st.markdown(f"**{photo['name']}**")
                st.caption(f"📅 {photo['date']}")
                
                # 編輯標籤
                current_tags = st.multiselect("標籤", TAG_OPTIONS, default=photo['tags'], key=f"t_{photo['id']}")
                if current_tags != photo['tags']:
                    photo['tags'] = current_tags
                    # 這裡偷懶：每改一個就存檔一次會比較慢，實際應用可以用「儲存按鈕」一次存
                    # 為了教學方便，我們省略即時存檔，請使用者按「儲存變更」
                    
                if st.button("🗑️ 刪除索引", key=f"d_{photo['id']}"):
                    st.session_state.gallery.remove(photo)
                    st.rerun()

if st.button("💾 儲存所有變更 (標籤/刪除)"):
    # 轉換資料格式以存檔
    save_list = [{
        "id": p['id'],
        "name": p['name'],
        "date_str": p['date'].strftime("%Y-%m-%d"),
        "tags": p['tags']
    } for p in st.session_state.gallery]
    
    upload_db(drive_service, save_list)
    st.success("資料庫已更新！")
