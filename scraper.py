import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

def scrape_real_649_data():
    all_draws = []
    urls = [
        "https://www.lottomaxnumbers.com/lotto-649/past-numbers",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2026",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2025"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for url in urls:
        print(f"📡 掃描大表: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for row in soup.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 3:
                    date_str = cols[0].get_text(" ", strip=True)
                    if not re.search(r'202[4-9]', date_str):
                        continue
                    
                    # 1. 抽 6 個主波
                    ball_elements = cols[1].find_all(['li', 'span', 'div'])
                    nums_found = []
                    for b in ball_elements:
                        txt = b.get_text(strip=True)
                        if txt.isdigit():
                            val = int(txt)
                            if 1 <= val <= 49 and val not in nums_found:
                                nums_found.append(val)
                                
                    if len(nums_found) < 6:
                        row_text = cols[1].get_text(" ")
                        nums_found = [int(x) for x in re.findall(r'\b\d{1,2}\b', row_text) if 1 <= int(x) <= 49]
                        nums_found = list(dict.fromkeys(nums_found))
                        
                    if len(nums_found) >= 6:
                        main_balls = sorted(nums_found[:6])
                        clean_date = re.sub(r'(?i)latest|\*', '', date_str).strip()
                        
                        # 大表嘅初步判斷
                        prize_col_text = cols[2].get_text(" ").lower()
                        b_type = "White" if "white" in prize_col_text else ("Gold" if "gold" in prize_col_text else "?")
                        pm = re.search(r'\d{8,10}-\d{2}', prize_col_text)
                        gold_no = pm.group(0) if pm else "-"
                        
                        # 🌟 特工模式 2.0：直接喺大表條 Link 撳入去！
                        if gold_no == "-" or b_type == "?":
                            try:
                                link = row.find('a') # 自動搵隱藏嘅網址
                                detail_url = ""
                                if link and link.has_attr('href'):
                                    detail_url = link['href']
                                    if not detail_url.startswith('http'):
                                        detail_url = "https://www.lottomaxnumbers.com" + detail_url
                                        
                                if detail_url:
                                    print(f"   🕵️ 潛入分析: {clean_date}")
                                    detail_resp = requests.get(detail_url, headers=headers, timeout=10)
                                    if detail_resp.status_code == 200:
                                        detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                                        # 將成個網頁嘅字變細階，方便搵
                                        detail_text = detail_soup.get_text(" ", strip=True).lower()
                                        
                                        # 搵 12345678-01 呢種格式嘅號碼
                                        pm_detail = re.search(r'\b\d{8,10}-\d{2}\b', detail_text)
                                        if pm_detail:
                                            gold_no = pm_detail.group(0)
                                            
                                        # 搵係咪白波 (通常白波會寫明 "white ball")
                                        if "white ball" in detail_text or "white" in detail_text:
                                            b_type = "White"
                                        elif "gold ball" in detail_text:
                                            b_type = "Gold"
                            except Exception as e:
                                pass # 潛入失敗都唔會死機，繼續行
                                
                        # 如果全部都搵唔到，按機率預設為白波
                        if b_type == "?": b_type = "White"
                        
                        all_draws.append({
                            'date': clean_date,
                            'n1': main_balls[0], 'n2': main_balls[1], 'n3': main_balls[2],
                            'n4': main_balls[3], 'n5': main_balls[4], 'n6': main_balls[5],
                            'ball_type': b_type, 'gold_no': gold_no
                        })
        except Exception as e:
            print(f"⚠️ 錯誤: {e}")
            
    df = pd.DataFrame(all_draws)
    if not df.empty:
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
        
    final_df = pd.DataFrame(results).sort_values('date_obj', ascending=False)
    final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
    return final_df

def main():
    print("🚀 啟動 Lotto 6/49 神級特工爬蟲 2.0 (自動追蹤導航)...")
    raw_df = scrape_real_649_data()
    
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
        cols = ['date','n1','n2','n3','n4','n5','n6','ball_type','gold_no','odd_even','consecutive','repeats','zone']
        final_df[cols].to_csv('data.csv', index=False)
        print(f"✅ 大功告成！成功寫入 {len(final_df)} 期完美數據落 CSV。")
    else:
        print("❌ 警告：完全搵唔到數據！程式強制終止。")
        exit(1)

if __name__ == "__main__":
    main()
