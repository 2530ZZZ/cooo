import requests
import re
import time
import base64
import json
from datetime import datetime, timedelta, timezone
import os
import signal
from functools import wraps
from email.utils import parsedate_to_datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 配置部分 ====================
# 从 GitHub Actions 环境变量获取 Token（如果没有则使用公共访问）
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
headers = {
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
    "User-Agent": "Mozilla/5.0 (compatible; FreeNodesCollector/2.0)"
}

# 关键词列表（可以继续添加或删除）

QUERIES = [

    # ==================== 4. 中文高频搜索词 ====================
    "免费节点",
    "免费clash订阅",
    "免费v2ray订阅",
    "免费trojan订阅",
    "免费hysteria订阅",
    "免费hysteria2订阅",
    "免费机场节点",
    "免费节点订阅",
    "免费机场订阅",
    "免费clash节点",
    "免费v2ray节点",
    "免费机场",
    "节点订阅",
    "clash 订阅",
    "v2ray 订阅",
    "科学上网",
    "梯子",
    "节点",
    "代理",


]

# ==================== 全局变量 ====================
all_links = []                  # 最终收集到的所有订阅链接（no_li.txt）
seen_repos = set()              # 已检查过的仓库（实现跳过重复仓库,防止重复处理）
blacklist_repos = set()         # ljck.txt 黑名单仓库（持久化排除无用仓库）


checked_count = 0               # 统计总共检查了多少个仓库



unique_nodes = set()            # 全局去重集合（set自动去重,用于最终生成干净的 no.txt）
query_links_count = 0           # 每关键词贡献的链接数（模块级全局）
beijing_tz = timezone(timedelta(hours=8))  # 所有日志、打印、commit 消息都改成北京时间显示








# ====================== 记录程序开始时间（用于计算总耗时） ======================

start_time = time.time()
print(f"[{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 🚀 程序启动,开始动态搜索...", flush=True)



# ====================== 读取 ljck.txt 黑名单（持久化排除无用仓库） ======================
# ljck.txt 作用：记录“完全没有提取到任何节点”的仓库
# 第一次运行时文件不存在 → 自动创建空文件
# 以后运行时自动加载，避免重复处理无用仓库，大幅节省时间和 API 调用
ljck_file = "ljck.txt"
if os.path.exists(ljck_file):
    with open(ljck_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("https://github.com/"):
                blacklist_repos.add(line)
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 已加载 ljck.txt，黑名单仓库数量: {len(blacklist_repos)}", flush=True)
else:
    # 第一次运行，创建空文件
    with open(ljck_file, "w", encoding="utf-8") as f:
        pass
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ljck.txt 不存在，已自动创建（首次运行）", flush=True)



# ====================== 创建带强力重试和超时的 Session ======================
# 这段代码的作用是创建一个全局的 requests.Session() 对象
# 作用1：复用 TCP 连接，减少每次请求的握手开销
# 作用2：自动重试（Retry），当 GitHub 返回 429/500 等临时错误时自动重试
# 作用3：严格控制超时（timeout），防止某个请求永远卡住导致整个程序挂起
# 作用4：连接池设置（pool_connections/pool_maxsize），适合并发请求场景
session = requests.Session()







# Retry 策略：最多重试2次，只对特定错误码重试
retry_strategy = Retry(
    total=2,                    # 最多重试2次
    backoff_factor=1,           # 每次重试间隔逐渐增加（1秒、2秒...）
    status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码才触发重试



)

# HTTPAdapter：配置连接池和重试策略
adapter = HTTPAdapter(
    max_retries=retry_strategy,   # 使用上面的重试策略
    pool_connections=10,          # 最多同时保持10个连接
    pool_maxsize=10               # 连接池最大容量10



)

# 把适配器挂载到 https 和 http
session.mount("https://", adapter)
session.mount("http://", adapter)

# ====================== 强制超时装饰器（仅 Linux，解决 requests 永久阻塞问题） ======================

def timeout_decorator(seconds):
    """
    使用 signal.alarm 强制中断卡死的函数，适用于 GitHub Actions 的 Linux 环境。
    如果函数执行超过指定秒数，抛出 TimeoutError 异常。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"函数 {func.__name__} 执行超过 {seconds} 秒，强制终止")
            old = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old)
        return wrapper
    return decorator



# ====================== 安全请求函数（防止卡死 加强防挂起） ======================

def safe_get(url, timeout=(8, 15), max_retries=2, operation_name="请求"):

    """


    1. timeout 改为元组 (连接超时, 读取超时)，避免 DNS/连接阶段永久卡死。
    2. 区分 403 和 409 错误：
       - 403 限流：根据 X-RateLimit-Reset 等待，但限制最大等待时间 120 秒。
       - 409 冲突（仓库空/无commit）：立即返回 None，不等待不重试。
    3. 所有 print 添加 flush=True，确保日志实时输出，便于定位卡死位置。
    """
    for attempt in range(1, max_retries + 1):
        try:
            #print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔄 {operation_name} 第 {attempt}/{max_retries} 次尝试...", flush=True)
            resp = session.get(url, headers=headers, timeout=timeout)

            if resp.status_code == 200:
                # 成功立即返回
                return resp

            if resp.status_code == 404:
                # 404 快速失败，不进行长时间等待
                print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回 404，快速跳过", flush=True)
                return None

            # 409 冲突错误直接返回 None，不等待
            if resp.status_code == 409:
                print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回 409，快速跳过", flush=True)
                return None

            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回状态码: {resp.status_code} (尝试 {attempt}/{max_retries})", flush=True)

            # ===== 只有 403 才处理限流，并限制最长等待时间 =====
            if resp.status_code == 403:
                reset_time = resp.headers.get('X-RateLimit-Reset')



                if reset_time:
                    wait_seconds = int(reset_time) - int(time.time()) + 5
                    # 限制最大等待 120 秒，避免超长阻塞
                    if wait_seconds > 120:
                        print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 限流等待时间过长({wait_seconds}秒)，放弃本次请求", flush=True)
                        return None
                    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 触发限流 | 等待 {wait_seconds} 秒...", flush=True)
                    time.sleep(max(wait_seconds, 10))
                else:
                    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 返回 403，保守等待 30 秒...", flush=True)
                    time.sleep(30)
                continue

            # 其他错误码（如 500, 502, 503）进行短暂重试
            wait = 3 + attempt * 2
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回状态码: {resp.status_code if resp.status_code else '未知'}，等待 {wait} 秒后重试...", flush=True)
            time.sleep(wait)


        except requests.exceptions.Timeout:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 超时 (尝试 {attempt}/{max_retries})", flush=True)
        except requests.exceptions.ConnectionError:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 连接错误 (尝试 {attempt}/{max_retries})", flush=True)
        except Exception as e:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 异常: {type(e).__name__}: {e} (尝试 {attempt}/{max_retries})", flush=True)
            time.sleep(3 * attempt)

    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ❌ {operation_name} 多次失败，已跳过", flush=True)
    return None




# ====================== 增强版节点提取函数（支持 markdown 代码块 + 递归） ======================
def extract_nodes_from_text(text):

    """
    增强版节点提取函数 - 支持几乎所有协议和格式
    重要改进：




    - 优先处理大段 base64（很多订阅文件是整行 base64 编码）
    - 支持 trojan://、hysteria2://、hy2://、ss:// 等带复杂参数、plugin 的格式
    - 支持 markdown 代码块提取（``` 或 ` 包裹的内容）




    - 多阶段提取：base64 → 协议链接 → YAML/JSON → 清理


    - 使用非捕获组 + 更宽松的匹配规则，现在能完整提取你提供的 trojan://、hysteria2://、hy2://、ss://（带 plugin）等所有格式

    重要逻辑：
    - 直接从文件内容提取节点
    - 返回提取到的节点列表,没有提取到就是空（供上层决定是否保留该 raw 链接）
    - 标准协议链接 vmess:// vless:// trojan:// ss:// ssr:// hysteria:// hysteria2:// tuic:// reality://
    - Shadowsocks ss:// 完整 base64 格式（包括带 # 备注）
    - Clash/Sing-box YAML 单行和多行 proxies：- {name: ..., server: ..., type: vless, ...}
    - Clash 多行 proxies 格式
    - README 中直接写的 raw 订阅链接（https://raw.githubusercontent.com/...）
    - 各种 base64 编码的节点（自动解码 + 清理）
    - Clash / Sing-box 的 proxies 数组（JSON 或 YAML 格式）
    - JSON 格式的 proxies 数组和 outbounds


    - 嵌套在对象中的 proxies 列表
    - 标准协议链接 + base64 + YAML 单行/多行
    - 支持 markdown 代码块中的 raw 链接
    """
    nodes = []
    if not text or len(text.strip()) < 10:
        return nodes


    # ==================== 阶段1：提取 markdown 代码块并递归处理 ====================
    # 支持 ```xxx ... ``` 和 `xxx` 两种代码块
    # 使用 (?:```|`) 避免捕获组问题
    code_block_pattern = r'(?:```(?:[\w]*)\n?)([\s\S]*?)(?:\n?```)|`([^`\n]+)`'
    for match in re.findall(code_block_pattern, text):
        # match 是 tuple，第一个是 ``` 块内容，第二个是 ` 块内容
        block_content = match[0] if match[0] else match[1]
        if block_content and block_content.strip():
            # 递归调用自身处理代码块内容（关键！这样 base64、协议等都能被提取）
            nodes.extend(extract_nodes_from_text(block_content))


    # ==================== 阶段2：大段 base64 处理 ====================
    base64_full_pattern = r'[A-Za-z0-9+/=]{100,}'
    for candidate in re.findall(base64_full_pattern, text):
        try:
            # 补全 padding
            padding = len(candidate) % 4
            if padding:
                candidate += '=' * (4 - padding)
            decoded = base64.b64decode(candidate, validate=False).decode('utf-8', errors='ignore')


            # 解码后递归提取（重要！）
            nodes.extend(extract_nodes_from_text(decoded))
        except:
            pass




    # ==================== 阶段3：标准协议链接（全协议支持） ====================
    # 使用非捕获组，确保返回完整链接
    protocol_pattern = r'(?i)(?:vmess|vless|trojan|ss|ssr|hysteria|hysteria2|hy2|tuic|reality)://[^\s<>"\']+'
    nodes.extend(re.findall(protocol_pattern, text))



    # ==================== 阶段4：Shadowsocks ss:// 带 plugin 格式 ====================

    ss_pattern = r'ss://[A-Za-z0-9+/=]+(?:\?[^\s<>"\']*)?(?:#[^\s<>"\']*)?'
    nodes.extend(re.findall(ss_pattern, text, re.IGNORECASE))



    # ==================== 阶段5：Clash / Sing-box YAML 单行节点 ====================

    yaml_single_pattern = r'-\s*\{[^}]*?(?:name|server|port|type|uuid|password|ps|flow|reality-opts|sni|fp|client-fingerprint)[^}]*\}'


    yaml_matches = re.findall(yaml_single_pattern, text, re.IGNORECASE | re.DOTALL)
    for match in yaml_matches:
        clean = re.sub(r'\s+', ' ', match.strip())
        if len(clean) > 40:
            nodes.append(clean)


    # ==================== 阶段6：Clash YAML 多行 proxies ====================
    yaml_multi_pattern = r'-\s*name:.*?(?=-\s*name:|\Z)'


    multi_matches = re.findall(yaml_multi_pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    for match in multi_matches:
        clean = re.sub(r'\s+', ' ', match.strip())
        if len(clean) > 30 and ('server:' in clean or 'type:' in clean):
            nodes.append(clean)



    # ==================== 阶段7：JSON 格式 proxies / outbounds ====================

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            proxies = data.get("proxies") or data.get("outbounds") or data.get("proxy_groups")
            if isinstance(proxies, list):
                for p in proxies:
                    if isinstance(p, dict):
                        nodes.append(json.dumps(p, ensure_ascii=False))
                    elif isinstance(p, str) and any(proto in p.lower() for proto in ["trojan://", "hysteria2://", "hy2://", "vmess://", "vless://", "ss://"]):
                        nodes.append(p)
    except:
        pass


    # ==================== 阶段8：文本中 proxies 数组 ====================
    for arr in re.findall(r'"proxies"\s*:\s*\[([\s\S]*?)\]', text, re.IGNORECASE):
        for obj in re.findall(r'\{[\s\S]*?\}', arr):
            if any(proto in obj.lower() for proto in ["trojan", "hysteria2", "hy2", "vmess", "vless", "ss"]):
                nodes.append(obj.strip())



    """
    # ==================== 阶段9：raw 订阅链接 ====================

    raw_pattern = r'https?://raw[.]githubusercontent[.]com/[^ \t\n<>"\']+'
    for link in re.findall(raw_pattern, text, re.IGNORECASE):
        try:
            repo_path = '/'.join(link.split('githubusercontent.com/')[1].split('/')[:2])
        if repo_path not in seen_repos and f"https://github.com/{repo_path}" not in blacklist_repos:
            seen_repos.add(repo_path)
            global checked_count
            checked_count += 1
            process_repo(repo_path)
        except:
                pass
    """


    # ==================== 最终清理：去重 + 过滤无效行 ====================

    cleaned_nodes = []
    seen = set()
    for n in nodes:
        n = n.strip()
        if not n or n.startswith('//') or len(n) < 15 or n in seen:
            continue
        seen.add(n)
        cleaned_nodes.append(n)

    return cleaned_nodes






# ====================== 公共方法：处理单个仓库（增加强制超时保护） ======================

# 单个仓库处理总时间不得超过60秒，防止网络死锁
@timeout_decorator(60)
def process_repo(repo):

    """公共方法：处理单个仓库（检查更新时间 + 调用文件树处理）"""
    # 如果在 ljck.txt 黑名单中，直接跳过  是必要的,因为此函数可能被直接调用
    github_url = f"https://github.com/{repo}"
    if github_url in blacklist_repos:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 仓库 {repo} 在 ljck.txt 黑名单中，已跳过", flush=True)
        return

    # 获取仓库默认分支（解决 main/master 不一致问题）
    repo_info_url = f"https://api.github.com/repos/{repo}"
    repo_resp = safe_get(repo_info_url, timeout=(8, 15), operation_name=f"仓库 {repo} 信息查询")
    if repo_resp is None or repo_resp.status_code != 200:
        return

    repo_data = repo_resp.json()
    # ===== 【新增】提前过滤空仓库或被禁用的仓库 =====
    if repo_data.get('size', 0) == 0:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 仓库 {repo} 为空（size=0），跳过", flush=True)
        return
    if repo_data.get('disabled', False):
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 仓库 {repo} 已禁用，跳过", flush=True)
        return

    default_branch = repo_data.get("default_branch", "main")
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 仓库 {repo} 默认分支为: {default_branch}", flush=True)


    # 仓库commit查询
    commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    c_resp = safe_get(commit_url, timeout=(8, 15), operation_name=f"仓库 {repo} commit 查询")
    if c_resp is None or c_resp.status_code != 200:
        return
    # 有可能出现异常（API 有时返回的数据格式不标准、字段缺失、JSON 解析失败等）
    try:
        commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
        commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - commit_time >= timedelta(hours=24):
            return

        #print(f" ✓ 发现新的24h更新仓库 ({checked_count}): https://github.com/{repo}", flush=True)

        # 调用文件树处理方法，传递 has_nodes 标志列表以便递归共享
        has_nodes_flag = [False]
        process_file_tree(repo, path="", branch=default_branch, has_nodes=has_nodes_flag)
        # 如果整个仓库都没有提取到节点，则加入黑名单
        if not has_nodes_flag[0]:
            if github_url not in blacklist_repos:
                print(f" 仓库 {github_url} ❌ 提取失败 | 没有提取到有效节点 → 加入 ljck.txt 黑名单", flush=True)
                with open("ljck.txt", "a", encoding="utf-8") as f:
                    f.write(github_url + "\n")
                blacklist_repos.add(github_url)
    except Exception as e:
        print(f" 处理仓库 https://github.com/{repo} 时发生异常: {e}（已跳过）", flush=True)

# ====================== 公共方法：处理文件树（核心逻辑） ======================

def process_file_tree(repo, path="", branch="main", has_nodes=None):
    """
    公共方法：处理仓库的文件树，提取符合条件的订阅文件
    递归分层处理目录：只有上级目录新鲜，才继续检查子目录或文件
    新增参数 has_nodes：列表，用于在递归中共享提取状态（已提取到节点则为 True）
    这解决了原来对所有文件都查询 commit 的性能爆炸问题

    【本次重大修改】
    - 完全切换到 Contents API（/contents），不再使用 git/trees?recursive=1
    - Contents API 对根目录文件更稳定，不会再出现“只返回2个条目”的情况
    - 继续保留你原来的“per-directory commit 判断 + 递归”逻辑
    - 速度稍慢一点，但可靠性大幅提升，符合你当前的需求
    """

    # 用于标记该仓库是否提取到任何节点（用于 ljck.txt 黑名单）
    # 使用 list 作为 mutable 对象，在递归中共享标志（关键修复）
    # 这样整个仓库（包括所有子目录）只会在最顶层调用结束时统一判断一次

    if has_nodes is None:
        # 调用时初始化 仓库是否提取出节点
        has_nodes = [False]

    current_path = path if path else "（根目录）"
    # 显示可点击的目录链接
    dir_url = f"https://github.com/{repo}/tree/{branch}/{path}" if path else f"https://github.com/{repo}"
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 📁 进入目录: {current_path} -> {dir_url}", flush=True)

    # 使用 Contents API 获取当前目录内容
    contents_url = f"https://api.github.com/repos/{repo}/contents/{path}" if path else f"https://api.github.com/repos/{repo}/contents"
    c_resp = safe_get(contents_url, timeout=(10, 20), operation_name=f"Contents API {current_path}")
    if c_resp is None or c_resp.status_code != 200:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] Contents API 请求失败或超时: {contents_url}", flush=True)
        return

    items = c_resp.json()
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] Contents API 加载成功，共 {len(items)} 个条目", flush=True)

    # 循环仓库文件树查询提取节点
    for item in items:
        item_path = item["path"]        # ✅ 关键修复：直接使用 API 返回的完整路径，不再手动拼接
        item_type = item["type"]        # "file" 或 "dir"

        # 检查该路径的 commit 时间
        # ---------- 获取路径的最后修改时间（多层备选） ----------
        file_time = None
        time_source = None  # 记录时间来源，便于调试


        # 【主力方案】通过 commits API 获取
        commit_url = f"https://api.github.com/repos/{repo}/commits?path={item_path}&per_page=1"
        f_resp = safe_get(commit_url, timeout=(8, 12), operation_name=f"路径 {item_path} commit 查询")
        if f_resp and f_resp.status_code == 200:
            try:
                commits_data = f_resp.json()
                if commits_data:
                    file_time_str = commits_data[0]["commit"]["committer"]["date"]
                    file_time = datetime.fromisoformat(file_time_str.replace("Z", "+00:00"))
                    time_source = "commits API"
            except Exception as e:
                print(f"   ⚠️ 解析 commits 响应失败: {e} 获取修改时间失败", flush=True)

        # 【第一备选】如果 commits API 返回空，且是文件，则用 HEAD 请求获取 Last-Modified
        if file_time is None and item_type == "file":
            head_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{item_path}"
            head_resp = safe_get(head_url, timeout=(8, 10), operation_name=f"HEAD 请求 {item_path}", max_retries=1)
            if head_resp and head_resp.status_code == 200:
                last_modified = head_resp.headers.get('Last-Modified')
                if last_modified:
                    try:
                        file_time = parsedate_to_datetime(last_modified).replace(tzinfo=timezone.utc)
                        time_source = "Last-Modified header"
                    except Exception as e:
                        print(f"   ⚠️ 解析 Last-Modified 失败: {e} 获取修改时间失败", flush=True)

        # 如果仍然无法获取时间，则对于目录继续递归，对于文件则跳过
        if file_time is None:
            if item_type == "dir":
                # 目录没有时间也不影响，继续递归
                print(f"   ➡️ 进入目录 {item_path}（未能获取修改时间，继续递归）", flush=True)
                process_file_tree(repo, item_path, branch, has_nodes)
            else:
                print(f"   ⏭️ 跳过文件 {item_path}：无法获取修改时间", flush=True)
            continue

        # 检查是否在24小时内
        if datetime.now(timezone.utc) - file_time >= timedelta(hours=24):
            print(f"   ⏭️ 跳过 {item_path}：最后更新超过 24 小时（{file_time}，来源：{time_source}）", flush=True)
            # 如果是目录且超过24小时，则无需递归
            if item_type == "dir":
                print(f"   🚫 目录 {item_path} 超过24小时未更新，跳过递归", flush=True)
                continue
            else:
                continue

        # ---------- 时间在24小时内，继续处理 ----------
        print(f"   ✅ {item_path} 在24小时内更新（{file_time}，来源：{time_source}）", flush=True)


        # 如果是目录 → 递归进入
        if item_type == "dir":

            # 递归进入子目录，传递同一个 has_nodes 列表
            process_file_tree(repo, item_path, branch, has_nodes)

        # 如果是文件 → 处理订阅文件
        elif item_type == "file":

            # 【可选】文件名过滤，目前注释状态以处理所有文件
            """
            fname = item_path.lower()
            if not fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64", ".list", "readme.md")):
                continue

            if not any(k in fname for k in ["clash", "v2ray", "trojan", "hysteria", "hysteria2", "hy2", "vless", "vmess", "ss", "ssr", "tuic", "reality", "sub", "proxy", "node", "base64", "config", "list", "output", "readme"]):
                continue
            """

            file_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{item_path}"
            print(f"   🔍 检查文件: {file_url}", flush=True)

            # 直接请求一次文件内容，然后提取节点
            resp = safe_get(file_url, timeout=(10, 30), operation_name="获取订阅文件内容")
            if resp is None or resp.status_code != 200:
                print(f" 📄 文件 {file_url} ❌ 下载失败", flush=True)
                continue


            # 直接调用节点提取函数
            content = resp.text
            nodes = extract_nodes_from_text(content)



            if nodes:



                # 只要提取到节点，就标记该仓库有效,就不用加入黑名单
                has_nodes[0] = True
                # === 区分三种情况的核心逻辑 ===
                before_count = len(unique_nodes)
                #节点加入去重集合
                unique_nodes.update(nodes)
                added_count = len(unique_nodes) - before_count
                # 情况1：提取出新增节点
                if added_count > 0:
                    #有新增节点, 把链接加入
                    all_links.append(file_url)
                    print(f" 📄 文件 {file_url} ✅ 提取成功 | 新增 {added_count} 条新节点（共 {len(nodes)} 条）", flush=True)

                    #搜索词提供链接计数
                    global query_links_count
                    query_links_count += 1
                # 情况2：提取出的所有节点已存在
                else:
                    print(f" 📄 文件 {file_url} ⚪ 全部重复（不保留链接）", flush=True)
            else:
                # 情况3：没有提取出任何节点
                print(f" 📄 文件 {file_url} ❌ 无有效节点", flush=True)
        else:
            # 以防出现其他类型（如 submodule）
            print(f"   ⚠️ 未知条目类型: {item_type} - {item_path}", flush=True)



# ====================== 主程序 ======================

for query_idx, query in enumerate(QUERIES, 1):
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔎 开始搜索第 {query_idx}/{len(QUERIES)} 个关键词: {query}", flush=True)
    # 每关键词重置关键词贡献的链接数量计数器
    query_links_count = 0
    page = 1

    # 不能超过 30 页，前面几页质量更好更高效
    while page <= 10:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 正在请求第 {page} 页...", flush=True)
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
        resp = safe_get(url, timeout=(15, 30), operation_name=f"搜索关键词第{page}页")

        if resp is None or resp.status_code != 200:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 搜索失败，第{page}页状态码: {resp.status_code if resp else 'None'}", flush=True)
            break

        items = resp.json().get("items", [])
        if not items:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 第{page}页没有结果，结束当前关键词搜索", flush=True)
            break

        print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 本页找到 {len(items)} 个仓库，开始处理...", flush=True)
        for item in items:
            repo = item["full_name"]
            # 如果仓库已经存在 或者 在黑名单中 就不处理
            if repo in seen_repos or f"https://github.com/{repo}" in blacklist_repos:
                continue
            # 加入已处理仓库名单
            seen_repos.add(repo)
            checked_count += 1
            # 调用仓库处理方法（已添加超时装饰器 会检查 commit 时间 + 处理文件树 + 提取节点）
            process_repo(repo)
            # (秒)在处理完一个仓库后（不管成功还是失败）轻微等待，避免请求过快
            time.sleep(1.2)
        page += 1
        # (秒)翻页间隔，每页处理完后强制冷却，降低 API 压力
        time.sleep(6)

    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] └─ 本关键词贡献 {query_links_count} 条有效链接", flush=True)




# ====================== 最终处理 写入文件 ======================
# 先读取旧文件做对比，再写入新文件

old_nodes = set()
if os.path.exists("no.txt"):
    with open("no.txt", "r", encoding="utf-8") as f:
        old_nodes = {line.strip() for line in f if line.strip()}

old_links = set()
if os.path.exists("no_li.txt"):
    with open("no_li.txt", "r", encoding="utf-8") as f:
        old_links = {line.strip() for line in f if line.strip()}

# 把去重后的节点写入 no.txt
if unique_nodes:
    with open("no.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ 已将 {len(unique_nodes):,} 条去重后的节点保存到 no.txt", flush=True)
else:
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ 未提取到任何有效节点", flush=True)


# 生成 no.txt 的 raw 链接并加入到 no_li.txt
repo_name = os.getenv("GITHUB_REPOSITORY", "2530ZZZ/cooo")
no_txt_raw_url = f"https://raw.githubusercontent.com/{repo_name}/main/no.txt"
all_links.append(no_txt_raw_url)

# 全局去重常规链接
all_links = list(dict.fromkeys(all_links))

with open("no_li.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_links))


# ====================== 日志信息处理 ======================
# 计算总耗时
total_seconds = int(time.time() - start_time)
hours = total_seconds // 3600
minutes = (total_seconds % 3600) // 60
seconds = total_seconds % 60
runtime_str = f"{hours}小时 {minutes}分 {seconds}秒" if hours > 0 else f"{minutes}分 {seconds}秒"

# ====================== no.txt 新旧节点对比 ======================

new_nodes = unique_nodes


print(f"\n📈 no.txt 节点对比报告")
print(f" 新 no.txt 节点总数 : {len(new_nodes):,} 条")
print(f" 旧 no.txt 节点总数 : {len(old_nodes):,} 条")
print(f" 新增节点 : {len(new_nodes - old_nodes):,} 条")
print(f" 去除节点 : {len(old_nodes - new_nodes):,} 条")
print(f" 保留节点 : {len(new_nodes & old_nodes):,} 条")


# ====================== no_li.txt 新旧链接对比 ======================

new_links = set(all_links)
print(f"\n🔗 no_li.txt 链接对比报告")
print(f" 新 no_li.txt 链接总数 : {len(new_links):,} 条")
print(f" 旧 no_li.txt 链接总数 : {len(old_links):,} 条")
print(f" 新增链接 : {len(new_links - old_links):,} 条")
print(f" 去除链接 : {len(old_links - new_links):,} 条")

# ====================== 最终总结日志 ======================
print(f"\n🎉 [{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 搜集任务完成！总耗时: {runtime_str}")
print(f" 共检查仓库数量: {len(seen_repos):,} 个")
print(f" 最终获得独特订阅链接: {len(all_links):,} 条")
print(f" no.txt 中去重后节点数量: {len(unique_nodes):,} 条")
print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ 已保存 no_li.txt 和 no.txt 文件")
