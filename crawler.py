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
SAVE_ROOT = os.path.join(BASE_DIR, "Fudan_News_Data")

BASE_URL = "https://www.fdsm.fudan.edu.cn/AboutUs/"
LIST_URL_TEMPLATE = "https://www.fdsm.fudan.edu.cn/AboutUs/SchoolNews.html?p={}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

# 打印锁
print_lock = threading.Lock()

def safe_print(msg):
    with print_lock:
        print(msg)

# --- 2. 工具函数 ---

def clean_filename(text):
    """清理文件名"""
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
    """下载图片"""
    try:
        if not img_url: return
        full_url = urljoin(BASE_URL, img_url)
        ext = determine_ext(full_url)
        img_name = f"image_{index}{ext}"
        save_path = os.path.join(save_dir, img_name)

        # 如果图片已存在，跳过下载
        if os.path.exists(save_path):
            return

        resp = requests.get(full_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
    except:
        pass 

def parse_detail_page(url, title, date):
    """
    解析详情页
    ★ 核心修改：增加了【文件已存在检测】，实现断点续爬
    """
    try:
        # --- 1. 预计算路径，检查是否已爬取 ---
        month_str = date[:7] 
        # 强制截断，保持和之前逻辑一致
        safe_title = clean_filename(title)[:50] 
        folder_name = f"{date}_{safe_title}"
        target_dir = os.path.join(SAVE_ROOT, month_str, folder_name)
        content_file = os.path.join(target_dir, "content.txt")

        # ★★★ 续爬逻辑的核心 ★★★
        if os.path.exists(content_file):
            safe_print(f"   [跳过] (已存在) {safe_title}...")
            return

        # --- 2. 开始正式爬取 ---
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        mode = "unknown"
        content_div = soup.find('div', class_='detail-con')
        if content_div:
            mode = "school_native"
        else:
            content_div = soup.find('div', id='js_content')
            if content_div: mode = "wechat"
        
        if not content_div:
            safe_print(f"   [警告] {safe_title} -> 无法识别结构，跳过")
            return

        # 创建文件夹
        os.makedirs(target_dir, exist_ok=True)

        # 提取内容
        text_content = content_div.get_text(separator="\n", strip=True)

        # 保存文本 (实时保存)
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"标题: {title}\n")
            f.write(f"日期: {date}\n")
            f.write(f"链接: {url}\n")
            f.write(f"来源: {mode}\n")
            f.write("-" * 40 + "\n\n")
            f.write(text_content)

        # 提取并保存图片
        images = content_div.find_all('img')
        img_count = 0
        for i, img in enumerate(images):
            src = ""
            if mode == "wechat":
                src = img.get('data-src') or img.get('src')
            else:
                src = img.get('src')
            
            if src:
                save_image(src, target_dir, i+1)
                img_count += 1
        
        safe_print(f" [成功] {date} | {safe_title}... [图:{img_count}]")

    except Exception as e:
        safe_print(f" [错误] {title} 解析失败: {e}")

def process_single_page_list(page_num):
    """处理单个列表页"""
    list_url = LIST_URL_TEMPLATE.format(page_num)
    safe_print(f"--> 读取列表: 第 {page_num} 页")
    
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

            href = link_tag['href']
            full_url = urljoin(BASE_URL, href)

            container = link_tag.find_parent('li') or link_tag.parent.parent
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', container.get_text())
            date = date_match.group(0) if date_match else "Unknown_Date"

            valid_items.append({'title': title, 'date': date, 'url': full_url})

        # 在线程内顺序处理
        for item in valid_items:
            parse_detail_page(item['url'], item['title'], item['date'])
            # 如果文件已存在，上面的函数会秒退，这里几乎不耗时
            # 如果文件不存在，这里会正常爬取
            # 我们不需要加大的 sleep，因为跳过是非常快的

    except Exception as e:
        safe_print(f"列表页 {page_num} 异常: {e}")

if __name__ == "__main__":
    if not os.path.exists(SAVE_ROOT): os.makedirs(SAVE_ROOT)
    
    # 设定全量范围
    START_PAGE = 1
    END_PAGE = 396
    MAX_WORKERS = 5 # 并发数
    
    print("="*60)
    print(f"保存路径: {SAVE_ROOT}")
    print(f"任务范围: 第 {START_PAGE} - {END_PAGE} 页")
    print("支持断点续爬：已存在的文章会自动跳过。")
    print("="*60)

    # 记录总耗时
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_single_page_list, page) 
                   for page in range(START_PAGE, END_PAGE + 1)]
        
        # 等待完成
        for future in futures:
            try:
                future.result()
            except Exception:
                pass

    print(f"\n全部完成！总耗时: {time.time() - start_time:.2f}秒")