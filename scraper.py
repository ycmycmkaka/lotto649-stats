import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}

LOTTOMAX_URLS = [
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2026",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2025",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2024",
]

OLG_URL = "https://www.olg.ca/en/lottery/play-lotto-649-encore/past-results.html"


def fetch_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.get_text("\n", strip=True)


def parse_lottomax_text(text: str):
    draws = []

    pattern = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})\s+(20\d{2})"
        r"(.*?)"
        r"(?=(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\s+20\d{2}|$)",
        re.S
    )

    for m in pattern.finditer(text):
        month, day, year, block = m.group(1), m.group(2), m.group(3), m.group(4)

        nums = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d)\b", block)]

        ordered = []
        for n in nums:
            if n not in ordered:
                ordered.append(n)

        if len(ordered) >= 7:
            main = sorted(ordered[:6])
            bonus = ordered[6]
            date = pd.to_datetime(f"{month} {day} {year}", errors="coerce")
            if pd.notna(date):
                draws.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "n1": main[0],
                    "n2": main[1],
                    "n3": main[2],
                    "n4": main[3],
                    "n5": main[4],
                    "n6": main[5],
                    "bonus": bonus,
                    "classic_result": f"{main[0]} - {main[1]} - {main[2]} - {main[3]} - {main[4]} - {main[5]} | Bonus {bonus}"
                })

    return draws


def parse_olg_goldball(text: str):
    gold_map = {}

    # 按日期分 block
    blocks = re.split(
        r"(?=(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2})",
        text
    )

    rebuilt = []
    i = 0
    while i < len(blocks):
        if i + 2 < len(blocks) and re.fullmatch(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)",
            str(blocks[i + 1] or "")
        ):
            rebuilt.append(blocks[i + 1] + blocks[i + 2])
            i += 3
        else:
            i += 1

    for block in rebuilt:
        dm = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d{2})",
            block
        )
        if not dm:
            continue

        date = pd.to_datetime(f"{dm.group(1)} {dm.group(2)} {dm.group(3)}", errors="coerce")
        if pd.isna(date):
            continue

        date_key = date.strftime("%Y-%m-%d")

        # 抽 Gold Ball prize type
        prize_type = ""
        if re.search(r"GOLD BALL\.\s*\$1 Million", block, re.I):
            prize_type = "$1 Million"
        elif re.search(r"GOLD BALL.*Jackpot", block, re.I):
            prize_type = "Gold Ball Jackpot"

        # 抽 10 位 winning number
        gm = re.search(r"GOLD BALL\..*?([0-9]{8,10}(?:-[0-9]{2})?)", block, re.I | re.S)
        gold_number = gm.group(1) if gm else ""

        gold_map[date_key] = {
            "gold_ball_number": gold_number,
            "gold_prize_type": prize_type,
            "gold_result": f"{prize_type} | {gold_number}".strip(" |")
        }

    return gold_map


def scrape_real_649_data():
    all_draws = []

    print("🚀 啟動 Lotto 6/49 爬蟲...")

    for url in LOTTOMAX_URLS:
        print(f"📡 抓取 Classic/Bonus: {url}")
        try:
            text = fetch_text(url)
            draws = parse_lottomax_text(text)
            all_draws.extend(draws)
            print(f"   ✅ 抽到 {len(draws)} 期")
        except Exception as e:
            print(f"   ⚠️ 失敗: {e}")

    df = pd.DataFrame(all_draws)
    if df.empty:
        return pd.DataFrame()

    df["date_obj"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_obj"])
    df = df.sort_values("date_obj").drop_duplicates(subset=["date"], keep="last")

    df["gold_ball_number"] = ""
    df["gold_prize_type"] = ""
    df["gold_result"] = ""

    try:
        print(f"📡 抓取 Gold Ball: {OLG_URL}")
        olg_text = fetch_text(OLG_URL)
        gold_map = parse_olg_goldball(olg_text)

        df["gold_ball_number"] = df["date"].map(lambda d: gold_map.get(d, {}).get("gold_ball_number", ""))
        df["gold_prize_type"] = df["date"].map(lambda d: gold_map.get(d, {}).get("gold_prize_type", ""))
        df["gold_result"] = df["date"].map(lambda d: gold_map.get(d, {}).get("gold_result", ""))
    except Exception as e:
        print(f"   ⚠️ Gold Ball 抽取失敗: {e}")

    return df


def calculate_metrics(df):
    if df.empty:
        return df

    prev_numbers = set()
    results = []

    for _, row in df.iterrows():
        record = row.to_dict()
        nums = [int(record[f"n{i}"]) for i in range(1, 7)]

        record["odd_even"] = f"{sum(1 for n in nums if n % 2 != 0)}單 {sum(1 for n in nums if n % 2 == 0)}雙"
        record["consecutive"] = "Yes" if any(sorted(nums)[i + 1] - sorted(nums)[i] == 1 for i in range(5)) else "No"

        curr_set = set(nums)
        record["repeats"] = len(curr_set.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = curr_set

        zones = sorted(set((n - 1) // 10 + 1 for n in nums))
        record["zone"] = f"{len(zones)}個區 ({','.join(map(str, zones))})"

        results.append(record)

    final_df = pd.DataFrame(results).sort_values("date_obj", ascending=False)
    final_df["date"] = final_df["date_obj"].dt.strftime("%Y-%m-%d")
    return final_df


def main():
    raw_df = scrape_real_649_data()

    if raw_df.empty:
        print("❌ 抽唔到任何資料")
        raise SystemExit(1)

    final_df = calculate_metrics(raw_df)

    cols = [
        "date",
        "n1", "n2", "n3", "n4", "n5", "n6",
        "bonus",
        "classic_result",
        "gold_ball_number",
        "gold_prize_type",
        "gold_result",
        "odd_even", "consecutive", "repeats", "zone"
    ]

    for c in cols:
        if c not in final_df.columns:
            final_df[c] = ""

    final_df[cols].to_csv("data.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 成功寫入 {len(final_df)} 期數據到 data.csv")


if __name__ == "__main__":
    main()
