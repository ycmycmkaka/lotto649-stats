import pandas as pd
import requests
from bs4 import BeautifulSoup
import re


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

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
    """
    由 lottomaxnumbers 抽：
    date + 6 個主號碼 + bonus(第7個)
    """
    draws = []

    # 例：
    # February 25 2026
    # 17 24 32 37 46 49 43
    pattern = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})\s+(20\d{2})"
        r"(.*?)"
        r"(?=(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\s+20\d{2}|$)",
        re.S
    )

    for m in pattern.finditer(text):
        month = m.group(1)
        day = m.group(2)
        year = m.group(3)
        block = m.group(4)

        nums = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d)\b", block)]

        # 去重但保留次序
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
                    "white": bonus,   # 你網站叫白波
                    "result": f"{main[0]} - {main[1]} - {main[2]} - {main[3]} - {main[4]} - {main[5]} | White {bonus}"
                })

    return draws


def parse_olg_goldball(text: str):
    """
    由 OLG past results 抽：
    date -> Gold Ball
    """
    gold_map = {}

    # 例搜尋摘要格式：
    # 02. 16. 18. 37. 39. 41. Bonus. 47. GOLD BALL. $1 Million 53673602-09.
    # 加埋日期通常會喺附近，例如 March 21, 2026
    blocks = re.split(r"(?=(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2})", text)

    rebuilt = []
    i = 0
    while i < len(blocks):
        if i + 2 < len(blocks) and re.fullmatch(r"(January|February|March|April|May|June|July|August|September|October|November|December)", str(blocks[i + 1] or "")):
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

        gm = re.search(r"GOLD BALL\.?\s*(?:\$[\d,]+\s+)?([0-9]{8,10}(?:-[0-9]{2})?)", block, re.I)
        if gm:
            gold_map[date.strftime("%Y-%m-%d")] = gm.group(1)

    return gold_map


def scrape_real_649_data():
    all_draws = []

    print("🚀 啟動 Lotto 6/49 爬蟲...")

    for url in LOTTOMAX_URLS:
        print(f"📡 抓取主號碼/白波: {url}")
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

    # Gold Ball
    try:
        print(f"📡 抓取 Gold Ball: {OLG_URL}")
        olg_text = fetch_text(OLG_URL)
        gold_map = parse_olg_goldball(olg_text)
        df["gold"] = df["date"].map(gold_map)
    except Exception as e:
        print(f"   ⚠️ Gold Ball 抽取失敗: {e}")
        df["gold"] = ""

    # 補 result
    def build_result(row):
        main = [row[f"n{i}"] for i in range(1, 7)]
        txt = " - ".join(str(int(x)) for x in main)
        if pd.notna(row.get("white")) and str(row.get("white")).strip() != "":
            txt += f" | White {row['white']}"
        if pd.notna(row.get("gold")) and str(row.get("gold")).strip() != "":
            txt += f" | Gold {row['gold']}"
        return txt

    df["result"] = df.apply(build_result, axis=1)
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
        "white", "gold", "result",
        "odd_even", "consecutive", "repeats", "zone"
    ]

    for c in cols:
        if c not in final_df.columns:
            final_df[c] = ""

    final_df[cols].to_csv("data.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 成功寫入 {len(final_df)} 期數據到 data.csv")


if __name__ == "__main__":
    main()
