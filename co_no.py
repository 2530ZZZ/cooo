import requests
import re
import time
import base64
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
"free nodes subscription clash v2ray trojan hysteria", "free clash sub github",
"free v2ray config subscription", "V2RayRoot subscription", "TelegramV2rayCollector",
"ProxyCollector", "V2RAY-CLASH-BASE64-Subscription", "free proxy nodes sub trojan hysteria2",
"free nodes clash yaml", "v2ray subscription links github", "free clash subscribe",
"proxy collector v2ray", "free v2ray nodes subscription", "clash sub github",
"free airport nodes", "免费节点 订阅 clash v2ray", "免费clash订阅", "免费v2ray订阅",
"免费trojan订阅", "免费hysteria订阅", "免费节点 clash", "免费v2ray配置 github",
"免费机场节点", "free nodes daily", "free proxy daily github", "clash meta free nodes",
"singbox free nodes", "hysteria2 free sub github", "trojan free sub github",
"vless free nodes github", "vmess free nodes github", "ss free nodes github",
"ssr free nodes github", "free clash meta sub github", "free v2ray sub github",
"airport free nodes github", "free proxy collector github", "free v2ray collector github",
"free clash collector github", "免费节点订阅", "免费clash节点", "免费v2ray节点",
"免费机场订阅", "clash free subscription github", "v2ray free sub github",
"free nodes sub", "free proxy list clash", "free v2ray config github", "free hysteria2 nodes",
"free trojan nodes github", "free ss nodes github", "free ssr nodes github",
"free singbox nodes github", "free mihomo nodes", "free clash for windows nodes",
"free shadowrocket nodes", "free hiddify nodes", "free v2rayng nodes"
]

# ==================== 全局变量 ====================
all_links = []                    # 最终收集到的所有订阅链接（常规订阅文件）



seen_repos = set()                # 已检查过的仓库（关键：实现智能跳过重复仓库）
checked_count = 0                 # 统计总共检查了多少个仓库
unique_nodes = set()              # 全局去重集合（用于最终生成干净的 no.txt）
query_links_count = 0             # 当前关键词贡献的链接数量

beijing_tz = timezone(timedelta(hours=8))     # 所有日志、打印、commit 消息都改成北京时间显示

# ====================== 记录程序开始时间（用于计算总耗时） ======================
start_time = time.time()

print(f"[{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 🚀 程序启动，开始动态搜索...")

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

# ====================== 新增：统一节点提取函数 ======================
def extract_nodes_from_text(text):
    """
    公共方法：从任意文本（README 或订阅文件内容）中提取节点
    支持所有常见协议 + base64 解码
    返回去重后的节点列表
    """
    nodes = []
    # 协议节点提取
    protocol_pattern = r'(vmess|vless|trojan|ss|ssr|hysteria2|tuic|reality)://[^\s<>"\']{10,}'
    found = re.findall(protocol_pattern, text)
    nodes.extend(found)

    # base64 整段节点提取 + 解码
    base64_pattern = r'[A-Za-z0-9+/=]{80,}'
    base64_candidates = re.findall(base64_pattern, text)
    for b64 in base64_candidates:
        try:
            decoded = base64.b64decode(b64 + '==').decode('utf-8', errors='ignore')
            lines = decoded.splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith(('vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://', 'hysteria2://', 'tuic://')):
                    nodes.append(line)
        except:
            # 解码失败，保留原始 base64
            nodes.append(b64)
    return nodes

# ====================== 新增：验证raw链接是否有效且包含节点 =================
def is_valid_node_link(link):
    """
    验证 raw 链接是否可访问且包含有效节点
    同时返回所包含的节点
    """
    try:
        resp = requests.get(link, headers=headers, timeout=10)
        if resp.status_code != 200:
            return False, None
        content = resp.text.strip()
        if len(content) < 50:    # 内容太短，基本无效
            return False, None
        nodes = extract_nodes_from_text(content)
        if nodes:
            return True, nodes
        return False, None
    except:
        return False, None

# ====================== 公共方法：处理单个仓库 ======================
def process_repo(repo):
    """公共方法：处理单个仓库（检查更新时间 + 调用文件树处理）"""
    print(f"    [{datetime.now(beijing_tz).strftime('%H:%M:%S')}]     检查仓库 ({checked_count}): {repo}")

    commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
    c_resp = requests.get(commit_url, headers=headers, timeout=10)
    if handle_rate_limit(c_resp, f"仓库 {repo} commit 查询"):
        return
    if c_resp.status_code != 200:
        return

    try:
        commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
        commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - commit_time >= timedelta(hours=24):
            return

        print(f"      ✓ 发现24h更新仓库 ({checked_count}): {repo}")
        # 调用文件树处理方法
        process_file_tree(repo)
    except Exception as e:
        print(f"      处理仓库 {repo} 时发生异常: {e}（已跳过）")

# ====================== 公共方法：处理文件树（核心逻辑） ======================
def process_file_tree(repo):
    """公共方法：处理仓库的文件树，提取符合条件的订阅文件"""
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    t_resp = requests.get(tree_url, headers=headers, timeout=10)
    if t_resp.status_code != 200:
        return

    for file in t_resp.json().get("tree", []):
        if file["type"] != "blob":
            continue

        fname = file["path"].lower()
        # 把 README.md 也当作普通文件处理
        if not fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64", ".list", "readme.md")):
            continue
        if not any(k in fname for k in ["clash", "v2ray", "trojan", "hysteria", "vless", "vmess", "ss", "sub", "proxy", "node", "base64", "config", "list", "readme"]):
            continue

        # 对每个具体文件单独检查最后 commit 时间（解决多层嵌套问题）
        file_commit_url = f"https://api.github.com/repos/{repo}/commits?path={file['path']}&per_page=1"
        f_resp = requests.get(file_commit_url, headers=headers, timeout=10)
        if f_resp.status_code != 200:
            continue

        try:
            file_time_str = f_resp.json()[0]["commit"]["committer"]["date"]
            file_time = datetime.fromisoformat(file_time_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - file_time >= timedelta(hours=24):
                continue

            file_url = f"https://raw.githubusercontent.com/{repo}/main/{file['path']}"

            # 关键修改：验证 + 提取节点
            valid, nodes = is_valid_node_link(file_url)
            if valid and nodes:
                all_links.append(file_url)
                unique_nodes.update(nodes)    # ← 这里把节点加入去重集合
                print(f"      📄 文件 {file['path']:.<60} ✅ 有效 | 提取 {len(nodes):>5} 条节点")
            else:
                print(f"      📄 文件 {file['path']:.<60} ❌ 无效（无有效节点或无法访问）")
        except Exception as e:
            print(f"      📄 文件 {file['path']:.<60} ❌ 处理异常: {e} (已跳过)")

# ====================== 主程序 ======================
for query_idx, query in enumerate(QUERIES, 1):
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔎 开始搜索第 {query_idx}/{len(QUERIES)} 个关键词: {query}")
    global query_links_count          # 声明全局变量
    query_links_count = 0
    page = 1
    while page <= 8:
        print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 正在请求第 {page} 页...")
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if handle_rate_limit(resp, f"搜索关键词第{page}页"):
                continue
            if resp.status_code != 200:
                print(f" 搜索失败，第{page}页状态码: {resp.status_code}")
                break
            items = resp.json().get("items", [])
            if not items:
                print(f" [{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 第{page}页没有结果，结束当前关键词搜索")
                break

            for item in items:
                repo = item["full_name"]
                if repo in seen_repos:
                    continue
                seen_repos.add(repo)
                checked_count += 1
                # 调用仓库处理方法
                process_repo(repo)
                time.sleep(0.25)
        except Exception as e:
            print(f"  关键词 '{query}' 第{page}页发生异常: {e}")
        page += 1
        time.sleep(0.6)
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}]   └─ 本关键词贡献 {query_links_count} 条有效链接")

# ====================== 最终处理 写入文件 ======================
# 把去重后的节点写入 no.txt
if unique_nodes:
    with open("no.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ 已将 {len(unique_nodes):,} 条去重后的节点保存到 no.txt")
else:
    print(f"\n[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️  未提取到任何有效节点")

# 生成 no.txt 的 raw 链接 加入到 da_fr_no.txt
repo_name = os.getenv("GITHUB_REPOSITORY", "2530ZZZ/cooo")
no_txt_raw_url = f"https://raw.githubusercontent.com/{repo_name}/main/no.txt"
all_links.append(no_txt_raw_url)

# 全局去重常规链接
all_links = list(dict.fromkeys(all_links))

with open("da_fr_no.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_links))


# ====================== 日志信息处理 ======================
# 计算总耗时
total_seconds = int(time.time() - start_time)
hours = total_seconds // 3600
minutes = (total_seconds % 3600) // 60
seconds = total_seconds % 60
runtime_str = f"{hours}小时 {minutes}分 {seconds}秒" if hours > 0 else f"{minutes}分 {seconds}秒"

# ====================== no.txt 新旧节点对比 ======================

old_nodes = set()
if os.path.exists("no.txt"):
    with open("no.txt", "r", encoding="utf-8") as f:
        old_nodes = {line.strip() for line in f if line.strip()}

new_nodes = unique_nodes
added_nodes = new_nodes - old_nodes
removed_nodes = old_nodes - new_nodes
kept_nodes = new_nodes & old_nodes

print(f"\n📈 no.txt 节点对比报告")
print(f"   新 no.txt 节点总数     : {len(new_nodes):,} 条")
print(f"   旧 no.txt 节点总数     : {len(old_nodes):,} 条")
print(f"   新增节点               : {len(added_nodes):,} 条 (+{len(added_nodes)})")
print(f"   去除节点               : {len(removed_nodes):,} 条 (-{len(removed_nodes)})")
print(f"   保留节点（新旧都有）   : {len(kept_nodes):,} 条")

# ====================== da_fr_no.txt 新旧链接对比 ======================
old_links = set()
if os.path.exists("da_fr_no.txt"):
    with open("da_fr_no.txt", "r", encoding="utf-8") as f:
        old_links = {line.strip() for line in f if line.strip()}

new_links = set(all_links)
added_links = new_links - old_links
removed_links = old_links - new_links
kept_links = new_links & old_links

print(f"\n🔗 da_fr_no.txt 链接对比报告")
print(f"   新 da_fr_no.txt 链接总数 : {len(new_links):,} 条")
print(f"   旧 da_fr_no.txt 链接总数 : {len(old_links):,} 条")
print(f"   新增链接                 : {len(added_links):,} 条 (+{len(added_links)})")
print(f"   去除链接                 : {len(removed_links):,} 条 (-{len(removed_links)})")
print(f"   保留链接（新旧都有）     : {len(kept_links):,} 条")



# ====================== 最终总结日志 ======================
print(f"\n🎉 [{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 搜集任务完成！总耗时: {runtime_str}")
print(f"   共检查仓库数量: {len(seen_repos):,} 个")
print(f"   最终获得独特订阅链接: {len(all_links):,} 条")
print(f"   no.txt 中去重后节点数量: {len(unique_nodes):,} 条")
print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ 已保存 da_fr_no.txt 和 no.txt 文件")
