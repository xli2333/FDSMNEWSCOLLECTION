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
# 修改保存目录，避免混淆
SAVE_ROOT = os.path.join(BASE_DIR, "Fudan_Wechat_Data")

BASE_URL = "https://www.fdsm.fudan.edu.cn/AboutUs/"
# 修改为微信头条的列表地址
LIST_URL_TEMPLATE = "https://www.fdsm.fudan.edu.cn/AboutUs/wechat.html?p={}"

HEADERS = {
    # 模拟真实浏览器，防止微信链接拦截
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
    """适配微信图片后缀"""
    if "wx_fmt=png" in url: return ".png"
    if "wx_fmt=gif" in url: return ".gif"
    if "wx_fmt=jpeg" in url or "wx_fmt=jpg" in url: return ".jpg"
    ext = os.path.splitext(url)[1]
    if ext and len(ext) <= 5: return ext
    return ".jpg"

def save_image(img_url, save_dir, index):
    try:
        if not img_url: return
        full_url = urljoin(BASE_URL, img_url)
        ext = determine_ext(full_url)
        img_name = f"image_{index}{ext}"
        save_path = os.path.join(save_dir, img_name)

        if os.path.exists(save_path): return

        resp = requests.get(full_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
    except:
        pass 

def parse_detail_page(url, title, date):
    """
    解析内页：【逻辑翻转版】
    优先匹配微信结构 (js_content)，其次匹配官网结构 (detail-con)
    """
    try:
        # --- 1. 断点续爬检测 ---
        month_str = date[:7] 
        safe_title = clean_filename(title)[:50] 
        folder_name = f"{date}_{safe_title}"
        target_dir = os.path.join(SAVE_ROOT, month_str, folder_name)
        content_file = os.path.join(target_dir, "content.txt")

        if os.path.exists(content_file):
            safe_print(f"   [跳过] (已存在) {safe_title}...")
            return

        # --- 2. 请求页面 ---
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        mode = "unknown"
        content_div = None
        
        # ★★★ 核心修改：优先判断微信结构 ★★★
        # 1. 尝试找微信公众号正文容器
        content_div = soup.find('div', id='js_content') or soup.find('div', class_='rich_media_content')
        if content_div:
            mode = "wechat"
        else:
            # 2. 如果没找到，再尝试找学校官网容器
            content_div = soup.find('div', class_='detail-con')
            if content_div:
                mode = "school_native"
        
        if not content_div:
            safe_print(f"   [警告] {safe_title} -> 无法识别页面结构 (可能不是微信也不是官网)")
            return

        # 创建文件夹
        os.makedirs(target_dir, exist_ok=True)

        # 提取文字
        text_content = content_div.get_text(separator="\n", strip=True)

        # 保存文本
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"标题: {title}\n")
            f.write(f"日期: {date}\n")
            f.write(f"链接: {url}\n")
            f.write(f"来源模式: {mode} (优先微信)\n")
            f.write("-" * 40 + "\n\n")
            f.write(text_content)

        # 提取图片
        images = content_div.find_all('img')
        img_count = 0
        for i, img in enumerate(images):
            src = ""
            if mode == "wechat":
                # 微信模式：必须优先取 data-src
                src = img.get('data-src') or img.get('src')
            else:
                # 官网模式：优先取 src
                src = img.get('src')
            
            if src:
                save_image(src, target_dir, i+1)
                img_count += 1
        
        safe_print(f" [成功] {date} | {safe_title}... [{mode} | 图:{img_count}]")

    except Exception as e:
        safe_print(f" [错误] {title} 解析失败: {e}")

def process_page(page_num):
    list_url = LIST_URL_TEMPLATE.format(page_num)
    safe_print(f"--> 读取列表: 第 {page_num} 页")
    
    try:
        resp = requests.get(list_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 列表解析逻辑通常是一样的 (<p class="h">)
        title_tags = soup.find_all('p', class_='h')
        valid_items = []
        
        for p_tag in title_tags:
            title = p_tag.get_text(strip=True)
            if not title: continue

            link_tag = p_tag.find_parent('a') or p_tag.find('a')
            if not link_tag: continue

            href = link_tag['href']
            full_url = urljoin(BASE_URL, href)

            container = link_tag.find_parent('li') or link_tag.parent.parent
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', container.get_text())
            date = date_match.group(0) if date_match else "Unknown_Date"

            valid_items.append({'title': title, 'date': date, 'url': full_url})

        # 并发后的串行执行
        for item in valid_items:
            parse_detail_page(item['url'], item['title'], item['date'])
            # time.sleep(0.1) 

    except Exception as e:
        safe_print(f"列表页 {page_num} 异常: {e}")

if __name__ == "__main__":
    if not os.path.exists(SAVE_ROOT): os.makedirs(SAVE_ROOT)
    
    # 微信头条的页数，请根据实际情况调整
    # 我刚才看了一下，大概有 16 页左右
    START_PAGE = 1
    END_PAGE = 137 
    MAX_WORKERS = 5
    
    print("="*60)
    print(f"保存路径: {SAVE_ROOT}")
    print(f"任务: 微信优先模式 | 第 {START_PAGE} - {END_PAGE} 页")
    print("="*60)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_page, page) 
                   for page in range(START_PAGE, END_PAGE + 1)]
        
        for future in futures:
            try: future.result()
            except: pass

    print("\n微信头条爬取完成！")