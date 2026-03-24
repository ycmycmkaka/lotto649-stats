import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

def scrape_real_649_data():
    all_draws = []
    # 🌟 雙劍合璧：主力去 LotteryCanada 搵詳情，後備去 lottonumbers 補底
    urls = [
        "https://lotterycanada.com/lotto-649/past-draws",
        "https://lotterycanada.com/lotto-649",
        "https://ca.lottonumbers.com/lotto-649/numbers"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for url in urls:
        print(f"📡 嘗試抓取: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for row in soup.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    date_str = cols[0].get_text(" ", strip=True)
                    # 只要係 2023-2029 嘅年份就行
                    if not re.search(r'202[3-9]', date_str):
                        continue
                        
                    # 搵號碼
                    row_text = cols[1].get_text(" ")
                    nums_found = [int(x) for x in re.findall(r'\b\d{1,2}\b', row_text) if 1 <= int(x) <= 49]
                    nums_found = list(dict.fromkeys(nums_found)) # 剷走重複
                    
                    if len(nums_found) >= 6:
                        main_balls = sorted(nums_found[:6])
                        
                        # 🌟 終極金/白波 AI 判斷邏輯
                        full_row = row.get_text(" ").lower()
                        
                        # 如果明確寫住 white 或者 1,000,000 獎金 -> 白波
                        if "white" in full_row or "1,000,000" in full_row:
                            b_type = "White"
                        # 如果明確寫住 gold ball jackpot -> 金波
                        elif "gold ball jackpot" in full_row or "gold ball winner" in full_row:
                            b_type = "Gold"
                        # 如果含糊不清 (例如 ca.lottonumbers)，按現實概率預設為白波
                        else:
                            b_type = "White"
                            
                        # 搵抽獎號碼 (12345678-01)
                        pm = re.search(r'\d{8,10}-\d{2}', full_row)
                        clean_date = re.sub(r'(?i)latest|\*', '', date_str).strip()
                        
                        all_draws.append({
                            'date': clean_date,
                            'n1': main_balls[0], 'n2': main_balls[1], 'n3': main_balls[2],
                            'n4': main_balls[3], 'n5': main_balls[4], 'n6': main_balls[5],
                            'ball_type': b_type, 'gold_no': pm.group(0) if pm else "-"
                        })
        except Exception as e:
            print(f"⚠️ 錯誤: {e}")
            
    df = pd.DataFrame(all_draws)
    if not df.empty:
        # 智能合併，剷走重複日期，由舊排到新 (方便下面計連續同重複)
        df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date_obj']).drop_duplicates(subset=['date_obj']).sort_values('date_obj', ascending=True)
        return df
    return pd.DataFrame()

def calculate_metrics(df):
    if df.empty: return df
    
    prev_numbers = set()
    results = []
    
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
        
    # 計完晒所有嘢，排返由最新到最舊出 CSV
    final_df = pd.DataFrame(results).sort_values('date_obj', ascending=False)
    final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
    return final_df

def main():
    print("🚀 啟動 Lotto 6/49 智能分辨金白波版爬蟲...")
    raw_df = scrape_real_649_data()
    
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
        cols = ['date','n1','n2','n3','n4','n5','n6','ball_type','gold_no','odd_even','consecutive','repeats','zone']
        final_df[cols].to_csv('data.csv', index=False)
        print(f"✅ 大功告成！成功寫入 {len(final_df)} 期真實數據落 CSV。")
    else:
        print("❌ 警告：依然搵唔到數據！程式強制終止。")
        exit(1)

if __name__ == "__main__":
    main()
