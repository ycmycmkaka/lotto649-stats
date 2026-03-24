import pandas as pd
import requests
import re

def scrape_real_649_data():
    all_draws = []
    # 呢個先係真正存在、專門記錄加拿大 6/49 嘅權威網站！
    urls = [
        "https://www.lottery.net/canada-lotto-649/numbers/2026",
        "https://www.lottery.net/canada-lotto-649/numbers/2025"
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for url in urls:
        print(f"📡 真正抓取中: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            # 神級魔法：自動將網頁入面所有 Table 變成資料表
            tables = pd.read_html(resp.text)
            
            for df in tables:
                # 確保個表有最少兩欄 (日期 + 號碼)
                if len(df.columns) >= 2 and len(df) > 0:
                    for _, row in df.iterrows():
                        date_str = str(row.iloc[0]) # 第一欄永遠係日期
                        if "202" not in date_str: continue
                        
                        # 將後面啲欄位合埋一齊，抽號碼出嚟
                        row_str = " ".join(map(str, row.values[1:])) 
                        nums_found = [int(x) for x in re.findall(r'\b\d{1,2}\b', row_str) if 1 <= int(x) <= 49]
                        
                        # 過濾重複數字，攞頭 6 個主波
                        unique_nums = []
                        for n in nums_found:
                            if n not in unique_nums: unique_nums.append(n)
                        
                        if len(unique_nums) >= 6:
                            main_balls = sorted(unique_nums[:6])
                            
                            # 判斷金波同抽獎號碼
                            full_row_str = " ".join(map(str, row.values))
                            b_type = "Gold" if "Gold" in full_row_str or "gold" in full_row_str else "White"
                            pm = re.search(r'\d{8}-\d{2}', full_row_str)
                            
                            # 清洗日期字眼 (抹走 Latest 呢啲多餘字)
                            clean_date = re.sub(r'(?i)latest', '', date_str).strip()
                            
                            all_draws.append({
                                'date': clean_date,
                                'n1': main_balls[0], 'n2': main_balls[1], 'n3': main_balls[2],
                                'n4': main_balls[3], 'n5': main_balls[4], 'n6': main_balls[5],
                                'ball_type': b_type, 'gold_no': pm.group(0) if pm else "-"
                            })
        except Exception as e:
            print(f"⚠️ 錯誤: {e}")
            
    return pd.DataFrame(all_draws)

def calculate_metrics(df):
    if df.empty: return df
    df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date_obj']).drop_duplicates(subset=['date_obj']).sort_values('date_obj', ascending=True)
    
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
        
    return pd.DataFrame(results).sort_values('date_obj', ascending=False)

def main():
    print("🚀 啟動 Lotto 6/49 終極修復版爬蟲...")
    raw_df = scrape_real_649_data()
    
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
        final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
        cols = ['date','n1','n2','n3','n4','n5','n6','ball_type','gold_no','odd_even','consecutive','repeats','zone']
        final_df[cols].to_csv('data.csv', index=False)
        print(f"✅ 大功告成！成功寫入 {len(final_df)} 期真實數據落 CSV。")
    else:
        print("❌ 警告：完全搵唔到數據！程式強制終止。")
        exit(1) # 呢句極重要！如果搵唔到數據，會強制將 Action 變紅交叉，以後唔會再呃到我哋！

if __name__ == "__main__":
    main()
