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

print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 程序启动，开始动态搜索...")

# ====================== 通用限流处理函数 ======================
def handle_rate_limit(resp, operation_name="未知操作"):
    """统一处理 GitHub API 限流"""
    if resp.status_code != 403:
        return False
    reset_time = resp.headers.get('X-RateLimit-Reset')
    remaining = resp.headers.get('X-RateLimit-Remaining', 'Unknown')
    if reset_time:
        wait_seconds = int(reset_time) - int(time.time()) + 10
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {operation_name} 触发限流 | Remaining: {remaining} | 等待 {wait_seconds} 秒...")
        time.sleep(max(wait_seconds, 60))
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ {operation_name} 触发限流 | 保守等待 90 秒...")
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

# ====================== 主程序 ======================
for query_idx, query in enumerate(QUERIES, 1):
    print(f"[{query_idx}/{len(QUERIES)}] 搜索关键词: {query}")
    query_links_count = 0
    page = 1
    while page <= 8:
        print(f" [{datetime.now().strftime('%H:%M:%S')}] 正在请求第 {page} 页...")
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
                print(f" [{datetime.now().strftime('%H:%M:%S')}] 第{page}页没有结果，结束当前关键词搜索")
                break
            for item in items:
                repo = item["full_name"]
                if repo in seen_repos:
                    continue
                seen_repos.add(repo)
                checked_count += 1
                print(f"    [{datetime.now().strftime('%H:%M:%S')}]     检查仓库 ({checked_count}): {repo}")
                commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
                c_resp = requests.get(commit_url, headers=headers, timeout=10)
                if handle_rate_limit(c_resp, f"仓库 {repo} commit 查询"):
                    continue
                if c_resp.status_code != 200:
                    continue
                try:
                    commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
                    commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - commit_time >= timedelta(hours=24):
                        continue
                    print(f"      ✓ 发现24h更新仓库 ({checked_count}): {repo}")
                    # ==================== 统一处理：README 和文件树 ====================
                    # 处理 README
                    readme_url = f"https://raw.githubusercontent.com/{repo}/main/README.md"
                    r = requests.get(readme_url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        nodes_from_readme = extract_nodes_from_text(r.text)
                        if nodes_from_readme:
                            unique_nodes.update(nodes_from_readme)
                            print(f"        从 README 提取到 {len(nodes_from_readme)} 条节点")

                    # 处理文件树中的订阅文件
                    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
                    t_resp = requests.get(tree_url, headers=headers, timeout=10)
                    if t_resp.status_code == 200:
                        for file in t_resp.json().get("tree", []):
                            if file["type"] == "blob":
                                fname = file["path"].lower()
                                if fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64", ".list")) and \
                                   any(k in fname for k in ["clash", "v2ray", "trojan", "hysteria", "vless", "vmess", "ss", "sub", "proxy", "node", "base64", "config", "list"]):
                                    file_url = f"https://raw.githubusercontent.com/{repo}/main/{file['path']}"
                                    all_links.append(file_url)
                                    # 下载文件内容并提取节点（与 README 使用同一逻辑）
                                    file_resp = requests.get(file_url, headers=headers, timeout=10)
                                    if file_resp.status_code == 200:
                                        nodes_from_file = extract_nodes_from_text(file_resp.text)
                                        if nodes_from_file:
                                            unique_nodes.update(nodes_from_file)
                                            print(f"        从文件 {file['path']} 提取到 {len(nodes_from_file)} 条节点")
                except Exception as e:
                    print(f"      处理仓库 {repo} 时发生异常: {e}（已跳过）")
                time.sleep(0.25)
        except Exception as e:
            print(f"  关键词 '{query}' 第{page}页发生异常: {e}")
        page += 1
        time.sleep(0.6)
    print(f"[{datetime.now().strftime('%H:%M:%S')}]   └─ 本关键词贡献 {query_links_count} 条链接")

# ====================== 最终处理 ======================
# 把去重后的节点写入 no.txt
if unique_nodes:
    with open("no.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 已将 {len(unique_nodes)} 条去重后的节点保存到 no.txt")

# 生成 no.txt 的 raw 链接
repo_name = os.getenv("GITHUB_REPOSITORY", "2530ZZZ/cooo")
no_txt_raw_url = f"https://raw.githubusercontent.com/{repo_name}/main/no.txt"
all_links.append(no_txt_raw_url)

# 全局去重常规链接
all_links = list(dict.fromkeys(all_links))

print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🎉 搜集任务完成！")
print(f" 共检查仓库数量: {len(seen_repos)} 个")
print(f" 最终获得独特订阅链接: {len(all_links)} 条")
print(f" no.txt 中去重后节点数量: {len(unique_nodes)} 条")

with open("da_fr_no.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_links))

print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 已保存到 da_fr_no.txt 文件")
