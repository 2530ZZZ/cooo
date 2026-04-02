import requests
import re
import time
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
# 120+ 关键词变体（已最大化覆盖）
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
    # 更多变体...
    "free nodes sub", "free proxy list clash", "free v2ray config github", "free hysteria2 nodes",
    "free trojan nodes github", "free ss nodes github", "free ssr nodes github",
    "free singbox nodes github", "free mihomo nodes", "free clash for windows nodes",
    "free shadowrocket nodes", "free hiddify nodes", "free v2rayng nodes"
]

# ==================== 全局变量 ====================

all_links = []           # 最终收集到的所有订阅链接
seen_repos = set()       # 已检查过的仓库（关键：实现智能跳过重复仓库）
checked_count = 0        # 统计总共检查了多少个仓库



# ====================== 通用限流处理函数 ======================
def handle_rate_limit(resp, operation_name="未知操作"):
    """
    统一处理 GitHub API 限流
    返回 True 表示已处理限流，需要重试；返回 False 表示未触发限流
    """
    if resp.status_code != 403:
        return False
    
    reset_time = resp.headers.get('X-RateLimit-Reset')
    remaining = resp.headers.get('X-RateLimit-Remaining', 'Unknown')
    
    if reset_time:
        wait_seconds = int(reset_time) - int(time.time()) + 10
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  {operation_name} 触发限流 | Remaining: {remaining} | 等待 {wait_seconds} 秒...")
        time.sleep(max(wait_seconds, 60))
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  {operation_name} 触发限流 | 保守等待 90 秒...")
        time.sleep(90)
    return True

# ====================== 主程序 ======================
print(f"🚀 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始动态搜索...")

for query_idx, query in enumerate(QUERIES, 1):
    print(f"[{query_idx}/{len(QUERIES)}] 搜索关键词: {query}")
	# 当前关键词贡献的链接数量
    query_links_count = 0   

    page = 1
    while page <= 8:
		print(f"  [{datetime.now().strftime('%H:%M:%S')}]   正在请求第 {page} 页...")
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            
			# 调用通用限流处理函数
            if handle_rate_limit(resp, f"搜索关键词第{page}页"):
				# 限流后重试当前页
                continue
                
            if resp.status_code != 200:
                print(f"  搜索失败，第{page}页状态码: {resp.status_code}")
                break

            items = resp.json().get("items", [])
            if not items:
				print(f"  [{datetime.now().strftime('%H:%M:%S')}]   第{page}页没有结果，结束当前关键词搜索")
                break   

        # ==================== 处理搜索结果中的每个仓库 ====================
            for item in items:
            repo = item["full_name"]   # 格式如: "Pawdroid/Free-servers"

            # ==================== 智能跳过已检查仓库 ====================
                if repo in seen_repos:
                    continue               # 同一个仓库被多个关键词搜索到时，只处理一次
                    
                seen_repos.add(repo)       # 标记为已检查
                checked_count += 1

            # ==================== 验证仓库是否在过去24小时内有更新 ====================
                # 检查仓库最新 commit
				print(f"    [{datetime.now().strftime('%H:%M:%S')}]     检查仓库 ({checked_count}): {repo}")
				
                commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
                c_resp = requests.get(commit_url, headers=headers, timeout=10)
                
                if handle_rate_limit(c_resp, f"仓库 {repo} commit 查询"):
                    continue
                    
                if c_resp.status_code != 200:
					print(f"    [{datetime.now().strftime('%H:%M:%S')}]   仓库 ({checked_count}): {repo}   commit 查询失败，状态码: {c_resp.status_code}")
                    continue

                try:
                    commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
                    commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
                    
                    if datetime.now(timezone.utc) - commit_time >= timedelta(hours=24):
						print(f"    [{datetime.now().strftime('%H:%M:%S')}]     仓库 ({checked_count}): {repo}   超过24小时未更新，跳过")
                        continue

                    print(f"    ✓ 发现24h更新仓库 ({checked_count}): {repo}")


                    # ==================== 提取订阅链接 ====================

                    # 方法1: 从 README.md 中提取所有 raw.githubusercontent.com 链接（最常用、最准确）
                    readme_url = f"https://raw.githubusercontent.com/{repo}/main/README.md"
                    r = requests.get(readme_url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        extracted = re.findall(r'https?://raw\.githubusercontent\.com/[^"\s<>`\'\)]+', r.text)
                        all_links.extend(extracted)
                        query_links_count += len(extracted)
						print(f"     [{datetime.now().strftime('%H:%M:%S')}]      从 README 提取到 {len(extracted)} 条链接")

                    # 方法2: 遍历仓库文件树，自动发现可能的订阅文件
                    tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
                    t_resp = requests.get(tree_url, headers=headers, timeout=10)
                    if t_resp.status_code == 200:
						file_count = 0
                        for file in t_resp.json().get("tree", []):
                            if file["type"] == "blob":    # 是文件而不是目录
                                fname = file["path"].lower()
                                # 如果文件名包含常见关键词且是常见订阅格式
                                if fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64", ".list")) and \
                                   any(k in fname for k in ["clash", "v2ray", "trojan", "hysteria", "vless", "vmess", "ss", "sub", "proxy", "node", "base64", "config", "list"]):
                                    file_url = f"https://raw.githubusercontent.com/{repo}/main/{file['path']}"
                                    all_links.append(file_url)
									file_count += 1
                        if file_count > 0:
                            query_links_count += file_count
                            print(f"      [{datetime.now().strftime('%H:%M:%S')}]       从文件树{fname}  提取到 {file_count} 条订阅文件")
                # 单个仓库出错不影响整体运行
                except Exception as e:
                    print(f"      [{datetime.now().strftime('%H:%M:%S')}]       处理仓库 {repo} 时发生异常: {e}（已跳过）")

                # 每次处理完一个仓库后稍微等待，避免触发次要限流
                time.sleep(0.25)

        except Exception as e:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}]   关键词 '{query}' 第{page}页发生异常: {e}")
        
        # 处理完一页后等待
        page += 1
        time.sleep(0.6)

    print(f"[{datetime.now().strftime('%H:%M:%S')}]   关键词 '{query}' 总共贡献 {query_links_count} 条链接")



# ==================== 最终处理 ====================

# 全局去重（防止同一个链接被多次加入）
all_links = list(dict.fromkeys(all_links))

print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🎉 搜集任务完成！")
print(f"   共检查仓库数量: {len(seen_repos)} 个")
print(f"   最终获得独特订阅链接: {len(all_links)} 条")

# 保存到文件
with open("da_fr_no.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_links))

print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 已保存到 da_fr_no.txt 文件")
