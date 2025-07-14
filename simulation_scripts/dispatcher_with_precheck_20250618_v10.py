import json
import math
import requests
import time
import random
import os
import pandas as pd

ORS_API_KEY = "5b3ce3597851110001cf624833dd6c06156e46888a0ff84ee6e7df1c"
DEPOT_LAT, DEPOT_LON = 24.1469, 120.6839
ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
HEADERS = {"Authorization": ORS_API_KEY}
LOAD_UNLOAD_MIN = 5
START_TIME_MIN = 8 * 60
END_TIME_MIN = 17 * 60

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def greedy_round_alternate(parcels, vehicles, round_tag="round1"):
    discarded_parcels = []
    waiting_parcels = []

    for v in vehicles:
        v["assigned_parcels"] = []
        v["used_volume"] = 0
        v["route"] = [[DEPOT_LAT, DEPOT_LON]]
        if round_tag == "round1":
            v["current_time_min"] = START_TIME_MIN
        v["curr_lat"], v["curr_lon"] = DEPOT_LAT, DEPOT_LON

    vehicle_index = 0

    for idx, p in enumerate(parcels):
        v = vehicles[vehicle_index % len(vehicles)]
        vehicle_index += 1

        print(f"[{round_tag}] [{idx+1}/{len(parcels)}] 嘗試包裹 {p['id']} → 車輛 {v['id']}：體積 {p['volume']}，已用 {v['used_volume']} / {v['max_volume']}")

        coords = [[v["curr_lon"], v["curr_lat"]], [p["lon"], p["lat"]]]
        try:
            resp = requests.post(ORS_URL, headers=HEADERS, json={"coordinates": coords, "units": "m"})
            resp.raise_for_status()
            data = resp.json()
            travel_min = data["routes"][0]["summary"]["duration"] / 60
        except Exception as e:
            print(f"❌ {p['id']} → 車輛 {v['id']}：無法查詢路線，列入待處理。錯誤: {e}")
            waiting_parcels.append(p)
            continue

        

        if v["used_volume"] + p["volume"] > v["max_volume"]:
            print(f"  🚫 空間不足，改列入丟棄。")
            discarded_parcels.append(p)
            continue

        coords_back = [[p["lon"], p["lat"]], [DEPOT_LON, DEPOT_LAT]]
        try:
            resp_back = requests.post(ORS_URL, headers=HEADERS, json={"coordinates": coords_back, "units": "m"})
            resp_back.raise_for_status()
            duration_back_min = resp_back.json()["routes"][0]["summary"]["duration"] / 60
        except Exception as e:
            print(f"❌ 回程路線無法查詢 → 車輛 {v['id']}，列入待處理。錯誤: {e}")
            waiting_parcels.append(p)
            continue

        total_time_if_deliver = v["current_time_min"] + travel_min + duration_back_min
        if total_time_if_deliver > END_TIME_MIN:
            print(f"  🕒 時間不夠 → 嘗試交由其他車輛補位...")

            if round_tag == "round2":
                other_vehicle = [veh for veh in vehicles if veh["id"] != v["id"]][0]
                if other_vehicle["used_volume"] + p["volume"] <= other_vehicle["max_volume"]:
                    coords_1 = [[other_vehicle["curr_lon"], other_vehicle["curr_lat"]], [p["lon"], p["lat"]]]
                    coords_2 = [[p["lon"], p["lat"]], [DEPOT_LON, DEPOT_LAT]]
                    try:
                        r1 = requests.post(ORS_URL, headers=HEADERS, json={"coordinates": coords_1, "units": "m"})
                        r2 = requests.post(ORS_URL, headers=HEADERS, json={"coordinates": coords_2, "units": "m"})
                        r1.raise_for_status()
                        r2.raise_for_status()
                        t1 = r1.json()["routes"][0]["summary"]["duration"] / 60
                        t2 = r2.json()["routes"][0]["summary"]["duration"] / 60
                        total_other = other_vehicle["current_time_min"] + t1 + LOAD_UNLOAD_MIN + t2

                        if total_other <= END_TIME_MIN:
                            print(f"  🔁 改交由 {other_vehicle['id']} 補送")
                            other_vehicle["assigned_parcels"].append(p)
                            other_vehicle["used_volume"] += p["volume"]
                            other_vehicle["current_time_min"] += t1 + LOAD_UNLOAD_MIN
                            other_vehicle["curr_lat"], other_vehicle["curr_lon"] = p["lat"], p["lon"]
                            other_vehicle["route"].append([p["lat"], p["lon"]])
                            v["assigned_parcels"] = [x for x in v["assigned_parcels"] if x["id"] != p["id"]]
                            time.sleep(random.uniform(2, 4))
                            continue
                        else:
                            print(f"  ⛔ 補位後仍超時，丟棄")
                    except Exception as e:
                        print(f"  ⚠️ 補位查詢錯誤：{e}")
                else:
                    print(f"  🚫 補位車輛空間不足")

            discarded_parcels.append(p)
            continue

        # === 計算抵達時間與回程時間，檢查是否能在 17:00 回倉 ===
        # === 計算抵達時間與回程時間，檢查是否能在 17:00 回倉 ===
        arrival_time_min = v["current_time_min"] + travel_min
        try:
            resp_back = requests.post(ORS_URL, headers=HEADERS, json={"coordinates": [[p["lon"], p["lat"]], [DEPOT_LON, DEPOT_LAT]], "units": "m"})
            resp_back.raise_for_status()
            duration_back_min = resp_back.json()["routes"][0]["summary"]["duration"] / 60
        except Exception as e:
            print(f"❌ 回程路線查詢失敗，包裹 {p['id']}：{e}")
            waiting_parcels.append(p)
            continue

        total_mission_time = arrival_time_min + LOAD_UNLOAD_MIN + duration_back_min
        arrival_str = f"{int(arrival_time_min // 60):02d}:{int(arrival_time_min % 60):02d}"
        back_str = f"{int((arrival_time_min + LOAD_UNLOAD_MIN + duration_back_min) // 60):02d}:{int((arrival_time_min + LOAD_UNLOAD_MIN + duration_back_min) % 60):02d}"
        print(f"⏱️ 包裹 {p['id']} 抵達時間：{arrival_str}，預估回倉時間：{back_str}")

        if round_tag == "round2" and total_mission_time > END_TIME_MIN:
            print(f"  ⛔ Round2 包裹 {p['id']} 任務超過 17:00，丟棄")
            discarded_parcels.append(p)
            continue

        # 寫入抵達時間
        p["arrival_time"] = arrival_str
        v["assigned_parcels"].append(p)
        v["used_volume"] += p["volume"]
        v["current_time_min"] = arrival_time_min + LOAD_UNLOAD_MIN
        v["curr_lat"], v["curr_lon"] = p["lat"], p["lon"]
        v["route"].append([p["lat"], p["lon"]])
        print(f"  ✅ 已成功分配給車輛 {v['id']}。")

        time.sleep(random.uniform(2, 4))

    for v in vehicles:
        v["route"].append([DEPOT_LAT, DEPOT_LON])

    return {
        "vehicles": vehicles,
        "discarded_parcels": discarded_parcels,
        "waiting_parcels": waiting_parcels
    }

with open("data/parcels_with_real_coords_updated_full.json", "r", encoding="utf-8") as f:
    all_parcels = json.load(f)
with open("data/vehicles.json", "r", encoding="utf-8") as f:
    vehicles_template = json.load(f)

for p in all_parcels:
    p["distance_to_depot"] = haversine(DEPOT_LAT, DEPOT_LON, p["lat"], p["lon"])
all_parcels = sorted(all_parcels, key=lambda x: x["distance_to_depot"])

vehicles_round1 = json.loads(json.dumps(vehicles_template))
result_round1 = greedy_round_alternate(all_parcels, vehicles_round1, round_tag="round1")

if result_round1["discarded_parcels"]:
    print("\n🚀 開始第二輪配送（針對第一輪被捨棄的包裹，交替分配）")
    for p in result_round1["discarded_parcels"]:
        p["distance_to_depot"] = haversine(DEPOT_LAT, DEPOT_LON, p["lat"], p["lon"])
    discarded_parcels = sorted(result_round1["discarded_parcels"], key=lambda x: x["distance_to_depot"])
    vehicles_round2 = json.loads(json.dumps(vehicles_template))
    # ✅ 加入 Round1 回艙後休息 90 分鐘邏輯
    for v1, v2 in zip(result_round1["vehicles"], vehicles_round2):
        v2["current_time_min"] = v1["current_time_min"] + 90
        v2["curr_lat"] = DEPOT_LAT
        v2["curr_lon"] = DEPOT_LON

    result_round2 = greedy_round_alternate(discarded_parcels, vehicles_round2, round_tag="round2")
else:
    result_round2 = {"vehicles": [], "discarded_parcels": [], "waiting_parcels": []}

output = {
    "round1": result_round1,
    "round2": result_round2
}
os.makedirs("output", exist_ok=True)
with open("output/refined.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n✅ refined.json 已輸出完成。")

all_assigned_ids = []
for round_key in ["round1", "round2"]:
    for v in output[round_key]["vehicles"]:
        all_assigned_ids.extend([p["id"] for p in v["assigned_parcels"]])

expected_ids = [f"P{i:03d}" for i in range(1, 51)]
missing_ids = [pid for pid in expected_ids if pid not in all_assigned_ids]

if missing_ids:
    print(f"❗ 共 {len(missing_ids)} 件包裹未成功配送：{missing_ids}")
    df_missing = pd.DataFrame([{"missing_id": pid} for pid in missing_ids])
    df_missing.to_excel("output/missing_parcels.xlsx", index=False)
    print("📤 已匯出 missing_parcels.xlsx")
else:
    print("🎉 所有 50 件包裹皆已成功送達！")
