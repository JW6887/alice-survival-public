"""
Alice 跨境AI选品Agent — 核心引擎原型
HS编码查询 + 关税计算 + 供应链匹配
"""
import json
import re
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# HS编码数据库（核心品类）
# ═══════════════════════════════════════════════════════════
HS_DB = {
    "储能电池": {"hs_cn": "8507.60", "hs_eu": "8507.60", "hs_us": "8507.60.00", "duty_eu": 0, "duty_us": 3.4},
    "锂电池": {"hs_cn": "8507.60", "hs_eu": "8507.60", "hs_us": "8507.60.00", "duty_eu": 0, "duty_us": 3.4},
    "便携电源": {"hs_cn": "8507.60", "hs_eu": "8507.60", "hs_us": "8507.60.00", "duty_eu": 0, "duty_us": 3.4},
    "逆变器": {"hs_cn": "8504.40", "hs_eu": "8504.40", "hs_us": "8504.40.95", "duty_eu": 0, "duty_us": 0},
    "太阳能板": {"hs_cn": "8541.43", "hs_eu": "8541.43", "hs_us": "8541.43.00", "duty_eu": 0, "duty_us": 0},
    "LED灯": {"hs_cn": "9405.40", "hs_eu": "9405.40", "hs_us": "9405.40.84", "duty_eu": 3.7, "duty_us": 3.9},
    "数据线": {"hs_cn": "8544.42", "hs_eu": "8544.42", "hs_us": "8544.42.90", "duty_eu": 0, "duty_us": 0},
    "充电器": {"hs_cn": "8504.40", "hs_eu": "8504.40", "hs_us": "8504.40.95", "duty_eu": 0, "duty_us": 0},
    "蓝牙耳机": {"hs_cn": "8518.30", "hs_eu": "8518.30", "hs_us": "8518.30.20", "duty_eu": 0, "duty_us": 0},
    "手机壳": {"hs_cn": "3926.90", "hs_eu": "3926.90", "hs_us": "3926.90.99", "duty_eu": 6.5, "duty_us": 5.3},
    "瑜伽垫": {"hs_cn": "9506.91", "hs_eu": "9506.91", "hs_us": "9506.91.00", "duty_eu": 4.7, "duty_us": 4.8},
    "厨房收纳": {"hs_cn": "7323.93", "hs_eu": "7323.93", "hs_us": "7323.93.00", "duty_eu": 3.2, "duty_us": 2.0},
    "宠物用品": {"hs_cn": "4201.00", "hs_eu": "4201.00", "hs_us": "4201.00.00", "duty_eu": 2.7, "duty_us": 4.8},
}

# ═══════════════════════════════════════════════════════════
# 关税计算引擎
# ═══════════════════════════════════════════════════════════
def calculate_landed_cost(product_name: str, exw_price_cny: float, 
                          weight_kg: float, destination: str = "EU") -> dict:
    """计算全程落地成本"""
    info = HS_DB.get(product_name)
    if not info:
        return {"error": f"未找到'{product_name}'的HS编码，请尝试其他关键词"}
    
    # 汇率
    cny_to_usd = 0.14  # 1 CNY ≈ 0.14 USD
    cny_to_eur = 0.13  # 1 CNY ≈ 0.13 EUR
    
    # 海运费用估算（每kg约$1.5-3）
    freight_per_kg = 2.0  # USD
    freight_usd = weight_kg * freight_per_kg
    
    # FOB价格
    fob_usd = exw_price_cny * cny_to_usd
    
    # 关税
    duty_rate = info.get("duty_eu" if destination == "EU" else "duty_us", 0)
    duty_usd = fob_usd * (duty_rate / 100)
    
    # VAT（欧盟约19-21%，美国各州不同取平均8%）
    vat_rate = 0.19 if destination == "EU" else 0.08
    vat_usd = (fob_usd + freight_usd + duty_usd) * vat_rate
    
    # 总落地成本
    total_usd = fob_usd + freight_usd + duty_usd + vat_usd
    
    return {
        "产品": product_name,
        "HS编码(目的地)": info.get("hs_eu" if destination == "EU" else "hs_us"),
        "出厂价(¥)": exw_price_cny,
        "FOB(USD)": round(fob_usd, 2),
        "运费(USD)": round(freight_usd, 2),
        f"关税({duty_rate}%)": round(duty_usd, 2),
        f"VAT({vat_rate*100:.0f}%)": round(vat_usd, 2),
        "总落地成本(USD)": round(total_usd, 2),
        "落地加价率": f"{(total_usd/fob_usd - 1)*100:.0f}%",
        "建议零售价(USD)": round(total_usd * 2.5, 2),  # keystone markup
    }

# ═══════════════════════════════════════════════════════════
# 关键词→产品匹配引擎
# ═══════════════════════════════════════════════════════════
def match_product(user_query: str) -> list:
    """从自然语言中匹配产品"""
    query_lower = user_query.lower()
    matches = []
    keywords_map = {
        "储能电池": ["储能", "储能电池", "电池储能", "bess", "energy storage", "lifepo4"],
        "便携电源": ["便携", "户外电源", "portable power", "移动电源"],
        "逆变器": ["逆变器", "inverter", "转换器", "变流器"],
        "太阳能板": ["太阳能", "光伏", "solar", "panel", "太阳能板"],
        "LED灯": ["led", "灯", "照明", "lighting", "灯泡"],
        "蓝牙耳机": ["耳机", "蓝牙", "earbuds", "earphone", "tws"],
        "手机壳": ["手机壳", "case", "保护壳"],
        "瑜伽垫": ["瑜伽", "yoga", "健身垫", "运动垫"],
        "厨房收纳": ["厨房", "收纳", "kitchen", "organizer", "置物架"],
        "宠物用品": ["宠物", "pet", "猫", "狗", "dog", "cat"],
    }
    for product, keywords in keywords_map.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            matches.append((product, score))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches

# ═══════════════════════════════════════════════════════════
# 主Agent逻辑
# ═══════════════════════════════════════════════════════════
def alice_select(user_query: str, budget_cny: float = 0, 
                 destination: str = "EU", weight_kg: float = 1.0):
    """
    Alice选品Agent主入口
    
    参数:
        user_query: 自然语言需求描述
        budget_cny: 采购预算（人民币）
        destination: 目标市场 EU/US
        weight_kg: 单件重量
    """
    matches = match_product(user_query)
    
    if not matches:
        return {"error": "未能匹配产品，请提供更具体的描述"}
    
    results = []
    for product, score in matches[:3]:
        cost = calculate_landed_cost(product, budget_cny if budget_cny else 50, 
                                      weight_kg, destination)
        cost["匹配度"] = f"{score}/{len(matches[0]) if matches else 1}"
        results.append(cost)
    
    return {
        "查询": user_query,
        "目标市场": destination,
        "匹配产品": [m[0] for m in matches[:5]],
        "成本分析": results,
        "建议": generate_recommendation(results, destination),
    }

def generate_recommendation(results: list, destination: str) -> str:
    """生成选品建议"""
    if not results:
        return "数据不足，无法生成建议"
    
    best = results[0]
    margin = float(best.get("落地加价率", "0%").replace("%", ""))
    
    tips = []
    if margin < 15:
        tips.append(f"⚠️ 落地加价率仅{margin:.0f}%，利润空间偏薄，建议议价或更换品类")
    elif margin < 25:
        tips.append(f"落地加价率{margin:.0f}%，利润适中")
    else:
        tips.append(f"✅ 落地加价率{margin:.0f}%，利润空间充足")
    
    if destination == "EU":
        tips.append("欧盟注意CE认证+WEEE注册")
    else:
        tips.append("美国注意FCC认证+UL标准")
    
    return " | ".join(tips)

# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    test_queries = [
        ("帮我找欧洲市场、客单价100元左右的储能相关产品", 100, "EU", 2.0),
        ("美国有什么厨房收纳的好品类", 30, "US", 0.5),
    ]
    
    for q, budget, dest, weight in test_queries:
        print(f"\n{'='*60}")
        print(f"🔍 {q}")
        print(f"{'='*60}")
        result = alice_select(q, budget, dest, weight)
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print(f"匹配产品: {result['匹配产品']}")
            for item in result['成本分析']:
                print(f"\n📦 {item.get('产品','?')}:")
                for k, v in item.items():
                    if k != "产品":
                        print(f"   {k}: {v}")
            print(f"\n💡 {result['建议']}")
