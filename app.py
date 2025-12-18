import streamlit as st
import os
import shutil
from datetime import datetime
import pandas as pd

# 設定基礎路徑 (所有的相簿都會放在這個 albums 資料夾下)
BASE_DIR = "albums"

# 確保基礎資料夾存在
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

st.title("📸 雲端智慧相簿管理系統")

# --- 側邊欄：相簿管理 ---
st.sidebar.header("📁 相簿管理")

# 1. 建立新相簿
new_album = st.sidebar.text_input("建立新相簿名稱")
if st.sidebar.button("新增相簿"):
    if new_album:
        album_path = os.path.join(BASE_DIR, new_album)
        if not os.path.exists(album_path):
            os.makedirs(album_path)
            st.sidebar.success(f"相簿 '{new_album}' 已建立！")
        else:
            st.sidebar.warning("該相簿已存在。")

# 2. 選擇相簿
albums_list = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
selected_album = st.sidebar.selectbox("選擇相簿", albums_list)

if selected_album:
    album_path = os.path.join(BASE_DIR, selected_album)
    
    # --- 上傳照片區域 ---
    st.subheader(f"📂 目前相簿：{selected_album}")
    uploaded_files = st.file_uploader("上傳照片 (支援多選)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_path = os.path.join(album_path, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        st.success(f"成功上傳 {len(uploaded_files)} 張照片！")

    # --- 讀取照片與日期處理 ---
    # 讀取該相簿下所有檔案
    files = [f for f in os.listdir(album_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if files:
        # 建立一個資料表來管理照片資訊
        data = []
        for f in files:
            file_full_path = os.path.join(album_path, f)
            # 獲取檔案修改時間 (模擬拍攝時間)
            timestamp = os.path.getmtime(file_full_path)
            dt = datetime.fromtimestamp(timestamp)
            data.append({
                "Filename": f,
                "Path": file_full_path,
                "Year": dt.year,
                "Month": dt.month
            })
        
        df = pd.DataFrame(data)

        # --- 篩選器 (Filter) ---
        st.divider()
        st.subheader("🔍 篩選照片")
        col1, col2 = st.columns(2)
        
        with col1:
            # 抓出所有的年份選項
            all_years = sorted(df['Year'].unique())
            selected_years = st.multiselect("選擇年份", all_years, default=all_years)
        
        with col2:
            # 抓出所有的月份選項
            all_months = sorted(df['Month'].unique())
            selected_months = st.multiselect("選擇月份", all_months, default=all_months)

        # 根據使用者選擇進行資料篩選
        filtered_df = df[
            (df['Year'].isin(selected_years)) & 
            (df['Month'].isin(selected_months))
        ]

        # --- 批次管理區域 ---
        st.divider()
        st.subheader("🛠️ 批次管理 (修改標籤/刪除)")
        
        # 讓使用者勾選要處理的照片
        selected_files_to_edit = st.multiselect(
            "選擇要操作的照片：", 
            filtered_df['Filename'].tolist()
        )

        # 展示選中的照片預覽
        if selected_files_to_edit:
            st.write("已選取照片預覽：")
            cols = st.columns(len(selected_files_to_edit)) if len(selected_files_to_edit) < 4 else st.columns(4)
            for idx, file_name in enumerate(selected_files_to_edit):
                img_path = os.path.join(album_path, file_name)
                # 使用簡單的數學運算來分配圖片到欄位中
                cols[idx % 4].image(img_path, caption=file_name, use_container_width=True)

            # 操作按鈕
            col_action1, col_action2 = st.columns(2)
            
            with col_action1:
                # 批次新增標籤 (這裡演示邏輯，實際儲存需要資料庫)
                new_tag = st.text_input("輸入新標籤")
                if st.button("批次更新標籤"):
                    st.toast(f"已為 {len(selected_files_to_edit)} 張照片添加標籤：{new_tag}")
                    st.info("💡 提示：在真實系統中，這裡會將標籤寫入資料庫或 CSV 檔。")

            with col_action2:
                # 批次刪除
                if st.button("🗑️ 批次刪除照片", type="primary"):
                    for file_name in selected_files_to_edit:
                        os.remove(os.path.join(album_path, file_name))
                    st.success("照片已刪除！請手動重新整理頁面。")
                    
        else:
            st.info("請從上方清單選擇照片以進行批次操作。")

    else:
        st.write("此相簿目前沒有照片，請先上傳。")
else:
    st.info("請從左側側邊欄建立或選擇一個相簿。")
