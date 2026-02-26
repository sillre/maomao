# ==========================================
# 版本: WebDAV 影视聚合引擎 V6.9 (最终完善版)
# 
# 【历史版本变更记录】
# - V6.0: 引入 AI 自动探针，自动剔除死链、超时、失效域名。
# - V6.5: 解除 500 部限制，采用深度分页架构，总容量扩充至近 30,000 部。
# - V6.6: 引入“黑白双名单”机制，只允许分类带“片/剧/电影”的资源放行，彻底绞杀综艺和短剧。
# - V6.7: “免豆瓣热榜”引入 pg 深度分页抓取，容量从几十部暴增至近千部。
# - V6.8: 修复豆瓣缓存键值遗漏 t_type 导致“最新电影”与“最新剧集”混淆碰撞的 Bug。
#
# 【V6.9 当前更新内容】: 
#   1. 修复“最新开播剧集”无法获取的问题：豆瓣 TV 类无“最新”标签，修正为“热门”+ sort=time。
#   2. 优化 PROPFIND 超时：将抓取延时从 2.5s 压缩至 0.4-0.8s，防止 VidHub 等待超 10s 断开连接。
#   3. 升级主缓存文件名为 douban_cache_v6.json，强行清空旧的空载缓存。
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
# ⚙️ 超大备胎库 (自动测试，死的丢弃，活的选用)
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

# 💎 海量垂类矩阵 (总计近 30000 部)
LIBRARY_CATEGORIES = {
    "🔥 全网源站实时热榜 (免豆瓣)": {"type": "cms_hot"},
    "🆕 最新上线电影": {"type": "movie", "tag": "最新", "sort": "time"},
    # 【V6.9 修复】豆瓣TV没有"最新"标签，改为"热门"并按时间排序即可获取最新剧集
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
# 【V6.9 更新】修改主缓存文件名，彻底抛弃之前因为标签错误导致的空载数据
CACHE_FILE = "douban_cache_v6.json" 
DOUBAN_CACHE = {}
TV_EPISODES_CACHE = {}

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
        
        print(f"\n[*] 🌊 [后台建库] 正在抓取豆瓣 {t_type} 类的 {tag} (第{offset+1}到{offset+count}部) ...")
        for url in urls:
            try:
                # 【V6.9 核心优化】延时压缩至 0.4-0.8 秒，总耗时控制在 4 秒内，防止播放器 PROPFIND 超时断连
                time.sleep(random.uniform(0.4, 0.8))
                r = requests.get(url, headers={'User-Agent': get_random_ua(), 'Referer': 'https://movie.douban.com/'}, timeout=8)
                if r.status_code == 403: 
                    print(" [!] 触发限流，避险中...")
                    return ["豆瓣接口限制_请使用免豆瓣或稍后刷新"]
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
            
        # 如果豆瓣确实没有返回数据（例如非法tag组合）
        print(" [!] 警告：豆瓣 API 未返回任何数据。")
        return ["该分类豆瓣暂无数据_或接口异常"]

# ==========================================
# 2. 洗流与搜索引擎
# ==========================================
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
        
        main_domain = Counter([urllib.parse.urlparse(u).netloc for u in ts_urls]).most_common(1)[0][0]
        clean_lines, has_vod_tag, i = [], False, 0
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1; continue
            if line.startswith('#EXT-X-PLAYLIST-TYPE'):
                has_vod_tag = True; clean_lines.append(line)
            elif line.startswith('#EXTINF'):
                extinf_line = line
                i += 1
                if i < len(lines):
                    ts_url = lines[i].strip()
                    ts_url = ts_url if ts_url.startswith('http') else f"{base_path}/{ts_url}"
                    if urllib.parse.urlparse(ts_url).netloc == main_domain:
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES)) as executor:
        futures = [executor.submit(search_single_api, url, keyword) for url in ACTIVE_SOURCES.values()]
        for future in concurrent.futures.as_completed(futures):
            for vod in future.result():
                if keyword not in vod.get('vod_name', ''): continue
                for group in vod.get('vod_play_url', '').split('$$$'):
                    if '.m3u8' in group or '.mp4' in group:
                        for ep in group.split('#'):
                            ep_url = ep.split('$', 1)[1] if '$' in ep else ep
                            if check_playability_and_duration(ep_url): return ep_url
    return None

def get_tv_episodes(keyword):
    episodes_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES)) as executor:
        futures = {executor.submit(search_single_api, url, keyword): name for name, url in ACTIVE_SOURCES.items()}
        for future in concurrent.futures.as_completed(futures):
            source_name = futures[future]
            for vod in future.result():
                if keyword not in vod.get('vod_name', ''): continue
                for group in vod.get('vod_play_url', '').split('$$$'):
                    if '.m3u8' in group or '.mp4' in group:
                        for ep in group.split('#'):
                            if '$' in ep:
                                ep_name, ep_url = ep.split('$', 1)
                                safe_ep_name = re.sub(r'[\\/*?:"<>|]', "", ep_name).strip()
                                episodes_dict[f"[{source_name}] {keyword}_{safe_ep_name}.mp4"] = ep_url
                        return episodes_dict 
    return episodes_dict

# ==========================================
# 3. WebDAV 路由 (海量深潜架构)
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

        # 根目录：展示十几大分类
        if len(parts) == 0:
            items.append({'path': '/', 'name': 'Root', 'is_dir': True})
            if depth != '0':
                for cat in LIBRARY_CATEGORIES.keys(): items.append({'path': f"/{cat}", 'name': cat, 'is_dir': True})

        # 一级目录：生成 10 个深度分页文件夹
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

        # 二级目录：提取数据
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

        # 三级目录：如果是电视剧，点进去展开集数
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
                        for ep_name in episodes.keys(): items.append({'path': f"{decoded_path}/{ep_name}", 'name': ep_name, 'is_dir': False})

        elif len(parts) == 4 and decoded_path.endswith('.mp4'):
            items.append({'path': decoded_path, 'name': parts[-1], 'is_dir': False})
        else: return Response("Not Found", status=404)

        return Response(generate_propfind_xml(items), status=207, mimetype='application/xml')

    if request.method in ['GET', 'HEAD']:
        if decoded_path.endswith('.mp4'):
            parent_dir = parts[-2]
            file_name = parts[-1]
            m3u8_url = TV_EPISODES_CACHE.get(parent_dir, {}).get(file_name)
            
            if not m3u8_url:
                movie_name = file_name.replace('.mp4', '')
                m3u8_url = get_movie_stream(movie_name)
                
            if m3u8_url: return redirect(f"/proxy/m3u8?url={urllib.parse.quote(m3u8_url)}", code=302) 

    return Response("Method Not Allowed", status=405)

if __name__ == '__main__':
    print("="*75)
    print(f" 🌍 WebDAV 影视终极引擎 V6.9 (最终完善版) 启动就绪！")
    print("="*75)
    app.run(host='0.0.0.0', port=8080, debug=False)
