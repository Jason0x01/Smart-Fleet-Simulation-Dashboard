import requests
from math import radians, cos, sin, asin, sqrt
import folium
import time
import polyline
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import random

GRAPH_KEY = "18523c59-d6a2-476a-ad8c-6f3a33b2db71"
GRAPH_URL = "https://graphhopper.com/api/1/route"
DEPOT_LAT, DEPOT_LON = 24.1469, 120.6839
error_log = []
vehicle_colors = {"V001": "blue", "V002": "red"}

with open("output/refined.json", "r", encoding="utf-8") as f:
    data = json.load(f)

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r

def get_round1_end_times_from_refined():
    result = {}
    for vehicle in data["round1"]["vehicles"]:
        vid = vehicle["id"]
        if vehicle["assigned_parcels"]:
            last = vehicle["assigned_parcels"][-1]
            t = datetime.strptime(last["arrival_time"], "%H:%M")
            base = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            result[vid] = base + timedelta(hours=t.hour, minutes=t.minute) + timedelta(minutes=30 + 90)
    return result

round2_start_times = get_round1_end_times_from_refined()

def query_graphhopper(lat1, lon1, lat2, lon2):
    params = {
        "point": [f"{lat1},{lon1}", f"{lat2},{lon2}"],
        "vehicle": "car",
        "locale": "zh_TW",
        "calc_points": "true",
        "key": GRAPH_KEY
    }
    retry = 0
    while retry < 5:
        try:
            time.sleep(random.uniform(6.0, 10.0))
            resp = requests.get(GRAPH_URL, params=params, timeout=40)
            resp.raise_for_status()
            route = resp.json()["paths"][0]
            return route["distance"] / 1000, route["time"] / 1000 / 60, polyline.decode(route["points"])
        except Exception as e:
            retry += 1
            print(f"⚠️ 第 {retry} 次查詢失敗，重試中...：{e}")
            if retry == 5:
                raise

def plot_vehicle_route(vehicle, vehicle_id, parcels, round_tag, m, excel_rows):
    remaining = parcels[:]
    sorted_parcels = []
    curr_lat, curr_lon = DEPOT_LAT, DEPOT_LON
    while remaining:
        nearest = min(remaining, key=lambda p: haversine(curr_lon, curr_lat, p["lon"], p["lat"]))
        sorted_parcels.append(nearest)
        curr_lat, curr_lon = nearest["lat"], nearest["lon"]
        remaining.remove(nearest)

    parcels = sorted_parcels
    route_coords = [[DEPOT_LAT, DEPOT_LON]]
    stop_seq = 1
    total_distance_km = 0
    total_duration_min = 0
    total_weight = 0
    total_volume = 0

    if round_tag == "round1":
        start_time = datetime.strptime("08:00", "%H:%M")
    else:
        start_time = round2_start_times.get(vehicle_id, datetime.strptime("13:00", "%H:%M"))

    print(f"⏱️ {round_tag} {vehicle_id} 起始時間：{start_time.strftime('%H:%M')}")
    time_cursor = start_time

    for p in parcels:
        try:
            distance_km, duration_min, segment_coords = query_graphhopper(route_coords[-1][0], route_coords[-1][1], p["lat"], p["lon"])
        except Exception as e:
            msg = f"⛔ {round_tag} {vehicle_id} → {p['id']} 查詢失敗：{str(e)}"
            print(msg)
            error_log.append(msg)
            continue

        arrival_time = time_cursor + timedelta(minutes=duration_min)
        print(f"🔄 {round_tag} 查詢 {vehicle_id} → {p['id']}，抵達時間：{arrival_time.strftime('%H:%M')} (含運送時間 {round(duration_min,1)} 分鐘)")

        popup = (
            f"<b>{round_tag} 車輛: {vehicle_id}</b><br>"
            f"順序: {stop_seq}<br>"
            f"包裹編號: {p['id']}<br>"
            f"抵達時間: {arrival_time.strftime('%H:%M')}<br>"
            f"重量: {p['weight']} kg<br>"
            f"體積: {p['volume']} m³"
        )
        folium.Marker(
            [p["lat"], p["lon"]],
            icon=folium.DivIcon(html=f"<div style='font-size: 10pt; color: white; background: {vehicle_colors[vehicle_id]}; border-radius: 50%; width: 24px; height: 24px; text-align: center;'>{stop_seq}</div>"),
            popup=popup
        ).add_to(m)

        excel_rows.append({
            "round": round_tag,
            "車輛": vehicle_id,
            "順序": stop_seq,
            "包裹編號": p["id"],
            "抵達時間": arrival_time.strftime("%H:%M"),
            "重量 (kg)": p["weight"],
            "體積 (m³)": p["volume"],
            "座標 (lat, lon)": f"{p['lat']}, {p['lon']}",
            "路段距離 (km)": round(distance_km, 2),
            "路段時間 (min)": round(duration_min, 1),
            "平均時速 (km/h)": round(distance_km / duration_min * 60, 1)
        })

        time_cursor = arrival_time + timedelta(minutes=5)
        route_coords.extend(segment_coords)
        total_distance_km += distance_km
        total_duration_min += duration_min
        total_weight += p["weight"]
        total_volume += p["volume"]
        stop_seq += 1

    try:
        distance_km, duration_min, segment_coords = query_graphhopper(route_coords[-1][0], route_coords[-1][1], DEPOT_LAT, DEPOT_LON)
        route_coords.extend(segment_coords)
        excel_rows.append({
            "round": round_tag,
            "車輛": vehicle_id,
            "順序": "回程",
            "包裹編號": "-",
            "抵達時間": (time_cursor + timedelta(minutes=duration_min)).strftime("%H:%M"),
            "重量 (kg)": "-",
            "體積 (m³)": "-",
            "座標 (lat, lon)": f"{DEPOT_LAT}, {DEPOT_LON}",
            "路段距離 (km)": round(distance_km, 2),
            "路段時間 (min)": round(duration_min, 1),
            "平均時速 (km/h)": round(distance_km / duration_min * 60, 1),
            "回艙總里程 (km)": round(total_distance_km + distance_km, 2),
            "總耗時 (min)": round(total_duration_min + duration_min, 1),
            "總重量 (kg)": round(total_weight, 2),
            "總體積 (m³)": round(total_volume, 2)
        })
    except Exception as e:
        msg = f"⚠️ {round_tag} {vehicle_id} 回程段失敗：{str(e)}"
        print(msg)
        error_log.append(msg)

    folium.PolyLine(route_coords, color=vehicle_colors[vehicle_id], weight=5, opacity=0.8).add_to(m)

m1 = folium.Map(location=[DEPOT_LAT, DEPOT_LON], zoom_start=12)
folium.Marker([DEPOT_LAT, DEPOT_LON], icon=folium.Icon(color="green"), popup="起點/終點").add_to(m1)
excel_rows = []
for vehicle in data["round1"]["vehicles"]:
    plot_vehicle_route(vehicle, vehicle["id"], vehicle["assigned_parcels"], "round1", m1, excel_rows)
m1.save("output/vehicles_realroute_eta_map_round1.html")

m2 = folium.Map(location=[DEPOT_LAT, DEPOT_LON], zoom_start=12)
folium.Marker([DEPOT_LAT, DEPOT_LON], icon=folium.Icon(color="green"), popup="起點/終點").add_to(m2)
for vehicle in data["round2"]["vehicles"]:
    plot_vehicle_route(vehicle, vehicle["id"], vehicle["assigned_parcels"], "round2", m2, excel_rows)
m2.save("output/vehicles_realroute_eta_map_round2.html")

pd.DataFrame(excel_rows).to_excel("output/vehicles_eta_detail_combined.xlsx", index=False)
if error_log:
    with open("output/error_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(error_log))
    print(f"⚠️ 共 {len(error_log)} 筆查詢失敗，詳見 output/error_log.txt")
print("✅ round1、round2 地圖與整併 Excel 已完成輸出")
