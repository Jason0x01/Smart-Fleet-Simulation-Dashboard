# 雙車多輪配送模擬系統

本專案旨在應對現代物流業在**效率、成本、合規性**上的核心挑戰。我們透過建構一個整合了真實路況、時間窗、車輛容量等多重限制的智慧派遣模型，來模擬並驗證一個資料驅動的車隊調度解決方案。

## 功能亮點
- **動態模擬**：以分鐘級別，視覺化呈現多車輛、多趟次的完整配送流程。
- **互動式探索**：提供時間軸滑桿與篩選器，讓使用者能深入探索特定趟次的細節。
- **KPI 儀表板**：即時計算並展示關鍵績效指標，如總配送包裹數、總載重、總體積等。
- **真實路徑整合**：所有路徑皆基於真實世界的路網資料，提供高度擬真的模擬結果。

## 如何運行
1.  **安裝必要的函式庫**:
    ```bash
    pip install streamlit pandas folium streamlit-folium openpyxl
    ```
2.  **準備資料檔案**:
    請確保以下檔案與主程式位於同一個資料夾：
    - `master_timeline_data_final.csv`
    - `parcels_with_real_coords_updated_full.json`
    - `POWER BI圖片.png`

3.  **啟動應用**:
    在終端機中執行以下指令：
    ```bash
    streamlit run final_dashboard_app.py
    ```