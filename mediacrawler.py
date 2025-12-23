import os
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import threading

# --- 1. 配置区域 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_ROOT = os.path.join(BASE_DIR, "Fudan_Media_Data")

BASE_URL = "https://www.fdsm.fudan.edu.cn/AboutUs/"
LIST_URL_TEMPLATE = "https://www.fdsm.fudan.edu.cn/AboutUs/MediaView.html?p={}"

MAX_WORKERS = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

print_lock = threading.Lock()

def safe_print(msg):
    with print_lock:
        print(msg)

# --- 2. 工具函数 ---

def clean_filename(text):
    return re.sub(r'[\\/*?:"<>|\n\t]', "", text).strip()

def determine_ext(url):
    if "wx_fmt=png" in url: return ".png"
    if "wx_fmt=gif" in url: return ".gif"
    if "wx_fmt=jpeg" in url or "wx_fmt=jpg" in url: return ".jpg"
    ext = os.path.splitext(url)[1]
    if ext and len(ext) <= 5: return ext
    return ".jpg"

def save_image(img_url, current_page_url, save_dir, index):
    try:
        if not img_url: return
        full_url = urljoin(current_page_url, img_url)
        
        # 过滤明显的非内容图片
        if "logo" in full_url.lower() or "icon" in full_url.lower() or "share" in full_url.lower():
            return

        ext = determine_ext(full_url)
        img_name = f"image_{index}{ext}"
        save_path = os.path.join(save_dir, img_name)

        if os.path.exists(save_path): return

        resp = requests.get(full_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
    except:
        pass 

def find_content_container(soup):
    """
    ★ 智能策略引擎 v2.0 ★
    引入黑名单机制，防止 over-fetching
    """
    
    # --- 策略 1: 微信公众号 (最高优) ---
    node = soup.find('div', id='js_content') or soup.find('div', class_='rich_media_content')
    if node: return node, 'wechat'

    # --- 策略 2: 明确的 Article 类名 (高优) ---
    # 匹配 article, mainarticle, article-body, main-article
    def match_strict_article(cls):
        if not cls: return False
        c = cls.lower()
        # 必须包含 article 且不包含列表、预览等词
        if 'article' in c and not any(bad in c for bad in ['list', 'preview', 'item', 'teaser']):
            return True
        return False
    
    node = soup.find('div', class_=match_strict_article)
    if node: return node, 'class_article_strict'

    # --- 策略 3: 你提供的特殊结构 (人民网等) ---
    node = soup.find('div', class_='rm_txt_con')
    if node: return node, 'media_rm_style'

    # --- 策略 4: 带黑名单的 Content 模糊匹配 (中优) ---
    # 这里回答你的问题：加 content 是否会 over 抓取？
    # 答：加上黑名单就不会。
    def match_content_safe(cls):
        if not cls: return False
        c = cls.lower()
        
        # 必须包含 content
        if 'content' not in c: return False
        
        # ★★★ 核心黑名单：包含这些词的 content 一律不要 ★★★
        blacklist = [
            'sidebar', 'right', 'left', 'footer', 'header', 'nav', 'menu', 
            'wrapper', 'container', 'widget', 'comment', 'related', 'share',
            'layout', 'recommend', 'meta'
        ]
        if any(bad in c for bad in blacklist):
            return False
            
        return True

    node = soup.find('div', class_=match_content_safe)
    if node: return node, 'class_content_safe'

    # --- 策略 5: 学校官网 (Fallback) ---
    node = soup.find('div', class_='detail-con') or soup.find('div', class_='TRS_Editor')
    if node: return node, 'school_native'
    
    # --- 策略 6: HTML5 语义化标签 ---
    node = soup.find('article')
    if node: return node, 'html5_tag'

    # --- 策略 7: (终极大招) 文本密度统计 ---
    # 如果上面都失败了，遍历页面所有 div，找字数最多的那个（通常就是正文）
    # 排除掉 body 和 html 标签
    max_len = 0
    best_div = None
    
    # 只看 body 下的 div
    body = soup.find('body')
    if body:
        for div in body.find_all('div'):
            # 简单的过滤：如果含有太多链接，可能是导航
            if len(div.find_all('a')) > 20: continue
            
            text = div.get_text(strip=True)
            length = len(text)
            
            # 记录当前最长的 div
            if length > max_len:
                max_len = length
                best_div = div

    if best_div and max_len > 100: # 至少得有100个字吧
        return best_div, 'text_density_max'

    return None, 'unknown'

def parse_detail_page(url, title, date):
    try:
        month_str = date[:7] 
        safe_title = clean_filename(title)[:50] 
        folder_name = f"{date}_{safe_title}"
        target_dir = os.path.join(SAVE_ROOT, month_str, folder_name)
        content_file = os.path.join(target_dir, "content.txt")

        if os.path.exists(content_file):
            safe_print(f"   [跳过] (已存在) {safe_title}...")
            return

        resp = requests.get(url, headers=HEADERS, timeout=15)
        # 自动识别编码，这对媒体网站至关重要
        resp.encoding = resp.apparent_encoding 
        
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 调用智能引擎
        content_div, mode = find_content_container(soup)
        
        if not content_div:
            safe_print(f"   [警告] 无法识别结构: {url}")
            # 记录失败链接以便人工查看
            with open(os.path.join(SAVE_ROOT, "failed_urls.txt"), "a") as f:
                f.write(f"{url}\n")
            return

        os.makedirs(target_dir, exist_ok=True)

        # 提取并清洗文本
        raw_text = content_div.get_text(separator="\n", strip=True)
        # 去除连续空行
        text_content = re.sub(r'\n\s*\n', '\n', raw_text)

        # 保存
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"标题: {title}\n")
            f.write(f"日期: {date}\n")
            f.write(f"链接: {url}\n")
            f.write(f"解析模式: {mode}\n")
            f.write("-" * 40 + "\n\n")
            f.write(text_content)

        # 图片提取
        images = content_div.find_all('img')
        img_count = 0
        for i, img in enumerate(images):
            src = ""
            if mode == 'wechat':
                src = img.get('data-src') or img.get('src')
            else:
                src = img.get('src') or img.get('data-src')
            
            # 过滤 base64 和 空链接
            if src and len(src) < 1000: 
                save_image(src, resp.url, target_dir, i+1)
                img_count += 1
        
        safe_print(f" [成功] {safe_title}... [{mode}|图:{img_count}]")

    except Exception as e:
        safe_print(f" [错误] {title}: {e}")

def process_page_list(page_num):
    list_url = LIST_URL_TEMPLATE.format(page_num)
    safe_print(f"--> 扫描第 {page_num} 页")
    
    try:
        resp = requests.get(list_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        title_tags = soup.find_all('p', class_='h')
        valid_items = []
        
        for p_tag in title_tags:
            title = p_tag.get_text(strip=True)
            if not title: continue

            link_tag = p_tag.find_parent('a') or p_tag.find('a')
            if not link_tag: continue

            full_url = urljoin(BASE_URL, link_tag['href'])

            container = link_tag.find_parent('li') or link_tag.parent.parent
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', container.get_text())
            date = date_match.group(0) if date_match else "Unknown_Date"

            valid_items.append({'title': title, 'date': date, 'url': full_url})

        for item in valid_items:
            parse_detail_page(item['url'], item['title'], item['date'])

    except Exception as e:
        safe_print(f"列表页 {page_num} 异常: {e}")

if __name__ == "__main__":
    if not os.path.exists(SAVE_ROOT): os.makedirs(SAVE_ROOT)
    
    # 媒体视角大概有 29 页
    START_PAGE = 1
    END_PAGE = 252
    
    print("="*60)
    print(f"保存路径: {SAVE_ROOT}")
    print(f"任务: 媒体视角 (智能过滤版) | 第 {START_PAGE} - {END_PAGE} 页")
    print("="*60)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_page_list, page) 
                   for page in range(START_PAGE, END_PAGE + 1)]
        for future in futures:
            try: future.result()
            except: pass

    print("\n完成。")