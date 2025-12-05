from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python3.9 以降
import csv
import os


app = Flask(__name__)

# このファイル(app.py)がある場所
BASE_DIR = os.path.dirname(__file__)

def load_timetable(filename: str):
    """
    data/ 以下の CSV から
    [{"departure": "07:00", "arrival": "07:12"}, ...] を作って返す
    """
    path = os.path.join(BASE_DIR, "data", filename)
    trains = []
    # Excel 由来の BOM 対応で utf-8-sig にしてある
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trains.append({
                "departure": row["departure"],
                "arrival": row["arrival"],
            })
    return trains

# ==========
# 時刻表データ
# ==========

TIMETABLE = {
    "ichigaya_tameike": {
        "from": "市ヶ谷",
        "to": "溜池山王",
        "line": "有楽町線→南北線",
        "trains": load_timetable("ichigaya_tameike.csv"),
    },
    "tameike_shimbashi": {
        "from": "溜池山王",
        "to": "新橋",
        "line": "銀座線",
        "trains": load_timetable("tameike_shimbashi.csv"),
    },
    "shimbashi_kamakura": {
        "from": "新橋",
        "to": "鎌倉",
        "line": "横須賀線",
        "trains": load_timetable("shimbashi_kamakura.csv"),
    },
}


# 乗り換えにかかる平均時間（分）
TRANSFER_MINUTES = {
    "溜池山王": 5,
    "新橋": 7,
}

# ==========
# ユーティリティ
# ==========

def parse_hhmm_to_minutes(hhmm: str) -> int:
    """'HH:MM' を 00:00 からの分数に変換"""
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m

def minutes_to_hhmm(minutes: int) -> str:
    """00:00 からの分数を 'HH:MM' に変換（24h を超えない前提）"""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def find_next_train(trains, earliest_departure_min):
    """
    trains: [{"departure": "07:00", "arrival": "07:12"}, ...]
    earliest_departure_min: この分数以降で乗れる電車を探す
    """
    candidate = None
    candidate_dep_min = None

    for t in trains:
        dep_min = parse_hhmm_to_minutes(t["departure"])
        if dep_min >= earliest_departure_min:
            if candidate is None or dep_min < candidate_dep_min:
                candidate = t
                candidate_dep_min = dep_min

    return candidate


# ==========
# API エンドポイント
# ==========

@app.route("/")
def index():
    # templates/index.html を返す
    return render_template("index.html")


# デバッグ用：CSV の中身をそのまま返す
@app.route("/api/debug/ichigaya")
def debug_ichigaya():
    trains = load_timetable("ichigaya_tameike.csv")
    return jsonify(trains)


# 本番用：ルート検索API
@app.route("/api/routes", methods=["GET"])
def api_routes():
    # クエリパラメータ max_offset（分）
    try:
        max_offset = int(request.args.get("max_offset", 30))
    except ValueError:
        max_offset = 3

    if max_offset < 0:
        max_offset = 0
    if max_offset > 60:
        max_offset = 60

    # 現在時刻（JST）
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
    search_time_jst_str = now_jst.strftime("%Y-%m-%d %H:%M:%S")


    # 「出発基準時刻」は「今」
    departure_base = now_jst
    departure_base_str = departure_base.strftime("%Y-%m-%d %H:%M:%S")

    # この時刻までに市ヶ谷を出る電車を候補にする
    latest_departure = departure_base + timedelta(minutes=max_offset)

    # 同じ日の 00:00 からの分数に変換して比較する（簡略化）
    base_minutes = departure_base.hour * 60 + departure_base.minute
    latest_minutes = latest_departure.hour * 60 + latest_departure.minute

    routes = []

    # 1本目：市ヶ谷→溜池山王
    first_leg = TIMETABLE["ichigaya_tameike"]
    second_leg = TIMETABLE["tameike_shimbashi"]
    third_leg = TIMETABLE["shimbashi_kamakura"]

    for t1 in first_leg["trains"]:
        dep1_min = parse_hhmm_to_minutes(t1["departure"])

        # 今〜今+max_offset分の範囲だけ見る
        if dep1_min < base_minutes or dep1_min > latest_minutes:
            continue

        arr1_min = parse_hhmm_to_minutes(t1["arrival"])

        # 溜池山王での乗り換え時間を足す
        earliest_dep2_min = arr1_min + TRANSFER_MINUTES["溜池山王"]

        t2 = find_next_train(second_leg["trains"], earliest_dep2_min)
        if t2 is None:
            continue  # 2本目が見つからない

        dep2_min = parse_hhmm_to_minutes(t2["departure"])
        arr2_min = parse_hhmm_to_minutes(t2["arrival"])

        # 新橋での乗り換え時間
        earliest_dep3_min = arr2_min + TRANSFER_MINUTES["新橋"]
        t3 = find_next_train(third_leg["trains"], earliest_dep3_min)
        if t3 is None:
            continue  # 3本目が見つからない

        dep3_min = parse_hhmm_to_minutes(t3["departure"])
        arr3_min = parse_hhmm_to_minutes(t3["arrival"])

        # ルート全体の情報を作る
        total_duration_min = arr3_min - dep1_min
        total_duration_str = f"{total_duration_min}分"

        # 料金はとりあえずダミー
        fare_str = "（料金未設定）"

        route = {
            "departure_time": minutes_to_hhmm(dep1_min),
            "arrival_time": minutes_to_hhmm(arr3_min),
            "total_duration": total_duration_str,
            "fare": fare_str,
            "transfers": [
                {
                    "from": first_leg["from"],
                    "to": first_leg["to"],
                    "line": first_leg["line"],
                    "departure": t1["departure"],
                    "arrival": t1["arrival"],
                },
                {
                    "from": second_leg["from"],
                    "to": second_leg["to"],
                    "line": second_leg["line"],
                    "departure": t2["departure"],
                    "arrival": t2["arrival"],
                },
                {
                    "from": third_leg["from"],
                    "to": third_leg["to"],
                    "line": third_leg["line"],
                    "departure": t3["departure"],
                    "arrival": t3["arrival"],
                },
            ],
        }

        routes.append(route)

    # 出発時刻の早い順に並べ替え
    routes.sort(key=lambda r: r["departure_time"])

    return jsonify({
        "search_time_jst": search_time_jst_str,
        "departure_base_jst": departure_base_str,
        "max_offset_minutes": max_offset,
        "routes": routes
    })



if __name__ == "__main__":
    app.run(debug=True)
