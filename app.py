import streamlit as st
import datetime
import json
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO
import time
import pandas as pd # 我們需要 pandas 來做漂亮的統計表

# 設定網頁標題
st.set_page_config(page_title="雲端圖庫 Ultimate", layout="wide")
st.title("☁️ 雲端圖庫 (插畫管理版)")

# --- 1. Cloudinary 連線設定 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )

DB_FILENAME = "photo_db_v2.json"

# --- 2. CSS 強力修正 (手機網格) ---
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
    # [新增] 頁面切換開關
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

# === 頁面邏輯分流 ===

if page_mode == "📸 相簿瀏覽":
    # ---------------------------------------------------------
    #  原本的相簿瀏覽頁面 (Gallery View)
    # ---------------------------------------------------------
    st.subheader("🔍 瀏覽設定")

    # 第一排：相簿 + 標籤 + [新增] 未分類開關
    f_c1, f_c2 = st.columns([1, 2])
    with f_c1:
        filter_album = st.selectbox("📂 相簿", ["全部"] + existing_albums)
    
    with f_c2:
        # [新增] 使用 columns 讓標籤篩選和 "只看未分類" 並排
        tag_col1, tag_col2 = st.columns([3, 1])
        with tag_col1:
            filter_tags = st.multiselect("🏷️ 標籤篩選", existing_tags, disabled=False)
        with tag_col2:
            st.write("") # 排版用，往下推一點
            st.write("") 
            # [新增功能 2] 只顯示未分類
            show_untagged = st.checkbox("只看未分類", help("勾選後，將只顯示沒有任何標籤的圖片"))

    # 第二排：排序 + 年份 + 月份
    f_c3, f_c4, f_c5 = st.columns([2, 1, 1]) 
    with f_c3:
        sort_option = st.selectbox("🔃 排序方式", 
            ["日期 (新→舊)", "日期 (舊→新)", "檔名 (A→Z)", "檔名 (Z→A)", "標籤 (A→Z)"], index=0)
    with f_c4:
        all_years = sorted(list(set([p['date'].year for p in st.session_state.gallery])), reverse=True)
        filter_year = st.selectbox("📅 年份", ["全部"] + all_years)
    with f_c5:
        all_months = list(range(1, 13))
        filter_month = st.selectbox("🌙 月份", ["全部"] + all_months)

    # 執行篩選
    filtered_photos = []
    for p in st.session_state.gallery:
        match_album = (filter_album == "全部") or (p['album'] == filter_album)
        match_year = (filter_year == "全部") or (p['date'].year == filter_year)
        match_month = (filter_month == "全部") or (p['date'].month == filter_month)
        
        # [修改邏輯] 標籤篩選邏輯
        if show_untagged:
            # 如果勾選了"只看未分類"，那麼這張照片必須沒有任何標籤 (tags 是空的)
            match_tags = (len(p['tags']) == 0)
        else:
            # 否則執行原本的篩選邏輯
            match_tags = True
            if filter_tags:
                match_tags = all(tag in p['tags'] for tag in filter_tags)
        
        if match_album and match_year and match_month and match_tags:
            filtered_photos.append(p)

    # 執行排序
    if sort_option == "日期 (舊→新)": filtered_photos.sort(key=lambda x: x['date']) 
    elif sort_option == "日期 (新→舊)": filtered_photos.sort(key=lambda x: x['date'], reverse=True)
    elif sort_option == "檔名 (A→Z)": filtered_photos.sort(key=lambda x: x['name'])
    elif sort_option == "檔名 (Z→A)": filtered_photos.sort(key=lambda x: x['name'], reverse=True)
    elif sort_option == "標籤 (A→Z)": filtered_photos.sort(key=lambda x: x['tags'][0] if x['tags'] else "zzzz")

    # 統計顯示
    st.divider()
    if filtered_photos:
        st.markdown(f"### 📸 共找到 :red[{len(filtered_photos)}] 張照片")
    else:
        st.warning("⚠️ 共找到 0 張照片。")

    # 2. 檢視與操作列
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

    # 3. 照片展示區
    selected_photos = [] 
    if filtered_photos:
        cols = st.columns(num_columns)
        for idx, photo in enumerate(filtered_photos):
            with cols[idx % num_columns]:
                st.image(photo['url'], use_container_width=True)
                key = f"sel_{photo['public_id']}"
                if key not in st.session_state: st.session_state[key] = False
                is_selected = st.checkbox(f"{photo['name']}", key=key)
                if photo['tags']: st.caption(f"🏷️ {','.join(photo['tags'])}")
                else: st.caption("❌ 未分類") # 提示未分類
                if num_columns == 1: st.text(f"相簿: {photo['album']} | 日期: {photo['date']}")
                st.write("") 
                if is_selected: selected_photos.append(photo)

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
    # ---------------------------------------------------------
    #  [新增功能 1] 數據統計頁面 (Statistics View)
    # ---------------------------------------------------------
    st.header("📊 數據統計中心")
    st.write("查看您每個月的創作產量統計")
    
    if not st.session_state.gallery:
        st.info("目前還沒有照片，請先上傳！")
    else:
        # 1. 準備數據
        # 我們要把資料整理成: [{'Year': 2023, 'Month': 5, 'Count': 10}, ...] 的格式
        stats_data = {} # 用字典先計數 {(2023, 5): 10, ...}
        
        for p in st.session_state.gallery:
            y = p['date'].year
            m = p['date'].month
            key = (y, m)
            if key in stats_data:
                stats_data[key] += 1
            else:
                stats_data[key] = 1
        
        # 轉成 DataFrame 表格
        df_list = []
        for (year, month), count in stats_data.items():
            df_list.append({
                "年份": year,
                "月份": month,
                "數量 (張)": count,
                "年月標籤": f"{year}-{month:02d}" # 用來畫圖的 X 軸
            })
            
        df = pd.DataFrame(df_list)
        
        # 排序：先按年，再按月
        df = df.sort_values(by=["年份", "月份"], ascending=False)
        
        # 2. 顯示總量指標 (Metrics)
        total_photos = len(st.session_state.gallery)
        untagged_count = len([p for p in st.session_state.gallery if not p['tags']])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("📸 總照片數", total_photos)
        m2.metric("❌ 未分類照片", untagged_count, delta_color="inverse")
        m3.metric("📅 統計月份數", len(df))
        
        st.divider()

        # 3. 顯示圖表 (Bar Chart)
        st.subheader("📈 每月上傳趨勢")
        # 為了畫圖漂亮，我們把 '年月標籤' 當索引
        chart_data = df.set_index("年月標籤")[["數量 (張)"]]
        st.bar_chart(chart_data, color="#ff4b4b")
        
        # 4. 顯示詳細表格
        st.subheader("📋 詳細數據表")
        # 隱藏索引列，只顯示數據
        st.dataframe(
            df[["年份", "月份", "數量 (張)"]], 
            use_container_width=True,
            hide_index=True
        )
