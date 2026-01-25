import streamlit as st
import datetime
import json
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO
import time
import pandas as pd
from PIL import Image # [新增] 引入圖片處理套件

# 設定網頁標題
st.set_page_config(page_title="雲端圖庫 Ultimate", layout="wide")
st.title("☁️ 雲端圖庫 (自動壓縮優化版)")

# --- 1. Cloudinary 連線設定 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

DB_FILENAME = "photo_db_v2.json"

# --- 2. CSS 強力修正 ---
def inject_custom_css():
    st.markdown("""
    <style>
    span[data-baseweb="tag"] { background-color: #ff4b4b !important; }
    @media (max-width: 640px) {
        [data-testid="column"] { width: 50% !important; flex: 1 1 50% !important; min-width: 50% !important; }
        [data-testid="column"] img { max-width: 100% !important; height: auto !important; }
        .stButton button { width: 100%; padding: 0.25rem 0.5rem; }
    }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- 3. 核心功能函數 ---

# [新增功能] 圖片自動壓縮大師
def compress_image(image_file):
    """
    接收一個圖片檔案，進行 resize 和壓縮，
    回傳一個縮小後的 BytesIO 物件。
    """
    try:
        # 1. 打開圖片
        img = Image.open(image_file)
        
        # 2. 處理因手機拍攝方向(EXIF)導致的旋轉問題
        try:
            from PIL import ExifTags, ImageOps
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = img._getexif()
            if exif is not None:
                orientation = exif.get(orientation)
                if orientation == 3: img = img.rotate(180, expand=True)
                elif orientation == 6: img = img.rotate(270, expand=True)
                elif orientation == 8: img = img.rotate(90, expand=True)
        except:
            pass # 如果沒有 EXIF 資訊就不處理

        # 3. 調整尺寸 (如果寬度超過 1920，就等比例縮小)
        max_width = 1920
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # 4. 轉換格式 (統一轉為 RGB 模式，避免 PNG 透明度在轉 JPEG 時變黑)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 5. 壓縮存入記憶體
        output_buffer = BytesIO()
        # quality=80 是平衡畫質與檔案大小的最佳甜蜜點
        img.save(output_buffer, format="JPEG", quality=80, optimize=True)
        output_buffer.seek(0) # 指針歸零，準備讓上傳程式讀取
        
        return output_buffer
    except Exception as e:
        # 如果壓縮失敗，就回傳原始檔案，並印出錯誤
        print(f"壓縮失敗: {e}")
        image_file.seek(0)
        return image_file

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

def clear_all_selections():
    for key in st.session_state.keys():
        if key.startswith("sel_"):
            st.session_state[key] = False

# 原生穩定版大圖
@st.dialog("📸 照片詳情", width="large")
def show_large_image(photo):
    st.image(photo['url'], use_container_width=True)
    st.divider()
    st.markdown(f"**檔名**: {photo['name']}")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"📅 **日期**: {photo['date']}")
        st.write(f"📂 **相簿**: {photo['album']}")
    with c2:
        if photo['tags']: st.write(f"🏷️ **標籤**: {', '.join(photo['tags'])}")
        else: st.write("🏷️ **標籤**: (無)")
    st.download_button(label="⬇️ 下載原始圖檔", data=requests.get(photo['url']).content, file_name=photo['name'], mime="image/jpeg", use_container_width=True)


# --- 4. 應用程式主邏輯 ---
if 'gallery' not in st.session_state:
    with st.spinner('載入資料庫...'):
        st.session_state.gallery = load_db()

# 資料整理
existing_albums = sorted(list(set([item['album'] for item in st.session_state.gallery])))
if "未分類" not in existing_albums: existing_albums.append("未分類")

existing_tags = sorted(list(set([tag for item in st.session_state.gallery for tag in item['tags']])))
DEFAULT_TAGS = ["彩色", "線稿", "單人", "雙人"]
ALL_TAG_OPTIONS = sorted(list(set(DEFAULT_TAGS + existing_tags)))

# === 側邊欄：功能選單與上傳 ===
with st.sidebar:
    st.header("功能選單")
    page_mode = st.radio("前往頁面", ["📸 相簿瀏覽", "📊 數據統計"])
    st.divider()
    st.header("📂 上傳作品")
    
    album_mode = st.radio("模式", ["選擇現有相簿", "建立新相簿"])
    if album_mode == "建立新相簿":
        current_album = st.text_input("輸入新相簿名稱")
    else:
        current_album = st.selectbox("選擇上傳相簿", existing_albums)

    uploaded_files = st.file_uploader("選擇圖片 (可多選)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files and st.button("確認上傳", type="primary"):
        if not current_album: st.error("請輸入相簿名稱")
        else:
            progress = st.progress(0)
            status_text = st.empty() # 顯示目前處理進度
            
            for i, f in enumerate(uploaded_files):
                status_text.text(f"正在處理第 {i+1}/{len(uploaded_files)} 張：{f.name} (壓縮中...)")
                
                try:
                    # [核心修改] 上傳前先進行壓縮
                    compressed_file = compress_image(f)
                    
                    # 上傳到 Cloudinary
                    res = cloudinary.uploader.upload(compressed_file)
                    
                    try: d = datetime.datetime.strptime(f.name[:8], "%Y%m%d").date()
                    except: d = datetime.date.today()
                    
                    st.session_state.gallery.append({
                        "public_id": res['public_id'], "url": res['secure_url'], 
                        "name": f.name, "date": d, "tags": [], "album": current_album
                    })
                except Exception as e:
                    # [修正] 顯示明確的錯誤訊息，而不是 pass 過去
                    st.error(f"❌ 照片 {f.name} 上傳失敗。原因：{e}")
                
                progress.progress((i+1)/len(uploaded_files))
            
            status_text.text("儲存資料庫中...")
            save_db(st.session_state.gallery)
            st.success("完成！")
            time.sleep(1)
            st.rerun()

# === 頁面邏輯分流 ===

if page_mode == "📸 相簿瀏覽":
    st.subheader("🔍 瀏覽設定")
    f_c1, f_c2 = st.columns([1, 2])
    with f_c1: filter_album = st.selectbox("📂 相簿", ["全部"] + existing_albums)
    with f_c2:
        tag_col1, tag_col2 = st.columns([3, 1])
        with tag_col1: filter_tags = st.multiselect("🏷️ 標籤篩選", existing_tags)
        with tag_col2:
            st.write("") 
            st.write("") 
            show_untagged = st.checkbox("只看未分類", help("勾選後，將只顯示沒有任何標籤的圖片"))

    f_c3, f_c4, f_c5 = st.columns([2, 1, 1]) 
    with f_c3: sort_option = st.selectbox("🔃 排序方式", ["日期 (新→舊)", "日期 (舊→新)", "檔名 (A→Z)", "檔名 (Z→A)", "標籤 (A→Z)"], index=0)
    with f_c4:
        all_years = sorted(list(set([p['date'].year for p in st.session_state.gallery])), reverse=True)
        filter_year = st.selectbox("📅 年份", ["全部"] + all_years)
    with f_c5:
        all_months = list(range(1, 13))
        filter_month = st.selectbox("🌙 月份", ["全部"] + all_months)

    filtered_photos = []
    for p in st.session_state.gallery:
        match_album = (filter_album == "全部") or (p['album'] == filter_album)
        match_year = (filter_year == "全部") or (p['date'].year == filter_year)
        match_month = (filter_month == "全部") or (p['date'].month == filter_month)
        
        if show_untagged: match_tags = (len(p['tags']) == 0)
        else:
            match_tags = True
            if filter_tags: match_tags = all(tag in p['tags'] for tag in filter_tags)
        
        if match_album and match_year and match_month and match_tags: filtered_photos.append(p)

    if sort_option == "日期 (舊→新)": filtered_photos.sort(key=lambda x: x['date']) 
    elif sort_option == "日期 (新→舊)": filtered_photos.sort(key=lambda x: x['date'], reverse=True)
    elif sort_option == "檔名 (A→Z)": filtered_photos.sort(key=lambda x: x['name'])
    elif sort_option == "檔名 (Z→A)": filtered_photos.sort(key=lambda x: x['name'], reverse=True)
    elif sort_option == "標籤 (A→Z)": filtered_photos.sort(key=lambda x: x['tags'][0] if x['tags'] else "zzzz")

    st.divider()
    if filtered_photos: st.markdown(f"### 📸 共找到 :red[{len(filtered_photos)}] 張照片")
    else: st.warning("⚠️ 共找到 0 張照片。")

    ctrl_c1, ctrl_c2 = st.columns([1, 1])
    with ctrl_c1:
        view_mode = st.radio("👀 模式", ["網格", "大圖"], horizontal=True, label_visibility="collapsed")
        num_columns = 3 if view_mode == "網格" else 1

    with ctrl_c2:
        sel_c1, sel_c2 = st.columns(2)
        if sel_c1.button("✅ 全選本頁"):
            for p in filtered_photos: st.session_state[f"sel_{p['public_id']}"] = True
            st.rerun()
        if sel_c2.button("❎ 取消全選"):
            for p in filtered_photos: st.session_state[f"sel_{p['public_id']}"] = False
            st.rerun()

    selected_photos = [] 
    if filtered_photos:
        cols = st.columns(num_columns)
        for idx, photo in enumerate(filtered_photos):
            with cols[idx % num_columns]:
                st.image(photo['url'], use_container_width=True)
                btn_col, check_col = st.columns([1, 4]) 
                with btn_col:
                    if st.button("🔍", key=f"zoom_{photo['public_id']}", help="查看大圖"): show_large_image(photo)
                with check_col:
                    key = f"sel_{photo['public_id']}"
                    if key not in st.session_state: st.session_state[key] = False
                    is_selected = st.checkbox(f"{photo['name']}", key=key)
                if photo['tags']: st.caption(f"🏷️ {','.join(photo['tags'])}")
                else: st.caption("❌ 未分類") 
                if num_columns == 1: st.text(f"相簿: {photo['album']} | 日期: {photo['date']}")
                st.write("") 
                if is_selected: selected_photos.append(photo)

    if selected_photos:
        st.markdown("---")
        st.info(f"⚡ 已選取 {len(selected_photos)} 張照片")
        act_c1, act_c2 = st.columns(2)
        with act_c1:
            new_tags = st.multiselect("批次設定標籤", ALL_TAG_OPTIONS)
            if st.button("更新標籤"):
                for p in selected_photos:
                    for origin in st.session_state.gallery:
                        if origin['public_id'] == p['public_id']: origin['tags'] = new_tags
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
        st.write("") 
        st.button("❎ 取消所有選取 (離開編輯模式)", use_container_width=True, on_click=clear_all_selections) 

else:
    st.header("📊 數據統計中心")
    st.write("查看您每個月的創作產量統計")
    if not st.session_state.gallery: st.info("目前還沒有照片，請先上傳！")
    else:
        stats_data = {} 
        for p in st.session_state.gallery:
            y = p['date'].year
            m = p['date'].month
            key = (y, m)
            if key in stats_data: stats_data[key] += 1
            else: stats_data[key] = 1
        df_list = []
        for (year, month), count in stats_data.items():
            df_list.append({"年份": year, "月份": month, "數量 (張)": count, "年月標籤": f"{year}-{month:02d}"})
        df = pd.DataFrame(df_list)
        df = df.sort_values(by=["年份", "月份"], ascending=False)
        total_photos = len(st.session_state.gallery)
        untagged_count = len([p for p in st.session_state.gallery if not p['tags']])
        m1, m2, m3 = st.columns(3)
        m1.metric("📸 總照片數", total_photos)
        m2.metric("❌ 未分類照片", untagged_count, delta_color="inverse")
        m3.metric("📅 統計月份數", len(df))
        st.divider()
        st.subheader("📈 每月上傳趨勢")
        chart_data = df.set_index("年月標籤")[["數量 (張)"]]
        st.bar_chart(chart_data, color="#ff4b4b")
        st.subheader("📋 詳細數據表")
        st.dataframe(df[["年份", "月份", "數量 (張)"]], use_container_width=True, hide_index=True)
