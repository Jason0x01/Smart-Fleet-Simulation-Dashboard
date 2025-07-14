# -*- coding: utf-8 -*-
"""
智慧運輸模擬儀表板 (最終交付版)
版本說明：
- 最終版，整合所有功能、修正與內容。
- 採用最穩健的佈局，確保所有靜態說明區塊在任何情況下都能正常、優先顯示。
"""

import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- 1. 頁面設定 (最優先) ---
st.set_page_config(layout="wide", page_title="智慧運輸模擬儀表板")

# --- 2. 核心功能函式定義 ---
@st.cache_data
def load_data(timeline_filepath, parcels_filepath):
    """從 CSV 和 JSON 載入並預處理資料。"""
    try:
        timeline_df = pd.read_csv(timeline_filepath)
        with open(parcels_filepath, 'r', encoding='utf-8') as f:
            parcels_data = json.load(f)
        
        timeline_df[['lat', 'lon']] = timeline_df['Location'].str.split(', ', expand=True)
        timeline_df['lat'] = pd.to_numeric(timeline_df['lat'])
        timeline_df['lon'] = pd.to_numeric(timeline_df['lon'])
        timeline_df['Timestamp'] = pd.to_datetime(timeline_df['Date'] + ' ' + timeline_df['Time'])

        parcels_df = pd.DataFrame(parcels_data).set_index('id')
        
        return timeline_df, parcels_df
    except FileNotFoundError as e:
        # 僅在主控台報錯，並回傳 None，讓介面能繼續顯示靜態內容
        print(f"ERROR: Cannot find data files. Please ensure '{timeline_filepath}' and '{parcels_filepath}' exist. Details: {e}")
        return None, None
    except Exception as e:
        print(f"ERROR reading data: {e}")
        return None, None

def display_dynamic_content(df, parcels_df):
    """
    處理所有與資料相關的動態UI元件（側邊欄、KPI、地圖等）。
    """
    # --- 側邊欄 ---
    with st.sidebar:
        st.header("篩選條件")
        vehicle_options = sorted(df['vehicle_id'].unique())
        selected_vehicle = st.selectbox("選擇車輛:", options=vehicle_options, key="vehicle_select")
        
        round_options = sorted(df[df['vehicle_id'] == selected_vehicle]['round_id'].unique())
        selected_round = st.selectbox("選擇趟次:", options=round_options, key="round_select")
        
        st.markdown("---")
        st.info("App Version: 10.0 (Definitive)")
        st.info(f"Last Updated: {datetime.now().strftime('%Y-%m-%d')}")

    # --- 互動介面主體 ---
    filtered_df = df[
        (df['vehicle_id'] == selected_vehicle) &
        (df['round_id'] == selected_round)
    ].copy()

    if filtered_df.empty:
        st.warning("找不到符合條件的資料，請更換篩選條件。")
        return

    # --- KPI, 地圖, 時間軸等互動內容 ---
    st.subheader(f"趟次即時動態 ({selected_vehicle} / {selected_round})")

    delivered_parcels = filtered_df[filtered_df['Status'].str.startswith('抵達 P')]['Status'].str.extract(r'抵達 (P\d+)')
    delivered_parcel_ids = delivered_parcels[0].dropna().unique().tolist()
    total_weight = parcels_df.loc[delivered_parcel_ids, 'weight'].sum() if delivered_parcel_ids else 0
    total_volume = parcels_df.loc[delivered_parcel_ids, 'volume'].sum() if delivered_parcel_ids else 0
    end_time_series = filtered_df[filtered_df['Status'] != '休息中']['Timestamp']
    end_time = end_time_series.max().strftime('%H:%M:%S') if not end_time_series.empty else "N/A"
    total_stops = len(delivered_parcel_ids)

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric(label="總配送包裹數", value=f"{total_stops} 件")
    kpi2.metric(label="總載重 (kg)", value=f"{total_weight:.2f}")
    kpi3.metric(label="總體積 (m³)", value=f"{total_volume:.2f}")
    st.metric(label="最終回廠時間", value=end_time)

    st.markdown("---")

    time_options = filtered_df.sort_values(by='Timestamp')['Time'].unique()
    selected_time_str = st.select_slider("拖動時間軸查看車輛動態:", options=time_options, key=f"slider_{selected_vehicle}_{selected_round}")
    current_state = filtered_df[filtered_df['Time'] == selected_time_str].iloc[0]

    col1, col2 = st.columns(2)
    col1.info(f"**目前狀態：** `{current_state['Status']}`")
    col2.info(f"**目前位置：** `{current_state['Location']}`")

    m = folium.Map(tiles='CartoDB positron')
    path_coords = list(zip(filtered_df['lat'], filtered_df['lon']))
    folium.PolyLine(path_coords, color="grey", weight=3, opacity=0.7).add_to(m)
    
    parcel_stops = filtered_df[filtered_df['Status'].str.startswith('抵達 P')]
    for _, stop in parcel_stops.iterrows():
        folium.CircleMarker(location=[stop['lat'], stop['lon']], radius=5, color='purple', fill=True, fill_color='purple', popup=f"{stop['Status']} @ {stop['Time']}").add_to(m)

    current_location_coords = [current_state['lat'], current_state['lon']]
    folium.Marker(location=current_location_coords, popup=f"目前位置<br>{current_state['Status']}<br>時間: {current_state['Time']}", icon=folium.Icon(color='green', icon='truck', prefix='fa')).add_to(m)
    folium.Marker(location=[24.1469, 120.6839], popup='起點/倉庫', icon=folium.Icon(color='black', icon='home')).add_to(m)

    bounds = [[filtered_df['lat'].min(), filtered_df['lon'].min()], [filtered_df['lat'].max(), filtered_df['lon'].max()]]
    m.fit_bounds(bounds, padding=(20, 20))

    st_folium(m, width='100%', height=500, returned_objects=[])

    with st.expander("顯示/隱藏 詳細時間軸資料"):
        st.dataframe(filtered_df[['Time', 'Status', 'Location', 'vehicle_id', 'round_id']])

# --- 3. 主程式執行流程 ---

# --- 首先，繪製所有靜態內容 ---
st.title("雙車多輪配送模擬系統")
st.caption("結合真實路況與時限的智慧派遣模型")

with st.expander("壹、專案摘要", expanded=False):
    st.markdown("""
    本專案旨在應對現代物流業在**效率、成本、合規性**上的核心挑戰。我們透過建構一個整合了真實路況、時間窗、車輛容量等多重限制的智慧派遣模型，來模擬並驗證一個資料驅動的車隊調度解決方案。其最終目標是展現如何透過演算法與數據視覺化，在實務中有效提升營運效率與管理品質。
    """)
st.markdown("---")

# --- 其次，嘗試載入資料並顯示動態內容 ---
TIMELINE_FILE = "master_timeline_data_final.csv"
PARCELS_FILE = "parcels_with_real_coords_updated_full.json"
df, parcels_df = load_data(TIMELINE_FILE, PARCELS_FILE)

if df is not None and parcels_df is not None:
    # 如果資料成功載入，才呼叫函式來顯示所有互動元件
    display_dynamic_content(df, parcels_df)
else:
    # 如果資料載入失敗，只顯示一則錯誤訊息
    st.error("無法載入必要的資料檔案，互動圖表無法顯示。請檢查檔案是否存在且格式正確。")

# --- 最後，繪製頁面底部的靜態內容 ---
st.markdown("---")
st.header("專案洞察與未來展望")

with st.expander("Power BI 商業智慧儀表板", expanded=False):
    st.markdown("此儀表板呈現了專案整體的宏觀績效指標（KPI），旨在為管理層提供一個高層次的決策視角，快速掌握運輸效益的全貌。")
    try:
        st.image("POWER BI圖片.png", caption="Power BI 總覽儀表板")
    except Exception as e:
        st.warning(f"無法載入 Power BI 圖片，請確認 'POWER BI圖片.png' 檔案位於同一資料夾中。")

with st.expander("本案應用技術與後續做法", expanded=False):
    st.markdown("""
    #### 智慧車聯網應用趨勢
    本專案所累積的專業知識，可直接應用於推廣以下前瞻性業務：
    - **5G路口安全智慧輔助系統**: 結合 5G 與 AIoT 技術，透過即時的車輛動態偵測，預判違規與碰撞事件，並即時推播告警，提升用路安全。
    - **AI影像辨識智能停車場**: 利用 AI 影像辨識即時偵測車格狀態，並透過 5G 回傳至平台，讓管理者能即時掌握車格使用率。
    - **電信大數據交通分析與預測**: 運用行動信令數據分析人車活動，協助政府評估交通效率、預測趨勢，乃至進行城市旅次的碳排分析。

    #### 本專案知識的應用價值
    本模擬系統的開發過程，已驗證了我們在以下幾個核心領域的專業能力：
    - **即時數據處理與視覺化**: 處理並即時呈現動態 GPS 軌跡的能力，是實現「5G路口安全輔助」等應用的技術基礎。
    - **路線規劃與優化演算法**: 本專案的排程與補位邏輯，可延伸應用於「電信大數據交通分析」中的車流預測與交通績效評估。
    - **多源資料整合能力**: 成功整合多種異質資料（Excel, JSON, CSV），是建構「AI智慧停車場」等複雜系統的關鍵能力。
    - **系統模擬與可行性驗證**: 本儀表板作為一個小型的「數位分身」(Digital Twin) 應用，能在真實部署前，有效模擬並驗證新系統的效益，大幅降低開發風險。
    """)