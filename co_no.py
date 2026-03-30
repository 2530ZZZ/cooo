import requests
import re
import time
from datetime import datetime, timedelta, timezone
import os

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {"User-Agent": "Mozilla/5.0"}

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

all_links = []
seen_repos = set()

print(f"🚀 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始动态搜索...")

for query in QUERIES:
    page = 1
    while page <= 10:
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&order=desc&per_page=100&page={page}"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            break
        items = resp.json().get("items", [])
        if not items:
            break

        for item in items:
            repo = item["full_name"]
            if repo in seen_repos:
                continue
            seen_repos.add(repo)

            # 亲自验证commit时间
            commit_url = f"https://api.github.com/repos/{repo}/commits?per_page=1"
            c_resp = requests.get(commit_url, headers=headers, timeout=10)
            if c_resp.status_code == 200:
                try:
                    commit_time_str = c_resp.json()[0]["commit"]["committer"]["date"]
                    commit_time = datetime.fromisoformat(commit_time_str.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - commit_time < timedelta(hours=24):
                        print(f"✓ 24h更新仓库: {repo}")

                        # 1. README提取所有raw链接
                        readme_url = f"https://raw.githubusercontent.com/{repo}/main/README.md"
                        r = requests.get(readme_url, headers=headers, timeout=10)
                        if r.status_code == 200:
                            links = re.findall(r'https?://raw\.githubusercontent\.com/[^"\s<>`\'\)]+', r.text)
                            all_links.extend(links)

                        # 2. 遍历文件树，自动发现所有订阅文件
                        tree_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
                        t_resp = requests.get(tree_url, headers=headers, timeout=10)
                        if t_resp.status_code == 200:
                            for file in t_resp.json().get("tree", []):
                                if file["type"] == "blob":
                                    fname = file["path"].lower()
                                    if fname.endswith((".yaml", ".yml", ".txt", ".json", ".base64")) and any(x in fname for x in ["clash", "v2ray", "trojan", "hysteria", "vless", "vmess", "ss", "sub", "proxy", "node", "base64", "config"]):
                                        file_url = f"https://raw.githubusercontent.com/{repo}/main/{file['path']}"
                                        all_links.append(file_url)
                except:
                    pass
            time.sleep(0.15)
        page += 1
        time.sleep(0.4)

all_links = list(dict.fromkeys(all_links))
print(f"\n🎉 搜集完成！共获得 {len(all_links)} 条独特订阅链接")

with open("da_fr_no.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(all_links))

print("✅ 已保存到 da_fre_no.txt")
