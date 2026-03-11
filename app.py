跳至內容
soraacg02-雲
我的照片庫
儲存庫導航
程式碼
問題
拉取請求
行動
專案
安全
洞察
設定
文件
轉到文件
t
.streamlit
README.md
app.py
app.py2
requirements.txt
我的照片庫
/
app.py
在
主要的

編輯

預覽
縮排模式

空格
壓痕尺寸

4
自動換行模式

無需包裝
編輯 app.py 檔案內容
  1
  2
  3
  4
  5
  6
  7
  8
  9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
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
用於Control + Shift + m切換tab關鍵的移動焦點。或者，使用esc該按鈕tab移動到頁面上的下一個互動元素。
