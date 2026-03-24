import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

def scrape_real_649_data():
    all_draws = []
    # 🌟 多重保險：加入 4 個真實有效嘅加拿大彩票網站！一個死咗都有另一個頂上！
    urls = [
        "https://www.lotto.net/canada-lotto-649/results/2026",
        "https://www.lotto.net/canada-lotto-649/results/2025",
        "https://lotterycanada.com/lotto-649",
        "https://lotterycanada.com/lotto-649/past-draws"
    ]
    # 扮成真人用緊 Google Chrome，唔會被當做機械人
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in urls:
        print(f"📡 嘗試抓取: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            print(f"   -> 回應代碼: {resp.status_code}")
            
            if resp.status_code != 200:
                print("   -> 🚫 網頁無反應，自動跳去下一個網。")
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            tables = soup.find_all('table')
            
            for table in tables:
                for row in table.find_all('tr'):
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 2:
                        date_str = cols[0].get_text(" ", strip=True)
                        
                        # 確定第一格真係有 2024/2025/2026 年份嘅日期
                        if not re.search(r'202[4-9]', date_str):
                            continue
                            
                        # 將後面啲格仔合併，然後用 AI 邏輯抽出所有 1-49 嘅波
                        row_text = " ".join([c.get_text(" ") for c in cols[1:]])
                        nums_found = [int(x) for x in re.findall(r'\b\d{1,2}\b', row_text) if 1 <= int(x) <= 49]
                        
                        unique_nums = []
                        for n in nums_found:
                            if n not in unique_nums: unique_nums.append(n)
                            
                        # 如果齊 6 個波就記錄落嚟
                        if len(unique_nums) >= 6:
                            main_balls = sorted(unique_nums[:6])
                            
                            # 判斷有無 "Gold" 字眼，同埋搵抽獎號碼
                            full_row = " ".join([c.get_text(" ") for c in cols])
                            b_type = "Gold" if re.search(r'(?i)gold', full_row) else "White"
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
            
    # 將爬到嘅所有數據變成 DataFrame
    df = pd.DataFrame(all_draws)
    if not df.empty:
        # 因為去咗幾個網，會有重複，所以要智能合併，只保留獨一無二嘅日期
        df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date_obj']).drop_duplicates(subset=['date_obj']).sort_values('date_obj', ascending=False)
        df['date'] = df['date_obj'].dt.strftime('%Y-%m-%d')
        df = df.drop(columns=['date_obj'])
        
    return df

def calculate_metrics(df):
    if df.empty: return df
    # 由最舊計到最新，確保「上期重複」計得準
    df = df.sort_values('date', ascending=True)
    
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
        
    # 排返由最新到最舊出 CSV
    return pd.DataFrame(results).sort_values('date', ascending=False)

def main():
    print("🚀 啟動 Lotto 6/49 無敵多重保險版爬蟲...")
    raw_df = scrape_real_649_data()
    
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
        cols = ['date','n1','n2','n3','n4','n5','n6','ball_type','gold_no','odd_even','consecutive','repeats','zone']
        final_df[cols].to_csv('data.csv', index=False)
        print(f"✅ 大功告成！成功寫入 {len(final_df)} 期真實數據落 CSV。")
    else:
        print("❌ 警告：所有網站都搵唔到數據！程式強制終止。")
        exit(1)

if __name__ == "__main__":
    main()
