import re
import csv
from pathlib import Path

# 生テキストファイル
RAW_PATH = Path("shimbashi_raw.txt")

# 出力する CSV ファイル（data フォルダに作る）
OUT_PATH = Path("data") / "shimbashi_kamakura.csv"
OUT_PATH.parent.mkdir(exist_ok=True)

text = RAW_PATH.read_text(encoding="utf-8")

# 「HH:MM発  HH:MM着」だけ全部抜き出す
pairs = re.findall(r"(\d{2}:\d{2})発\s+(\d{2}:\d{2})着", text)

print("抽出できた本数:", len(pairs))

with OUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["departure", "arrival"])
    writer.writerows(pairs)

print("書き出し完了:", OUT_PATH)
