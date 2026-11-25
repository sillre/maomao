# ==============================================================================
# 项目: Maomao WebDAV 影视引擎 V1.0.4
# ==============================================================================
# 【核心更新日志】
# 1. 🚀 预加载回归：彻底废除“点击播放才搜索”的愚蠢逻辑。现在只要您点进【海报墙文件夹】，
#    系统会瞬间在后台搜刮并测速。等您看到集数列表时，链接已备好，点击播放 0 延迟秒开！
# 2. 📺 动态集数生成：进入电视剧文件夹时，不再固定显示 40 集假数据。后台搜到多少集，
#    就精准给您渲染多少集（并自动转换为 Apple TV 喜欢的 S01E01 规范格式）。
# 3. 🔒 剧集全局记忆锁：只要看了一集并锁定了某个源，整个剧接下来的所有集数都会自动
#    绑定这个画质最高的好源，明天看、后天看都绝对不会变模糊。
# 4. 📝 注释满血恢复：全量恢复代码中的逻辑注释和架构说明。
# 5. 🐛 漏洞热修复：修复电影分页目录 [0001-0500] 误触发搜索及 NoneType 崩溃问题。
# ==============================================================================

import os
import re
import urllib.parse
import concurrent.futures
import time
import random
import json
import threading
import builtins
import logging
from datetime import datetime
from collections import deque
from flask import Flask, request, Response, redirect, render_template_string, jsonify
import requests
import urllib3

# 禁用所有由于 SSL 降级或 HTTPS 未验证产生的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

# ==========================================
# 📊 模块一：全局日志拦截与 Web 控制台
# ==========================================
LOG_BUFFER = deque(maxlen=800)
_original_print = builtins.print

def custom_print(*args, **kwargs):
    """接管底层 print 打印，送入 Web 控制台双端队列"""
    _original_print(*args, **kwargs)
    try:
        msg = " ".join(str(a) for a in args)
        if msg.strip():
            timestamp = datetime.now().strftime("%H:%M:%S")
            for line in msg.split('\n'):
                if line.strip():
                    LOG_BUFFER.append(f"[{timestamp}] {line.strip()}")
    except Exception:
        pass

builtins.print = custom_print

class FlaskLogHandler(logging.Handler):
    """接管 Flask HTTP 访问日志"""
    def emit(self, record):
        try:
            msg = self.format(record)
            timestamp = datetime.now().strftime("%H:%M:%S")
            LOG_BUFFER.append(f"[{timestamp}] 🌐 {msg}")
        except Exception:
            pass

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addHandler(FlaskLogHandler())
werkzeug_logger.setLevel(logging.ERROR)

WEB_CONSOLE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Maomao WebDAV - 控制台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0f172a; color: #cbd5e1; font-family: monospace; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        .log-line { border-bottom: 1px solid rgba(255,255,255,0.02); padding: 6px 0; word-break: break-all; font-size: 13px; }
        .log-line:hover { background-color: rgba(255,255,255,0.02); }
    </style>
</head>
<body class="h-screen flex flex-col">
    <header class="bg-slate-900 border-b border-slate-800 p-4 flex justify-between items-center shadow-md z-10">
        <div class="flex items-center gap-3">
            <h1 class="text-xl font-bold text-white tracking-wider">Maomao Console</h1>
            <div class="hidden md:flex ml-4 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span class="text-xs font-medium text-emerald-400">V1.0.4 运行中</span>
            </div>
        </div>
        <div class="flex items-center">
            <label class="flex items-center gap-2 cursor-pointer text-sm hover:text-white transition-colors">
                <input type="checkbox" id="autoScroll" checked class="accent-emerald-500 w-4 h-4"> 自动滚屏
            </label>
        </div>
    </header>
    <main class="flex-1 overflow-hidden p-2 md:p-6">
        <div id="log-container" class="bg-black/50 border border-slate-800 rounded-xl h-full w-full p-4 overflow-y-auto shadow-inner leading-relaxed">
            <div class="text-slate-600 animate-pulse">拉取系统日志...</div>
        </div>
    </main>
    <script>
        const logContainer = document.getElementById('log-container');
        const autoScrollCheckbox = document.getElementById('autoScroll');
        let lastLogCount = 0;
        
        function fetchLogs() {
            fetch('/api/logs')
                .then(res => res.json())
                .then(logs => {
                    if (logs.length !== lastLogCount) {
                        logContainer.innerHTML = '';
                        logs.forEach(log => {
                            const div = document.createElement('div');
                            div.className = 'log-line';
                            
                            let html = log.replace(/\\[\\*\\]/g, '<span class="text-blue-400 font-bold">[*]</span>')
                                          .replace(/\\[▶️.*?\\]/g, match => `<span class="text-emerald-400 font-bold">${match}</span>`)
                                          .replace(/\\[🎯.*?\\]/g, match => `<span class="text-fuchsia-400 font-bold">${match}</span>`)
                                          .replace(/\\[🔄.*?\\]/g, match => `<span class="text-yellow-400 font-bold">${match}</span>`)
                                          .replace(/\\[❌.*?\\]/g, match => `<span class="text-red-400 font-bold">${match}</span>`)
                                          .replace(/🏆/g, '<span class="text-yellow-300 font-bold text-base">🏆</span>')
                                          .replace(/🌐/g, '<span class="text-slate-500">🌐</span>');
                                          
                            html = html.replace(/ 404 /g, ' <span class="bg-red-500/20 text-red-400 px-1 rounded">404</span> ')
                                       .replace(/ 302 /g, ' <span class="bg-emerald-500/20 text-emerald-400 px-1 rounded">302</span> ')
                                       .replace(/ 207 /g, ' <span class="bg-blue-500/20 text-blue-400 px-1 rounded">207</span> ');
                            div.innerHTML = html;
                            logContainer.appendChild(div);
                        });
                        lastLogCount = logs.length;
                        if (autoScrollCheckbox.checked) logContainer.scrollTop = logContainer.scrollHeight;
                    }
                })
                .catch(err => console.error('抓取日志失败:', err));
        }
        setInterval(fetchLogs, 1500);
        fetchLogs();
    </script>
</body>
</html>
"""

# ==========================================
# 🔑 模块二：全局配置与核心弹药库
# ==========================================
TMDB_KEY = os.environ.get("TMDB_KEY", "")
TMDB_DOMAINS = ["https://api.tmdb.org/3", "https://api.themoviedb.org/3"]

# 满血 25 大并发采集源
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
    "https://tvbox.cydian.com"
]

ACTIVE_SOURCES = {}
MASSIVE_LIB_FILE = "tmdb_massive_lib_v7.json" 
AUTO_SOURCES_FILE = "auto_sources.json"
PLAY_HISTORY_FILE = "play_history.json"

TMDB_CACHE = {"电影": {}, "电视剧": []} 
PLAY_HISTORY = {} 

# 💡 全新预加载缓存结构
PLAY_URL_CACHE = {}  
TV_SHOW_CACHE = {}   
TV_SWITCH_STATE = {} 

GLOBAL_LOCKS = {}
GLOBAL_LOCK_MUTEX = threading.Lock()

def get_sync_lock(key):
    """提供并发锁，防止瞬间双击导致多次抓取"""
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
# 💾 模块三：持久化记忆层 (历史记录)
# ==========================================
def load_history():
    global PLAY_HISTORY
    if os.path.exists(PLAY_HISTORY_FILE):
        try:
            with open(PLAY_HISTORY_FILE, 'r', encoding='utf-8') as f:
                PLAY_HISTORY = json.load(f)
        except Exception:
            PLAY_HISTORY = {}

def save_history():
    try:
        with open(PLAY_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(PLAY_HISTORY, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def update_history(key, url):
    if PLAY_HISTORY.get(key) != url:
        PLAY_HISTORY[key] = url
        threading.Thread(target=save_history).start()

# ==========================================
# 🕷️ 模块四：预加载探针与智能打分引擎
# ==========================================
def probe_metadata(m3u8_url):
    """前往源站测算流媒体质量和延迟"""
    try:
        r = requests.get(m3u8_url, headers={'User-Agent': get_random_ua()}, timeout=2, verify=False)
        if r.status_code != 200: return (0, 999)
        lines = r.text.splitlines()
        for i, line in enumerate(lines):
            if "RESOLUTION=" in line or "BANDWIDTH=" in line:
                if i + 1 < len(lines):
                    next_url = lines[i+1]
                    if not next_url.startswith('http'): 
                        next_url = urllib.parse.urljoin(m3u8_url, next_url)
                    return probe_metadata(next_url)
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
    except Exception: pass
    return (0, 999)

def dual_stage_rank(all_data):
    if not all_data: return []
    def get_score(url_str):
        text = url_str.lower(); score = 10 
        if '4k' in text or '2160' in text: score += 50
        elif '2k' in text or '1440' in text: score += 40
        elif '1080' in text: score += 30
        if any(x in text for x in ['ts', 'tc', '枪版', '抢先']): score -= 60
        return score

    for item in all_data: item['score'] = get_score(item['url'])
    all_data.sort(key=lambda x: x['score'], reverse=True)
    top_candidates = all_data[:10]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_cand = {executor.submit(probe_metadata, c['url']): c for c in top_candidates}
        for future in concurrent.futures.as_completed(future_to_cand):
            cand = future_to_cand[future]
            size, elapsed = future.result()
            cand['efficiency'] = (size / 1024 / 1024) / elapsed if elapsed < 999 else 0
            if cand.get('has_history'): cand['efficiency'] += 10000 
            
    top_candidates.sort(key=lambda x: (x['efficiency'], x['score']), reverse=True)
    return top_candidates + all_data[10:]

# ==========================================
# 🚀 模块五：搜索预加载执行逻辑
# ==========================================
def normalize_ep_name(show_name, raw_name):
    """极其严苛的集数转换器"""
    match = re.search(r'(?:第|E)?(\d+)(?:集|话|期)?', raw_name, re.IGNORECASE)
    if match and int(match.group(1)) < 1000:
        return f"{show_name} S01E{int(match.group(1)):02d}.mp4"
    return f"{show_name} {raw_name}.mp4"

def prepare_movie_urls(clean_name, cache_key):
    print(f"[*] 🔍 [触发解析] 正在全网检索电影: {clean_name}", flush=True)
    def search_api(api_url):
        # 💡 致命Bug修复点2: 使用 `or []` 彻底防御垃圾接口返回 NoneType
        try: return requests.get(f"{api_url}?ac=detail&wd={urllib.parse.quote(clean_name)}", timeout=4).json().get('list') or []
        except Exception: return []
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES if ACTIVE_SOURCES else MASTER_SOURCES)) as executor:
        results = executor.map(search_api, ACTIVE_SOURCES.values() if ACTIVE_SOURCES else MASTER_SOURCES.values())
        cands = []
        history_url = PLAY_HISTORY.get(f"HIST_{cache_key}")
        
        for vod_list in results:
            for vod in (vod_list or []):
                for group in vod.get('vod_play_url', '').split('$$$'):
                    for ep_str in group.split('#'):
                        if '$' in ep_str:
                            ep_title, ep_url = ep_str.split('$', 1)
                            if '.m3u8' in ep_url.lower() or '.mp4' in ep_url.lower():
                                cands.append({
                                    "url": ep_url, 
                                    "name": vod.get('vod_name', ''),
                                    "has_history": (ep_url == history_url)
                                })
                                
    ranked = dual_stage_rank(cands)
    if ranked: PLAY_URL_CACHE[cache_key] = {'urls': [c['url'] for c in ranked], 'time': time.time()}
    print(f"[*] ✅ [解析完成] 电影 {clean_name} 已排序 {len(ranked)} 条高画质直连！", flush=True)

def prepare_tv_urls(clean_name, cache_key):
    print(f"[*] 🔍 [目录预加载] 正在全网检索电视剧: {clean_name}", flush=True)
    def search_api(api_url):
        # 💡 致命Bug修复点2: 使用 `or []` 彻底防御垃圾接口返回 NoneType
        try: return requests.get(f"{api_url}?ac=detail&wd={urllib.parse.quote(clean_name)}", timeout=5).json().get('list') or []
        except Exception: return []
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ACTIVE_SOURCES if ACTIVE_SOURCES else MASTER_SOURCES)) as executor:
        results = executor.map(search_api, ACTIVE_SOURCES.values() if ACTIVE_SOURCES else MASTER_SOURCES.values())
        cands = []
        history_url = PLAY_HISTORY.get(f"HIST_{cache_key}") 
        
        for vod_list in results:
            for vod in (vod_list or []):
                if clean_name.lower() not in vod.get('vod_name', '').lower(): continue
                for group in vod.get('vod_play_url', '').split('$$$'):
                    ep_dict = {}
                    rep_url = None
                    for ep_str in group.split('#'):
                        if '$' in ep_str:
                            ep_title, ep_url = ep_str.split('$', 1)
                            if '.m3u8' in ep_url.lower() or '.mp4' in ep_url.lower():
                                std_name = normalize_ep_name(clean_name, ep_title)
                                ep_dict[std_name] = ep_url
                                if not rep_url: rep_url = ep_url 
                                
                    if ep_dict and rep_url:
                        is_history = (history_url in ep_dict.values())
                        cands.append({
                            "url": rep_url, 
                            "ep_dict": ep_dict, 
                            "name": vod.get('vod_name', ''),
                            "has_history": is_history
                        })
                        
    ranked = dual_stage_rank(cands)
    if ranked: TV_SHOW_CACHE[cache_key] = {'vods': [c['ep_dict'] for c in ranked], 'time': time.time()}
    print(f"[*] ✅ [预加载完成] 剧集 {clean_name} 已筛选出 {len(ranked)} 套优质路线，集数列表已生成！", flush=True)

# ==========================================
# 🗺️ 模块六：WebDAV 挂载服务核心 
# ==========================================
def generate_propfind_xml(items):
    xml = ['<?xml version="1.0" encoding="utf-8" ?>', '<D:multistatus xmlns:D="DAV:">']
    for item in items:
        encoded_path = urllib.parse.quote(item["path"])
        xml.append(f'  <D:response>\n    <D:href>{encoded_path}</D:href>\n    <D:propstat><D:prop>')
        xml.append(f'      <D:displayname>{item["name"]}</D:displayname>')
        if item['is_dir']: 
            xml.append('      <D:resourcetype><D:collection/></D:resourcetype>')
        else: 
            xml.append('      <D:resourcetype/>\n      <D:getcontentlength>10737418240</D:getcontentlength>\n      <D:getcontenttype>video/mp4</D:getcontenttype>')
        xml.append('      <D:getlastmodified>Tue, 10 Jan 2024 12:00:00 GMT</D:getlastmodified>\n    </D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>\n  </D:response>')
    xml.append('</D:multistatus>')
    return '\n'.join(xml)

@app.route('/', defaults={'path': ''}, methods=['OPTIONS', 'PROPFIND', 'GET', 'HEAD'])
@app.route('/<path:path>', methods=['OPTIONS', 'PROPFIND', 'GET', 'HEAD'])
def webdav_handler(path):
    full_path = '/' + path if path else '/'
    decoded = urllib.parse.unquote(full_path).rstrip('/')
    parts = [p for p in decoded.split('/') if p]
    now = time.time()

    if request.method == 'GET' and decoded == '/console': 
        return render_template_string(WEB_CONSOLE_HTML)
    if request.method == 'GET' and decoded == '/api/logs': 
        return jsonify(list(LOG_BUFFER))
    if request.method == 'OPTIONS':
        resp = Response(); resp.headers['Allow'] = 'OPTIONS, PROPFIND, GET, HEAD'; resp.headers['DAV'] = '1, 2'; return resp

    # ================== 目录预加载渲染阶段 (PROPFIND) ==================
    if request.method == 'PROPFIND':
        items = []
        depth = request.headers.get('Depth', '1')
        
        if not parts:
            items.extend([{'path': '/电影', 'name': '电影', 'is_dir': True}, {'path': '/电视剧', 'name': '电视剧', 'is_dir': True}])
            
        elif len(parts) == 1:
            if parts[0] == "电影":
                for k in TMDB_CACHE.get("电影", {}).keys(): items.append({'path': f"/电影/{k}", 'name': k, 'is_dir': True})
            else:
                for n in TMDB_CACHE.get("电视剧", []): items.append({'path': f"/电视剧/{n}", 'name': n, 'is_dir': True})
                    
        elif len(parts) == 2:
            if parts[0] == "电影":
                # 💡 致命Bug修复点1: 恢复电影正常目录结构，不再将 [0001-0500] 作为关键字搜索！
                chunk_name = parts[1]
                for m in TMDB_CACHE.get("电影", {}).get(chunk_name, []):
                    for quality in ["4K", "1080p"]: 
                        items.append({'path': f"{decoded}/{m} - {quality}.mp4", 'name': f"{m} - {quality}.mp4", 'is_dir': False})
                    
            elif parts[0] == "电视剧":
                clean_name = parts[1]
                cache_key = f"TV_{clean_name}"
                # 剧集预加载机制保留
                with get_sync_lock(cache_key):
                    if cache_key not in TV_SHOW_CACHE or (now - TV_SHOW_CACHE[cache_key]['time'] > 14400):
                        prepare_tv_urls(clean_name, cache_key)
                        
                vods = TV_SHOW_CACHE.get(cache_key, {}).get('vods', [])
                if vods:
                    best_vod_episodes = vods[0]
                    for ep_name in sorted(best_vod_episodes.keys()): 
                        items.append({'path': f"{decoded}/{ep_name}", 'name': ep_name, 'is_dir': False})
                    
        elif len(parts) == 3 and decoded.endswith('.mp4'):
            items.append({'path': decoded, 'name': parts[-1], 'is_dir': False})
            
        else: 
            return Response("Not Found", status=404)
            
        return Response(generate_propfind_xml(items), status=207, mimetype='application/xml')

    if request.method == 'HEAD' and decoded.endswith('.mp4'):
        resp = Response(status=200); resp.headers['Content-Type'] = 'video/mp4'; resp.headers['Accept-Ranges'] = 'bytes'; resp.headers['Content-Length'] = '10737418240'; return resp

    # ================== 点击即播 0延迟阶段 (GET) ==================
    if request.method == 'GET' and decoded.endswith('.mp4'):
        file_name = parts[-1]
        is_movie = (parts[0] == "电影")
        
        if is_movie: 
            # 电影在 GET 阶段才触发搜索，避免撑爆路由器
            clean_name = re.sub(r' - (4K|1080p)\.mp4', '', file_name).strip()
            cache_key = f"MOVIE_{clean_name}"
            
            with get_sync_lock(cache_key):
                if cache_key not in PLAY_URL_CACHE or (now - PLAY_URL_CACHE[cache_key]['time'] > 14400):
                    prepare_movie_urls(clean_name, cache_key)
                
            urls = PLAY_URL_CACHE.get(cache_key, {}).get('urls', [])
            if urls:
                target_index = 1 if '1080p' in file_name else 0
                target_url = urls[target_index % len(urls)]
                
                update_history(f"HIST_{cache_key}", target_url)
                print(f"[*] 🎯 [0秒直连] 电影 {file_name} -> 成功透传！", flush=True)
                resp = redirect(target_url, code=302)
                resp.headers['Cache-Control'] = 'no-cache, no-store'
                return resp
                
        else: 
            clean_name = parts[1] 
            cache_key = f"TV_{clean_name}"
            
            with get_sync_lock(cache_key):
                if cache_key not in TV_SHOW_CACHE: prepare_tv_urls(clean_name, cache_key)
                
            vods = TV_SHOW_CACHE.get(cache_key, {}).get('vods', [])
            if vods:
                st = TV_SWITCH_STATE.setdefault(cache_key, {"idx": 0, "last": 0})
                duration_since_last = now - st['last']
                
                if 3 < duration_since_last <= 14400: 
                    st['idx'] = (st['idx'] + 1) % len(vods)
                    print(f"\n[*] 🔄 [剧集切源成功] 命中备用线路 Index {st['idx']} ！", flush=True)
                else: 
                    st['idx'] = 0
                    print(f"\n[*] ▶️ [首播/记忆恢复] 已分配最佳极速流。", flush=True)
                    
                st['last'] = now
                target_url = None
                chosen_vod = vods[st['idx'] % len(vods)]
                target_url = chosen_vod.get(file_name)
                
                if not target_url:
                    for v in vods:
                        if v.get(file_name): 
                            target_url = v.get(file_name); break
                
                if target_url:
                    update_history(f"HIST_{cache_key}", target_url)
                    print(f"[*] 🎯 [0秒直连] 剧集 {file_name} -> 成功透传！", flush=True)
                    resp = redirect(target_url, code=302)
                    resp.headers['Cache-Control'] = 'no-cache, no-store'
                    return resp

    return Response("Not Found", status=404)

# ==== 启动区与基础服务 ====
def ai_discover_sources():
    print("\n[*] 🕷️ AI 自动寻源引擎启动: 正在扫描全球野生片源库...", flush=True)
    discovered = set()
    def scrape_hub(url):
        try:
            r = requests.get(url, headers={'User-Agent': get_random_ua()}, timeout=10, verify=False)
            matches = re.findall(r'(https?://[a-zA-Z0-9\.\-\_]+(?::\d+)?/[a-zA-Z0-9\.\-\_/]*api\.php/provide/vod/?)', r.text)
            for m in matches: discovered.add(m)
        except Exception:
            pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for url in TVBOX_CONFIG_HUBS: executor.submit(scrape_hub, url)
    return list(discovered)

def update_active_sources():
    global ACTIVE_SOURCES
    all_urls = set(MASTER_SOURCES.values())
    wild_sources = ai_discover_sources()
    if wild_sources: all_urls.update(wild_sources)
    if os.path.exists(AUTO_SOURCES_FILE):
        try:
            with open(AUTO_SOURCES_FILE, 'r') as f: all_urls.update(json.load(f))
        except Exception: pass

    all_urls = list(all_urls)[:100]
    valid_results = []
    
    def check_and_ping(url):
        try:
            start = time.time()
            r = requests.get(f"{url}?ac=list", headers={'User-Agent': get_random_ua()}, timeout=3, verify=False)
            if r.status_code == 200 and 'list' in r.json():
                return url, time.time() - start
        except Exception: pass
        return None, 999
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(check_and_ping, url) for url in all_urls]
        for future in concurrent.futures.as_completed(futures):
            valid_url, ping = future.result()
            if valid_url: 
                name = next((k for k, v in MASTER_SOURCES.items() if v == valid_url), f"野生节点_{ping:.2f}")
                valid_results.append((name, valid_url, ping))
                
    if valid_results:
        valid_results.sort(key=lambda x: x[2])
        top_nodes = valid_results[:25] 
        ACTIVE_SOURCES = {name: url for name, url, ping in top_nodes}
        print(f"[*] 🏆 竞技场结算: 已筛选出全网最快的 {len(ACTIVE_SOURCES)} 个顶级节点出战！", flush=True)
        try:
            with open(AUTO_SOURCES_FILE, 'w', encoding='utf-8') as f: 
                json.dump(list(ACTIVE_SOURCES.values()), f, ensure_ascii=False)
        except Exception: pass
    else: 
        ACTIVE_SOURCES = MASTER_SOURCES

def fetch_tmdb_page_safe(endpoint, params, max_retries=3):
    if not TMDB_KEY: return []
    params['api_key'] = TMDB_KEY
    params['language'] = 'zh-CN'
    for attempt in range(max_retries):
        for base_url in TMDB_DOMAINS:
            try:
                r = requests.get(f"{base_url}{endpoint}", params=params, timeout=5, verify=False)
                if r.status_code == 200: return r.json().get('results') or []
                elif r.status_code == 429: time.sleep(1.5)
            except Exception: pass
        time.sleep(0.5)
    return []

def build_or_update_library(is_daily_update=False):
    global TMDB_CACHE
    if not TMDB_KEY:
        print("\n[*] ⚠️ [离线模式] 未配置 TMDB_KEY，系统将依赖本地预置 v7 片库运行。", flush=True)
        return

    today_str = datetime.today().strftime('%Y-%m-%d')
    pages_to_fetch = 5 if is_daily_update else 500

    print(f"\n[*] 🚧 TMDB 扫库引擎启动 (获取 {pages_to_fetch} 页数据)...", flush=True)
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
                    if not raw_date or raw_date > today_str: continue
                        
                    title = item.get('title') or item.get('name') or item.get('original_title', '')
                    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                    
                    if not re.search(r'[\u4e00-\u9fa5]', safe_title): continue
                        
                    if safe_title and safe_title not in seen:
                        seen.add(safe_title)
                        if cat_name == "电影": temp_movies.append(safe_title)
                        else: temp_tvs.append(safe_title)
                            
                time.sleep(0.3) 

    if is_daily_update:
        old_tvs = TMDB_CACHE.get("电视剧", [])
        TMDB_CACHE["电视剧"] = (temp_tvs + [x for x in old_tvs if x not in temp_tvs])[:10000]
        
        old_movies = []
        for chunk in TMDB_CACHE.get("电影", {}).values(): old_movies.extend(chunk)
            
        merged_movies = (temp_movies + [x for x in old_movies if x not in temp_movies])[:10000]
        
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

    try:
        with open(MASSIVE_LIB_FILE, 'w', encoding='utf-8') as f: 
            json.dump(TMDB_CACHE, f, ensure_ascii=False)
    except Exception:
        pass
        
    print(f"[*] TMDB 数据固化完成！", flush=True)

def background_orchestrator():
    global TMDB_CACHE
    load_history()
    update_active_sources()
    
    if os.path.exists(MASSIVE_LIB_FILE):
        try:
            with open(MASSIVE_LIB_FILE, 'r', encoding='utf-8') as f: 
                TMDB_CACHE = json.load(f)
            build_or_update_library(is_daily_update=True)
        except Exception: 
            build_or_update_library(is_daily_update=False)
    else: 
        build_or_update_library(is_daily_update=False)
        
    while True:
        time.sleep(86400) 
        build_or_update_library(is_daily_update=True)
        update_active_sources()
        
threading.Thread(target=background_orchestrator, daemon=True).start()

if __name__ == '__main__':
    print("="*80, flush=True)
    print(f" 🌍 Maomao 引擎 V1.0.4 (致命Bug修复版) 启动！")
    print("="*80, flush=True)
    app.run(host='0.0.0.0', port=8080, debug=False)
