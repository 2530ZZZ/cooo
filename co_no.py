import requests
import re
import time
import base64
import json
from datetime import datetime, timedelta, timezone
import os

# ==================== 配置部分 ====================
# 从 GitHub Actions 环境变量获取 Token（如果没有则使用公共访问）
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
headers = {
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
    "User-Agent": "Mozilla/5.0 (compatible; FreeNodesCollector/2.0)"
}


# 关键词列表（你可以继续添加或删除）
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
all_links = []                      # 最终收集到的所有订阅链接（常规订阅文件）
seen_repos = set()                  # 已检查过的仓库（关键：实现智能跳过重复仓库）
checked_count = 0                   # 统计总共检查了多少个仓库
unique_nodes = set()                # 全局去重集合（set自动去重,用于最终生成干净的 no.txt）
beijing_tz = timezone(timedelta(hours=8))  # 所有日志、打印、commit 消息都改成北京时间显示

# ====================== 记录程序开始时间（用于计算总耗时） ======================
start_time = time.time()
print(f"[{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 🚀 程序启动,开始动态搜索...")

# ====================== 通用限流处理函数 ======================
def handle_rate_limit(resp, operation_name="未知操作"):
    """统一处理 GitHub API 限流"""
    if resp.status_code != 403:
        return False
    reset_time = resp.headers.get('X-RateLimit-Reset')
    remaining = resp.headers.get('X-RateLimit-Remaining', 'Unknown')
    if reset_time:
        wait_seconds = int(reset_time) - int(time.time()) + 10
        print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 触发限流 | Remaining: {remaining} | 等待 {wait_seconds} 秒...")
        time.sleep(max(wait_seconds, 60))
    else:
        print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 触发限流 | 保守等待 90 秒...")
        time.sleep(90)
    return True

# ====================== 新增：安全请求函数（防止卡死） ======================
def safe_get(url, timeout=25, max_retries=3, operation_name="请求"):
    """
    带重试、超时和限流处理的请求函数
    目的是防止脚本在 GitHub API 响应慢或限流时卡死
    """
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔄 {operation_name} 第 {attempt}/{max_retries} 次尝试...")
            resp = requests.get(url, headers=headers, timeout=timeout)

            # 处理限流
            if handle_rate_limit(resp, operation_name):
                continue
                
            if resp.status_code != 200:
                print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 返回状态码: {resp.status_code} (尝试 {attempt}/{max_retries})")
                time.sleep(5)
                continue
                
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] {operation_name} 成功")
            return resp

        except requests.exceptions.Timeout:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 超时 (尝试 {attempt}/{max_retries})")
        except requests.exceptions.ConnectionError:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 连接错误 (尝试 {attempt}/{max_retries})")
        except Exception as e:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ {operation_name} 异常: {e} (尝试 {attempt}/{max_retries})")

        # 指数退避等待
        wait = 8 * attempt
        print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 等待 {wait} 秒后重试...")
        time.sleep(wait)
    
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ❌ {operation_name} 多次失败，已跳过")
    return None

# ====================== 增强版节点提取函数（大幅优化，支持更多风格） ======================
def extract_nodes_from_text(text):
    """
    增强版节点提取函数 - 支持几乎所有协议和格式
    支持协议和格式：
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
    """
    nodes = []
    if not text or len(text.strip()) < 10:
        return nodes

    # 1. 提取标准协议链接（vmess://, vless://, trojan://, ss:// 等）
    protocol_pattern = r'(vmess|vless|trojan|ss|ssr|hysteria|hysteria2|tuic|reality)://[^\s<>"\']{15,}'
    found = re.findall(protocol_pattern, text, re.IGNORECASE)
    nodes.extend(found)

    # 2. 特别处理 Shadowsocks ss:// 完整 base64 格式（包括带 # 备注）
    ss_pattern = r'ss://[A-Za-z0-9+/=]+(?:#[^\s<>"\']*)?'
    ss_matches = re.findall(ss_pattern, text, re.IGNORECASE)
    nodes.extend(ss_matches)

    # 3. 提取 Clash / Sing-box YAML 单行节点 - {name: ..., server: ..., type: ...}
    yaml_single_pattern = r'-\s*\{[^}]*?(?:name|server|port|type|uuid|password|ps|flow|reality-opts|sni|fp|client-fingerprint)[^}]*\}'
    yaml_matches = re.findall(yaml_single_pattern, text, re.IGNORECASE | re.DOTALL)
    for match in yaml_matches:
        clean = match.strip()
        if clean and len(clean) > 40 and ('type:' in clean or 'uuid:' in clean or 'password:' in clean):
            clean = re.sub(r'\s+', ' ', clean)  # 清理多余空格
            nodes.append(clean)

    # 4. 提取 Clash 多行 proxies 格式（从 name: 开始到下一个 name: 或结尾）
    yaml_multi_pattern = r'-\s*name:.*?(?=-\s*name:|\Z)'
    multi_matches = re.findall(yaml_multi_pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    for match in multi_matches:
        clean = match.strip()
        if clean and len(clean) > 30 and ('server:' in clean or 'type:' in clean):
            clean = re.sub(r'\s+', ' ', clean)
            nodes.append(clean)

    # 5. JSON 格式 proxies / outbounds 
    # 匹配 proxies: [ { "name": "...", "type": "vless", ... } ]
    try:
        # 尝试解析整个文本为 JSON（有些文件是纯 JSON）
        data = json.loads(text)
        if isinstance(data, dict):
            proxies = data.get("proxies") or data.get("outbounds")
            if isinstance(proxies, list):
                for p in proxies:
                    if isinstance(p, dict):
                        node_str = json.dumps(p, ensure_ascii=False)
                        nodes.append(node_str)
    except:
        pass

    # 6. 新增：匹配文本中出现的 proxies 数组（即使不是完整 JSON）
    proxies_array_pattern = r'"proxies"\s*:\s*\[([\s\S]*?)\]'
    array_matches = re.findall(proxies_array_pattern, text, re.IGNORECASE)
    for arr in array_matches:
        # 提取每个对象
        obj_pattern = r'\{[\s\S]*?\}'
        objs = re.findall(obj_pattern, arr)
        for obj in objs:
            if '"type"' in obj and ('"vless"' in obj or '"trojan"' in obj or '"ss"' in obj or '"hysteria"' in obj):
                nodes.append(obj.strip())

    # 7. 提取 raw 订阅链接并加入处理队列
    raw_link_pattern = r'https?://raw\.githubusercontent\.com/([^/\s]+/[^/\s]+)'
    raw_matches = re.findall(raw_link_pattern, text, re.IGNORECASE)
    for repo_path in raw_matches:
        repo_path = repo_path.strip()
        if not repo_path or '/' not in repo_path:
            continue
        # 如果这个仓库还没有处理过，就当作正常发现的仓库处理
        if repo_path not in seen_repos:
            print(f" 🔗 从文本中发现 raw 订阅链接 → https://github.com/{repo_path} ，加入处理队列")
            # 防止重复处理
            seen_repos.add(repo_path)
            # 注意：checked_count 是全局变量，必须用 global 声明才能修改
            global checked_count
            checked_count += 1
            # 走完整处理流程（commit时间 + 文件树）
            process_repo(repo_path)

    # 8. 加强 base64 解码（处理各种嵌套和复杂情况）
    base64_pattern = r'[A-Za-z0-9+/=]{60,}'
    base64_candidates = re.findall(base64_pattern, text)

    for b64 in base64_candidates:
        b64 = b64.strip()
        if len(b64) < 60 or b64.startswith('//'):
            continue
        try:
            # 自动补全 padding
            padding = len(b64) % 4
            if padding:
                b64 += '=' * (4 - padding)
            decoded = base64.b64decode(b64, validate=False).decode('utf-8', errors='ignore')
            for line in decoded.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith(('vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://', 'hysteria://', 'hysteria2://', 'tuic://', 'reality://')):

                    nodes.append(line)
                elif '{' in line and ('type:' in line or 'uuid:' in line or 'password:' in line):
                    nodes.append(line)
        except:
            # 尝试去掉前导 // 再解码一次
            try:
                clean = b64.lstrip('/')
                padding = len(clean) % 4
                if padding:
                    clean += '=' * (4 - padding)
                decoded = base64.b64decode(clean, validate=False).decode('utf-8', errors='ignore')
                for line in decoded.splitlines():
                    line = line.strip()
                    if line.startswith(('vmess://', 'vless://', 'trojan://', 'ss://', 'hysteria2://', 'tuic://')):
                        nodes.append(line)
            except:
                pass

    # 最终清理：去重 + 过滤明显无效行
    cleaned_nodes = []
    seen = set()
    for n in nodes:
        n = n.strip()
        if not n or n.startswith('//') or len(n) < 15:
            continue
        if n in seen:
            continue
        seen.add(n)
        cleaned_nodes.append(n)
    return cleaned_nodes

# ====================== 新增：验证raw链接是否有效且包含有效节点 =================
def is_valid_node_link(link):
    """
    验证 raw 链接是否可访问且包含有效节点
    返回 (valid, nodes)
    """
    try:
        print(f" 🔄 验证订阅链接: {link}")   # 显示完整 raw 链接
        resp = safe_get(link, timeout=20, operation_name="验证订阅链接")
        if resp is None or resp.status_code != 200:
            return False, None

        content = resp.text.strip()
        if len(content) < 30:    # 内容太短，基本无效
            return False, None
        nodes = extract_nodes_from_text(content)
        # 返回 True 只要提取到了节点（即使后续去重）
        return bool(nodes), nodes
    except Exception as e:
        print(f" ⚠️ 验证链接时发生异常: {e} | 链接: {link}")
        return False, None


# ====================== 公共方法：处理单个仓库 ======================
def process_repo(repo):
    """公共方法：处理单个仓库（检查更新时间 + 调用文件树处理）"""
    #print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 检查仓库 ({checked_count}): https://github.com/{repo}")

    commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    c_resp = safe_get(commit_url, timeout=15, operation_name=f"仓库 {repo} commit 查询")
    if c_resp is None or c_resp.status_code != 200:
        return
    try:
        commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
        commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - commit_time >= timedelta(hours=24):
            return

        #print(f" ✓ 发现新的24h更新仓库 ({checked_count}): https://github.com/{repo}")
        # 调用文件树处理方法
        process_file_tree(repo)
    except Exception as e:
        print(f" 处理仓库 https://github.com/{repo} 时发生异常: {e}（已跳过）")


# ====================== 公共方法：处理文件树（核心逻辑） ======================
def process_file_tree(repo):

    """公共方法：处理仓库的文件树，提取符合条件的订阅文件"""
    print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 开始处理文件树: https://github.com/{repo}")
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    t_resp = safe_get(tree_url, timeout=25, operation_name=f"文件树 {repo}")
    if t_resp is None or t_resp.status_code != 200:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 文件树请求失败或超时: {github_url}")
        return
    
    for file in t_resp.json().get("tree", []):
        if file["type"] != "blob":
            continue
        fname = file["path"].lower()
        # 把 README.md 也当作普通文件处理
        if not fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64", ".list", "readme.md")):
            continue
        if not any(k in fname for k in ["clash", "v2ray", "trojan", "hysteria", "hysteria2", "vless", "vmess", "ss", "ssr", "tuic", "reality", "sub", "proxy", "node", "base64", "config", "list", "readme"]):
            continue

        # 对每个具体文件单独检查最后 commit 时间（解决多层嵌套问题）
        file_commit_url = f"https://api.github.com/repos/{repo}/commits?path={file['path']}&per_page=1"
        f_resp = safe_get(file_commit_url, timeout=12, operation_name=f"文件 {file['path']} commit 查询")
        if f_resp is None or f_resp.status_code != 200:
            continue
        
        try:
            file_time_str = f_resp.json()[0]["commit"]["committer"]["date"]
            file_time = datetime.fromisoformat(file_time_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - file_time >= timedelta(hours=24):
                continue
            
            # 生成完整的 raw 链接
            file_url = f"https://raw.githubusercontent.com/{repo}/main/{file['path']}"
            #print(f" 🔄 验证订阅链接: {file_url}")   # 显示完整 raw 链接
            # 关键修改：验证 + 提取节点
            valid, nodes = is_valid_node_link(file_url)

            if valid and nodes:
                all_links.append(file_url)

                # === 区分三种情况的核心逻辑 ===
                before_count = len(unique_nodes)
                unique_nodes.update(nodes)        #把节点加入去重集合
                after_count = len(unique_nodes)

                added_count = after_count - before_count
                #if added_count > 0:
                    # 情况1：提取出了新节点
                    #print(f" 📄 文件 {file_url:.<60} ✅ 提取成功 | 新增 {added_count} 条节点（共 {len(nodes)} 条）")
                #else:
                    # 情况2：提取出了节点，但全部重复
                    #print(f" 📄 文件 {file_url:.<60} ⚪ 全部重复 | 提取 {len(nodes)} 条节点（均已存在）")
                global query_links_count
                query_links_count += 1
            else:
                # 情况3：没有提取出任何节点
                print(f" 📄 文件 {file_url:.<60} ❌ 提取失败 | 没有提取到有效节点（格式不支持或内容无效）")
        except Exception as e:
            file_url = f"https://raw.githubusercontent.com/{repo}/main/{file['path']}"
            print(f" 📄 文件 {file_url:.<60} ❌ 处理异常: {e} (已跳过)")

# ====================== 主程序 ======================

for query_idx, query in enumerate(QUERIES, 1):
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔎 开始搜索第 {query_idx}/{len(QUERIES)} 个关键词: {query}")

    query_links_count = 0   # 当前关键词贡献的链接数量

    page = 1
    while page <= 10:          # 不能超过 30 页，前面几页质量更好更高效
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 正在请求第 {page} 页...")
        
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
        resp = safe_get(url, timeout=30, operation_name=f"搜索关键词第{page}页")
        
        if resp is None:
            print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 搜索请求失败，跳过当前页")
            break
        
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
            if repo in seen_repos:
                continue
            seen_repos.add(repo)
            checked_count += 1
            # 调用仓库处理方法（会检查 commit 时间 + 处理文件树 + 提取节点）
            process_repo(repo)
            time.sleep(0.5)   # (秒)每个仓库轻微等待，避免请求过快
        page += 1
        time.sleep(2)   # (秒)翻页间隔，降低 API 压力
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] └─ 本关键词贡献 {query_links_count} 条有效链接")

# ====================== 最终处理 写入文件 ======================
# 【关键修复】先读取旧文件做对比，再写入新文件

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
added_nodes = new_nodes - old_nodes
removed_nodes = old_nodes - new_nodes
kept_nodes = new_nodes & old_nodes

print(f"\n📈 no.txt 节点对比报告")
print(f" 新 no.txt 节点总数 : {len(new_nodes):,} 条")
print(f" 旧 no.txt 节点总数 : {len(old_nodes):,} 条")
print(f" 新增节点 : {len(added_nodes):,} 条 (+{len(added_nodes)})")
print(f" 去除节点 : {len(removed_nodes):,} 条 (-{len(removed_nodes)})")
print(f" 保留节点（新旧都有） : {len(kept_nodes):,} 条")


# ====================== no_li.txt 新旧链接对比 ======================

new_links = set(all_links)
added_links = new_links - old_links
removed_links = old_links - new_links
kept_links = new_links & old_links

print(f"\n🔗 no_li.txt 链接对比报告")
print(f" 新 no_li.txt 链接总数 : {len(new_links):,} 条")
print(f" 旧 no_li.txt 链接总数 : {len(old_links):,} 条")
print(f" 新增链接 : {len(added_links):,} 条 (+{len(added_links)})")
print(f" 去除链接 : {len(removed_links):,} 条 (-{len(removed_links)})")
print(f" 保留链接（新旧都有） : {len(kept_links):,} 条")


# ====================== 最终总结日志 ======================
print(f"\n🎉 [{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 搜集任务完成！总耗时: {runtime_str}")
print(f" 共检查仓库数量: {len(seen_repos):,} 个")
print(f" 最终获得独特订阅链接: {len(all_links):,} 条")
print(f" no.txt 中去重后节点数量: {len(unique_nodes):,} 条")
print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ 已保存 no_li.txt 和 no.txt 文件")
