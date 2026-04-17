import requests
import re
import time
import base64
import json
from datetime import datetime, timedelta, timezone
import os
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
    # ==================== 1. 基础高频 + 通用词 ====================
    "free nodes",
    "free proxy nodes",
    "free v2ray nodes",
    "free clash nodes",
    "free trojan nodes",
    "free hysteria nodes",
    "free vless nodes",
    "free hysteria2 nodes",
    "free tuic nodes",
    "free reality nodes",
    "free singbox nodes",

    # ==================== 2. 知名主流项目（高价值） ====================
    "ACL4SSR",
    "ACL4SSR ACL",
    "subconverter",
    "subconverter subscription",
    "v2rayN",
    "v2rayNG",
    "Clash.Meta",
    "mihomo",
    "Clash for Windows",
    "Hiddify",
    "Shadowrocket",
    "Quantumult X",
    "Stash",
    "sing-box subscription",

    # ==================== 3. 订阅相关高频词 ====================
    "clash subscription github",
    "v2ray subscription github",
    "trojan subscription github",
    "hysteria2 subscription",
    "singbox subscription",
    "free subscription github",
    "daily subscription",
    "base64 subscription",

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

    # ==================== 5. 混合 OR 组合（覆盖最广） ====================

    "免费 (clash OR v2ray OR trojan OR hysteria OR hysteria2 OR tuic OR reality OR singbox) (订阅 OR 节点 OR 机场)",
    "clash (订阅 OR 配置 OR 节点 OR 免费) github",
    "v2ray (订阅 OR 配置 OR 节点) github",
    "trojan (订阅 OR 节点) github",
    "hysteria2 (订阅 OR 节点) github",

    # ==================== 6. 其他重要变体与收集器 ====================
    "free proxy daily github",
    "free nodes daily",
    "proxy collector github",
    "v2ray collector github",
    "clash collector github",
    "TelegramV2rayCollector",
    "ProxyCollector",
    "V2RAY-CLASH-BASE64-Subscription",
    "V2RayRoot subscription",
    "airport free nodes github",
    "free airport nodes",
    "free shadowrocket nodes",
    "free hiddify nodes",
    "free v2rayng nodes",
    "free clash meta nodes",
    "free mihomo nodes",
    "free sing-box nodes github",
    "free ss nodes github",
    "free ssr nodes github",

    # ==================== 7. 额外高价值关键词 ====================

    "sub list github",
    "节点列表 github",
    "免费节点列表",
    "clash yaml github",
    "vless free nodes github",
    "reality free nodes github",
    "tuic free nodes github",
    "subconverter list",
    "ACL4SSR list"
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
print(f"[{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 🚀 程序启动,开始动态搜索...")


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
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 已加载 ljck.txt，黑名单仓库数量: {len(blacklist_repos)}")
else:
    # 第一次运行，创建空文件
    with open(ljck_file, "w", encoding="utf-8") as f:
        pass
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ljck.txt 不存在，已自动创建（首次运行）")


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



# ====================== 安全请求函数（防止卡死 加强防挂起） ======================

def safe_get(url, timeout=12, max_retries=2, operation_name="请求"):

    """
    带重试、超时和限流(403 409)处理的请求函数
    目的是防止脚本在 GitHub API 响应慢或限流时卡死
    404 快速失败（不再长等待），因为很多仓库默认分支不是 main
    只有 403/409 才进行较长等待
    """
    for attempt in range(1, max_retries + 1):
        try:
            #print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔄 {operation_name} 第 {attempt}/{max_retries} 次尝试...")
            resp = session.get(url, headers=headers, timeout=timeout)

            if resp.status_code == 200:
                # 成功立即返回
                return resp

            if resp.status_code == 404:




                # 404 快速失败，不进行长时间等待
                print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回 404（资源不存在），快速跳过")
                return None

            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回状态码: {resp.status_code} (尝试 {attempt}/{max_retries})")

            if resp.status_code in (403, 409):
                reset_time = resp.headers.get('X-RateLimit-Reset')



                if reset_time:
                    wait_seconds = int(reset_time) - int(time.time()) + 10
                    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 触发限流 | 等待 {wait_seconds} 秒...")
                    time.sleep(max(wait_seconds, 30))
                else:
                    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 返回 {resp.status_code}，保守等待 60 秒...")
                    time.sleep(60)
                continue

            # 其他错误码也进行等待重试
            wait = 3 + attempt * 2
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回状态码: {resp.status_code} (尝试 {attempt}/{max_retries})，等待 {wait} 秒后重试...")
            time.sleep(wait)
            continue

        except requests.exceptions.Timeout:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 超时 (尝试 {attempt}/{max_retries})")
        except requests.exceptions.ConnectionError:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 连接错误 (尝试 {attempt}/{max_retries})")
        except Exception as e:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 异常: {type(e).__name__}: {e} (尝试 {attempt}/{max_retries})")
            time.sleep(5 * attempt)
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ❌ {operation_name} 多次失败，已跳过")
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



# ====================== 公共方法：处理单个仓库 ======================
def process_repo(repo):

    """公共方法：处理单个仓库（检查更新时间 + 调用文件树处理）"""
    # 如果在 ljck.txt 黑名单中，直接跳过  是必要的,因为此函数可能被直接调用
    github_url = f"https://github.com/{repo}"
    if github_url in blacklist_repos:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 仓库 {repo} 在 ljck.txt 黑名单中，已跳过")
        return

    # 获取仓库默认分支（解决 main/master 不一致问题）
    repo_info_url = f"https://api.github.com/repos/{repo}"
    repo_resp = safe_get(repo_info_url, timeout=12, operation_name=f"仓库 {repo} 信息查询")
    if repo_resp is None or repo_resp.status_code != 200:
        return
    default_branch = repo_resp.json().get("default_branch", "main")
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 仓库 {repo} 默认分支为: {default_branch}")
    #print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 检查仓库 : https://github.com/{repo}")

    commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    c_resp = safe_get(commit_url, timeout=12, operation_name=f"仓库 {repo} commit 查询")
    if c_resp is None or c_resp.status_code != 200:
        return
    #有可能出现异常（API 有时返回的数据格式不标准、字段缺失、JSON 解析失败等）
    try:
        commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
        commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - commit_time >= timedelta(hours=24):
            return

        #print(f" ✓ 发现新的24h更新仓库 ({checked_count}): https://github.com/{repo}")
        # 调用文件树处理方法
        process_file_tree(repo, path="", branch=default_branch)
    except Exception as e:
        print(f" 处理仓库 https://github.com/{repo} 时发生异常: {e}（已跳过）")

# ====================== 公共方法：处理文件树（核心逻辑） ======================
def process_file_tree(repo, path="", branch="main"):

    """公共方法：处理仓库的文件树，提取符合条件的订阅文件
    递归分层处理目录：只有上级目录新鲜，才继续检查子目录或文件
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
    has_nodes = [False]

    current_path = path or "（根目录）"
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 进入目录: {current_path} | 仓库: https://github.com/{repo} | 分支: {branch}")

    # 使用 Contents API 获取当前目录内容（更稳定）
    contents_url = f"https://api.github.com/repos/{repo}/contents/{path}" if path else \
                   f"https://api.github.com/repos/{repo}/contents"

    c_resp = safe_get(contents_url, timeout=20, operation_name=f"Contents API {current_path}")
    if c_resp is None or c_resp.status_code != 200:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] Contents API 请求失败或超时: https://github.com/{repo}")
        return

    items = c_resp.json()
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] Contents API 加载成功，共 {len(items)} 个条目")
    # 循环仓库文件树查询提取节点
    for item in items:
        item_path = item["path"]
        item_type = item["type"]          # "file" 或 "dir"
        full_item_path = f"{path}/{item_path}" if path else item_path

        # 检查该路径的 commit 时间
        commit_url = f"https://api.github.com/repos/{repo}/commits?path={full_item_path}&per_page=1"
        f_resp = safe_get(commit_url, timeout=10, operation_name=f"路径 {full_item_path} commit 查询")
        if f_resp is None or f_resp.status_code != 200:
            continue

        try:
            file_time_str = f_resp.json()[0]["commit"]["committer"]["date"]
            file_time = datetime.fromisoformat(file_time_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - file_time >= timedelta(hours=24):
                continue


        except Exception as e:
            #print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 路径 {full_item_path} 日期解析异常: {e}（已跳过）")
            continue

        # 如果是目录 → 递归进入
        if item_type == "dir":
            process_file_tree(repo, full_item_path, branch)

        # 如果是文件 → 处理订阅文件
        elif item_type == "file":
            fname = item_path.lower()
            if not fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64", ".list", "readme.md")):
                continue
            if not any(k in fname for k in ["clash", "v2ray", "trojan", "hysteria", "hysteria2", "hy2", "vless", "vmess", "ss", "ssr", "tuic", "reality", "sub", "proxy", "node", "base64", "config", "list", "output", "readme"]):
                continue

            file_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{full_item_path}"


            #print(f" 🔄 处理订阅文件: {file_url}")   # 显示完整 raw 链接

            # 直接请求一次文件内容，然后提取节点
            resp = safe_get(file_url, timeout=20, operation_name="获取订阅文件内容")
            if resp is None or resp.status_code != 200:
                print(f" 📄 文件 {file_url} ❌ 下载失败")
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








                    all_links.append(file_url)    #有新增节点, 把链接加入
                    #print(f" 📄 文件 {file_url} ✅ 提取成功 | 新增 {added_count} 条新节点（共 {len(nodes)} 条）")

                    #搜索词提供链接计数
                    global query_links_count
                    query_links_count += 1
                # 情况2：提取出的所有节点已存在
                else:
                    print(f" 📄 文件 {file_url} ⚪ 全部重复（不保留链接）")
            else:
                # 情况3：没有提取出任何节点
                print(f" 📄 文件 {file_url} ❌ 提取失败 | 没有提取到有效节点")

    # 【关键修复】只有整个仓库（包括所有子目录）都没有提取到节点，才加入ljck.txt 黑名单

    if not has_nodes[0]:
        github_url = f"https://github.com/{repo}"
        if github_url not in blacklist_repos:           # 防止重复写入
            print(f" 仓库 {github_url} ❌ 提取失败 | 没有提取到有效节点 → 加入 ljck.txt 黑名单")
            with open("ljck.txt", "a", encoding="utf-8") as f:
                f.write(github_url + "\n")
            blacklist_repos.add(github_url)



# ====================== 主程序 ======================

for query_idx, query in enumerate(QUERIES, 1):
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔎 开始搜索第 {query_idx}/{len(QUERIES)} 个关键词: {query}")
    # 每关键词重置关键词贡献的链接数量计数器
    query_links_count = 0
    page = 1

    # 不能超过 30 页，前面几页质量更好更高效
    while page <= 10:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 正在请求第 {page} 页...")

        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
        resp = safe_get(url, timeout=30, operation_name=f"搜索关键词第{page}页")

        if resp.status_code != 200:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 搜索失败，第{page}页状态码: {resp.status_code}")
            break

        items = resp.json().get("items", [])
        if not items:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 第{page}页没有结果，结束当前关键词搜索")
            break

        print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 本页找到 {len(items)} 个仓库，开始处理...")
        for item in items:
            repo = item["full_name"]
            # 如果仓库已经存在 或者 在黑名单中 就不处理
            if repo in seen_repos or f"https://github.com/{repo}" in blacklist_repos:
                continue
            # 加入已处理仓库名单
            seen_repos.add(repo)
            checked_count += 1
            # 调用仓库处理方法（会检查 commit 时间 + 处理文件树 + 提取节点）
            process_repo(repo)
            # (秒)在处理完一个仓库后（不管成功还是失败）轻微等待，避免请求过快
            time.sleep(1.2)
        page += 1
        # (秒)翻页间隔，每页处理完后强制冷却，降低 API 压力
        time.sleep(6)


    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] └─ 本关键词贡献 {query_links_count} 条有效链接")

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
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ 已将 {len(unique_nodes):,} 条去重后的节点保存到 no.txt")
else:
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ 未提取到任何有效节点")


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
