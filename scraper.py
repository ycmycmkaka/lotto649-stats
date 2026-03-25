import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://ca.lottonumbers.com"
LIST_URLS = [
    "https://ca.lottonumbers.com/lotto-649/past-numbers",
    "https://ca.lottonumbers.com/lotto-649/past-numbers/2026",
    "https://ca.lottonumbers.com/lotto-649/past-numbers/2025",
    "https://ca.lottonumbers.com/lotto-649/past-numbers/2024",
]

MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_text(url: str) -> str:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


def money_to_int(text: str) -> int:
    if not text:
        return 0
    text = text.replace(",", "").strip()
    m = re.search(r"\$([0-9]+)", text)
    return int(m.group(1)) if m else 0


def normalize_money(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace(" ,", ",")


def parse_listing_page(text: str):
    draws = []

    pattern = re.compile(
        rf"(Wednesday|Saturday)\s+{MONTHS}\s+(\d{{1,2}})\s+(20\d{{2}})"
        rf"(.*?)"
        rf"(?=(Wednesday|Saturday)\s+{MONTHS}\s+\d{{1,2}}\s+20\d{{2}}|$)",
        re.S
    )

    for m in pattern.finditer(text):
        month = m.group(2)
        day = m.group(3)
        year = m.group(4)
        block = m.group(5)

        date_obj = pd.to_datetime(f"{month} {day} {year}", errors="coerce")
        if pd.isna(date_obj):
            continue

        date = date_obj.strftime("%Y-%m-%d")

        nums = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d)\b", block)]

        ordered = []
        for n in nums:
            if n not in ordered:
                ordered.append(n)

        if len(ordered) < 7:
            continue

        main = ordered[:6]
        bonus = ordered[6]

        gold_ball_number = ""
        gm = re.search(r"Gold Ball Number:\s*([0-9]{8,10}(?:-[0-9]{2})?)", block, re.I)
        if gm:
            gold_ball_number = gm.group(1).strip()

        prize_link = ""
        lm = re.search(r"(\/lotto-649\/numbers\/\d{4}-\d{2}-\d{2})", block)
        if lm:
            prize_link = BASE_URL + lm.group(1)
        else:
            prize_link = f"{BASE_URL}/lotto-649/numbers/{date}"

        draws.append({
            "date": date,
            "n1": main[0],
            "n2": main[1],
            "n3": main[2],
            "n4": main[3],
            "n5": main[4],
            "n6": main[5],
            "bonus": bonus,
            "gold_ball_number": gold_ball_number,
            "detail_url": prize_link,
        })

    return draws


def parse_detail_page(text: str):
    result = {
        "classic_jackpot": "",
        "gold_prize_type": "",         # Gold Ball Jackpot amount, e.g. $14,000,000
        "gold_result": "",             # outcome summary
        "gold_next_jackpot": "",       # Next Gold Ball Jackpot
    }

    # Classic jackpot
    m = re.search(r"Jackpot:\s*\$([0-9,]+)", text, re.I)
    if m:
        result["classic_jackpot"] = f"${m.group(1)}"

    # Gold Ball jackpot shown in header
    gm = re.search(r"Gold Ball Jackpot:\s*\$([0-9,]+)", text, re.I)
    if gm:
        result["gold_prize_type"] = f"${gm.group(1)}"

    # Next Gold Ball jackpot
    nm = re.search(r"Next Gold Ball Jackpot\s*-\s*-\s*\$([0-9,]+)", text, re.I)
    if nm:
        result["gold_next_jackpot"] = f"${nm.group(1)}"

    # payout row for Gold Ball outcome
    # example:
    # Gold Ball Jackpot $1,000,000  1 $1,000,000
    # or if jackpot won, prize could equal the header jackpot
    payout = re.search(
        r"Gold Ball Jackpot\s+\$([0-9,]+)\s+([0-9,]+)\s+\$([0-9,]+)",
        text,
        re.I
    )

    if payout:
        payout_prize = f"${payout.group(1)}"
        winners = payout.group(2).replace(",", "")
        payout_fund = f"${payout.group(3)}"

        header_val = money_to_int(result["gold_prize_type"])
        payout_val = money_to_int(payout_prize)

        if winners != "0":
            if header_val and payout_val == header_val:
                result["gold_result"] = f"Gold Ball Jackpot won ({winners} winner)"
            elif payout_val == 1000000:
                result["gold_result"] = f"White Ball $1 Million ({winners} winner)"
            else:
                result["gold_result"] = f"Gold Ball payout {payout_prize} ({winners} winner)"
        else:
            result["gold_result"] = "No Gold Ball winner"

        if result["gold_next_jackpot"]:
            result["gold_result"] += f" | Next {result['gold_next_jackpot']}"

    return result


def scrape_real_649_data():
    all_draws = []

    print("🚀 啟動 Lotto 6/49 爬蟲...")

    # Step 1: 抓主列表
    for url in LIST_URLS:
        print(f"📡 抓主列表: {url}")
        try:
            text = fetch_text(url)
            draws = parse_listing_page(text)
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

    # 預設欄位
    df["classic_jackpot"] = ""
    df["gold_prize_type"] = ""
    df["gold_result"] = ""
    df["gold_next_jackpot"] = ""

    # Step 2: 逐期入 details page 補 Gold Ball 真資料
    for idx, row in df.iterrows():
        url = row["detail_url"]
        print(f"🔎 詳情頁: {row['date']} -> {url}")

        try:
            text = fetch_text(url)
            detail = parse_detail_page(text)

            df.at[idx, "classic_jackpot"] = detail["classic_jackpot"]
            df.at[idx, "gold_prize_type"] = detail["gold_prize_type"]
            df.at[idx, "gold_result"] = detail["gold_result"]
            df.at[idx, "gold_next_jackpot"] = detail["gold_next_jackpot"]

            time.sleep(0.5)
        except Exception as e:
            print(f"   ⚠️ 詳情頁失敗: {e}")

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
        "classic_jackpot",
        "gold_prize_type",
        "gold_result",
        "gold_next_jackpot",
        "odd_even",
        "consecutive",
        "repeats",
        "zone",
    ]

    for c in cols:
        if c not in final_df.columns:
            final_df[c] = ""

    final_df[cols].to_csv("data.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 成功寫入 {len(final_df)} 期數據到 data.csv")


if __name__ == "__main__":
    main()
