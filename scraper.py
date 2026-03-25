import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

def scrape_real_649_data():
    all_draws = []
    # 專注去你搵到嘅 lottomaxnumbers 大寶藏，淨係抄核心號碼！
    urls = [
        "https://www.lottomaxnumbers.com/lotto-649/past-numbers",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2026",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2025",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2024"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for url in urls:
        print(f"📡 極速抓取核心號碼: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200: continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            for row in soup.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    date_str = cols[0].get_text(" ", strip=True)
                    if not re.search(r'202[4-9]', date_str): continue
                    
                    # 1. 抽 6 個核心主波 (呢個一定準！)
                    nums_found = []
                    for b in cols[1].find_all(['li', 'span', 'div']):
                        txt = b.get_text(strip=True)
                        if txt.isdigit() and int(txt) <= 49 and int(txt) not in nums_found:
                            nums_found.append(int(txt))
                            
                    if len(nums_found) < 6:
                        row_text = cols[1].get_text(" ")
                        nums_found = list(dict.fromkeys([int(x) for x in re.findall(r'\b\d{1,2}\b', row_text) if int(x) <= 49]))
                        
                    if len(nums_found) >= 6:
                        main_balls = sorted(nums_found[:6])
                        clean_date = re.sub(r'(?i)latest|\*', '', date_str).strip()
                            
                        all_draws.append({
                            'date': clean_date,
                            'n1': main_balls[0], 'n2': main_balls[1], 'n3': main_balls[2],
                            'n4': main_balls[3], 'n5': main_balls[4], 'n6': main_balls[5]
                            # ✅ 剷除晒金波、白波、獎金、號碼！
                        })
        except Exception as e:
            print(f"⚠️ 核心錯誤: {e}")
            
    df = pd.DataFrame(all_draws)
    if not df.empty:
        df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
        # 剷走重複日期，由舊排到新 (方便計統計)
        return df.dropna(subset=['date_obj']).drop_duplicates('date_obj').sort_values('date_obj', ascending=True)
    return pd.DataFrame()

def calculate_metrics(df):
    if df.empty: return df
    prev_numbers = set()
    results = []
    
    # 由舊到新行，計連續同重複
    for _, row in df.iterrows():
        nums = [int(row[f'n{i}']) for i in range(1, 7)]
        row['odd_even'] = f"{sum(1 for n in nums if n%2!=0)}單 {sum(1 for n in nums if n%2==0)}雙"
        row['consecutive'] = "Yes" if any(nums[i+1] - nums[i] == 1 for i in range(len(nums)-1)) else "No"
        
        curr_set = set(nums)
        row['repeats'] = len(curr_set.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = curr_set
        
        zones = sorted(list(set([(n - 1) // 10 + 1 for n in nums])))
        row['zone'] = f"{len(zones)}個區 ({','.join(map(str, zones))})"
        results.append(row)
        
    # 計完，排返最新到最舊出 CSV
    final_df = pd.DataFrame(results).sort_values('date_obj', ascending=False)
    final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
    return final_df

def main():
    print("🚀 啟動 Lotto 6/49 核心號碼走勢爬蟲 (只攻不守)...")
    raw_df = scrape_real_649_data()
    
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
        cols = ['date','n1','n2','n3','n4','n5','n6','odd_even','consecutive','repeats','zone']
        final_df[cols].to_csv('data.csv', index=False)
        print(f"✅ 極速搞掂！成功寫入 {len(final_df)} 期核心數據。")
    else:
        print("❌ 警告：搵唔到數據！強制終止。")
        exit(1)

if __name__ == "__main__":
    main()
