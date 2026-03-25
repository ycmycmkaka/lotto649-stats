import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import os

def load_existing_data():
    """讀取現有 CSV，記住已經搵到嘅金波號碼，避免重複抓取被 Block"""
    existing = {}
    if os.path.exists('data.csv'):
        try:
            df = pd.read_csv('data.csv')
            for _, r in df.iterrows():
                # 如果嗰期已經有靚靚嘅抽獎號碼 (唔係 "-")，就記住佢
                if pd.notna(r.get('gold_no')) and str(r['gold_no']).strip() != "-":
                    existing[str(r['date'])] = {
                        'ball_type': r.get('ball_type', 'White'),
                        'gold_no': str(r['gold_no']).strip()
                    }
        except: pass
    return existing

def scrape_real_649_data():
    all_draws = []
    existing_data = load_existing_data()
    print(f"📂 已經從記憶體讀取 {len(existing_data)} 期舊資料，準備開工...")
    
    urls = [
        "https://www.lottomaxnumbers.com/lotto-649/past-numbers",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2026",
        "https://www.lottomaxnumbers.com/lotto-649/numbers/2025"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in urls:
        print(f"📡 掃描大表: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200: continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for row in soup.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 3:
                    date_str = cols[0].get_text(" ", strip=True)
                    if not re.search(r'202[4-9]', date_str): continue
                    
                    clean_date = re.sub(r'(?i)latest|\*', '', date_str).strip()
                    
                    # 抽 6 個主波
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
                        
                        # 🌟 記憶體系統：如果已經查過呢期，直接抄舊答案，跳過潛入！
                        if clean_date in existing_data:
                            b_type = existing_data[clean_date]['ball_type']
                            gold_no = existing_data[clean_date]['gold_no']
                        else:
                            # 否則，啟動特工模式潛入
                            b_type = "White"
                            gold_no = "-"
                            link = row.find('a')
                            if link and link.has_attr('href'):
                                detail_url = link['href']
                                if not detail_url.startswith('http'):
                                    detail_url = "https://www.lottomaxnumbers.com" + detail_url
                                
                                print(f"   🕵️ 潛入新日子: {clean_date} (扮真人停頓 2 秒...)")
                                time.sleep(2) # 🌟 致命武器：停頓 2 秒，防止被網站保安封鎖
                                
                                try:
                                    detail_resp = requests.get(detail_url, headers=headers, timeout=10)
                                    if detail_resp.status_code == 200:
                                        detail_text = BeautifulSoup(detail_resp.text, 'html.parser').get_text(" ", strip=True).lower()
                                        
                                        # 包容埋有空格嘅號碼格式
                                        pm_detail = re.search(r'\b\d{8,10}\s*-\s*\d{2}\b', detail_text)
                                        if pm_detail:
                                            gold_no = pm_detail.group(0).replace(" ", "")
                                            
                                        if "gold ball winner" in detail_text or "gold ball jackpot" in detail_text:
                                            b_type = "Gold"
                                        elif "white ball" in detail_text:
                                            b_type = "White"
                                except Exception as e:
                                    print(f"     ❌ 潛入失敗，可能被擋: {e}")
                        
                        all_draws.append({
                            'date': clean_date,
                            'n1': main_balls[0], 'n2': main_balls[1], 'n3': main_balls[2],
                            'n4': main_balls[3], 'n5': main_balls[4], 'n6': main_balls[5],
                            'ball_type': b_type, 'gold_no': gold_no
                        })
        except Exception as e:
            print(f"⚠️ 大表錯誤: {e}")
            
    df = pd.DataFrame(all_draws)
    if not df.empty:
        df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
        return df.dropna(subset=['date_obj']).drop_duplicates('date_obj').sort_values('date_obj', ascending=True)
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
    print("🚀 啟動 Lotto 6/49 終極隱形特工爬蟲 (帶記憶功能)...")
    raw_df = scrape_real_649_data()
    
    if not raw_df.empty:
        final_df = calculate_metrics(raw_df)
        cols = ['date','n1','n2','n3','n4','n5','n6','ball_type','gold_no','odd_even','consecutive','repeats','zone']
        final_df[cols].to_csv('data.csv', index=False)
        print(f"✅ 大功告成！成功寫入 {len(final_df)} 期完美數據。")
    else:
        print("❌ 警告：搵唔到數據！強制終止。")
        exit(1)

if __name__ == "__main__":
    main()
