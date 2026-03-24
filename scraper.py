import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

def scrape_649(url, all_draws):
    print(f"📡 抓取 6/49 數據: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                raw_date = cols[0].get_text(" ", strip=True)
                clean_date = re.sub(r'(?i)latest|\*', '', raw_date).strip()
                
                # 1. 攞 6 個主號碼 (通常喺第二格)
                balls = [int(b.get_text()) for b in cols[1].find_all(['li', 'span']) if b.get_text().isdigit()]
                
                # 2. 攞 Gold Ball 結果 (通常喺第三格)
                # 邏輯：如果文字包含 "Gold", "White" 或一串長號碼
                gold_info = cols[2].get_text(" ", strip=True)
                ball_type = "Gold" if "Gold" in gold_info else "White"
                prize_no = re.search(r'\d{8}-\d{2}', gold_info) # 搵出例如 12345678-01 嘅號碼
                gold_no = prize_no.group(0) if prize_no else "-"

                if len(balls) >= 6:
                    nums = sorted(balls[:6])
                    all_draws.append({
                        'date': clean_date,
                        'n1': nums[0], 'n2': nums[1], 'n3': nums[2],
                        'n4': nums[3], 'n5': nums[4], 'n6': nums[5],
                        'ball_type': ball_type,
                        'gold_no': gold_no
                    })
    except Exception as e: print(f"⚠️ 錯誤: {e}")

def calculate_649_metrics(df):
    df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date_obj']).sort_values('date_obj', ascending=True)
    df = df.drop_duplicates(subset=['date_obj'], keep='first')
    
    prev_numbers = set()
    results = []
    
    for _, row in df.iterrows():
        nums = [int(row[f'n{i}']) for i in range(1, 7)]
        # 單雙 (649 總共 6 個波)
        odds = sum(1 for n in nums if n % 2 != 0)
        row['odd_even'] = f"{odds}單 {6-odds}雙"
        # 連續
        row['consecutive'] = "Yes" if any(nums[i+1] - nums[i] == 1 for i in range(len(nums)-1)) else "No"
        # 重複
        curr_set = set(nums)
        row['repeats'] = len(curr_set.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = curr_set
        # 分區 (1-10, 11-20... 649 最高 49 號)
        zones = set([(n - 1) // 10 + 1 for n in nums])
        row['zone'] = f"{len(zones)}個區 ({','.join(map(str, sorted(list(zones))))})"
        results.append(row)
        
    final_df = pd.DataFrame(results).sort_values('date_obj', ascending=False)
    final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
    return final_df

def main():
    all_draws = []
    # 6/49 專屬 URL
    scrape_649("https://www.lotto649numbers.com/past-numbers", all_draws)
    scrape_649("https://www.lotto649numbers.com/numbers/2026", all_draws)
    
    if all_draws:
        df = calculate_649_metrics(pd.DataFrame(all_draws))
        df.to_csv('data.csv', index=False)
        print("✅ 6/49 數據更新成功！")

if __name__ == "__main__":
    main()
