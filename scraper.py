import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import re

def get_649_data():
    all_draws = []
    # 爬取最新鮮同埋 2026 嘅數據
    urls = ["https://www.lotto649numbers.com/past-numbers", "https://www.lotto649numbers.com/numbers/2026"]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for url in urls:
        print(f"📡 抓取 6/49 數據: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # 1. 日期
                    raw_date = cols[0].get_text(" ", strip=True)
                    clean_date = re.sub(r'(?i)latest|\*', '', raw_date).strip()
                    
                    # 2. 6 個主號碼
                    balls = []
                    ball_elements = cols[1].find_all(['li', 'span', 'div', 'b'])
                    for b in ball_elements:
                        txt = b.get_text(strip=True)
                        if txt.isdigit(): balls.append(int(txt))
                    
                    # 3. 金/白波抽獎 (Gold/White Ball)
                    gold_info = cols[2].get_text(" ", strip=True)
                    b_type = "Gold" if "Gold" in gold_info else "White"
                    # 攞 12345678-01 呢類格式
                    prize_match = re.search(r'\d{8}-\d{2}', gold_info)
                    g_no = prize_match.group(0) if prize_match else "-"

                    if len(balls) >= 6:
                        nums = sorted(balls[:6])
                        all_draws.append({
                            'date': clean_date,
                            'n1': nums[0], 'n2': nums[1], 'n3': nums[2],
                            'n4': nums[3], 'n5': nums[4], 'n6': nums[5],
                            'ball_type': b_type,
                            'gold_no': g_no
                        })
        except Exception as e:
            print(f"⚠️ 抓取失敗: {e}")
            
    return pd.DataFrame(all_draws)

def calculate_metrics(df):
    if df.empty: return df
    df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date_obj']).drop_duplicates(subset=['date_obj']).sort_values('date_obj', ascending=True)
    
    prev_numbers = set()
    results = []
    
    for _, row in df.iterrows():
        nums = [int(row[f'n{i}']) for i in range(1, 7)]
        # 單雙
        odds = sum(1 for n in nums if n % 2 != 0)
        row['odd_even'] = f"{odds}單 {6-odds}雙"
        # 連續
        row['consecutive'] = "Yes" if any(nums[i+1] - nums[i] == 1 for i in range(len(nums)-1)) else "No"
        # 重複
        curr_set = set(nums)
        row['repeats'] = len(curr_set.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = curr_set
        # 分區 (6/49 係 1-49 號)
        zones = sorted(list(set([(n - 1) // 10 + 1 for n in nums])))
        row['zone'] = f"{len(zones)}個區 ({','.join(map(str, zones))})"
        results.append(row)
        
    return pd.DataFrame(results).sort_values('date_obj', ascending=False)

def main():
    raw_df = get_649_data()
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
