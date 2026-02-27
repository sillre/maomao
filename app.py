# ==========================================
# 版本: WebDAV 影视聚合引擎 V7.3 (终极形态版)
# 
# 【历史版本变更记录】
# - V6.9: 修复剧集空载超时问题，延时极速压缩。
# - V7.0: 洗流引擎引入目录频次指纹，彻底物理删除压制/切片广告。
# - V7.1: 新增“无缝切源弹夹”。
# - V7.2: 引入“画质权重打分引擎”，4K/1080P/蓝光强制排前，枪版/TS强制垫底。
#
# 【V7.3 当前更新内容】: 
#   1. 引入“Time-Lock 时间锁与双击切源”引擎。
#   2. 解决续播痛点：播放超过 60 秒后，自动固化锁定当前源站，下次续播绝不乱切，保证进度和画质连贯。
#   3. 操作革新：若遇卡顿需要切源，只需“退出视频，并在 60 秒内再次点击播放”，系统即刻为您切换下一个顶级源。
# ==========================================

import os
import re
import urllib.parse
import concurrent.futures
import time
import random
import json
import threading
from flask import Flask, request, Response, redirect
import requests
import urllib3
from collections import Counter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

# ==========================================
# ⚙️ 超大备胎库
# ==========================================
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
    "Libvio": "https://www.libvio.com/api.php/provide/vod/",
    "新厂长": "https://czzy.top/api.php/provide/vod/",
    "MonTV": "https://montv.api.com/api.php/provide/vod/",
    "闪电": "https://sdzyapi.com/api.php/provide/vod/",
    "天堂": "https://vip.kuaikan-api.com/api.php/provide/vod/",
    "极速": "https://jszyapi.com/api.php/provide/vod/",
    "豪华": "https://hhzyapi.com/api.php/provide/vod/",
    "金鹰": "https://jyzyapi.com/api.php/provide/vod/"
}

ACTIVE_SOURCES = {}

LIBRARY_CATEGORIES = {
    "🔥 全网源站实时热榜 (免豆瓣)": {"type": "cms_hot"},
    "🆕 最新上线电影": {"type": "movie", "tag": "最新", "sort": "time"},
    "🆕 最新开播剧集": {"type": "tv", "tag": "热门", "sort": "time"},
    "🎬 热门电影总榜": {"type": "movie", "tag": "热门", "sort": "recommend"},
    "🏆 豆瓣高分神作": {"type": "movie", "tag": "豆瓣高分", "sort": "recommend"},
    "🛸 科幻巨制精选": {"type": "movie", "tag": "科幻", "sort": "recommend"},
    "🔫 动作爆米花榜": {"type": "movie", "tag": "动作", "sort": "recommend"},
    "😂 喜剧欢乐精选": {"type": "movie", "tag": "喜剧", "sort": "recommend"},
    "👻 惊悚悬疑烧脑": {"type": "movie", "tag": "悬疑", "sort": "recommend"},
    "📺 热门国剧大全": {"type": "tv", "tag": "国产剧", "sort": "recommend"},
    "📺 经典美剧大片": {"type": "tv", "tag": "美剧", "sort": "recommend"},
    "🌸 高分动漫漫区": {"type": "tv", "tag": "日本动画", "sort": "recommend"},
    "🌍 经典纪录片库": {"type": "tv", "tag": "纪录片", "sort": "recommend"}
}

DOUBAN_LOCK = threading.Lock()
CACHE_FILE = "douban_cache_v6.json" 
DOUBAN_CACHE = {}

TV_EPISODES_CACHE = {}
MOVIE_STREAM_CACHE = {}

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            DOUBAN_CACHE = json.load(f)
    except: pass

def save_cache():
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(DOUBAN_CACHE, f, ensure_ascii=False, indent=2)
    except: pass

def get_random_ua():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/119.0.0.0 Safari/537.36"
    ])

# ==========================================
# 🚀 探针引擎
# ==========================================
def probe_single_source(name, url):
    try:
        start_time = time.time()
        r = requests.get(f"{url}?ac=list", headers={'User-Agent': get_random_ua()}, timeout=3, verify=False)
        if r.status_code == 200 and 'list' in r.json():
            return name, url, time.time() - start_time
    except: pass
    return name, None, 999

def update_active_sources():
    global ACTIVE_SOURCES
    print("\n[*] 🕵️‍♂️ 探针引擎启动: 正在全网扫描存活源站...")
    temp_sources = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(probe_single_source, name, url) for name, url in MASTER_SOURCES.items()]
        for future in concurrent.futures.as_completed(futures):
            name, valid_url, ping = future.result()
            if valid_url: temp_sources[name] = valid_url
                
    if temp_sources:
        ACTIVE_SOURCES = temp_sources
        print(f"[*] ✅ 探针报告: 成功筛选出 {len(ACTIVE_SOURCES)} 个高速存活节点！")
    else:
        ACTIVE_SOURCES = {"默认兜底": "http://cj.ffzyapi.com/api.php/provide/vod/"}

def background_probe_task():
    while True:
        time.sleep(43200)
        update_active_sources()

update_active_sources()
threading.Thread(target=background_probe_task, daemon=True).start()

# ==========================================
# 1. 数据获取引擎 
# ==========================================
def fetch_cms_hot_list():
    cache_key = "cms_global_hot_v5" 
    if cache_key in DOUBAN_CACHE: return DOUBAN_CACHE[cache_key]
    
    results = set()
    def fetch_single_cms(url):
        for page in range(1, 6):
            try:
                r = requests.get(f"{url}?ac=detail&pg={page}", headers={'User-Agent': get_random_ua()}, timeout=5, verify=False)
                if r.status_code == 200:
                    v_list = r.json().get('list', [])
                    if not v_list: break 
                    
                    for vod in v_list:
                        name = re.sub(r'[\\/*?:"<>|]', "", vod.get('vod_name', '')).strip()
                        t_name = str(vod.get('type_name', ''))
                        
                        black_keywords = ["解说", "速看", "预告", "分钟", "短剧", "花絮", "盘点", "合集", 
                                          "福利", "伦理", "综艺", "记录", "纪录", "动漫", "动画", "体育", 
                                          "音乐", "其他", "写真", "微电", "盲盒", "头条", "B站", "抖音", "快手"]
                        if any(x in name for x in black_keywords) or any(x in t_name for x in black_keywords): 
                            continue
                            
                        white_type_keywords = ["片", "电影", "剧", "连续剧", "TV"]
                        if not any(x in t_name for x in white_type_keywords):
                            continue 
                            
                        results.add(name)
            except: pass

    print(f"\n[*] 🚀 正在穿透 {len(ACTIVE_SOURCES)} 个存活源站，向下深挖 5 页进行全网海选...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES)) as executor:
        [executor.submit(fetch_single_cms, url) for url in ACTIVE_SOURCES.values()]
    
    final_list = list(results)
    if len(final_list) > 800: final_list = final_list[:800]
        
    if final_list:
        DOUBAN_CACHE[cache_key] = final_list
        save_cache()
        
    print(f"[*] ✅ 免豆瓣热榜提取完毕！最终斩获 {len(final_list)} 部纯净大片/热剧！")
    return final_list

def fetch_douban_chunk(tag, is_movie, offset=0, count=250, sort_method="recommend"):
    t_type = "movie" if is_movie else "tv"
    cache_key = f"{t_type}_{tag}_{sort_method}_{offset}_{count}"
    
    if cache_key in DOUBAN_CACHE: return DOUBAN_CACHE[cache_key]

    with DOUBAN_LOCK:
        if cache_key in DOUBAN_CACHE: return DOUBAN_CACHE[cache_key]
        
        urls = [f"https://movie.douban.com/j/search_subjects?type={t_type}&tag={urllib.parse.quote(tag)}&sort={sort_method}&page_limit=50&page_start={i}" for i in range(offset, offset + count, 50)]
        results, seen = [], set()
        
        for url in urls:
            try:
                time.sleep(random.uniform(0.4, 0.8))
                r = requests.get(url, headers={'User-Agent': get_random_ua(), 'Referer': 'https://movie.douban.com/'}, timeout=8)
                if r.status_code == 403: return ["豆瓣接口限制_请使用免豆瓣或稍后刷新"]
                if r.status_code == 200:
                    for i in r.json().get('subjects', []):
                        name = re.sub(r'[\\/*?:"<>|]', "", i.get('title', '')).strip()
                        if name and name not in seen:
                            seen.add(name); results.append(name)
            except: pass
            
        if results:
            DOUBAN_CACHE[cache_key] = results
            save_cache()
            return results
        return ["该分类豆瓣暂无数据_或接口异常"]

# ==========================================
# 2. 洗流与搜索引擎 
# ==========================================
def get_video_quality_score(url, vod_name=""):
    text = (url + " " + vod_name).lower()
    score = 10 
    if '4k' in text or '2160' in text: score += 40
    elif '1080' in text: score += 30
    elif '蓝光' in text or 'bd' in text: score += 25
    elif '720' in text: score += 20
    elif 'hd' in text or '超清' in text or '高清' in text: score += 15
    if 'ts' in text or 'tc' in text or '枪版' in text or '抢先' in text or '韩版' in text:
        score -= 50
    return score

def clean_m3u8_stream(m3u8_url):
    try:
        r = requests.get(m3u8_url, headers={'User-Agent': get_random_ua()}, timeout=8, verify=False)
        content = r.text
        if "RESOLUTION=" in content:
            for line in content.splitlines():
                if line.endswith('.m3u8'):
                    return clean_m3u8_stream(line if line.startswith('http') else f"{m3u8_url.rsplit('/', 1)[0]}/{line}")
                    
        lines = content.splitlines()
        base_path = m3u8_url.rsplit('/', 1)[0]
        ts_urls = [line if line.startswith('http') else f"{base_path}/{line}" for line in lines if not line.startswith('#') and line.strip()]
        if not ts_urls: return content
        
        dir_paths = [u.rsplit('/', 1)[0] for u in ts_urls]
        dir_counts = Counter(dir_paths)
        valid_dirs = {d for d, c in dir_counts.items() if c > (len(ts_urls) * 0.02) or c > 10}
        if not valid_dirs: valid_dirs = {dir_counts.most_common(1)[0][0]}
        
        clean_lines, has_vod_tag, i = [], False, 0
        while i < len(lines):
            line = lines[i].strip()
            if not line: i += 1; continue
            if line.startswith('#EXT-X-PLAYLIST-TYPE'):
                has_vod_tag = True; clean_lines.append(line)
            elif line.startswith('#EXTINF'):
                extinf_line = line
                i += 1
                if i < len(lines):
                    ts_url = lines[i].strip()
                    ts_url = ts_url if ts_url.startswith('http') else f"{base_path}/{ts_url}"
                    if ts_url.rsplit('/', 1)[0] in valid_dirs:
                        clean_lines.extend([extinf_line, ts_url])
            elif line.startswith('#EXTM3U') or line.startswith('#EXT-X-VERSION') or line.startswith('#EXT-X-TARGETDURATION') or line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                clean_lines.append(line)
            i += 1

        if not has_vod_tag and len(clean_lines) > 1: clean_lines.insert(1, "#EXT-X-PLAYLIST-TYPE:VOD")
        clean_lines.append("#EXT-X-ENDLIST")
        return '\n'.join(clean_lines)
    except: return None

def check_playability_and_duration(m3u8_url):
    try:
        r = requests.get(m3u8_url, headers={'User-Agent': get_random_ua()}, timeout=5, verify=False)
        if r.status_code != 200: return False
        content = r.text
        if "RESOLUTION=" in content: return True
        return sum(float(m) for m in re.findall(r'#EXTINF:([\d\.]+)', content)) >= 1800
    except: return False

@app.route('/proxy/m3u8')
def proxy_m3u8():
    url = request.args.get('url')
    cleaned = clean_m3u8_stream(url)
    if cleaned: return Response(cleaned, mimetype='application/vnd.apple.mpegurl')
    return redirect(url, code=302)

def search_single_api(api_url, keyword):
    try:
        r = requests.get(f"{api_url}?ac=detail&wd={urllib.parse.quote(keyword)}", headers={'User-Agent': get_random_ua()}, timeout=6, verify=False)
        valid_vods = []
        for vod in r.json().get('list', []):
            name, t_name = vod.get('vod_name', ''), str(vod.get('type_name', ''))
            black_keywords = ["解说", "速看", "预告", "分钟", "短剧", "花絮", "盘点", "合集", "福利", "伦理", "综艺", "记录", "动漫"]
            if any(x in name for x in black_keywords) or any(x in t_name for x in black_keywords): continue
            valid_vods.append(vod)
        return valid_vods
    except: return []

def get_movie_stream(keyword):
    if keyword not in MOVIE_STREAM_CACHE:
        seen_urls = set()
        url_scores = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES)) as executor:
            futures = [executor.submit(search_single_api, url, keyword) for url in ACTIVE_SOURCES.values()]
            for future in concurrent.futures.as_completed(futures):
                for vod in future.result():
                    if keyword not in vod.get('vod_name', ''): continue
                    for group in vod.get('vod_play_url', '').split('$$$'):
                        if '.m3u8' in group or '.mp4' in group:
                            for ep in group.split('#'):
                                ep_url = ep.split('$', 1)[1] if '$' in ep else ep
                                if ep_url not in seen_urls:
                                    seen_urls.add(ep_url)
                                    score = get_video_quality_score(ep_url, vod.get('vod_name', ''))
                                    url_scores.append((score, ep_url))
        
        if url_scores:
            url_scores.sort(key=lambda x: x[0], reverse=True)
            sorted_urls = [u for s, u in url_scores]
            MOVIE_STREAM_CACHE[keyword] = {"urls": sorted_urls, "index": 0, "last_time": 0}
            
    return MOVIE_STREAM_CACHE.get(keyword)

def get_tv_episodes(keyword):
    episodes_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES)) as executor:
        futures = {executor.submit(search_single_api, url, keyword): name for name, url in ACTIVE_SOURCES.items()}
        for future in concurrent.futures.as_completed(futures):
            for vod in future.result():
                if keyword not in vod.get('vod_name', ''): continue
                for group in vod.get('vod_play_url', '').split('$$$'):
                    if '.m3u8' in group or '.mp4' in group:
                        for ep in group.split('#'):
                            if '$' in ep:
                                ep_name, ep_url = ep.split('$', 1)
                                nums = re.findall(r'\d+', ep_name)
                                # 彻底修复 Python 3.9 的 f-string 报错
                                safe_ep_name = re.sub(r'[\\/*?:"<>|]', "", ep_name).strip()
                                std_name = f"第{nums[-1].zfill(2)}集.mp4" if nums else f"{safe_ep_name}.mp4"
                                
                                if std_name not in episodes_dict:
                                    episodes_dict[std_name] = {"url_scores": [], "seen_urls": set(), "index": 0, "last_time": 0}
                                
                                if ep_url not in episodes_dict[std_name]["seen_urls"]:
                                    episodes_dict[std_name]["seen_urls"].add(ep_url)
                                    score = get_video_quality_score(ep_url, vod.get('vod_name', ''))
                                    episodes_dict[std_name]["url_scores"].append((score, ep_url))

    for std_name in episodes_dict:
        episodes_dict[std_name]["url_scores"].sort(key=lambda x: x[0], reverse=True)
        episodes_dict[std_name]["urls"] = [u for s, u in episodes_dict[std_name]["url_scores"]]
        del episodes_dict[std_name]["url_scores"]
        del episodes_dict[std_name]["seen_urls"]
        
    return episodes_dict

# ==========================================
# 3. WebDAV 路由
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
                for cat in LIBRARY_CATEGORIES.keys(): items.append({'path': f"/{cat}", 'name': cat, 'is_dir': True})

        elif len(parts) == 1 and parts[0] in LIBRARY_CATEGORIES:
            items.append({'path': decoded_path, 'name': parts[0], 'is_dir': True})
            if depth != '0':
                cat_config = LIBRARY_CATEGORIES[parts[0]]
                if cat_config['type'] == 'cms_hot':
                    for name in fetch_cms_hot_list(): items.append({'path': f"{decoded_path}/{name}", 'name': name, 'is_dir': True})
                else:
                    for i in range(10):
                        start_idx = i * 250 + 1
                        end_idx = (i + 1) * 250
                        prefix = "🔥" if i == 0 else "📚"
                        folder_name = f"{prefix} Top {start_idx}-{end_idx}"
                        items.append({'path': f"{decoded_path}/{folder_name}", 'name': folder_name, 'is_dir': True})

        elif len(parts) == 2 and parts[0] in LIBRARY_CATEGORIES:
            items.append({'path': decoded_path, 'name': parts[1], 'is_dir': True})
            if depth != '0':
                cat_config = LIBRARY_CATEGORIES[parts[0]]
                if cat_config['type'] == 'cms_hot':
                    name = parts[1]
                    if name not in TV_EPISODES_CACHE: TV_EPISODES_CACHE[name] = get_tv_episodes(name)
                    episodes = TV_EPISODES_CACHE[name]
                    if not episodes: items.append({'path': f"{decoded_path}/未找到有效源.mp4", 'name': "未找到有效源.mp4", 'is_dir': False})
                    else:
                        for ep_name in episodes.keys(): items.append({'path': f"{decoded_path}/{ep_name}", 'name': ep_name, 'is_dir': False})
                else:
                    match = re.search(r'Top (\d+)-', parts[1])
                    offset = int(match.group(1)) - 1 if match else 0
                    
                    for name in fetch_douban_chunk(cat_config['tag'], (cat_config['type'] == 'movie'), offset=offset, count=250, sort_method=cat_config['sort']):
                        if cat_config['type'] == 'movie': items.append({'path': f"{decoded_path}/{name}.mp4", 'name': f"{name}.mp4", 'is_dir': False})
                        else: items.append({'path': f"{decoded_path}/{name}", 'name': name, 'is_dir': True})

        elif len(parts) == 3:
            if decoded_path.endswith('.mp4'):
                items.append({'path': decoded_path, 'name': parts[-1], 'is_dir': False})
            else:
                tv_name = parts[-1]
                items.append({'path': decoded_path, 'name': tv_name, 'is_dir': True})
                if depth != '0':
                    if tv_name not in TV_EPISODES_CACHE: TV_EPISODES_CACHE[tv_name] = get_tv_episodes(tv_name)
                    episodes = TV_EPISODES_CACHE[tv_name]
                    if not episodes: items.append({'path': f"{decoded_path}/未找到该源或时长过短.mp4", 'name': "未找到该源或时长过短.mp4", 'is_dir': False})
                    else:
                        for ep_name in sorted(episodes.keys()): items.append({'path': f"{decoded_path}/{ep_name}", 'name': ep_name, 'is_dir': False})

        elif len(parts) == 4 and decoded_path.endswith('.mp4'):
            items.append({'path': decoded_path, 'name': parts[-1], 'is_dir': False})
        else: return Response("Not Found", status=404)

        return Response(generate_propfind_xml(items), status=207, mimetype='application/xml')

    # 【V7.3 核心：Time-Lock 固化续播与双击切源】
    if request.method in ['GET', 'HEAD']:
        if decoded_path.endswith('.mp4'):
            parent_dir = parts[-2]
            file_name = parts[-1]
            m3u8_url = None
            
            ep_data = TV_EPISODES_CACHE.get(parent_dir, {}).get(file_name)
            if not ep_data:
                movie_name = file_name.replace('.mp4', '')
                ep_data = get_movie_stream(movie_name)
                
            if ep_data and ep_data.get("urls"):
                urls = ep_data["urls"]
                last_time = ep_data.get("last_time", 0)
                now = time.time()
                
                # 判断用户是在“续播”还是在“请求切源”
                # 如果用户距离上次点击不足 60 秒，说明遇到了卡顿在强制切源
                is_switching = (last_time > 0 and (now - last_time) < 60)
                
                # 如果切源，从下一个节点开始找；如果是续播，从记录的稳固节点找
                check_start = (ep_data["index"] + 1) % len(urls) if is_switching else ep_data["index"]
                
                for i in range(len(urls)):
                    curr_idx = (check_start + i) % len(urls)
                    test_url = urls[curr_idx]
                    
                    if check_playability_and_duration(test_url):
                        ep_data["index"] = curr_idx   # 固化稳固源
                        ep_data["last_time"] = now    # 更新播放时间锁
                        m3u8_url = test_url
                        break
                        
            if m3u8_url: return redirect(f"/proxy/m3u8?url={urllib.parse.quote(m3u8_url)}", code=302) 
            return Response("所有节点均不可用或已被过滤", status=404)

    return Response("Method Not Allowed", status=405)

if __name__ == '__main__':
    print("="*75)
    print(f" 🌍 WebDAV 影视终极引擎 V7.3 (固化源站与画质优选版) 启动就绪！")
    print("="*75)
    app.run(host='0.0.0.0', port=8080, debug=False)
