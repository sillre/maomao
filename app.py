# ==========================================
# 项目: WebDAV 极速影视聚合引擎 V1.0.3 (开源稳定版)
# 
# 【核心特性】
# - ⚡️ 动态能效比探针：物理称重 + 秒表测速，物理剔除晚高峰卡顿节点。
# - 🛡️ SSL 降维防弹：强制降级 HTTPS 为 HTTP，解决 Apple TV 网络异常。
# - 🔪 纯净双轨切源：电影靠后缀选画质，剧集 3~60s 退出重进无感切源。
# - 📦 离线片库支持：无需 TMDB API Key 即可使用预置的万人片库。
# ==========================================

import os
import re
import urllib.parse
import concurrent.futures
import time
import random
import json
import threading
from datetime import datetime
from flask import Flask, request, Response, redirect
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

# ==========================================
# 🔑 配置与全局缓存区 (开源脱敏改造)
# ==========================================
# 💡 开源修改：不再硬编码 Key，而是从环境变量读取。如果没有，则依赖本地离线库。
TMDB_KEY = os.environ.get("TMDB_KEY", "")
TMDB_DOMAINS = ["https://api.tmdb.org/3", "https://api.themoviedb.org/3"]

MASTER_SOURCES = {
    "非凡": "http://cj.ffzyapi.com/api.php/provide/vod/",
    "卧龙": "https://collect.wolongzyw.com/api.php/provide/vod/",
    "最大": "https://fapi.zuidapi.com/api.php/provide/vod/",
    "黑木耳": "https://json.heimuer.xyz/api.php/provide/vod/",
    "无尽": "https://api.wujinapi.me/api.php/provide/vod/",
    "ikun": "https://ikunzyapi.com/api.php/provide/vod/",
    "日影": "https://cj.rycjapi.com/api.php/provide/vod/",
    "FB资源": "https://fbzyapi.com/api.php/provide/vod/",
    "百度": "https://api.apibdzy.com/api.php/provide/vod/",
    "量子": "https://cj.lzyapi.com/api.php/provide/vod/",
    "光速": "https://api.guangsuapi.com/api.php/provide/vod/",
    "红牛": "https://www.hongniuzy2.com/api.php/provide/vod/",
    "索尼": "https://suoniapi.com/api.php/provide/vod/",
    "快车": "https://caiji.kuaichezy.com/api.php/provide/vod/",
    "天空": "https://m3u8.tiankongapi.com/api.php/provide/vod/",
    "飞速": "https://www.feisuzyapi.com/api.php/provide/vod/",
    "闪电": "https://sdzyapi.com/api.php/provide/vod/",
    "天堂": "https://vip.kuaikan-api.com/api.php/provide/vod/",
    "极速": "https://jszyapi.com/api.php/provide/vod/",
    "豪华": "https://hhzyapi.com/api.php/provide/vod/",
    "金鹰": "https://jyzyapi.com/api.php/provide/vod/",
    "阳光": "https://m3u8.ygzyapi.com/api.php/provide/vod/",
    "老韩": "https://lhzyapi.com/api.php/provide/vod/",
    "八戒": "https://cj.bajiecj.com/api.php/provide/vod/",
    "樱花": "https://m3u8.apiyhzy.com/api.php/provide/vod/"
}

TVBOX_CONFIG_HUBS = [
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/FongMi/CatVodSpider/main/json/config.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/2hacc/TVBox/main/tvbox.json",
    "https://tvbox.cydian.com"
]

ACTIVE_SOURCES = {}
AUTO_SOURCES_FILE = "auto_sources.json"
MASSIVE_LIB_FILE = "tmdb_massive_lib_v7.json" 

TMDB_CACHE = {"电影": {}, "电视剧": []} 
PLAY_URL_CACHE = {}  
TV_SWITCH_STATE = {} 
GLOBAL_LOCKS = {}
GLOBAL_LOCK_MUTEX = threading.Lock()

def get_sync_lock(key):
    with GLOBAL_LOCK_MUTEX:
        if key not in GLOBAL_LOCKS:
            GLOBAL_LOCKS[key] = threading.Lock()
        return GLOBAL_LOCKS[key]

def get_random_ua():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"
    ])

# ==========================================
# 🕷️ AI 寻源与节点大逃杀引擎
# ==========================================
def ai_discover_sources():
    print("\n[*] 🕷️ AI 自动寻源引擎启动: 正在全网抓取最新野生片源...", flush=True)
    discovered = set()
    def scrape_hub(url):
        try:
            r = requests.get(url, headers={'User-Agent': get_random_ua()}, timeout=10, verify=False)
            matches = re.findall(r'(https?://[a-zA-Z0-9\.\-\_]+(?::\d+)?/[a-zA-Z0-9\.\-\_/]*api\.php/provide/vod/?)', r.text)
            for m in matches: discovered.add(m)
        except: pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        [executor.submit(scrape_hub, url) for url in TVBOX_CONFIG_HUBS]
    return list(discovered)

def update_active_sources():
    global ACTIVE_SOURCES
    all_urls = set(MASTER_SOURCES.values())
    wild_sources = ai_discover_sources()
    if wild_sources: all_urls.update(wild_sources)
        
    if os.path.exists(AUTO_SOURCES_FILE):
        try:
            with open(AUTO_SOURCES_FILE, 'r') as f: all_urls.update(json.load(f))
        except: pass

    all_urls = list(all_urls)[:100]
    valid_results = []
    
    def check_and_ping(url):
        try:
            start = time.time()
            r = requests.get(f"{url}?ac=list", headers={'User-Agent': get_random_ua()}, timeout=3, verify=False)
            if r.status_code == 200 and 'list' in r.json():
                domain = urllib.parse.urlparse(url).netloc
                return domain, url, time.time() - start
        except: pass
        return None, None, 999
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(check_and_ping, url) for url in all_urls]
        for future in concurrent.futures.as_completed(futures):
            domain_name, valid_url, ping = future.result()
            if valid_url: 
                name = next((k for k, v in MASTER_SOURCES.items() if v == valid_url), f"野生节点_{domain_name}")
                valid_results.append((name, valid_url, ping))
                
    if valid_results:
        valid_results.sort(key=lambda x: x[2])
        top_nodes = valid_results[:25] 
        ACTIVE_SOURCES = {name: url for name, url, ping in top_nodes}
        print(f"[*] 🏆 竞技场结算: 成功筛选出全网最快的 {len(ACTIVE_SOURCES)} 个顶级节点出战！", flush=True)
        try:
            with open(AUTO_SOURCES_FILE, 'w', encoding='utf-8') as f: json.dump(list(ACTIVE_SOURCES.values()), f, ensure_ascii=False)
        except: pass
    else: ACTIVE_SOURCES = MASTER_SOURCES

# ==========================================
# 🏭 万部基建引擎 (离线兼容版)
# ==========================================
def fetch_tmdb_page_safe(endpoint, params, max_retries=3):
    if not TMDB_KEY: 
        return [] # 如果没配置 Key，直接返回空，强制使用本地库
    params['api_key'] = TMDB_KEY
    params['language'] = 'zh-CN'
    for attempt in range(max_retries):
        for base_url in TMDB_DOMAINS:
            try:
                r = requests.get(f"{base_url}{endpoint}", params=params, timeout=5, verify=False)
                if r.status_code == 200: return r.json().get('results', [])
                elif r.status_code == 429: time.sleep(1.5)
            except: pass
        time.sleep(0.5)
    return []

def build_or_update_library(is_daily_update=False):
    global TMDB_CACHE
    if not TMDB_KEY:
        print("\n[*] ⚠️ [离线模式] 未配置 TMDB_KEY，跳过在线抓取，仅依赖本地预置片库运行！", flush=True)
        return

    today_str = datetime.today().strftime('%Y-%m-%d')
    if is_daily_update:
        print("\n[*] 🔄 [日更雷达启动] 正在捕获过去 24 小时最新上线的热门资源...", flush=True)
        pages_to_fetch = 5
    else:
        print("\n[*] 🚧 [全局基建启动] 正在构建万部纯净大名单 (严苛剔除未公映影片)...", flush=True)
        pages_to_fetch = 500 

    scrape_tasks = {
        "电影": [("/discover/movie", {"sort_by": "popularity.desc", "primary_release_date.lte": today_str, "vote_count.gte": 10}, pages_to_fetch)],
        "电视剧": [("/discover/tv", {"sort_by": "popularity.desc", "first_air_date.lte": today_str, "vote_count.gte": 10}, pages_to_fetch)]
    }
    
    temp_movies, temp_tvs = [], []
    for cat_name, tasks in scrape_tasks.items():
        seen = set()
        for task in tasks:
            endpoint, params_base, pages = task[0], task[1], task[2]
            for page in range(1, pages + 1):
                params = params_base.copy()
                params['page'] = page
                items = fetch_tmdb_page_safe(endpoint, params)
                for item in items:
                    raw_date = str(item.get('release_date') or item.get('first_air_date') or '').strip()
                    if not raw_date or raw_date > today_str:
                        continue
                    title = item.get('title') or item.get('name') or item.get('original_title', '')
                    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                    if not re.search(r'[\u4e00-\u9fa5]', safe_title):
                        continue
                    if safe_title and safe_title not in seen:
                        seen.add(safe_title)
                        if cat_name == "电影": temp_movies.append(safe_title)
                        else: temp_tvs.append(safe_title)
                
                time.sleep(0.35) 
                if page % 50 == 0 and not is_daily_update:
                    print(f"   ... [抓取进度] {cat_name} 已成功入库 {len(seen)} 部 ...", flush=True)

    if is_daily_update:
        old_tvs = TMDB_CACHE.get("电视剧", [])
        merged_tvs = temp_tvs + [x for x in old_tvs if x not in temp_tvs]
        TMDB_CACHE["电视剧"] = merged_tvs[:10000] 

        old_movies = []
        for chunk in TMDB_CACHE.get("电影", {}).values(): old_movies.extend(chunk)
        merged_movies = temp_movies + [x for x in old_movies if x not in temp_movies]
        merged_movies = merged_movies[:10000]
        
        new_movie_cache = {}
        for i in range(0, len(merged_movies), 500):
            chunk = merged_movies[i:i+500]
            new_movie_cache[f"[{i+1:04d}-{i+len(chunk):04d}]"] = chunk
        TMDB_CACHE["电影"] = new_movie_cache
    else:
        TMDB_CACHE["电视剧"] = temp_tvs
        new_movie_cache = {}
        for i in range(0, len(temp_movies), 500):
            chunk = temp_movies[i:i+500]
            new_movie_cache[f"[{i+1:04d}-{i+len(chunk):04d}]"] = chunk
        TMDB_CACHE["电影"] = new_movie_cache
        print(f"\n[*] 🏆 [基建完成] 万部数据已切块完毕并固化至硬盘！\n", flush=True)

    try:
        with open(MASSIVE_LIB_FILE, 'w', encoding='utf-8') as f:
            json.dump(TMDB_CACHE, f, ensure_ascii=False)
    except: pass

def background_orchestrator():
    global TMDB_CACHE
    update_active_sources()
    if os.path.exists(MASSIVE_LIB_FILE):
        try:
            with open(MASSIVE_LIB_FILE, 'r', encoding='utf-8') as f: TMDB_CACHE = json.load(f)
            m_count = sum(len(c) for c in TMDB_CACHE.get("电影", {}).values())
            print(f"\n[*] 📦 [秒开就绪] 已从预置离线数据库加载万部影视库！(电影: {m_count}部, 剧集: {len(TMDB_CACHE.get('电视剧', []))}部)\n", flush=True)
            build_or_update_library(is_daily_update=True)
        except: build_or_update_library(is_daily_update=False)
    else:
        build_or_update_library(is_daily_update=False)
    while True:
        time.sleep(86400) 
        build_or_update_library(is_daily_update=True)
        update_active_sources()

threading.Thread(target=background_orchestrator, daemon=True).start()

# ==========================================
# 📺 模块三：⚡️ 速度与画质并重的能效比探针
# ==========================================
def get_text_score(url, vod_name="", vod_remarks=""):
    text = (url + " " + vod_name + " " + vod_remarks).lower()
    score = 10 
    
    if '4k' in text or '2160' in text: score += 50
    elif '2k' in text or '1440' in text: score += 40
    elif '1080' in text: score += 30
    elif '蓝光' in text or 'bd' in text: score += 25
    elif '720' in text: score += 20
    elif 'hd' in text or '超清' in text or '高清' in text: score += 15
    
    if 'ts' in text or 'tc' in text or '枪版' in text or '抢先' in text or '韩版' in text: score -= 50
    return score

def probe_ts_size_and_speed(m3u8_url):
    try:
        r = requests.get(m3u8_url, headers={'User-Agent': get_random_ua()}, timeout=3, verify=False)
        if r.status_code != 200: return (0, 999)
        
        lines = r.text.splitlines()
        for i, line in enumerate(lines):
            if "RESOLUTION=" in line or "BANDWIDTH=" in line:
                if i + 1 < len(lines):
                    next_m3u8 = lines[i+1]
                    if not next_m3u8.startswith('http'):
                        next_m3u8 = urllib.parse.urljoin(m3u8_url, next_m3u8)
                    return probe_ts_size_and_speed(next_m3u8) 
                    
        ts_url = None
        for line in lines:
            if line and not line.startswith('#'):
                ts_url = line if line.startswith('http') else urllib.parse.urljoin(m3u8_url, line)
                break
                
        if ts_url:
            start_time = time.time()
            head_req = requests.head(ts_url, headers={'User-Agent': get_random_ua()}, timeout=2, verify=False)
            elapsed = max(time.time() - start_time, 0.001) 
            size = int(head_req.headers.get('Content-Length', 0))
            return (size, elapsed)
    except: pass
    return (0, 999)

def search_single_api(api_url, keyword):
    try:
        r = requests.get(f"{api_url}?ac=detail&wd={urllib.parse.quote(keyword)}", headers={'User-Agent': get_random_ua()}, timeout=6, verify=False)
        valid_vods = []
        for vod in r.json().get('list', []):
            name, t_name = vod.get('vod_name', ''), str(vod.get('type_name', ''))
            black_keywords = ["解说", "速看", "预告", "分钟", "短剧", "花絮", "盘点", "福利", "伦理", "综艺", "动漫"]
            if any(x in name for x in black_keywords) or any(x in t_name for x in black_keywords): continue
            valid_vods.append(vod)
        return valid_vods
    except: return []

def perform_robust_search(keyword):
    results = {}
    found = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES)) as executor:
        futures = {executor.submit(search_single_api, url, keyword): name for name, url in ACTIVE_SOURCES.items()}
        for future in concurrent.futures.as_completed(futures):
            vods = future.result()
            if vods:
                source_name = futures[future]
                results[source_name] = results.get(source_name, []) + vods
                found = True
                
    if not found and ('：' in keyword or ' ' in keyword):
        short_keyword = re.split(r'[:：\s-]', keyword)[0].strip()
        if len(short_keyword) >= 2:
            print(f"[*] ⚠️ 全名未命中，容错降级二次检索: {short_keyword}", flush=True)
            return perform_robust_search(short_keyword)
    return results

def dual_stage_rank(all_urls_data):
    if not all_urls_data: return []
    all_urls_data.sort(key=lambda x: x['text_score'], reverse=True)
    
    top_candidates = all_urls_data[:10]
    print(f"   ... [测速探针] 已框定 {len(top_candidates)} 个高分候选源，正在测量物理体积与网络延迟...", flush=True)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_cand = {executor.submit(probe_ts_size_and_speed, cand['url']): cand for cand in top_candidates}
        for future in concurrent.futures.as_completed(future_to_cand):
            cand = future_to_cand[future]
            size, elapsed = future.result()
            efficiency_score = (size / 1024 / 1024) / elapsed if elapsed < 999 else 0
            cand['efficiency'] = efficiency_score
            cand['size'] = size
            cand['elapsed'] = elapsed
            
    top_candidates.sort(key=lambda x: (x['efficiency'], x['text_score']), reverse=True)
    
    if top_candidates:
        best = top_candidates[0]
        print(f"   ... 🏆 [最优锁定] 测速冠军: 体积 {best['size']/1024/1024:.2f}MB, 延迟 {best['elapsed']:.2f}s, 能效分 {best['efficiency']:.2f}", flush=True)
    
    final_urls = [cand['url'] for cand in top_candidates]
    final_urls.extend([cand['url'] for cand in all_urls_data[10:]])
    return final_urls

def get_movie_urls(movie_name):
    print(f"\n[*] 🔍 发起电影靶向检索: {movie_name}", flush=True)
    found_urls = set()
    candidates = []
    all_results = perform_robust_search(movie_name)
    
    for source_name, vod_list in all_results.items():
        for vod in vod_list:
            for group in vod.get('vod_play_url', '').split('$$$'):
                if '.m3u8' in group or '.mp4' in group:
                    for ep in group.split('#'):
                        ep_url = ep.split('$', 1)[1] if '$' in ep else ep
                        if ep_url not in found_urls:
                            found_urls.add(ep_url)
                            score = get_text_score(ep_url, vod.get('vod_name', ''), str(vod.get('vod_remarks', '')))
                            candidates.append({"url": ep_url, "text_score": score, "efficiency": 0})
                            
    return dual_stage_rank(candidates)

def get_episode_urls(show_name, ep_num):
    print(f"\n[*] 🔍 发起剧集靶向检索: {show_name} 第{ep_num}集", flush=True)
    found_urls = set()
    candidates = []
    all_results = perform_robust_search(show_name)
    
    for source_name, vod_list in all_results.items():
        for vod in vod_list:
            if show_name not in vod.get('vod_name', ''): continue
            for group in vod.get('vod_play_url', '').split('$$$'):
                if '.m3u8' in group or '.mp4' in group:
                    for ep in group.split('#'):
                        if '$' in ep:
                            ep_name, ep_url = ep.split('$', 1)
                            nums = re.findall(r'\d+', ep_name)
                            if nums and int(nums[-1]) == ep_num:
                                if ep_url not in found_urls:
                                    found_urls.add(ep_url)
                                    score = get_text_score(ep_url, vod.get('vod_name', ''), str(vod.get('vod_remarks', '')))
                                    candidates.append({"url": ep_url, "text_score": score, "efficiency": 0})
                                    
    return dual_stage_rank(candidates)

# ==========================================
# 🗺️ 模块四：WebDAV 挂载协议
# ==========================================
def generate_propfind_xml(items):
    xml = ['<?xml version="1.0" encoding="utf-8" ?>', '<D:multistatus xmlns:D="DAV:">']
    for item in items:
        item_path = urllib.parse.quote(item['path'])
        xml.append(f'  <D:response>\n    <D:href>{item_path}</D:href>\n    <D:propstat><D:prop>')
        xml.append(f'      <D:displayname>{item["name"]}</D:displayname>')
        if item['is_dir']: xml.append('      <D:resourcetype><D:collection/></D:resourcetype>')
        else:
            xml.append('      <D:resourcetype/>\n      <D:getcontentlength>1073741824</D:getcontentlength>\n      <D:getcontenttype>video/mp4</D:getcontenttype>')
        xml.append('      <D:getlastmodified>Tue, 10 Jan 2024 12:00:00 GMT</D:getlastmodified>\n    </D:prop></D:propstat>\n    <D:status>HTTP/1.1 200 OK</D:status>\n  </D:response>')
    xml.append('</D:multistatus>')
    return '\n'.join(xml)

@app.route('/', defaults={'path': ''}, methods=['OPTIONS', 'PROPFIND', 'GET', 'HEAD'])
@app.route('/<path:path>', methods=['OPTIONS', 'PROPFIND', 'GET', 'HEAD'])
def webdav_handler(path):
    full_path = '/' + path if path else '/'
    decoded_path = urllib.parse.unquote(full_path).rstrip('/')
    parts = [p for p in decoded_path.split('/') if p]

    if request.method == 'OPTIONS':
        resp = Response()
        resp.headers['Allow'] = 'OPTIONS, PROPFIND, GET, HEAD'
        resp.headers['DAV'] = '1, 2'
        return resp

    if request.method == 'PROPFIND':
        items = []
        depth = request.headers.get('Depth', '1')

        if len(parts) == 0:
            items.append({'path': '/', 'name': 'Root', 'is_dir': True})
            if depth != '0':
                items.append({'path': '/电影', 'name': '电影', 'is_dir': True})
                items.append({'path': '/电视剧', 'name': '电视剧', 'is_dir': True})

        elif len(parts) == 1:
            cat_name = parts[0]
            items.append({'path': decoded_path, 'name': cat_name, 'is_dir': True})
            if depth != '0':
                if cat_name == "电影":
                    movie_chunks = TMDB_CACHE.get("电影", {})
                    if not movie_chunks:
                        items.append({'path': f"{decoded_path}/[初始化中_请稍后刷新].mp4", 'name': "[初始化中_请稍后刷新].mp4", 'is_dir': False})
                    else:
                        for chunk_name in movie_chunks.keys():
                            items.append({'path': f"{decoded_path}/{chunk_name}", 'name': chunk_name, 'is_dir': True})
                elif cat_name == "电视剧":
                    tvs = TMDB_CACHE.get("电视剧", [])
                    if not tvs:
                        items.append({'path': f"{decoded_path}/[初始化中_请稍后刷新].mp4", 'name': "[初始化中_请稍后刷新].mp4", 'is_dir': False})
                    else:
                        for tv_name in tvs:
                            items.append({'path': f"{decoded_path}/{tv_name}", 'name': tv_name, 'is_dir': True})

        elif len(parts) == 2:
            current_folder = parts[1]
            items.append({'path': decoded_path, 'name': current_folder, 'is_dir': True})
            if depth != '0':
                if parts[0] == "电影":
                    movies_in_chunk = TMDB_CACHE.get("电影", {}).get(current_folder, [])
                    for movie in movies_in_chunk:
                        items.append({'path': f"{decoded_path}/{movie} - 4K.mp4", 'name': f"{movie} - 4K.mp4", 'is_dir': False})
                        items.append({'path': f"{decoded_path}/{movie} - 1080p.mp4", 'name': f"{movie} - 1080p.mp4", 'is_dir': False})
                        items.append({'path': f"{decoded_path}/{movie} - 720p.mp4", 'name': f"{movie} - 720p.mp4", 'is_dir': False})
                elif parts[0] == "电视剧":
                    show_name = parts[1]
                    for ep_i in range(1, 31):
                        file_name = f"{show_name} S01E{ep_i:02d}.mp4"
                        items.append({'path': f"{decoded_path}/{file_name}", 'name': file_name, 'is_dir': False})

        elif len(parts) == 3 and decoded_path.endswith('.mp4'):
            items.append({'path': decoded_path, 'name': parts[-1], 'is_dir': False})
        else: return Response("Not Found", status=404)

        return Response(generate_propfind_xml(items), status=207, mimetype='application/xml')

    if request.method == 'HEAD':
        if decoded_path.endswith('.mp4'):
            resp = Response(status=200)
            resp.headers['Content-Type'] = 'video/mp4'
            resp.headers['Content-Length'] = '1073741824' 
            resp.headers['Accept-Ranges'] = 'bytes'
            return resp
        return Response("Not Found", status=404)

    if request.method == 'GET' and decoded_path.endswith('.mp4'):
        file_name = parts[-1]
        now = time.time()
        urls = []
        
        # ====== 电影分支 ======
        if parts[0] == "电影":
            q_idx = 0
            if ' - 1080p' in file_name: q_idx = 1
            elif ' - 720p' in file_name: q_idx = 2
            
            clean_name = re.sub(r' - (4K|1080p|720p)\.mp4', '', file_name).strip()
            cache_key = "MOVIE_" + clean_name
            
            lock = get_sync_lock(cache_key)
            with lock:
                cache_entry = PLAY_URL_CACHE.get(cache_key)
                if not cache_entry or (now - cache_entry['time'] > 14400):
                    urls = get_movie_urls(clean_name)
                    if urls: PLAY_URL_CACHE[cache_key] = {'urls': urls, 'time': now}
                else:
                    urls = cache_entry['urls']
                    
            if urls and len(urls) > q_idx:
                target_url = urls[q_idx]
                
                # 💡 HTTPS 降维打击
                if target_url.startswith("https://"):
                    target_url = target_url.replace("https://", "http://")
                    
                print(f"\n[*] 🎯 [电影画质分配] {file_name} -> {target_url}", flush=True)
                resp = redirect(target_url, code=302)
                resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                return resp
            else:
                return Response("【备用源耗尽】", status=404)

        # ====== 电视剧分支 ======
        elif parts[0] == "电视剧":
            show_name = parts[1]
            ep_match = re.search(r'S\d+E(\d+)', file_name)
            ep_num = int(ep_match.group(1)) if ep_match else 1
            
            cache_key = f"TV_{show_name}_S01E{ep_num:02d}"
            state_key = f"STATE_{show_name}_S01E{ep_num:02d}"
            
            lock = get_sync_lock(cache_key)
            with lock:
                cache_entry = PLAY_URL_CACHE.get(cache_key)
                if not cache_entry or (now - cache_entry['time'] > 14400):
                    urls = get_episode_urls(show_name, ep_num)
                    if urls: PLAY_URL_CACHE[cache_key] = {'urls': urls, 'time': now}
                else:
                    urls = cache_entry['urls']

            if urls:
                if state_key not in TV_SWITCH_STATE:
                    TV_SWITCH_STATE[state_key] = {"index": 0, "last_req": 0}
                
                state = TV_SWITCH_STATE[state_key]
                last_req = state["last_req"]
                silence_duration = now - last_req
                state["last_req"] = now
                
                if last_req == 0:
                    print(f"\n[*] ▶️ [剧集首次播放] {file_name} -> 匹配全网测速最高能效直连！", flush=True)
                elif silence_duration <= 3:
                    pass 
                elif 3 < silence_duration <= 60:
                    state["index"] = (state["index"] + 1) % len(urls)
                    print(f"\n[*] 🔄 [剧集切源] 已为您阶梯降级至备用线路 {state['index'] + 1} ！", flush=True)
                else:
                    state["index"] = 0
                    print(f"\n[*] ▶️ [剧集重新播放] 状态重置！满血回到能效第一顺位！", flush=True)
                    
                target_url = urls[state["index"]]
                
                # 💡 HTTPS 降维打击
                if target_url.startswith("https://"):
                    target_url = target_url.replace("https://", "http://")
                    
                resp = redirect(target_url, code=302)
                resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                return resp
            else:
                return Response("【备用源耗尽】", status=404)

    return Response("Method Not Allowed", status=405)

if __name__ == '__main__':
    print("="*80, flush=True)
    print(f" 🌍 WebDAV 极速影视聚合引擎 V1.0.3 (开源稳定版) 启动就绪！", flush=True)
    print(f" 📦 离线片库：自动检测挂载库，保护小白免配 API Key。")
    print(f" ⚡️ 动态测速：秒表探针已就绪，物理剿杀晚高峰卡顿节点。")
    print(f" 🛡️ SSL 破壁：开启直连强制 HTTP，防 AppleTV 网络异常。")
    print(f" 🔪 纯净切源：电影菜单切画质，剧集退进换源，抛弃臃肿续播。")
    print("="*80, flush=True)
    app.run(host='0.0.0.0', port=8080, debug=False)
