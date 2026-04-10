import sys
import re
import time
from datetime import datetime, timedelta, timezone

beijing_tz = timezone(timedelta(hours=8))

if len(sys.argv) < 3:
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ❌ 用法错误: python fi_no.py <alive.txt> <fi_no.txt>")
    sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]

print(f"[{datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')}] 🚀 开始处理最终节点...")

# =============== 读取 subs-check 输来的存活节点（标准协议格式） ================
START_TIME = time.time()
with open(input_file, "r", encoding="utf-8") as f:
    nodes = [line.strip() for line in f if line.strip()]

print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 📊 共加载 {len(nodes):,} 个存活节点（已通过 subs-check 测活测速）")

# 限制数量，防止 sing-box 或后续处理卡死（推荐 3000~5000）

MAX_NODES = 5000
if len(nodes) > MAX_NODES:
    original_count = len(nodes)
    nodes = nodes[:MAX_NODES]
    print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ⚠️ 节点过多，自动截取前 {MAX_NODES} 个")

# ====================== 国家识别函数 ======================
def extract_country(node_url: str) -> str:
    """从节点链接、备注、域名中智能提取国家/地区（覆盖30+ 常见地区）"""
    if not node_url:
        return '🌍 UN'

    upper = node_url.upper()


    # ==================== 1. 常见国家/地区映射（最高优先级） ====================
    country_map = {
        'US': '🇺🇸 US', 'USA': '🇺🇸 US', 'UNITED STATES': '🇺🇸 US',
        'JP': '🇯🇵 JP', 'JAPAN': '🇯🇵 JP',
        'SG': '🇸🇬 SG', 'SINGAPORE': '🇸🇬 SG',
        'HK': '🇭🇰 HK', 'HONG KONG': '🇭🇰 HK',
        'TW': '🇹🇼 TW', 'TAIWAN': '🇹🇼 TW',
        'KR': '🇰🇷 KR', 'KOREA': '🇰🇷 KR', 'SOUTH KOREA': '🇰🇷 KR',
        'DE': '🇩🇪 DE', 'GERMANY': '🇩🇪 DE',
        'FR': '🇫🇷 FR', 'FRANCE': '🇫🇷 FR',
        'GB': '🇬🇧 GB', 'UK': '🇬🇧 GB', 'UNITED KINGDOM': '🇬🇧 GB',
        'CA': '🇨🇦 CA', 'CANADA': '🇨🇦 CA',
        'AU': '🇦🇺 AU', 'AUSTRALIA': '🇦🇺 AU',
        'RU': '🇷🇺 RU', 'RUSSIA': '🇷🇺 RU',
        'BR': '🇧🇷 BR', 'BRAZIL': '🇧🇷 BR',
        'IN': '🇮🇳 IN', 'INDIA': '🇮🇳 IN',
        'NL': '🇳🇱 NL', 'NETHERLANDS': '🇳🇱 NL',
        'TR': '🇹🇷 TR', 'TURKEY': '🇹🇷 TR',
        'ID': '🇮🇩 ID', 'INDONESIA': '🇮🇩 ID',
        'MY': '🇲🇾 MY', 'MALAYSIA': '🇲🇾 MY',
        'TH': '🇹🇭 TH', 'THAILAND': '🇹🇭 TH',
        'VN': '🇻🇳 VN', 'VIETNAM': '🇻🇳 VN',
        'IT': '🇮🇹 IT', 'ITALY': '🇮🇹 IT',
        'ES': '🇪🇸 ES', 'SPAIN': '🇪🇸 ES',
        'SE': '🇸🇪 SE', 'SWEDEN': '🇸🇪 SE',
        'FI': '🇫🇮 FI', 'FINLAND': '🇫🇮 FI',
        'PL': '🇵🇱 PL', 'POLAND': '🇵🇱 PL',
    }


    # 先从备注或名称中精确匹配
    for code, flag in country_map.items():
        if code in upper or f" {code} " in f" {upper} " or f"#{code}" in upper or f"-{code}" in upper:
            return flag


    # ==================== 2. 域名后缀判断 ====================
    domain_patterns = {
        r'\.us|\.com|\.net|\.io': '🇺🇸 US',
        r'\.jp|\.co\.jp': '🇯🇵 JP',
        r'\.sg|\.com\.sg': '🇸🇬 SG',
        r'\.hk|\.com\.hk': '🇭🇰 HK',
        r'\.tw|\.com\.tw': '🇹🇼 TW',
        r'\.kr|\.co\.kr': '🇰🇷 KR',
        r'\.de': '🇩🇪 DE',
        r'\.fr': '🇫🇷 FR',
        r'\.uk|\.co\.uk': '🇬🇧 GB',
        r'\.ca': '🇨🇦 CA',
        r'\.au': '🇦🇺 AU',
        r'\.ru': '🇷🇺 RU',
        r'\.br': '🇧🇷 BR',
        r'\.in': '🇮🇳 IN',
        r'\.nl': '🇳🇱 NL',
        r'\.tr': '🇹🇷 TR',
        r'\.id': '🇮🇩 ID',
        r'\.my': '🇲🇾 MY',
        r'\.th': '🇹🇭 TH',
        r'\.vn': '🇻🇳 VN',
    }

    for pattern, flag in domain_patterns.items():
        if re.search(pattern, node_url, re.I):
            return flag


    # ==================== 3. 服务器地址 / IP 段简单判断（可选增强） ====================
    # 如果节点包含常见国家城市关键词
    city_keywords = {
        'tokyo': '🇯🇵 JP', 'singapore': '🇸🇬 SG', 'hongkong': '🇭🇰 HK',
        'seoul': '🇰🇷 KR', 'frankfurt': '🇩🇪 DE', 'london': '🇬🇧 GB',
        'new york': '🇺🇸 US', 'los angeles': '🇺🇸 US', 'sydney': '🇦🇺 AU'
    }

    for keyword, flag in city_keywords.items():
        if keyword.upper() in upper:
            return flag



    return '🌍 UN'  # 未知国家
# ====================== 重命名主逻辑 ======================
final_nodes = []
country_counter = {}

print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🔄 开始对节点进行重命名（总序号 | 国家 | 同国家序号 | 速度）...")

for i, node in enumerate(nodes, 1):
    country = extract_country(node)
    
    if country not in country_counter:
        country_counter[country] = 0
    country_counter[country] += 1
    country_seq = country_counter[country]
    
    # 目前速度为占位，后续可从 alive.txt 解析真实速度
    speed_kb = "0"
    
    new_name = f"{i:04d} | {country} | {country_seq:02d} | {speed_kb}KB/s"
    
    if '#' in node:
        base, _ = node.split('#', 1)
        new_node = f"{base}#{new_name}"
    else:
        new_node = f"{node}#{new_name}"
    
    final_nodes.append(new_node)

# ====================== 保存最终结果 ======================
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(final_nodes))

END_TIME = time.time()
DURATION = int(END_TIME - START_TIME)

print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] 🎉 重命名完成！共 {len(final_nodes):,} 条标准协议节点")
print(f"   处理耗时: {DURATION} 秒")
print(f"   文件已保存 → {output_file}")
print(f"   示例格式：0001 | 🇺🇸 US | 01 | 0KB/s | vless://...")

# ====================== 国家分布统计 ======================
print(f"\n📊 国家分布统计（Top 15）：")
sorted_countries = sorted(country_counter.items(), key=lambda x: x[1], reverse=True)
for country, count in sorted_countries[:15]:
    print(f"   {country} : {count} 条")

print(f"[{datetime.now(beijing_tz).strftime('%H:%M:%S')}] ✅ fi_no.py 执行完毕")
