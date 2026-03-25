import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

PAST_URL = "https://ca.lottonumbers.com/lotto-649/past-numbers"
YEAR_URLS = [
    "https://ca.lottonumbers.com/lotto-649/past-numbers/2026",
    "https://ca.lottonumbers.com/lotto-649/past-numbers/2025",
    "https://ca.lottonumbers.com/lotto-649/past-numbers/2024",
]

MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"


def fetch_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.get_text("\n", strip=True)


def normalize_gold_prize(raw: str) -> str:
    if not raw:
        return ""
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def parse_ca_lottonumbers_text(text: str):
    draws = []

    pattern = re.compile(
        rf"(Wednesday|Saturday)\s+{MONTHS}\s+(\d{{1,2}})\s+(20\d{{2}})"
        rf"(.*?)"
        rf"(?=(Wednesday|Saturday)\s+{MONTHS}\s+\d{{1,2}}\s+20\d{{2}}|$)",
        re.S,
    )

    for m in pattern.finditer(text):
        weekday = m.group(1)
        month = m.group(2)
        day = m.group(3)
        year = m.group(4)
        block = m.group(5)

        date = pd.to_datetime(f"{month} {day} {year}", errors="coerce")
        if pd.isna(date):
            continue

        # 抓號碼：呢個頁面每期通常先出 6 個主號碼，再出 1 個 bonus
        nums = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d)\b", block)]

        ordered = []
        for n in nums:
            if n not in ordered:
                ordered.append(n)

        if len(ordered) < 7:
            continue

        main = sorted(ordered[:6])
        bonus = ordered[6]

        # Gold Ball Number
        gold_ball_number = ""
        gm = re.search(r"Gold Ball Number:\s*([0-9]{8,10}(?:-[0-9]{2})?)", block, re.I | re.S)
        if gm:
            gold_ball_number = gm.group(1).strip()

        # Gold Prize / Jackpot 字樣
        # 例如: "$5 Million", "$60 Million", "$1 Million"
        gold_prize_type = ""
        pm = re.search(r"(\$\d+(?:\.\d+)?\s*(?:Million|Thousand))", block, re.I)
        if pm:
            gold_prize_type = normalize_gold_prize(pm.group(1))

        # 如果想分清楚 jackpot 類型，可加少少描述
        gold_result = " | ".join([x for x in [gold_prize_type, gold_ball_number] if x])

        draws.append({
            "date": date.strftime("%Y-%m-%d"),
            "n1": main[0],
            "n2": main[1],
            "n3": main[2],
            "n4": main[3],
            "n5": main[4],
            "n6": main[5],
            "bonus": bonus,
            "gold_ball_number": gold_ball_number,
            "gold_prize_type": gold_prize_type,
            "gold_result": gold_result,
        })

    return draws


def scrape_real_649_data():
    all_draws = []

    print("🚀 啟動 Lotto 6/49 爬蟲...")

    urls = [PAST_URL] + YEAR_URLS

    for url in urls:
        print(f"📡 抓取: {url}")
        try:
            text = fetch_text(url)
            draws = parse_ca_lottonumbers_text(text)
            all_draws.extend(draws)
            print(f"   ✅ 抽到 {len(draws)} 期")
        except Exception as e:
            print(f"   ⚠️ 失敗: {e}")

    df = pd.DataFrame(all_draws)
    if df.empty:
        return pd.DataFrame()

    df["date_obj"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_obj"])
    df = df.sort_values("date_obj").drop_duplicates(subset=["date"], keep="first")

    for col in ["gold_ball_number", "gold_prize_type", "gold_result"]:
        if col not in df.columns:
            df[col] = ""

    return df


def calculate_metrics(df):
    if df.empty:
        return df

    prev_numbers = set()
    results = []

    for _, row in df.sort_values("date_obj").iterrows():
        record = row.to_dict()
        nums = [int(record[f"n{i}"]) for i in range(1, 7)]

        odd_count = sum(1 for n in nums if n % 2 != 0)
        even_count = sum(1 for n in nums if n % 2 == 0)
        record["odd_even"] = f"{odd_count}單 {even_count}雙"

        sorted_nums = sorted(nums)
        record["consecutive"] = "Yes" if any(sorted_nums[i + 1] - sorted_nums[i] == 1 for i in range(5)) else "No"

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
        "gold_ball_number",
        "gold_prize_type",
        "gold_result",
        "odd_even",
        "consecutive",
        "repeats",
        "zone"
    ]

    for c in cols:
        if c not in final_df.columns:
            final_df[c] = ""

    final_df[cols].to_csv("data.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 成功寫入 {len(final_df)} 期數據到 data.csv")


if __name__ == "__main__":
    main()
