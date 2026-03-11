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
from PIL import Image

# 設定網頁標題
st.set_page_config(page_title="雲端圖庫 Ultimate", layout="wide")
st.title("☁️ 雲端圖庫 (分類統計升級版)")

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

def format_file_size(size_in_bytes):
    if not size_in_bytes: return "未知"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f} GB"

def compress_image(image_file):
    try:
        img = Image.open(image_file)
        try:
            from PIL import ExifTags
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation': break
            exif = img._getexif()
            if exif is not None:
                orientation = exif.get(orientation)
                if orientation == 3: img = img.rotate(180, expand=True)
                elif orientation == 6: img = img.rotate(270, expand=True)
                elif orientation == 8: img = img.rotate(90, expand=True)
        except: pass

        max_width = 1920
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            
        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=80, optimize=True)
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
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
                if 'size' not in item: item['size'] = 0
            return data
        else: return []
    except: return []

def save_db(data):
    save_list = []
    for item in data:
        save_list.append({
            "public_id": item['public_id'], "url": item['url'], "name": item['name'],
            "date_str": item['date'].strftime("%Y-%m-%d"), "tags": item['tags'],
            "album": item.get('album', '未分類'),
            "size": item.get('size', 0)
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

@st.dialog("📸 照片詳情", width="large")
def show_large_image(photo):
    st.image(photo['url'], use_container_width=True)
    st.divider()
    
    st.markdown(f"**檔名**: {photo['name']}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"📅 **日期**: {photo['date']}")
        st.write(f"📂 **相簿**: {photo['album']}")
    with c2:
        file_size_str = format_file_size(photo.get('size', 0))
        st.write(f"📏 **大小**: {file_size_str}")
        
    with c3:
        if photo['tags']: st.write(f"🏷️ **標籤**: {', '.join(photo['tags'])}")
        else: st.write("🏷️ **標籤**: (無)")
        
    st.download_button(label="⬇️ 下載圖檔", data=requests.get(photo['url']).content, file_name=photo['name'], mime="image/jpeg", use_container_width=True)

# --- 4. 應用程式主邏輯 ---
if 'gallery' not in st.session_state:
    with st.spinner('載入資料庫...'):
        st.session_state.gallery = load_db()

existing_albums = sorted(list(set([item['album'] for item in st.session_state.gallery])))
if "未分類" not in existing_albums: existing_albums.append("未分類")

existing_tags = sorted(list(set([tag for item in st.session_state.gallery for tag in item['tags']])))

# [修改處] 這裡新增了「無償」與「非無償」
DEFAULT_TAGS = ["彩色", "線稿", "單人", "雙人", "無償", "非無償"]
ALL_TAG_OPTIONS = sorted(list(set(DEFAULT_TAGS + existing_tags)))

# === 側邊欄 ===
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
            status_text = st.empty()
            
            for i, f in enumerate(uploaded_files):
                status_text.text(f"處理中 {i+1}/{len(uploaded_files)}：{f.name} (壓縮中...)")
                try:
                    compressed_file = compress_image(f)
                    file_size_bytes = compressed_file.getbuffer().nbytes
                    res = cloudinary.uploader.upload(compressed_file)
                    
                    try: d = datetime.datetime.strptime(f.name[:8], "%Y%m%d").date()
                    except: d = datetime.date.today()
                    
                    st.session_state.gallery.append({
                        "public_id": res['public_id'], "url": res['secure_url'], 
                        "name": f.name, "date": d, "tags": [], "album": current_album,
                        "size": file_size_bytes 
                    })
                except Exception as e:
                    st.error(f"❌ {f.name} 上傳失敗: {e}")
                
                progress.progress((i+1)/len(uploaded_files))
            
            status_text.text("儲存資料庫...")
            save_db(st.session_state.gallery)
            st.success("完成！")
            time.sleep(1)
            st.rerun()

# === 頁面分流 ===

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
            show_untagged = st.checkbox("只看未分類", help("只顯示無標籤圖片"))

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
                
                tags_str = f"🏷️ {','.join(photo['tags'])}" if photo['tags'] else "❌ 未分類"
                size_str = format_file_size(photo.get('size', 0))
                st.caption(f"{tags_str} | 📏 {size_str}")
                
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
    # -----------------------------------------------------------
    #  [統計頁面] 新增相簿切換功能
    # -----------------------------------------------------------
    st.header("📊 數據統計中心")
    st.write("查看不同相簿或整體的創作產量")

    if not st.session_state.gallery:
        st.info("無資料，請先上傳照片！")
    else:
        # [核心新增] 提供使用者選擇想統計的相簿
        stat_album = st.selectbox("📂 選擇要統計的相簿", ["全部"] + existing_albums)
        
        # 根據選擇過濾出要計算的圖片 (Data Filtering)
        if stat_album == "全部":
            stat_photos = st.session_state.gallery
        else:
            stat_photos = [p for p in st.session_state.gallery if p['album'] == stat_album]

        if not stat_photos:
            st.warning(f"相簿 '{stat_album}' 裡面目前沒有照片喔！")
        else:
            # 1. 顯示 KPI 指標 (現在是根據過濾後的 stat_photos 來算)
            total_photos = len(stat_photos)
            untagged_count = len([p for p in stat_photos if not p['tags']])
            total_size_bytes = sum([p.get('size', 0) for p in stat_photos])
            
            m1, m2, m3 = st.columns(3)
            m1.metric("📸 照片數", total_photos)
            m2.metric("❌ 未分類", untagged_count, delta_color="inverse")
            m3.metric("💾 空間使用", format_file_size(total_size_bytes))
            
            st.divider()
            
            # 2. 製作樞紐分析表 (Pivot Table)
            raw_data = []
            for p in stat_photos: # 這裡改用 stat_photos
                raw_data.append({
                    "Year": p['date'].year,
                    "Month": p['date'].month
                })
                
            if raw_data:
                df = pd.DataFrame(raw_data)
                
                # 計算交叉頻率 (Row=Month, Col=Year)
                pivot_df = pd.crosstab(df['Month'], df['Year'])
                
                # 確保 1~12 月都有顯示
                all_months = list(range(1, 13))
                pivot_df = pivot_df.reindex(all_months, fill_value=0)
                
                # 加入「總計」列
                pivot_df.loc['總計'] = pivot_df.sum()
                pivot_df.index.name = "月份"
                
                st.subheader(f"🗓️ 年度月別統計表 ({stat_album})")
                st.dataframe(pivot_df, use_container_width=True)
                
                st.subheader(f"📈 年度產量比較 ({stat_album})")
                chart_data = pivot_df.drop('總計')
                st.bar_chart(chart_data)
