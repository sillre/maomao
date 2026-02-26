# ==========================================
# 万部级 WebDAV 影视引擎 (终极防弹版)
# 1. 解说粉碎机：字面+M3U8真实时长双重校验，低于15分钟自动换源
# 2. 洗流引擎：精准剔除切片广告
# 3. 极简分类：支持 最新/热门/高分 独立文件夹
# ==========================================

import os
import re
import urllib.parse
import concurrent.futures
from flask import Flask, request, Response, redirect
import requests
import urllib3
from collections import Counter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

# ==========================================
# ⚙️ 核心 API 配置
# ==========================================
API_SOURCES = {
    "非凡": "http://cj.ffzyapi.com/api.php/provide/vod/",
    "卧龙": "https://collect.wolongzyw.com/api.php/provide/vod/",
    "最大": "https://fapi.zuidapi.com/api.php/provide/vod/",
    "黑木耳": "https://json.heimuer.xyz/api.php/provide/vod/",
    "无尽": "https://api.wujinapi.me/api.php/provide/vod/",
    "ikun": "https://ikunzyapi.com/api.php/provide/vod/",
    "日影": "https://cj.rycjapi.com/api.php/provide/vod/",
    "FB资源": "https://fbzyapi.com/api.php/provide/vod/",
    "百度": "https://api.apibdzy.com/api.php/provide/vod/"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://movie.douban.com/'
}

LIBRARY_CATEGORIES = {
    "🆕 最新上线电影": {"type": "movie", "tag": "最新", "sort": "time"},
    "🆕 最新开播剧集": {"type": "tv", "tag": "最新", "sort": "time"},
    "🎬 热门电影库": {"type": "movie", "tag": "热门", "sort": "recommend"},
    "🏆 高分电影榜": {"type": "movie", "tag": "豆瓣高分", "sort": "recommend"},
    "📺 热门电视剧": {"type": "tv", "tag": "热门", "sort": "recommend"},
    "🌍 经典纪录片": {"type": "tv", "tag": "纪录片", "sort": "recommend"}
}

DOUBAN_CHUNK_CACHE = {} 
TV_EPISODES_CACHE = {}

# ==========================================
# 1. M3U8 广告清洗与【时长检测引擎】
# ==========================================

def get_m3u8_duration(m3u8_url):
    """提取 m3u8 总时长(秒)，用于判定是否为解说/预告片"""
    try:
        r = requests.get(m3u8_url, headers=HEADERS, timeout=5, verify=False)
        content = r.text
        # 如果是主播放列表 (包含分辨率选择)，通常是正规大片，直接放行
        if "RESOLUTION=" in content: return 9999 
        # 累加所有的切片时长
        duration = sum(float(m) for m in re.findall(r'#EXTINF:([\d\.]+)', content))
        return duration
    except: return 0

def clean_m3u8_stream(m3u8_url):
    """剔除广告切片"""
    try:
        r = requests.get(m3u8_url, headers=HEADERS, timeout=8, verify=False)
        content = r.text
        if "RESOLUTION=" in content:
            for line in content.splitlines():
                if line.endswith('.m3u8'):
                    if not line.startswith('http'): line = f"{m3u8_url.rsplit('/', 1)[0]}/{line}"
                    return clean_m3u8_stream(line)
                    
        lines = content.splitlines()
        clean_lines, ts_urls = [], []
        base_path = m3u8_url.rsplit('/', 1)[0]
        
        for line in lines:
            if not line.startswith('#') and line.strip():
                ts_urls.append(line if line.startswith('http') else f"{base_path}/{line}")
                
        if not ts_urls: return content
        
        domains = [urllib.parse.urlparse(url).netloc for url in ts_urls if url.startswith('http')]
        if not domains: return content
        main_domain = Counter(domains).most_common(1)[0][0]
        
        for line in lines:
            if line.startswith('#EXT-X-DISCONTINUITY'): continue
            if line.startswith('#EXTINF'):
                clean_lines.append(line)
                continue
                
            if not line.startswith('#') and line.strip():
                ts_url = line if line.startswith('http') else f"{base_path}/{line}"
                if urllib.parse.urlparse(ts_url).netloc != main_domain:
                    if clean_lines and clean_lines[-1].startswith('#EXTINF'): clean_lines.pop()
                    continue
                clean_lines.append(ts_url)
            else:
                clean_lines.append(line)
        return '\n'.join(clean_lines)
    except: return None

@app.route('/proxy/m3u8')
def proxy_m3u8():
    url = request.args.get('url')
    if not url: return "Missing URL", 400
    cleaned = clean_m3u8_stream(url)
    if cleaned: return Response(cleaned, mimetype='application/vnd.apple.mpegurl')
    return redirect(url, code=302)

# ==========================================
# 2. 豆瓣引擎
# ==========================================
def fetch_douban_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200: return []
        return [re.sub(r'[\\/*?:"<>|]', "", i.get('title', '')).strip() for i in r.json().get('subjects', [])]
    except: return []

def fetch_douban_chunk(tag, is_movie, offset=0, count=1000, sort_method="recommend"):
    cache_key = f"{tag}_{sort_method}_{offset}_{count}"
    if cache_key in DOUBAN_CHUNK_CACHE: return DOUBAN_CHUNK_CACHE[cache_key]
    t_type = "movie" if is_movie else "tv"
    urls = [f"https://movie.douban.com/j/search_subjects?type={t_type}&tag={urllib.parse.quote(tag)}&sort={sort_method}&page_limit=50&page_start={i}" for i in range(offset, offset + count, 50)]

    print(f"\n[*] 🌊 正在拉取 豆瓣 {tag} ({sort_method}) 第 {offset+1}-{offset+count} 部...")
    results, seen = [], set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for f in [executor.submit(fetch_douban_page, url) for url in urls]:
            for name in f.result():
                if name and name not in seen:
                    seen.add(name)
                    results.append(name)
    if not results: results = ["豆瓣接口限制_请稍后再试"]
    DOUBAN_CHUNK_CACHE[cache_key] = results
    return results

# ==========================================
# 3. 搜索与【解说粉碎机】引擎
# ==========================================
def search_single_api(api_url, keyword):
    try:
        r = requests.get(f"{api_url}?ac=detail&wd={urllib.parse.quote(keyword)}", headers=HEADERS, timeout=6, verify=False)
        valid_vods = []
        for vod in r.json().get('list', []):
            name = vod.get('vod_name', '')
            t_name = str(vod.get('type_name', ''))
            # 【过滤第一层】：绝对不要解说、速看、预告片、短剧！
            if any(x in name for x in ["解说", "速看", "预告", "分钟"]): continue
            if any(x in t_name for x in ["解说", "短剧", "预告"]): continue
            valid_vods.append(vod)
        return valid_vods
    except: return []

def get_movie_stream(keyword):
    print(f"\n[▶ 寻址] 正在并发搜寻: {keyword}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(search_single_api, url, keyword) for url in API_SOURCES.values()]
        for future in concurrent.futures.as_completed(futures):
            for vod in future.result():
                if keyword not in vod.get('vod_name', ''): continue
                play_url_str = vod.get('vod_play_url', '')
                for group in play_url_str.split('$$$'):
                    if '.m3u8' in group or '.mp4' in group:
                        for ep in group.split('#'):
                            ep_url = ep.split('$', 1)[1] if '$' in ep else ep
                            # 【过滤第二层】：严格计算真实视频时长，少于 900秒(15分钟) 直接抛弃，找下一个！
                            if get_m3u8_duration(ep_url) >= 900:
                                return ep_url
                            else:
                                print(f" [!] 拦截到短视频/解说欺诈 ({ep_url})，自动换源中...")
    return None

def get_tv_episodes(keyword):
    print(f"\n[📂 剧集] 正在拉取全集: {keyword}")
    episodes_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(search_single_api, url, keyword): name for name, url in API_SOURCES.items()}
        for future in concurrent.futures.as_completed(futures):
            source_name = futures[future]
            for vod in future.result():
                if keyword not in vod.get('vod_name', ''): continue
                play_url_str = vod.get('vod_play_url', '')
                for group in play_url_str.split('$$$'):
                    if '.m3u8' in group or '.mp4' in group:
                        for ep in group.split('#'):
                            if '$' in ep:
                                ep_name, ep_url = ep.split('$', 1)
                                safe_ep_name = re.sub(r'[\\/*?:"<>|]', "", ep_name).strip()
                                episodes_dict[f"[{source_name}] {keyword}_{safe_ep_name}.mp4"] = ep_url
                        return episodes_dict 
    return episodes_dict

# ==========================================
# 4. WebDAV 路由核心
# ==========================================
def generate_propfind_xml(items):
    xml = ['<?xml version="1.0" encoding="utf-8" ?>', '<D:multistatus xmlns:D="DAV:">']
    for item in items:
        item_path = urllib.parse.quote(item['path'])
        xml.append('  <D:response>')
        xml.append(f'    <D:href>{item_path}</D:href>')
        xml.append('    <D:propstat><D:prop>')
        xml.append(f'      <D:displayname>{item["name"]}</D:displayname>')
        if item['is_dir']: xml.append('      <D:resourcetype><D:collection/></D:resourcetype>')
        else:
            xml.append('      <D:resourcetype/>')
            xml.append('      <D:getcontentlength>1073741824</D:getcontentlength>')
            xml.append('      <D:getcontenttype>video/mp4</D:getcontenttype>')
        xml.append('      <D:getlastmodified>Tue, 10 Jan 2024 12:00:00 GMT</D:getlastmodified>')
        xml.append('    </D:prop></D:propstat>')
        xml.append('    <D:status>HTTP/1.1 200 OK</D:status>')
        xml.append('  </D:response>')
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
                items.extend([
                    {'path': f"{decoded_path}/🔥 Top 1-1000 必看精选", 'name': '🔥 Top 1-1000 必看精选', 'is_dir': True},
                    {'path': f"{decoded_path}/📚 浩瀚片库 (1000部以外)", 'name': '📚 浩瀚片库 (1000部以外)', 'is_dir': True}
                ])

        elif len(parts) == 2 and parts[0] in LIBRARY_CATEGORIES:
            items.append({'path': decoded_path, 'name': parts[1], 'is_dir': True})
            if depth != '0':
                cat_name = parts[0]
                is_movie = (LIBRARY_CATEGORIES[cat_name]['type'] == 'movie')
                tag = LIBRARY_CATEGORIES[cat_name]['tag']
                sort_method = LIBRARY_CATEGORIES[cat_name].get('sort', 'recommend')
                
                offset = 0 if "1-1000" in parts[1] else 1000
                names = fetch_douban_chunk(tag, is_movie, offset=offset, count=1000, sort_method=sort_method)
                
                for name in names:
                    if is_movie: 
                        items.append({'path': f"{decoded_path}/{name}.mp4", 'name': f"{name}.mp4", 'is_dir': False})
                    else: 
                        items.append({'path': f"{decoded_path}/{name}", 'name': name, 'is_dir': True})

        elif len(parts) == 3 and not parts[-1].endswith('.mp4'):
            tv_name = parts[-1]
            items.append({'path': decoded_path, 'name': tv_name, 'is_dir': True})
            if depth != '0':
                if tv_name not in TV_EPISODES_CACHE:
                    TV_EPISODES_CACHE[tv_name] = get_tv_episodes(tv_name)
                episodes = TV_EPISODES_CACHE[tv_name]
                if not episodes: items.append({'path': f"{decoded_path}/未找到该剧源.mp4", 'name': "未找到该剧源.mp4", 'is_dir': False})
                else:
                    for ep_name in episodes.keys(): items.append({'path': f"{decoded_path}/{ep_name}", 'name': ep_name, 'is_dir': False})

        elif decoded_path.endswith('.mp4'):
            items.append({'path': decoded_path, 'name': parts[-1], 'is_dir': False})
        else: return Response("Not Found", status=404)

        return Response(generate_propfind_xml(items), status=207, mimetype='application/xml')

    if request.method in ['GET', 'HEAD']:
        if decoded_path.endswith('.mp4'):
            if len(parts) == 3: 
                movie_name = parts[-1].replace('.mp4', '')
                m3u8_url = get_movie_stream(movie_name)
            else: 
                tv_name = parts[-2]
                ep_file_name = parts[-1]
                m3u8_url = TV_EPISODES_CACHE.get(tv_name, {}).get(ep_file_name)

            if m3u8_url:
                proxy_url = f"/proxy/m3u8?url={urllib.parse.quote(m3u8_url)}"
                print(f" -> 🎉 投放纯净资源: {m3u8_url}\n")
                return redirect(proxy_url, code=302) 

    return Response("Method Not Allowed", status=405)

if __name__ == '__main__':
    print("="*75)
    print(" 🌍 WebDAV 影视终极引擎 (防弹洗流+解说过滤版) 启动就绪！")
    print("="*75)
    app.run(host='0.0.0.0', port=8080, debug=False)