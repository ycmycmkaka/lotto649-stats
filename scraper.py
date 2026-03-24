import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import re

def scrape_649_data():
    all_draws = []
    urls = ["https://www.lotto649numbers.com/past-numbers", "https://www.lotto649numbers.com/numbers/2026"]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for url in urls:
        print(f"📡 抓取中: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # 日期
                    raw_date = cols[0].get_text(" ", strip=True)
                    clean_date = re.sub(r'(?i)latest|\*', '', raw_date).strip()
                    # 號碼
                    balls = [int(b.get_text()) for b in cols[1].find_all(['li', 'span', 'b']) if b.get_text().isdigit()]
                    # 金/白波
                    prize_info = cols[2].get_text(" ", strip=True)
                    b_type = "Gold" if "Gold" in prize_info else "White"
                    p_match = re.search(r'\d{8}-\d{2}', prize_info)
                    g_no = p_match.group(0) if p_match else "-"

                    if len(balls) >= 6:
                        nums = sorted(balls[:6])
                        all_draws.append({
                            'date': clean_date, 'n1': nums[0], 'n2': nums[1], 'n3': nums[2],
                            'n4': nums[3], 'n5': nums[4], 'n6': nums[5],
                            'ball_type': b_type, 'gold_no': g_no
                        })
        except: pass
    return pd.DataFrame(all_draws)

def main():
    df = scrape_649_data()
    if not df.empty:
        df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date_obj']).drop_duplicates('date_obj').sort_values('date_obj', ascending=True)
        
        prev = set()
        res = []
        for _, r in df.iterrows():
            nums = [int(r[f'n{i}']) for i in range(1, 7)]
            r['odd_even'] = f"{sum(1 for n in nums if n%2!=0)}單 {sum(1 for n in nums if n%2==0)}雙"
            r['consecutive'] = "Yes" if any(nums[i+1]-nums[i]==1 for i in range(len(nums)-1)) else "No"
            curr = set(nums)
            r['repeats'] = len(curr.intersection(prev)) if prev else 0
            prev = curr
            z = sorted(list(set([(n-1)//10+1 for n in nums])))
            r['zone'] = f"{len(z)}個區 ({','.join(map(str, z))})"
            res.append(r)
        
        final_df = pd.DataFrame(res).sort_values('date_obj', ascending=False)
        final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
        final_df[['date','n1','n2','n3','n4','n5','n6','ball_type','gold_no','odd_even','consecutive','repeats','zone']].to_csv('data.csv', index=False)
        print("✅ 數據更新成功")

if __name__ == "__main__":
    main()
