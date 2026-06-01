"""报告工具模块 - 包含报告生成相关的辅助函数"""
import os
import json
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "mock_data")

def generate_report_summary(metrics, comments, report_type):
    """生成报告摘要"""
    product_names = {
        'game_a': '游戏A - 战神传说',
        'game_b': '游戏B - 星际争霸',
        'game_c': '游戏C - 魔法大陆'
    }
    
    products = list(set(m.get('product') for m in metrics))
    total_downloads = sum(int(m.get('值', 0)) for m in metrics if m.get('metric') == '用户总下载量')
    
    type_labels = {
        'daily': '日报',
        'weekly': '周报',
        'monthly': '月报'
    }
    
    return f"📊 {type_labels.get(report_type, '报表')} - {datetime.now().strftime('%Y年%m月%d日')}\n\n" \
           f"📱 覆盖产品：{', '.join([product_names.get(p, p) for p in products])}\n" \
           f"📥 总下载量：{total_downloads:,}\n" \
           f"💬 评论数量：{len(comments)}条\n" \
           f"📈 数据周期：{report_type}"

def generate_product_details(metrics):
    """生成产品详情"""
    product_names = {
        'game_a': '游戏A - 战神传说',
        'game_b': '游戏B - 星际争霸',
        'game_c': '游戏C - 魔法大陆'
    }
    
    products = list(set(m.get('product') for m in metrics))
    details = []
    
    for product in products:
        p_metrics = [m for m in metrics if m.get('product') == product]
        download = next((m for m in p_metrics if m.get('metric') == '用户总下载量'), None)
        arppu = next((m for m in p_metrics if 'ARPPU' in m.get('metric', '')), None)
        retention = next((m for m in p_metrics if '留存率' in m.get('metric', '')), None)
        
        details.append({
            "product": product_names.get(product, product),
            "downloads": download.get('值', 0) if download else 0,
            "arppu": arppu.get('值', '0') if arppu else '0',
            "retention": retention.get('值', '0%') if retention else '0%',
            "channels": list(set(m.get('channel') for m in p_metrics))
        })
    
    return details

def analyze_trends(metrics):
    """分析趋势"""
    trends = []
    
    products = list(set(m.get('product') for m in metrics))
    for product in products:
        p_metrics = [m for m in metrics if m.get('product') == product]
        download_metric = next((m for m in p_metrics if m.get('metric') == '用户总下载量'), None)
        
        if download_metric and download_metric.get('环比变化'):
            change = download_metric['环比变化']
            trend_type = 'up' if change.startswith('+') else 'down'
            trends.append({
                "product": product,
                "metric": "下载量",
                "change": change,
                "trend": trend_type
            })
    
    return trends

def generate_recommendations(metrics, comments):
    """生成建议"""
    recommendations = []
    
    products = list(set(m.get('product') for m in metrics))
    for product in products:
        p_metrics = [m for m in metrics if m.get('product') == product]
        retention = next((m for m in p_metrics if '留存率' in m.get('metric', '')), None)
        
        if retention:
            retention_val = float(retention.get('值', '0').replace('%', ''))
            if retention_val < 30:
                recommendations.append({
                    "product": product,
                    "type": "critical",
                    "title": "留存率偏低",
                    "suggestion": "建议优化新手引导流程，增加新手福利活动"
                })
    
    return recommendations