import datetime
from io import BytesIO
import json
import time
import urllib.parse
import cloudinary
import cloudinary.api
import cloudinary.uploader
import pandas as pd
from PIL import ExifTags, Image
import requests
import streamlit as st
import streamlit.components.v1 as components

# --- 網頁配置 ---
st.set_page_config(page_title="雲端圖庫 Ultimate", layout="wide", page_icon="🖼️")

# --- 1. Cloudinary 連線設定 ---
if "cloudinary" in st.secrets:
    cloudinary.config(
        cloud_name=st.secrets["cloudinary"]["cloud_name"],
        api_key=st.secrets["cloudinary"]["api_key"],
        api_secret=st.secrets["cloudinary"]["api_secret"],
        secure=True,
    )

DB_FILENAME = "photo_db_v2.json"


# --- 2. 專屬 CSS 魔法 (優化版：寬鬆輕盈的滿版菱形防護網) ---
def inject_custom_css():
    st.markdown(
        """
    <style>
    /* 標籤美化 */
    span[data-baseweb="tag"] { background-color: #ff4b4b !important; border-radius: 15px !important; padding: 2px 10px !important;}
    
    /* 懸浮按鈕基礎樣式 (向上 / 向下) */
    .float-btn {
        position: fixed;
        right: 25px;
        z-index: 999999;
        background-color: #ff4b4b;
        color: white !important;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        text-align: center;
        line-height: 50px;
        font-size: 22px;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.35);
        cursor: pointer;
        text-decoration: none !important;
        transition: all 0.3s ease;
    }
    .back-to-top { top: 100px; }
    .go-to-bottom { top: 160px; }
    
    .float-btn:hover {
        background-color: #e03e3e;
        transform: scale(1.1);
    }

    /* 菱形格紋浮水印圖層 (輕量透氣防護網) */
    .watermark-container {
        position: relative;
        width: 100%;
        display: inline-block;
        overflow: hidden;
        border-radius: 8px;
    }
    .watermark-container img {
        width: 100%;
        height: auto;
        display: block;
    }
    .watermark-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: all; /* 攔截滑鼠右鍵點擊照片 */
        background-color: transparent;
        /* 拉大網格間距 (140px)，縮小點點 (2px) 並調薄透明度 (0.15) */
        background-image: 
            repeating-linear-gradient(45deg, rgba(0,0,0,0.15) 0, rgba(0,0,0,0.15) 1px, transparent 0, transparent 100px),
            repeating-linear-gradient(-45deg, rgba(0,0,0,0.15) 0, rgba(0,0,0,0.15) 1px, transparent 0, transparent 100px),
            radial-gradient(circle at 50% 50%, rgba(0, 0, 0, 0.25) 2px, transparent 3px);
        background-size: 140px 140px, 140px 140px, 70px 70px;
        background-position: 0 0, 0 0, 0 0;
    }

    /* 手機版專屬排版 (小於 640px) */
    @media (max-width: 640px) {
        ::-webkit-scrollbar { width: 10px !important; height: 10px !important; }
        ::-webkit-scrollbar-track { background: #f1f1f1 !important; }
        ::-webkit-scrollbar-thumb { background: #ff4b4b !important; border-radius: 5px !important; }

        div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .gallery-marker) {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 0.5rem !important;
        }
        
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .gallery-marker) > div[data-testid="stHorizontalBlock"] {
            display: contents !important;
        }
        
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .gallery-marker) div[data-testid="column"] {
            width: 100% !important;
            min-width: 0 !important;
            flex: none !important;
        }
        
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .gallery-marker) .stButton button {
            padding: 0.2rem !important;
            font-size: 14px !important;
        }

        .float-btn { width: 42px; height: 42px; line-height: 42px; font-size: 16px; right: 12px; }
        .back-to-top { top: 75px; }
        .go-to-bottom { top: 125px; }
    }
    </style>

    <!-- 頂部與底部錨點 -->
    <div id="top-anchor"></div>
    <a href="#top-anchor" class="float-btn back-to-top" title="回到頂部">⬆️</a>
    <a href="#bottom-anchor" class="float-btn go-to-bottom" title="移至底部">⬇️</a>
    """,
        unsafe_allow_html=True,
    )


inject_custom_css()


# --- 3. 核心功能函數 ---
def get_thumbnail_url(url, width=800):
    """利用 Cloudinary 動態轉換取得輕量縮圖"""
    if "/upload/" in url:
        return url.replace("/upload/", f"/upload/w_{width},c_scale,q_auto,f_auto/")
    return url


def render_watermarked_image(image_url, watermark=False):
    """根據是否開啟浮水印，渲染對應的 HTML 圖片結構"""
    if watermark:
        html_code = f"""
        <div class="watermark-container">
            <img src="{image_url}" style="width:100%; border-radius: 5px;">
            <div class="watermark-overlay" title="SAMPLE WATERMARK"></div>
        </div>
        """
        st.markdown(html_code, unsafe_allow_html=True)
    else:
        st.image(image_url, use_container_width=True)


def format_file_size(size_in_bytes):
    if not size_in_bytes:
        return "未知"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f} GB"


def compress_image(image_file):
    try:
        img = Image.open(image_file)
        try:
            exif = img._getexif()
            if exif is not None:
                orientation_key = next(
                    (k for k, v in ExifTags.TAGS.items() if v == "Orientation"),
                    None,
                )
                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    if orientation == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
        except Exception:
            pass

        max_width = 1920
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

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
        url, options = cloudinary.utils.cloudinary_url(
            DB_FILENAME, resource_type="raw"
        )
        no_cache_url = f"{url}?t={int(time.time())}"
        response = requests.get(no_cache_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                item["date"] = datetime.datetime.strptime(
                    item["date_str"], "%Y-%m-%d"
                ).date()
                if "album" not in item:
                    item["album"] = "未分類"
                if "size" not in item:
                    item["size"] = 0
            return data
        else:
            return []
    except Exception:
        return []


def save_db(data):
    save_list = []
    for item in data:
        save_list.append(
            {
                "public_id": item["public_id"],
                "url": item["url"],
                "name": item["name"],
                "date_str": item["date"].strftime("%Y-%m-%d"),
                "tags": item["tags"],
                "album": item.get("album", "未分類"),
                "size": item.get("size", 0),
            }
        )
    json_str = json.dumps(save_list, ensure_ascii=False, indent=2)
    try:
        cloudinary.uploader.upload(
            BytesIO(json_str.encode("utf-8")),
            public_id=DB_FILENAME,
            resource_type="raw",
            overwrite=True,
            invalidate=True,
        )
    except Exception as e:
        st.error(f"資料庫同步雲端失敗: {e}")


def delete_image_from_cloud(public_id):
    try:
        cloudinary.uploader.destroy(public_id)
    except Exception as e:
        print(f"刪除圖片失敗 ({public_id}): {e}")


def request_clear_selections():
    st.session_state["need_clear_selections"] = True


# --- 4. 應用程式主邏輯 ---

if st.session_state.get("need_clear_selections", False):
    for key in list(st.session_state.keys()):
        if key.startswith("sel_"):
            st.session_state[key] = False
    st.session_state["need_clear_selections"] = False

if "gallery" not in st.session_state:
    with st.spinner("載入雲端資料庫..."):
        st.session_state.gallery = load_db()


# === 📸 照片詳情 Modal ===
@st.dialog("📸 照片詳情", width="large")
def show_large_image(photo):
    st.image(photo["url"], use_container_width=True)
    st.divider()

    # --- ✏️ 1. 修改檔名 ---
    st.subheader("✏️ 修改檔名")
    new_name = st.text_input("檔名", value=photo["name"], key=f"edit_name_modal_{photo['public_id']}")
    if st.button("💾 儲存檔名", key=f"btn_name_modal_{photo['public_id']}", use_container_width=True):
        if new_name.strip():
            for origin in st.session_state.gallery:
                if origin["public_id"] == photo["public_id"]:
                    origin["name"] = new_name.strip()
                    break
            save_db(st.session_state.gallery)
            st.toast("✅ 檔名已成功修改！")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("檔名不能為空！")

    st.divider()

    # --- 🏷️ 2. 修改獨立標籤 ---
    st.subheader("🏷️ 修改標籤")
    selected_tags_modal = st.multiselect(
        "標籤內容",
        options=ALL_TAG_OPTIONS,
        default=[t for t in photo.get("tags", []) if t in ALL_TAG_OPTIONS],
        key=f"edit_tags_modal_{photo['public_id']}"
    )
    if st.button("💾 儲存標籤", key=f"btn_tags_modal_{photo['public_id']}", use_container_width=True, type="primary"):
        for origin in st.session_state.gallery:
            if origin["public_id"] == photo["public_id"]:
                origin["tags"] = selected_tags_modal
                break
        save_db(st.session_state.gallery)
        st.toast("✅ 標籤已成功更新！")
        time.sleep(0.5)
        st.rerun()

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.write(f"📅 **日期**: {photo['date']}")
        st.write(f"📂 **相簿**: {photo['album']}")
    with c2:
        file_size_str = format_file_size(photo.get("size", 0))
        st.write(f"📏 **大小**: {file_size_str}")

    st.markdown(
        f'<a href="{photo["url"]}" target="_blank" download="{photo["name"]}">'
        f'<button style="width:100%; padding:10px; background-color:#ff4b4b; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold; margin-top:10px;">'
        f"⬇️ 開啟 / 下載高畫質原圖</button></a>",
        unsafe_allow_html=True,
    )


# =========================================================
# 🔗 [分享頁面]（鎖定：不可放大、不可下載圖片、防右鍵、菱形網格保護網）
# =========================================================
query_params = st.query_params

if "share" in query_params:
    st.title("🖼️ 專屬分享相簿")
    st.caption("您正透過專屬分享連結瀏覽特定相片內容")

    st.markdown(
        """
        <style>
        img {
            pointer-events: none !important;
            -webkit-touch-callout: none !important;
            -webkit-user-select: none !important;
            user-select: none !important;
        }
        </style>
        <script>
        document.addEventListener('contextmenu', event => event.preventDefault());
        </script>
        """,
        unsafe_allow_html=True,
    )

    raw_share = query_params["share"]
    shared_ids = [pid.strip() for pid in raw_share.split(",") if pid.strip()]

    # 檢查網址是否有勾選啟用浮水印 (&wm=1)
    use_watermark = query_params.get("wm", "0") == "1"

    shared_photos = [
        p for p in st.session_state.gallery if p["public_id"] in shared_ids
    ]

    if not shared_photos:
        st.error("⚠️ 找不到分享的照片，連結可能已失效或圖片已被刪除。")
    else:
        wm_status = " (已保護：已載入菱形 SAMPLE 浮水印)" if use_watermark else ""
        st.success(f"📷 共有 {len(shared_photos)} 張分享的作品{wm_status}")
        st.divider()

        for i in range(0, len(shared_photos), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(shared_photos):
                    photo = shared_photos[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            # 呼叫渲染函式帶入輕量菱形浮水印圖層
                            render_watermarked_image(
                                get_thumbnail_url(photo["url"], width=800), 
                                watermark=use_watermark
                            )
                            st.caption(f"📄 {photo['name']}")

    st.markdown('<div id="bottom-anchor"></div>', unsafe_allow_html=True)
    st.stop()

# =========================================================
# 🏠 完整圖庫後台模式
# =========================================================
st.title("☁️ 雲端圖庫 (電腦/手機 雙重適應版)")

existing_albums = sorted(
    list(set([item["album"] for item in st.session_state.gallery]))
)
if "未分類" not in existing_albums:
    existing_albums.append("未分類")

# === 預設標籤與指定排序設定 ===
DING_TAGS = [
    "無償",
    "非無償",
    "雙人",
    "單人",
    "線稿",
    "彩色",
    "✅SAMPLE",
]

RING_TAGS = [
    "人物",
    "生物",
    "風景",
]

DEFAULT_TAGS = DING_TAGS + RING_TAGS

db_existing_tags = [
    tag for item in st.session_state.gallery for tag in item["tags"]
]
extra_tags = [tag for tag in db_existing_tags if tag not in DEFAULT_TAGS]
ALL_TAG_OPTIONS = DEFAULT_TAGS + sorted(list(set(extra_tags)))

# === 側邊欄 ===
with st.sidebar:
    st.header("功能選單")
    page_mode = st.radio(
        "前往頁面",
        ["📸 相簿瀏覽", "📊 數據統計"],
        label_visibility="collapsed",
    )
    st.divider()

    st.header("📂 上傳作品")
    album_mode = st.radio("上傳模式", ["選擇現有相簿", "建立新相簿"])
    if album_mode == "建立新相簿":
        current_album = st.text_input("輸入新相簿名稱")
    else:
        current_album = st.selectbox("選擇上傳相簿", existing_albums)

    uploaded_files = st.file_uploader(
        "選擇圖片 (可多選)",
        type=["jpg", "png", "jpeg", "webp"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        existing_names = [p["name"] for p in st.session_state.gallery]
        duplicates = [
            f.name for f in uploaded_files if f.name in existing_names
        ]

        if duplicates:
            st.warning(f"⚠️ 發現重複檔名：\n{', '.join(duplicates)}")
            upload_mode = st.radio(
                "對重複檔案的操作：",
                ["略過重複檔案 (建議)", "強制全部上傳"],
            )
        else:
            upload_mode = "強制全部上傳"

        if st.button("確認上傳", type="primary", use_container_width=True):
            if not current_album:
                st.error("請輸入相簿名稱")
            else:
                if duplicates and upload_mode == "略過重複檔案 (建議)":
                    final_files = [
                        f
                        for f in uploaded_files
                        if f.name not in existing_names
                    ]
                else:
                    final_files = uploaded_files

                if not final_files:
                    st.info("💡 所有檔案皆已存在圖庫中，無新檔案上傳。")
                else:
                    progress = st.progress(0)
                    status_text = st.empty()

                    for i, f in enumerate(final_files):
                        status_text.text(
                            f"處理中 {i+1}/{len(final_files)}：{f.name} (壓縮上傳中...)"
                        )
                        try:
                            compressed_file = compress_image(f)
                            file_size_bytes = (
                                compressed_file.getbuffer().nbytes
                            )
                            res = cloudinary.uploader.upload(compressed_file)

                            try:
                                d = datetime.datetime.strptime(
                                    f.name[:8], "%Y%m%d"
                                ).date()
                            except Exception:
                                d = datetime.date.today()

                            st.session_state.gallery.append(
                                {
                                    "public_id": res["public_id"],
                                    "url": res["secure_url"],
                                    "name": f.name,
                                    "date": d,
                                    "tags": [],
                                    "album": current_album,
                                    "size": file_size_bytes,
                                }
                            )
                        except Exception as e:
                            st.error(f"❌ {f.name} 上傳失敗: {e}")

                        progress.progress((i + 1) / len(final_files))

                    status_text.text("儲存更新資料庫...")
                    save_db(st.session_state.gallery)
                    st.success("上傳完成！")
                    time.sleep(1)
                    st.rerun()

# === 頁面分流 ===

if page_mode == "📸 相簿瀏覽":

    with st.expander("🔍 篩選與排序設定", expanded=True):
        f_c1, f_c2, f_c3 = st.columns([1, 1.5, 1.5])
        with f_c1:
            filter_album = st.selectbox("📂 相簿", ["全部"] + existing_albums)
            show_untagged = st.checkbox(
                "只看未分類", help="只顯示無標籤圖片"
            )

        with f_c2:
            filter_tags = st.multiselect(
                "✅ 包含標籤 (同時符合)", ALL_TAG_OPTIONS
            )

        with f_c3:
            exclude_tags = st.multiselect(
                "🚫 排除標籤 (不要這些)", ALL_TAG_OPTIONS
            )

        st.divider()

        f_c4, f_c5, f_c6 = st.columns(3)
        with f_c4:
            sort_option = st.selectbox(
                "🔃 排序方式",
                [
                    "日期 (新→舊)",
                    "日期 (舊→新)",
                    "檔名 (A→Z)",
                    "檔名 (Z→A)",
                    "標籤 (A→Z)",
                ],
                index=0,
            )
        with f_c5:
            all_years = sorted(
                list(
                    set([p["date"].year for p in st.session_state.gallery])
                ),
                reverse=True,
            )
            filter_year = st.selectbox("📅 年份", ["全部"] + all_years)

        with f_c6:
            all_months = list(range(1, 13))
            filter_months = st.multiselect(
                "🌙 月份 (未選擇則代表全部)",
                options=all_months,
                default=all_months,
            )

    filtered_photos = []
    for p in st.session_state.gallery:
        match_album = (filter_album == "全部") or (p["album"] == filter_album)
        match_year = (filter_year == "全部") or (p["date"].year == filter_year)

        if not filter_months:
            match_month = True
        else:
            match_month = p["date"].month in filter_months

        if show_untagged:
            match_tags = len(p["tags"]) == 0
        else:
            match_tags = True
            if filter_tags:
                match_tags = all(tag in p["tags"] for tag in filter_tags)
            if match_tags and exclude_tags:
                if any(tag in exclude_tags for tag in p["tags"]):
                    match_tags = False

        if match_album and match_year and match_month and match_tags:
            filtered_photos.append(p)

    if sort_option == "日期 (舊→新)":
        filtered_photos.sort(key=lambda x: x["date"])
    elif sort_option == "日期 (新→舊)":
        filtered_photos.sort(key=lambda x: x["date"], reverse=True)
    elif sort_option == "檔名 (A→Z)":
        filtered_photos.sort(key=lambda x: x["name"])
    elif sort_option == "檔名 (Z→A)":
        filtered_photos.sort(key=lambda x: x["name"], reverse=True)
    elif sort_option == "標籤 (A→Z)":
        filtered_photos.sort(
            key=lambda x: x["tags"][0] if x["tags"] else "zzzz"
        )

    st.write("")
    s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
    with s_col1:
        if filtered_photos:
            st.markdown(f"### 📸 共找到 :red[{len(filtered_photos)}] 張照片")
        else:
            st.warning("⚠️ 共找到 0 張照片。")
    with s_col2:
        if st.button("✅ 全選本頁", use_container_width=True):
            for p in filtered_photos:
                st.session_state[f"sel_{p['public_id']}"] = True
            st.rerun()
    with s_col3:
        if st.button("❎ 取消全選", use_container_width=True):
            for p in filtered_photos:
                st.session_state[f"sel_{p['public_id']}"] = False
            st.rerun()

    st.divider()

    # --- 照片展示區 ---
    selected_photos = []
    if filtered_photos:
        with st.container():
            st.markdown(
                '<div class="gallery-marker" style="display:none;"></div>',
                unsafe_allow_html=True,
            )

            for i in range(0, len(filtered_photos), 3):
                cols = st.columns(3)

                for j in range(3):
                    if i + j < len(filtered_photos):
                        photo = filtered_photos[i + j]

                        with cols[j]:
                            with st.container(border=True):
                                st.image(
                                    get_thumbnail_url(photo["url"]),
                                    use_container_width=True,
                                )

                                btn_col, check_col = st.columns([1, 4])
                                with btn_col:
                                    if st.button(
                                        "🔍",
                                        key=f"zoom_{photo['public_id']}",
                                        help="查看大圖、修改檔名與標籤",
                                    ):
                                        show_large_image(photo)
                                with check_col:
                                    key = f"sel_{photo['public_id']}"
                                    if key not in st.session_state:
                                        st.session_state[key] = False
                                    is_selected = st.checkbox(
                                        f"{photo['name']}", key=key
                                    )

                                tags_str = (
                                    f"🏷️ {','.join(photo['tags'])}"
                                    if photo["tags"]
                                    else "❌ 未分類"
                                )
                                size_str = format_file_size(
                                    photo.get("size", 0)
                                )
                                st.caption(f"{tags_str} | 📏 {size_str}")

                                # --- ✏️ 單張獨立修改標籤區塊 ---
                                with st.expander("✏️ 單張修改標籤", expanded=False):
                                    card_tags = st.multiselect(
                                        "修改標籤",
                                        options=ALL_TAG_OPTIONS,
                                        default=[t for t in photo.get("tags", []) if t in ALL_TAG_OPTIONS],
                                        key=f"card_tags_{photo['public_id']}",
                                        label_visibility="collapsed"
                                    )
                                    if st.button("💾 儲存標籤", key=f"save_card_tags_{photo['public_id']}", use_container_width=True):
                                        for origin in st.session_state.gallery:
                                            if origin["public_id"] == photo["public_id"]:
                                                origin["tags"] = card_tags
                                                break
                                        save_db(st.session_state.gallery)
                                        st.toast(f"✅ {photo['name']} 標籤已更新！")
                                        time.sleep(0.5)
                                        st.rerun()

                                if is_selected:
                                    selected_photos.append(photo)

    # --- 批次操作控制面板 ---
    if selected_photos:
        st.write("")
        with st.container(border=True):
            st.info(
                f"⚡ 已選取 {len(selected_photos)} 張照片，請進行下方批次操作："
            )

            # --- 分享連結（含浮水印開關） ---
            st.subheader("🔗 產生專屬分享連結")
            
            enable_wm = st.checkbox("🔒 加上菱形 SAMPLE 防護浮水印（勾選後對方將看到輕透滿版保護線）", value=True)
            
            selected_pids = [p["public_id"] for p in selected_photos]
            pids_query = ",".join(selected_pids)
            wm_param = "&wm=1" if enable_wm else "&wm=0"

            copy_code = f"""
            <div style="margin-bottom: 10px;">
                <input type="text" id="shareUrlInput" style="width: 100%; padding: 10px; border: 1px solid #444; border-radius: 5px; background-color: #1e1e1e; color: #00ffcc; margin-bottom: 8px; font-size: 14px; box-sizing: border-box;" readonly>
                <button id="copyBtn" onclick="copyShareUrl()" style="width: 100%; padding: 10px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 15px;">
                    📋 一鍵複製完整分享連結
                </button>
            </div>

            <script>
                let parentOrigin = "";
                let parentPath = "";
                try {{
                    parentOrigin = window.parent.location.origin;
                    parentPath = window.parent.location.pathname;
                }} catch (e) {{
                    parentOrigin = window.location.origin;
                    parentPath = window.location.pathname;
                }}

                const fullShareUrl = parentOrigin + parentPath + "?share={pids_query}{wm_param}";
                
                const inputEl = document.getElementById("shareUrlInput");
                inputEl.value = fullShareUrl;

                function copyShareUrl() {{
                    const btn = document.getElementById("copyBtn");
                    const targetClipboard = (window.parent && window.parent.navigator && window.parent.navigator.clipboard) 
                                            ? window.parent.navigator.clipboard 
                                            : navigator.clipboard;

                    if (targetClipboard && window.isSecureContext) {{
                        targetClipboard.writeText(fullShareUrl).then(() => {{
                            btn.innerText = "✅ 已成功複製到剪貼簿！";
                            btn.style.backgroundColor = "#28a745";
                            setTimeout(() => {{
                                btn.innerText = "📋 一鍵複製完整分享連結";
                                btn.style.backgroundColor = "#ff4b4b";
                            }}, 2500);
                        }}).catch(err => {{
                            fallbackCopy();
                        }});
                    }} else {{
                        fallbackCopy();
                    }}
                }}

                function fallbackCopy() {{
                    const btn = document.getElementById("copyBtn");
                    inputEl.select();
                    document.execCommand('copy');
                    btn.innerText = "✅ 已成功複製到剪貼簿！";
                    btn.style.backgroundColor = "#28a745";
                    setTimeout(() => {{
                        btn.innerText = "📋 一鍵複製完整分享連結";
                        btn.style.backgroundColor = "#ff4b4b";
                    }}, 2500);
                }}
            </script>
            """

            components.html(copy_code, height=105)

            st.caption(
                "💡 **說明**：點擊「一鍵複製完整分享連結」發給其他人，對方開啟後將只能看到選取的作品，且無法放大或下載圖片。"
            )

            st.divider()

            # --- 標籤與刪除操作 ---
            act_c1, act_c2 = st.columns(2)
            with act_c1:
                action_tags = st.multiselect("設定標籤操作", ALL_TAG_OPTIONS)

                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.button("➕ 加入標籤", use_container_width=True):
                    for p in selected_photos:
                        for origin in st.session_state.gallery:
                            if origin["public_id"] == p["public_id"]:
                                current_tags = origin.get("tags", [])
                                origin["tags"] = list(
                                    set(current_tags + action_tags)
                                )
                    save_db(st.session_state.gallery)
                    request_clear_selections()
                    st.toast("✅ 標籤已加入！")
                    time.sleep(0.5)
                    st.rerun()

                if btn_col2.button("🔄 完全覆蓋", use_container_width=True):
                    for p in selected_photos:
                        for origin in st.session_state.gallery:
                            if origin["public_id"] == p["public_id"]:
                                origin["tags"] = action_tags
                    save_db(st.session_state.gallery)
                    request_clear_selections()
                    st.toast("🔄 標籤已覆蓋！")
                    time.sleep(0.5)
                    st.rerun()

            with act_c2:
                st.write("")
                st.write("")
                if st.button(
                    "🗑️ 刪除選取照片", type="primary", use_container_width=True
                ):
                    del_ids = {p["public_id"] for p in selected_photos}
                    for pid in del_ids:
                        delete_image_from_cloud(pid)

                    st.session_state.gallery = [
                        x
                        for x in st.session_state.gallery
                        if x["public_id"] not in del_ids
                    ]

                    save_db(st.session_state.gallery)
                    request_clear_selections()
                    st.success("已刪除！")
                    time.sleep(0.5)
                    st.rerun()

            st.divider()
            st.button(
                "❎ 取消所有選取 (離開編輯模式)",
                use_container_width=True,
                on_click=request_clear_selections,
            )

else:
    # -----------------------------------------------------------
    #  [統計頁面]
    # -----------------------------------------------------------
    st.header("📊 數據統計中心")
    st.write("查看不同相簿或整體的創作產量")

    if not st.session_state.gallery:
        st.info("無資料，請先上傳照片！")
    else:
        stat_album = st.selectbox(
            "📂 選擇要統計的相簿", ["全部"] + existing_albums
        )

        if stat_album == "全部":
            stat_photos = st.session_state.gallery
        else:
            stat_photos = [
                p for p in st.session_state.gallery if p["album"] == stat_album
            ]

        if not stat_photos:
            st.warning(f"相簿 '{stat_album}' 裡面目前沒有照片喔！")
        else:
            total_photos = len(stat_photos)
            untagged_count = len([p for p in stat_photos if not p["tags"]])
            total_size_bytes = sum([p.get("size", 0) for p in stat_photos])

            m1, m2, m3 = st.columns(3)
            m1.metric("📸 照片數", total_photos)
            m2.metric("❌ 未分類", untagged_count, delta_color="inverse")
            m3.metric("💾 空間使用", format_file_size(total_size_bytes))

            st.divider()

            raw_data = []
            for p in stat_photos:
                raw_data.append(
                    {"Year": p["date"].year, "Month": p["date"].month}
                )

            if raw_data:
                df = pd.DataFrame(raw_data)
                pivot_df = pd.crosstab(df["Month"], df["Year"])

                all_months = list(range(1, 13))
                pivot_df = pivot_df.reindex(all_months, fill_value=0)

                available_years = sorted(list(pivot_df.columns), reverse=True)
                selected_years = st.multiselect(
                    "📅 選擇要比較的年份 (可多選)：",
                    options=available_years,
                    default=available_years,
                )

                if selected_years:
                    filtered_pivot = pivot_df[selected_years]

                    st.subheader(f"📈 年度產量比較 ({stat_album})")
                    st.bar_chart(filtered_pivot)

                    st.divider()

                    st.subheader(f"🗓️ 年度月別統計表 ({stat_album})")
                    table_df = filtered_pivot.copy()
                    table_df.loc["總計"] = table_df.sum()
                    table_df.index.name = "月份"
                    st.dataframe(table_df, use_container_width=True)
                else:
                    st.info(
                        "💡 請至少選擇一個年份以顯示圖表與數據表。"
                    )

# 頁尾錨點 (供懸浮按鈕跳轉)
st.markdown('<div id="bottom-anchor"></div>', unsafe_allow_html=True)
