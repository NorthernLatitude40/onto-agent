import requests
from bs4 import BeautifulSoup

def scrape_get_lost_nz():
    target_url = "https://getlostinnz.co.nz/"
    
    # 设置标准的浏览器 User-Agent，避免被简单的反爬拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"正在抓取目标网站: {target_url} ...")
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status() # 检查请求是否成功
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return
    
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. 提取页面主标题 (H1)
    h1_tag = soup.find('h1')
    main_title = h1_tag.get_text(strip=True) if h1_tag else "未找到 H1 标题"
    print(f"\n【页面主标题】: {main_title}")
    
    print("\n【核心特色 / 标题提取 (H2)】:")
    # 2. 提取所有的二级标题 (H2)，通常包含房车核心卖点
    h2_tags = soup.find_all('h2')
    for idx, h2 in enumerate(h2_tags, 1):
        text = h2.get_text(strip=True)
        print(f"  {idx}. {text}")
        
    print("\n【段落文本摘要 (P)】:")
    # 3. 提取段落文本，用于后续的 RAG 文本切片
    paragraphs = soup.find_all('p')
    clean_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
    
    for idx, p_text in enumerate(clean_paragraphs[:5], 1): # 仅打印前 5 条作为预览
        print(f"  [片段 {idx}]: {p_text}")

if __name__ == "__main__":
    scrape_get_lost_nz()