import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

URLS = [
    "https://www.lottomaxnumbers.com/lotto-649/past-numbers",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2026",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2025",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2024"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_date(text: str):
    text = clean_text(text)

    patterns = [
        (r"\b\d{4}-\d{2}-\d{2}\b", "%Y-%m-%d"),
        (r"\b\d{2}/\d{2}/\d{4}\b", "%d/%m/%Y"),
        (r"\b[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}\b", "%B %d, %Y"),
        (r"\b[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b", "%b %d, %Y"),
        (r"\b\d{1,2}\s+[A-Z][a-z]{2,9}\s+\d{4}\b", "%d %B %Y"),
        (r"\b\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\b", "%d %b %Y"),
    ]

    for pattern, fmt in patterns:
        m = re.search(pattern, text)
        if m:
            raw = m.group(0)
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%Y-%m-%d"), raw
            except ValueError:
                continue

    return None, None


def extract_labeled_number(text: str, labels):
    for label in labels:
        pattern = rf"(?i)\b{label}\b[^0-9]{{0,20}}(\d{{1,2}})"
        m = re.search(pattern, text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 99:
                return n
    return None


def extract_main_bonus_gold(text: str, date_raw: str = None):
    working = text

    if date_raw:
        working = working.replace(date_raw, " ")

    # 移除年份，避免 2026 呢啲污染
    working = re.sub(r"\b20\d{2}\b", " ", working)

    # 先試圖搵 label
    white_ball = extract_labeled_number(
        working,
        ["white", "bonus", "bonus ball", "extra", "complementary"]
    )

    gold_ball = extract_labeled_number(
        working,
        ["gold", "gold ball", "g"]
    )

    # 抽所有 1-99 數字
    raw_nums = [int(x) for x in re.findall(r"\b\d{1,2}\b", working) if 1 <= int(x) <= 99]

    # 去重，但保留次序
    ordered_unique = []
    for n in raw_nums:
        if n not in ordered_unique:
            ordered_unique.append(n)

    if len(ordered_unique) < 6:
        return None

    main_balls = ordered_unique[:6]

    # 如果 label 搵唔到，就用第 7 / 8 個數估
    if white_ball is None and len(ordered_unique) >= 7:
        white_ball = ordered_unique[6]

    if gold_ball is None and len(ordered_unique) >= 8:
        gold_ball = ordered_unique[7]

    return {
        "main": sorted(main_balls),
        "white": white_ball,
        "gold": gold_ball
    }


def build_result_text(main, white_ball=None, gold_ball=None):
    parts = [" - ".join(str(n) for n in main)]
    if white_ball is not None:
        parts.append(f"White {white_ball}")
    if gold_ball is not None:
        parts.append(f"Gold {gold_ball}")
    return " | ".join(parts)


def scrape_real_649_data():
    all_draws = []

    print("🚀 啟動 Lotto 6/49 爬蟲...")

    for url in URLS:
        print(f"📡 抓取: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"⚠️ HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            candidates = []
            candidates.extend(soup.find_all("tr"))
            candidates.extend(soup.find_all("article"))
            candidates.extend(soup.find_all("section"))
            candidates.extend(soup.find_all("div"))

            seen_text = set()

            for node in candidates:
                row_text = clean_text(node.get_text(" ", strip=True))
                if not row_text or len(row_text) < 20:
                    continue
                if row_text in seen_text:
                    continue
                seen_text.add(row_text)

                clean_date, raw_date = parse_date(row_text)
                if not clean_date:
                    continue

                parsed = extract_main_bonus_gold(row_text, raw_date)
                if not parsed:
                    continue

                main_balls = parsed["main"]
                white_ball = parsed["white"]
                gold_ball = parsed["gold"]

                all_draws.append({
                    "date": clean_date,
                    "n1": main_balls[0],
                    "n2": main_balls[1],
                    "n3": main_balls[2],
                    "n4": main_balls[3],
                    "n5": main_balls[4],
                    "n6": main_balls[5],
                    "white": white_ball,
                    "gold": gold_ball,
                    "result": build_result_text(main_balls, white_ball, gold_ball),
                    "source_url": url
                })

        except Exception as e:
            print(f"⚠️ 抓取失敗: {e}")

    df = pd.DataFrame(all_draws)

    if df.empty:
        return pd.DataFrame()

    df["date_obj"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_obj"])
    df = df.drop_duplicates(subset=["date"]).sort_values("date_obj", ascending=True)

    return df


def calculate_metrics(df):
    if df.empty:
        return df

    prev_numbers = set()
    results = []

    for _, row in df.iterrows():
        record = row.to_dict()
        nums = [int(record[f"n{i}"]) for i in range(1, 7)]

        odd_count = sum(1 for n in nums if n % 2 != 0)
        even_count = sum(1 for n in nums if n % 2 == 0)
        record["odd_even"] = f"{odd_count}單 {even_count}雙"

        nums_sorted = sorted(nums)
        record["consecutive"] = "Yes" if any(nums_sorted[i + 1] - nums_sorted[i] == 1 for i in range(5)) else "No"

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
        "white", "gold", "result",
        "odd_even", "consecutive", "repeats", "zone",
        "source_url"
    ]

    for c in cols:
        if c not in final_df.columns:
            final_df[c] = ""

    final_df[cols].to_csv("data.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 成功寫入 {len(final_df)} 期數據到 data.csv")


if __name__ == "__main__":
    main()
