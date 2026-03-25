import json
import re
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

LOTTOMAX_URLS = [
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2026",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2025",
    "https://www.lottomaxnumbers.com/lotto-649/numbers/2024",
]

OLG_URL = "https://www.olg.ca/en/lottery/play-lotto-649-encore/past-results.html"

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_text(url: str) -> str:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


def normalize_date(date_obj) -> str:
    if pd.isna(date_obj):
        return ""
    return pd.to_datetime(date_obj).strftime("%Y-%m-%d")


def parse_lottomax_text(text: str):
    draws = []

    pattern = re.compile(
        rf"({MONTHS})\s+(\d{{1,2}})\s+(20\d{{2}})"
        rf"(.*?)"
        rf"(?=({MONTHS})\s+\d{{1,2}}\s+20\d{{2}}|$)",
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
                })

    return draws


def extract_candidate_scripts(html: str):
    soup = BeautifulSoup(html, "html.parser")
    chunks = [html]

    for tag in soup.find_all("script"):
      content = tag.string or tag.get_text(" ", strip=False)
      if content:
          chunks.append(content)

    return chunks


def clean_gold_number(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    raw = raw.replace(" ", "")
    raw = raw.replace("\u00a0", "")
    return raw


def parse_olg_goldball_from_text(text: str):
    """
    由可見文字抽 Gold Ball。
    呢個方法未必次次得，但可以做第一層。
    """
    gold_map = {}

    blocks = re.split(
        rf"(?=({MONTHS})\s+\d{{1,2}},\s+20\d{{2}})",
        text
    )

    rebuilt = []
    i = 0
    while i < len(blocks):
        if i + 2 < len(blocks) and re.fullmatch(rf"({MONTHS})", str(blocks[i + 1] or "")):
            rebuilt.append(blocks[i + 1] + blocks[i + 2])
            i += 3
        else:
            i += 1

    for block in rebuilt:
        dm = re.search(rf"({MONTHS})\s+(\d{{1,2}}),\s+(20\d{{2}})", block)
        if not dm:
            continue

        date = pd.to_datetime(f"{dm.group(1)} {dm.group(2)} {dm.group(3)}", errors="coerce")
        if pd.isna(date):
            continue

        date_key = date.strftime("%Y-%m-%d")

        prize_type = ""
        if re.search(r"\$1\s*Million", block, re.I):
            prize_type = "$1 Million"
        elif re.search(r"Jackpot", block, re.I):
            prize_type = "Gold Ball Jackpot"

        gold_number = ""
        gm = re.search(
            r"(?:Gold Ball(?: Draw)?(?: Number)?|Winning Gold Ball(?: Draw)? Number)[^\d]{0,40}(\d{8,10}(?:-\d{2})?)",
            block,
            re.I | re.S
        )
        if gm:
            gold_number = clean_gold_number(gm.group(1))

        result = " | ".join([x for x in [prize_type, gold_number] if x])

        gold_map[date_key] = {
            "gold_ball_number": gold_number,
            "gold_prize_type": prize_type,
            "gold_result": result
        }

    return gold_map


def parse_olg_goldball_from_html(html: str):
    """
    由原始 HTML / script 嘗試抽 Gold Ball。
    會試多幾種 pattern。
    """
    gold_map = {}

    chunks = extract_candidate_scripts(html)

    date_patterns = [
        r"\b(20\d{2}-\d{2}-\d{2})\b",
        rf"({MONTHS}\s+\d{{1,2}},\s+20\d{{2}})",
    ]

    number_patterns = [
        r'"goldBallNumber"\s*:\s*"([^"]+)"',
        r'"gold_ball_number"\s*:\s*"([^"]+)"',
        r'"winningGoldBall(?:Draw)?Number"\s*:\s*"([^"]+)"',
        r'"goldBallDrawNumber"\s*:\s*"([^"]+)"',
        r'"number"\s*:\s*"(\d{8,10}(?:-\d{2})?)"',
        r'Gold Ball(?: Draw)?(?: Number)?[^\d]{0,40}(\d{8,10}(?:-\d{2})?)',
    ]

    prize_patterns = [
        (r'"goldBallPrizeType"\s*:\s*"([^"]+)"', None),
        (r'"gold_prize_type"\s*:\s*"([^"]+)"', None),
        (r'"prizeType"\s*:\s*"([^"]+)"', None),
        (r'Gold Ball Jackpot', "Gold Ball Jackpot"),
        (r'\$1\s*Million', "$1 Million"),
    ]

    for chunk in chunks:
        compact = re.sub(r"\s+", " ", chunk)

        date_found = None
        for dp in date_patterns:
            dm = re.search(dp, compact, re.I)
            if dm:
                raw_date = dm.group(1)
                date_found = pd.to_datetime(raw_date, errors="coerce")
                break

        if pd.isna(date_found) or date_found is None:
            continue

        date_key = normalize_date(date_found)
        if not date_key:
            continue

        gold_number = ""
        for np in number_patterns:
            nm = re.search(np, compact, re.I)
            if nm:
                gold_number = clean_gold_number(nm.group(1))
                break

        prize_type = ""
        for pp, fixed in prize_patterns:
            pm = re.search(pp, compact, re.I)
            if pm:
                prize_type = fixed if fixed else pm.group(1).strip()
                break

        if gold_number or prize_type:
            gold_map[date_key] = {
                "gold_ball_number": gold_number,
                "gold_prize_type": prize_type,
                "gold_result": " | ".join([x for x in [prize_type, gold_number] if x])
            }

    return gold_map


def merge_gold_maps(*maps):
    merged = {}
    for mp in maps:
        for k, v in mp.items():
            if k not in merged:
                merged[k] = {
                    "gold_ball_number": "",
                    "gold_prize_type": "",
                    "gold_result": "",
                }

            if v.get("gold_ball_number"):
                merged[k]["gold_ball_number"] = v["gold_ball_number"]
            if v.get("gold_prize_type"):
                merged[k]["gold_prize_type"] = v["gold_prize_type"]

            merged[k]["gold_result"] = " | ".join(
                [x for x in [merged[k]["gold_prize_type"], merged[k]["gold_ball_number"]] if x]
            )

    return merged


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
        olg_html = fetch_html(OLG_URL)
        olg_text = BeautifulSoup(olg_html, "html.parser").get_text("\n", strip=True)

        gold_map_text = parse_olg_goldball_from_text(olg_text)
        gold_map_html = parse_olg_goldball_from_html(olg_html)
        gold_map = merge_gold_maps(gold_map_text, gold_map_html)

        df["gold_ball_number"] = df["date"].map(lambda d: gold_map.get(d, {}).get("gold_ball_number", ""))
        df["gold_prize_type"] = df["date"].map(lambda d: gold_map.get(d, {}).get("gold_prize_type", ""))
        df["gold_result"] = df["date"].map(lambda d: gold_map.get(d, {}).get("gold_result", ""))

        matched_count = int((df["gold_ball_number"].fillna("").astype(str).str.strip() != "").sum())
        print(f"   ✅ Gold Ball 成功配對 {matched_count} 期")
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

        odd_count = sum(1 for n in nums if n % 2 != 0)
        even_count = sum(1 for n in nums if n % 2 == 0)

        record["odd_even"] = f"{odd_count}單 {even_count}雙"
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
