"""
Game Analyzer Advanced Analytics Module
游戏数据分析引擎高级分析模块
包含：用户行为路径分析、漏斗分析、群组分析、实时数据流
"""
import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mock_data')


def _parse_metric_value(raw) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace("¥", "").replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def _sum_metric_values(metrics_data, *exact_names, contains=()):
    total = 0.0
    count = 0
    for row in metrics_data or []:
        name = str(row.get("metric") or "")
        if name in exact_names or any(token in name for token in contains):
            total += _parse_metric_value(row.get("值"))
            count += 1
    return total, count


def _derive_scale_metric(metrics_data) -> int:
    """Map mock + MVP Steam metrics to a comparable scale figure."""
    downloads, _ = _sum_metric_values(metrics_data, "用户总下载量")
    if downloads:
        return int(downloads)
    review_total, _ = _sum_metric_values(
        metrics_data,
        contains=("抓取评论数", "Steam汇总评论数", "评论数"),
    )
    if review_total:
        return int(review_total)
    return 0


def _derive_arppu(metrics_data) -> float:
    total, count = _sum_metric_values(metrics_data, contains=("ARPPU",))
    if count:
        return round(total / count, 2)
    price_total, price_count = _sum_metric_values(
        metrics_data,
        contains=("当前价格", "price"),
    )
    if price_count:
        return round((price_total / price_count) / 100.0, 2)
    return 0.0


class RealTimeDataStream:
    """
    实时数据流管理器
    - WebSocket 连接管理
    - 实时指标计算
    - 数据广播
    """
    
    def __init__(self):
        self.connections = []
        self.metrics_cache = {}
        self.last_update = None
        # 用于保持数据连续性的状态变量
        self.last_online_users = 2500
        # 今日收入基准值（0点开始累计）
        self.daily_revenue_base = 0
        self.last_hour = None
        # 最近30天的日均收入
        self.avg_daily_revenue = 10000
        self.current_daily_revenue = 0  # 今日实际累计收入
    
    def calculate_real_time_metrics(self, metrics_data):
        """
        计算实时指标
        
        指标说明：
        - today_revenue: 今日累计收入（从0点到现在），应该是递增的
        - estimated_daily_revenue: 预计今日总收入（根据当前进度估算）
        - current_rate: 当前时段的收入速率
        """
        current_time = datetime.now()
        hour = current_time.hour
        weekday = current_time.weekday()  # 0=周一, 6=周日
        
        # ============= 今日累计收入（实际发生） =============
        # 如果是新的一天，重置累计值
        if self.last_hour is not None and self.last_hour > hour:
            self.current_daily_revenue = 0
        self.last_hour = hour
        
        # 计算当前小时应该累计的收入
        # 基于历史数据和时段因子计算
        hour_factor = 1.5 if 20 <= hour <= 23 else 0.6 if 0 <= hour <= 6 else 1.0
        weekend_factor = 1.25 if weekday >= 5 else 1.0
        
        # 每小时的基础收入（根据历史数据）
        hourly_base = self.avg_daily_revenue * weekend_factor / 24
        
        # 当前小时的收入（考虑时段因子）
        current_hour_revenue = hourly_base * hour_factor
        
        # 添加小量随机波动（±5%）
        current_hour_revenue *= random.uniform(0.95, 1.05)
        
        # 累计到今日收入
        self.current_daily_revenue += current_hour_revenue
        
        # ============= 在线用户数（实时变化） =============
        # 时段效应：晚上8-11点在线人数最高
        online_hour_factor = 1.5 if 20 <= hour <= 23 else 0.7 if 0 <= hour <= 6 else 1.0
        # 平滑随机波动（避免剧烈跳变）
        online_change = random.randint(-50, 50)
        online_users = int(self.last_online_users + online_change * online_hour_factor)
        online_users = max(1000, min(5000, online_users))
        self.last_online_users = online_users
        
        # ============= 预计今日总收入 =============
        # 根据当前进度估算全天的收入
        hours_passed = hour + 1
        progress_rate = hours_passed / 24
        estimated_daily = self.current_daily_revenue / progress_rate if progress_rate > 0 else 0
        
        # ============= 关键指标（兼容 mock 与 MVP Steam 指标名） =============
        total_downloads = _derive_scale_metric(metrics_data)
        avg_arppu = _derive_arppu(metrics_data)
        positive_total, positive_count = _sum_metric_values(
            metrics_data,
            contains=("好评率", "评分", "rating"),
        )
        steam_positive_rate = (
            round(positive_total / positive_count, 1) if positive_count else None
        )
        
        real_time_metrics = {
            'timestamp': current_time.isoformat(),
            'online_users': online_users,
            'today_revenue': round(self.current_daily_revenue, 2),  # 今日累计收入（递增）
            'estimated_daily_revenue': round(estimated_daily, 2),  # 预计今日总收入
            'current_hour_revenue': round(current_hour_revenue, 2),  # 当前小时收入
            'hours_passed': hours_passed,
            'total_downloads': total_downloads,
            'avg_arppu': avg_arppu,
            'steam_positive_rate': steam_positive_rate,
            'revenue_trend': self._generate_trend_data(),
            'data_explanation': self._generate_data_explanation(
                hour, weekday, self.current_daily_revenue, estimated_daily, metrics_data
            )
        }
        
        self.metrics_cache = real_time_metrics
        self.last_update = current_time
        return real_time_metrics
    
    def _generate_trend_data(self):
        """
        生成趋势数据（用于图表）
        模拟真实的收入波动模式
        """
        now = datetime.now()
        current_hour = now.hour
        data = []
        base_value = 500
        
        for i in range(24):
            hour_time = now - timedelta(hours=23 - i)
            hour = hour_time.hour
            
            # 时段效应
            hour_factor = 1.5 if 20 <= hour <= 23 else 0.5 if 0 <= hour <= 6 else 1.0
            # 添加随机噪声
            noise = random.randint(-50, 50)
            
            value = int(base_value * hour_factor + noise)
            value = max(100, min(1000, value))
            
            data.append({
                'time': hour_time.strftime('%H:00'),
                'value': value,
                'is_current': hour == current_hour
            })
        
        return data
    
    def _generate_data_explanation(self, hour, weekday, current_revenue, estimated_revenue, metrics_data=None):
        """
        生成数据解释说明
        """
        explanations = []
        
        # 时段说明
        if 20 <= hour <= 23:
            explanations.append('当前处于晚间高峰时段，收入和在线人数通常较高')
        elif 0 <= hour <= 6:
            explanations.append('当前处于凌晨低谷时段，收入和在线人数通常较低')
        elif 9 <= hour <= 12:
            explanations.append('当前处于上午活跃时段')
        elif 14 <= hour <= 17:
            explanations.append('当前处于下午活跃时段')
        
        # 周末说明
        if weekday >= 5:
            explanations.append('今日是周末，用户活跃度和收入通常高于工作日')
        else:
            explanations.append('今日是工作日，数据符合正常业务规律')
        
        # 数据含义说明
        explanations.append(f'今日累计: ¥{current_revenue:,.0f} | 预计全天: ¥{estimated_revenue:,.0f}')
        if metrics_data and _derive_scale_metric(metrics_data) and not any(
            str(m.get("metric") or "") == "用户总下载量" for m in metrics_data
        ):
            explanations.append('规模指标来自 Steam 评论/口碑样本（演示实时曲线仍为模型估算）')
        
        return ' | '.join(explanations)

class UserJourneyAnalyzer:
    """
    用户行为路径分析器
    - 路径可视化
    - 流失节点识别
    - 转化率计算
    """
    
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        
    def analyze_user_journey(self, time_range: str = 'all', products: List[str] = None):
        """
        分析用户行为路径
        """
        if products is None:
            products = ['all']
        
        product_data = {}
        for product in products:
            base_count = hash(product) % 300 + 700
            
            journey_nodes = [
                {'id': 'launch', 'name': '启动游戏', 'count': 10000 * base_count // 1000, 'type': 'start'},
                {'id': 'login', 'name': '登录', 'count': 9500 * base_count // 1000, 'type': 'normal'},
                {'id': 'tutorial', 'name': '新手教程', 'count': 7500 * base_count // 1000, 'type': 'normal'},
                {'id': 'first_battle', 'name': '首次战斗', 'count': 6000 * base_count // 1000, 'type': 'normal'},
                {'id': 'level_up', 'name': '首次升级', 'count': 4500 * base_count // 1000, 'type': 'normal'},
                {'id': 'first_purchase', 'name': '首次付费', 'count': 800 * base_count // 1000, 'type': 'conversion'},
                {'id': 'churn', 'name': '流失', 'count': 9200 * base_count // 1000, 'type': 'end'}
            ]
            
            journey_edges = [
                {'source': 'launch', 'target': 'login', 'value': 9500 * base_count // 1000},
                {'source': 'login', 'target': 'tutorial', 'value': 7500 * base_count // 1000},
                {'source': 'tutorial', 'target': 'first_battle', 'value': 6000 * base_count // 1000},
                {'source': 'first_battle', 'target': 'level_up', 'value': 4500 * base_count // 1000},
                {'source': 'level_up', 'target': 'first_purchase', 'value': 800 * base_count // 1000},
                {'source': 'tutorial', 'target': 'churn', 'value': 1500 * base_count // 1000},
                {'source': 'first_battle', 'target': 'churn', 'value': 1500 * base_count // 1000},
                {'source': 'level_up', 'target': 'churn', 'value': 3700 * base_count // 1000}
            ]
            
            for i in range(len(journey_nodes) - 1):
                if journey_nodes[i].get('type') != 'start' and journey_nodes[i].get('count'):
                    prev_count = journey_nodes[i].get('count')
                    if i > 0:
                        prev_node = journey_nodes[i - 1]
                        prev_count = prev_node.get('count')
                    if prev_count > 0:
                        journey_nodes[i]['conversion_rate'] = round(journey_nodes[i]['count'] / prev_count * 100, 1)
            
            product_data[product] = {
                'nodes': journey_nodes,
                'edges': journey_edges,
                'summary': {
                    'total_users': 10000 * base_count // 1000,
                    'final_conversion_rate': 8.0 + (hash(product) % 5 - 2),
                    'high_dropoff_points': self._identify_dropoff_points(journey_edges, journey_nodes)
                }
            }
        
        first_product = products[0] if products else 'all'
        first_data = product_data.get(first_product, product_data.get('all'))
        
        return {
            'nodes': first_data['nodes'] if first_data else [],
            'edges': first_data['edges'] if first_data else [],
            'summary': {
                'total_users': 10000,
                'final_conversion_rate': 8.0,
                'high_dropoff_points': first_data['summary']['high_dropoff_points'] if first_data else [],
                'journey_nodes': first_data['nodes'] if first_data else []
            },
            'by_product': product_data
        }
    
    def _identify_dropoff_points(self, edges, nodes):
        """
        识别高流失节点
        """
        dropoff_points = []
        node_map = {node['id']: node for node in nodes}
        
        for edge in edges:
            if edge['target'] == 'churn':
                source_node = node_map.get(edge['source'], {})
                count = edge['value']
                dropoff_rate = round(count / source_node.get('count', 1) * 100, 1)
                if dropoff_rate > 20:
                    dropoff_points.append({
                        'node': edge['source'],
                        'node_name': source_node.get('name', ''),
                        'count': count,
                        'rate': dropoff_rate,
                        'severity': 'high' if dropoff_rate > 30 else 'medium'
                    })
        
        return sorted(dropoff_points, key=lambda x: x['count'], reverse=True)
    
    def get_path_distribution(self, products: List[str] = None, sample_size=100):
        """
        获取路径分布（多条路径对比）
        """
        if products is None:
            products = ['all']
        
        product_data = {}
        for product in products:
            base_count = hash(product) % 500 + 500
            paths = [
                {'path': '启动→登录→新手教程→战斗→升级→付费', 'count': int(800 * base_count / 1000), 'color': '#22c55e'},
                {'path': '启动→登录→新手教程→战斗→流失', 'count': int(3700 * base_count / 1000), 'color': '#ef4444'},
                {'path': '启动→登录→新手教程→流失', 'count': int(1500 * base_count / 1000), 'color': '#f59e0b'},
                {'path': '启动→登录→流失', 'count': int(2000 * base_count / 1000), 'color': '#ef4444'},
                {'path': '其他路径', 'count': int(2000 * base_count / 1000), 'color': '#8b5cf6'}
            ]
            product_data[product] = paths
        return product_data

class FunnelAnalyzer:
    """
    漏斗分析器
    - 漏斗可视化
    - 转化率计算
    - 流失原因分析
    """
    
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
    
    def _get_product_base_data(self, product):
        """
        为不同产品生成差异化的基础数据
        """
        product_configs = {
            'game_a': {
                'name': '游戏A - 战神传说',
                'download_base': 10000,
                'register_rate': 0.65,
                'tutorial_rate': 0.69,
                'battle_rate': 0.78,
                'purchase_rate': 0.22,
                'health_score': 75,
                'issues': ['注册流程复杂', '新手引导过长']
            },
            'game_b': {
                'name': '游戏B - 星际争霸',
                'download_base': 8000,
                'register_rate': 0.72,
                'tutorial_rate': 0.75,
                'battle_rate': 0.82,
                'purchase_rate': 0.18,
                'health_score': 68,
                'issues': ['付费深度不足', '缺乏月卡选项']
            },
            'game_c': {
                'name': '游戏C - 魔法大陆',
                'download_base': 12000,
                'register_rate': 0.78,
                'tutorial_rate': 0.85,
                'battle_rate': 0.88,
                'purchase_rate': 0.32,
                'health_score': 88,
                'issues': ['暂无重大问题']
            }
        }
        return product_configs.get(product, product_configs['game_a'])
        
    def create_funnel(self, steps: List[str] = None, time_range: str = 'all', products: List[str] = None):
        """
        创建漏斗分析
        """
        if steps is None:
            steps = ['下载', '注册', '完成新手教程', '首次战斗', '首次充值']
        
        if products is None or products == ['all']:
            products = ['game_a']
        
        # 使用第一个产品的数据
        config = self._get_product_base_data(products[0])
        
        # 基于产品配置生成漏斗数据
        download = config['download_base']
        register = int(download * config['register_rate'])
        tutorial = int(register * config['tutorial_rate'])
        battle = int(tutorial * config['battle_rate'])
        purchase = int(battle * config['purchase_rate'])
        
        funnel_data = [
            {'step': '下载', 'count': download, 'conversion_from_top': 100.0, 'conversion_from_prev': 100.0},
            {'step': '注册', 'count': register, 'conversion_from_top': round(register/download*100, 1), 'conversion_from_prev': round(register/download*100, 1)},
            {'step': '完成新手教程', 'count': tutorial, 'conversion_from_top': round(tutorial/download*100, 1), 'conversion_from_prev': round(tutorial/register*100, 1)},
            {'step': '首次战斗', 'count': battle, 'conversion_from_top': round(battle/download*100, 1), 'conversion_from_prev': round(battle/tutorial*100, 1)},
            {'step': '首次充值', 'count': purchase, 'conversion_from_top': round(purchase/download*100, 1), 'conversion_from_prev': round(purchase/battle*100, 1)}
        ]
        recommendations = self._generate_funnel_recommendations(funnel_data, config)
        
        return {
            'steps': funnel_data,
            'total_conversion_rate': round(purchase/download*100, 1),
            'health_score': config['health_score'],
            'high_dropoff_steps': self._find_high_dropoff_steps(funnel_data),
            'recommendations': recommendations,
            'health_improvements': self._generate_funnel_health_improvements(
                funnel_data, config, config['health_score'], recommendations
            ),
        }
    
    def _find_high_dropoff_steps(self, funnel_data):
        """
        发现高流失步骤
        """
        dropoff_steps = []
        for i in range(1, len(funnel_data)):
            prev_step = funnel_data[i - 1]
            curr_step = funnel_data[i]
            dropoff_rate = 100 - curr_step['conversion_from_prev']
            if dropoff_rate > 40:
                dropoff_steps.append({
                    'step': curr_step['step'],
                    'dropoff_rate': round(dropoff_rate, 1),
                    'potential_improvement': round(prev_step['count'] * 0.1)
                })
        return dropoff_steps
    
    def _generate_funnel_recommendations(self, funnel_data, config=None):
        """
        生成优化建议
        """
        recommendations = []
        
        if config is None:
            config = {'issues': []}
        
        if funnel_data[1]['conversion_from_prev'] < 70:
            recommendations.append({
                'type': 'critical',
                'step': '注册',
                'suggestion': '注册转化率偏低，建议简化注册流程，支持第三方登录'
            })
        
        if funnel_data[2]['conversion_from_prev'] < 75:
            recommendations.append({
                'type': 'high',
                'step': '完成新手教程',
                'suggestion': '新手教程流失率较高，建议缩短教程时长，增加奖励激励'
            })
        
        if funnel_data[-1]['conversion_from_prev'] < 25:
            recommendations.append({
                'type': 'high',
                'step': '首次充值',
                'suggestion': '付费转化率偏低，建议优化首充礼包，增加新手引导'
            })
        
        # 根据产品特定问题添加建议
        for issue in config.get('issues', []):
            if issue == '注册流程复杂':
                recommendations.append({
                    'type': 'critical',
                    'step': '注册',
                    'suggestion': '注册流程过于复杂，建议支持手机号一键登录或第三方账号登录'
                })
            elif issue == '新手引导过长':
                recommendations.append({
                    'type': 'high',
                    'step': '新手教程',
                    'suggestion': '新手引导步骤过多，建议拆分为渐进式引导，允许跳过部分内容'
                })
            elif issue == '付费深度不足':
                recommendations.append({
                    'type': 'high',
                    'step': '首次充值',
                    'suggestion': '付费深度不足，建议增加捆绑包、月卡和季卡选项'
                })
            elif issue == '缺乏月卡选项':
                recommendations.append({
                    'type': 'medium',
                    'step': '充值',
                    'suggestion': '建议推出月卡会员服务，提升用户留存和付费频次'
                })
        
        return recommendations
    
    def _generate_funnel_health_improvements(
        self,
        funnel_data: List[Dict],
        config: Dict,
        health_score: int,
        recommendations: List[Dict],
    ) -> List[Dict]:
        """根据漏斗转化与健康分生成待改进项。"""
        improvements: List[Dict] = []

        if len(funnel_data) >= 2 and funnel_data[1]['conversion_from_prev'] < 70:
            improvements.append({
                'priority': 'high',
                'area': '注册转化',
                'suggestion': '注册环节流失偏高，建议简化表单并接入第三方快捷登录',
            })
        if len(funnel_data) >= 3 and funnel_data[2]['conversion_from_prev'] < 75:
            improvements.append({
                'priority': 'high',
                'area': '新手教程',
                'suggestion': '新手教程完成率不足，建议缩短步骤并增加完成奖励',
            })
        if funnel_data and funnel_data[-1]['conversion_from_prev'] < 25:
            improvements.append({
                'priority': 'high',
                'area': '首次充值',
                'suggestion': '付费转化偏低，建议优化首充礼包与付费引导时机',
            })

        for rec in recommendations:
            item = {
                'priority': rec.get('type', 'medium'),
                'area': rec.get('step', '漏斗'),
                'suggestion': rec.get('suggestion', ''),
            }
            if item['suggestion'] and item not in improvements:
                improvements.append(item)

        if health_score < 60 and not improvements:
            improvements.append({
                'priority': 'critical',
                'area': '整体转化',
                'suggestion': '漏斗健康度偏低，建议优先排查高流失步骤并做 A/B 验证',
            })
        elif health_score >= 80 and not improvements:
            improvements.append({
                'priority': 'low',
                'area': '维持优化',
                'suggestion': '转化链路整体健康，建议持续监控各步骤转化率波动',
            })

        seen = set()
        deduped = []
        for item in improvements:
            key = (item.get('area'), item.get('suggestion'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:4]
    
    def compare_funnels(self, time_range_a: str, time_range_b: str):
        """
        对比两个时间段的漏斗
        """
        return {
            'funnel_a': self.create_funnel(time_range=time_range_a),
            'funnel_b': self.create_funnel(time_range=time_range_b),
            'improvement_analysis': self._calculate_funnel_improvement()
        }
    
    def _calculate_funnel_improvement(self):
        """
        计算漏斗提升度
        """
        return {
            'metric': '整体转化率',
            'change': '+2.5%',
            'improvement': 'positive'
        }

class CohortAnalyzer:
    """
    群组分析器
    - 按时间/行为分群
    - 留存曲线分析
    - 群组对比
    """
    
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
    
    def _get_product_cohort_config(self, product):
        """
        为不同产品生成差异化的群组数据配置
        """
        product_configs = {
            'game_a': {
                'name': '游戏A - 战神传说',
                'initial_users_range': (1000, 2000),
                'retention_d1_range': (40, 48),
                'retention_d7_range': (22, 30),
                'retention_d30_range': (10, 18),
                'revenue_range': (15, 25),
                'arppu_range': (50, 80),
                'health_score': 72
            },
            'game_b': {
                'name': '游戏B - 星际争霸',
                'initial_users_range': (800, 1500),
                'retention_d1_range': (35, 45),
                'retention_d7_range': (18, 28),
                'retention_d30_range': (8, 15),
                'revenue_range': (12, 22),
                'arppu_range': (45, 75),
                'health_score': 65
            },
            'game_c': {
                'name': '游戏C - 魔法大陆',
                'initial_users_range': (1500, 2500),
                'retention_d1_range': (48, 55),
                'retention_d7_range': (28, 38),
                'retention_d30_range': (15, 25),
                'revenue_range': (20, 35),
                'arppu_range': (60, 100),
                'health_score': 85
            }
        }
        return product_configs.get(product, product_configs['game_a'])
        
    def create_cohort(self, cohort_type: str = 'weekly', date_range: str = None, products: List[str] = None):
        """
        创建群组分析
        """
        if products is None or products == ['all']:
            products = ['game_a']
        
        # 使用第一个产品的配置
        config = self._get_product_cohort_config(products[0])
        
        # 生成群组数据
        weeks = ['第1周', '第2周', '第3周', '第4周', '第5周']
        cohorts = []
        
        for i, week in enumerate(weeks):
            # 使用产品特定的范围
            d1_range = config['retention_d1_range']
            d7_range = config['retention_d7_range']
            d30_range = config['retention_d30_range']
            rev_range = config['revenue_range']
            arppu_range = config['arppu_range']
            user_range = config['initial_users_range']
            
            cohort_data = {
                'cohort_week': week,
                'initial_users': random.randint(user_range[0], user_range[1]),
                'retention_d1': round(random.uniform(d1_range[0], d1_range[1]), 1),
                'retention_d7': round(random.uniform(d7_range[0], d7_range[1]), 1),
                'retention_d30': round(random.uniform(d30_range[0], d30_range[1]), 1),
                'revenue_per_user': round(random.uniform(rev_range[0], rev_range[1]), 2),
                'arppu': round(random.uniform(arppu_range[0], arppu_range[1]), 2)
            }
            cohorts.append(cohort_data)
        
        # 生成留存矩阵
        retention_matrix = self._generate_retention_matrix(cohorts)
        summary = {
            'best_retention_cohort': weeks[0],
            'avg_retention_d7': sum(c['retention_d7'] for c in cohorts) / len(cohorts),
            'avg_revenue_per_user': sum(c['revenue_per_user'] for c in cohorts) / len(cohorts),
            'health_score': config['health_score'],
        }
        summary['improvements'] = self._generate_cohort_improvements(cohorts, summary)
        
        return {
            'cohorts': cohorts,
            'retention_matrix': retention_matrix,
            'summary': summary,
        }
    
    def _generate_cohort_improvements(self, cohorts: List[Dict], summary: Dict) -> List[Dict]:
        """根据留存与付费指标生成待改进项。"""
        if not cohorts:
            return [{
                'priority': 'medium',
                'area': '数据',
                'suggestion': '群组样本不足，建议扩大观察周期后再评估',
            }]

        improvements: List[Dict] = []
        avg_d7 = float(summary.get('avg_retention_d7') or 0)
        avg_d30 = sum(c['retention_d30'] for c in cohorts) / len(cohorts)
        avg_arppu = sum(c['arppu'] for c in cohorts) / len(cohorts)
        health_score = int(summary.get('health_score') or 0)

        if avg_d7 < 20:
            improvements.append({
                'priority': 'critical',
                'area': '7日留存',
                'suggestion': f'平均7日留存仅 {avg_d7:.1f}%，需优先优化新手体验与首日目标引导',
            })
        elif avg_d7 < 30:
            improvements.append({
                'priority': 'high',
                'area': '7日留存',
                'suggestion': f'平均7日留存 {avg_d7:.1f}% 未达优秀线（30%），建议加强前3日内容与社交玩法',
            })

        if avg_d30 < 12:
            improvements.append({
                'priority': 'high',
                'area': '30日留存',
                'suggestion': f'30日留存 {avg_d30:.1f}% 偏低，建议增加中期活动、赛季目标与回流机制',
            })
        elif avg_d30 < 18:
            improvements.append({
                'priority': 'medium',
                'area': '30日留存',
                'suggestion': f'30日留存 {avg_d30:.1f}% 有提升空间，可优化长线内容与付费节奏',
            })

        if avg_arppu < 50:
            improvements.append({
                'priority': 'high',
                'area': 'ARPPU',
                'suggestion': f'平均 ARPPU ¥{avg_arppu:.2f} 偏低，建议优化付费点设计与首充转化',
            })
        elif avg_arppu < 65:
            improvements.append({
                'priority': 'medium',
                'area': 'ARPPU',
                'suggestion': f'平均 ARPPU ¥{avg_arppu:.2f} 可继续挖掘，建议测试捆绑包与月卡',
            })

        worst = min(cohorts, key=lambda c: c['retention_d7'])
        if worst['retention_d7'] < avg_d7 - 4:
            improvements.append({
                'priority': 'medium',
                'area': worst['cohort_week'],
                'suggestion': (
                    f'{worst["cohort_week"]} 7日留存 {worst["retention_d7"]}% 明显低于均值，'
                    '建议回溯该批次渠道质量与版本变更'
                ),
            })

        if health_score < 60 and not improvements:
            improvements.append({
                'priority': 'critical',
                'area': '综合健康度',
                'suggestion': '综合健康度偏低，建议联动漏斗分析与用户访谈定位核心流失原因',
            })
        elif health_score >= 80 and len(improvements) == 0:
            improvements.append({
                'priority': 'low',
                'area': '维持优化',
                'suggestion': '当前群组指标健康，建议持续监控留存曲线与 ARPPU 波动',
            })

        seen = set()
        deduped = []
        for item in improvements:
            key = (item.get('area'), item.get('suggestion'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:4]
    
    def _generate_retention_matrix(self, cohorts):
        """
        生成留存矩阵
        """
        matrix = []
        weeks = ['第0周', '第1周', '第2周', '第3周', '第4周']
        
        for cohort_idx in range(len(cohorts)):
            row = [100.0]  # 第0周留存率总是100%
            for week_idx in range(1, 5 - cohort_idx):
                base_retention = 100 - (week_idx * 15) + random.randint(-10, 10)
                row.append(max(5, round(base_retention, 1)))
            matrix.append(row)
        
        return {
            'weeks': weeks,
            'matrix': matrix
        }
    
    def analyze_retention_by_cohort(self, cohort_id: str):
        """
        分析特定群组的留存曲线
        """
        retention_curve = [
            {'day': 1, 'retention': 45.2},
            {'day': 3, 'retention': 35.8},
            {'day': 7, 'retention': 28.5},
            {'day': 14, 'retention': 18.2},
            {'day': 30, 'retention': 10.5},
            {'day': 60, 'retention': 6.3},
            {'day': 90, 'retention': 4.2}
        ]
        
        return {
            'cohort_id': cohort_id,
            'retention_curve': retention_curve,
            'health_score': self._calculate_health_score(retention_curve)
        }
    
    def _calculate_health_score(self, retention_curve):
        """
        计算健康度评分
        """
        if retention_curve and len(retention_curve) >= 2:
            d7_retention = retention_curve[2]['retention']
            if d7_retention >= 30:
                return {'score': 'A', 'color': '#22c55e', 'description': '优秀'}
            elif d7_retention >= 20:
                return {'score': 'B', 'color': '#f59e0b', 'description': '良好'}
            else:
                return {'score': 'C', 'color': '#ef4444', 'description': '需要关注'}
        return {'score': 'N/A', 'color': '#94a3b8', 'description': '数据不足'}
    
    def compare_cohorts(self, cohort_ids: List[str]):
        """
        对比多个群组
        """
        comparison_data = []
        for cohort_id in cohort_ids:
            cohort_data = self.analyze_retention_by_cohort(cohort_id)
            comparison_data.append(cohort_data)
        
        return {
            'comparison_data': comparison_data,
            'best_performer': cohort_ids[0] if cohort_ids else None
        }

class PredictiveAnalyzer:
    """
    预测分析器
    - 用户生命周期价值（LTV）预测
    - 流失概率预测
    - 高价值用户识别
    """
    
    def __init__(self):
        self.user_data_cache = {}
        
    def predict_ltv(self, user_id: str = None, prediction_days: int = 30):
        """
        预测用户LTV
        - 基于历史付费行为
        - 预测未来收益
        """
        # 模拟用户数据
        historical_revenue = random.uniform(50, 500)
        avg_purchase = random.uniform(20, 100)
        purchase_frequency = random.randint(1, 20)
        days_active = random.randint(1, 30)
        
        # 简单的线性回归预测模型
        base_ltv = historical_revenue * (1 + purchase_frequency * 0.5)
        growth_rate = 1.1 if days_active > 20 else 0.9 if days_active < 10 else 1.0
        predicted_ltv = base_ltv * growth_rate * (prediction_days / 30)
        
        confidence = min(95, max(60, 75 + days_active * 0.5))
        
        return {
            'user_id': user_id or f'user_{random.randint(1000, 9999)}',
            'historical_ltv': round(historical_revenue, 2),
            'predicted_ltv_30d': round(predicted_ltv, 2),
            'predicted_ltv_90d': round(predicted_ltv * 2.8, 2),
            'predicted_ltv_180d': round(predicted_ltv * 5.2, 2),
            'confidence': round(confidence, 1),
            'segment': self._classify_user_segment(predicted_ltv),
            'recommendations': self._generate_ltv_recommendations(predicted_ltv)
        }
    
    def predict_churn_probability(self, user_id: str = None):
        """
        预测用户流失概率
        """
        last_login_days = random.randint(0, 30)
        purchase_interval = random.randint(1, 60)
        level = random.randint(1, 100)
        session_duration = random.randint(1, 120)
        
        # 基于规则计算流失概率
        base_probability = 10
        
        if last_login_days > 7:
            base_probability += 25
        if last_login_days > 14:
            base_probability += 20
        if purchase_interval > 30:
            base_probability += 15
        if level < 10:
            base_probability += 10
        if session_duration < 5:
            base_probability += 15
        
        churn_probability = min(95, max(5, base_probability + random.randint(-5, 5)))
        
        risk_level = 'high' if churn_probability > 60 else 'medium' if churn_probability > 30 else 'low'
        
        return {
            'user_id': user_id or f'user_{random.randint(1000, 9999)}',
            'churn_probability': round(churn_probability, 1),
            'risk_level': risk_level,
            'last_login_days': last_login_days,
            'purchase_interval': purchase_interval,
            'level': level,
            'risk_factors': self._identify_risk_factors(last_login_days, purchase_interval, level),
            'retention_suggestions': self._generate_retention_suggestions(risk_level)
        }
    
    def identify_high_value_users(self, time_range: str = '30d', top_percent: int = 10):
        """
        识别高价值用户
        """
        users = []
        total_users = random.randint(5000, 10000)
        
        # 生成高价值用户
        for i in range(int(total_users * top_percent / 100)):
            users.append({
                'user_id': f'user_{i:05d}',
                'ltv': round(random.uniform(200, 2000), 2),
                'purchase_count': random.randint(10, 100),
                'avg_order_value': round(random.uniform(50, 500), 2),
                'retention_days': random.randint(30, 365),
                'segment': random.choice(['鲸鱼', '海豚', '活跃用户']),
                'engagement_score': random.randint(70, 100)
            })
        
        # 按LTV排序
        users.sort(key=lambda x: x['ltv'], reverse=True)
        
        return {
            'total_users': total_users,
            'high_value_users': len(users),
            'top_percentage': top_percent,
            'avg_ltv': round(sum(u['ltv'] for u in users) / len(users), 2) if users else 0,
            'segment_distribution': {
                '鲸鱼': len([u for u in users if u['segment'] == '鲸鱼']),
                '海豚': len([u for u in users if u['segment'] == '海豚']),
                '活跃用户': len([u for u in users if u['segment'] == '活跃用户'])
            },
            'top_users': users[:20],
            'recommendations': self._generate_high_value_recommendations(users)
        }
    
    def predict_revenue_forecast(self, days: int = 30):
        """
        收入预测
        """
        forecast_data = []
        base_revenue = 10000
        now = datetime.now()
        
        for i in range(days):
            forecast_date = now + timedelta(days=i)
            weekday = forecast_date.weekday()
            
            # 考虑周末效应
            weekday_factor = 1.25 if weekday >= 5 else 1.0
            # 添加趋势和季节性
            trend_factor = 1 + (i * 0.01)
            # 随机波动
            noise = random.uniform(0.9, 1.1)
            
            predicted_revenue = base_revenue * weekday_factor * trend_factor * noise
            
            forecast_data.append({
                'date': forecast_date.strftime('%Y-%m-%d'),
                'predicted_revenue': round(predicted_revenue, 2),
                'confidence_low': round(predicted_revenue * 0.85, 2),
                'confidence_high': round(predicted_revenue * 1.15, 2)
            })
        
        total_predicted = sum(d['predicted_revenue'] for d in forecast_data)
        
        return {
            'forecast_days': days,
            'daily_forecast': forecast_data,
            'total_predicted_revenue': round(total_predicted, 2),
            'avg_daily_revenue': round(total_predicted / days, 2),
            'trend': 'up' if forecast_data[-1]['predicted_revenue'] > forecast_data[0]['predicted_revenue'] else 'down',
            'trend_percentage': round((forecast_data[-1]['predicted_revenue'] - forecast_data[0]['predicted_revenue']) / forecast_data[0]['predicted_revenue'] * 100, 2)
        }
    
    def _classify_user_segment(self, ltv):
        """分类用户层级"""
        if ltv > 500:
            return '高价值用户（鲸鱼）'
        elif ltv > 200:
            return '中等价值用户（海豚）'
        elif ltv > 50:
            return '普通用户'
        else:
            return '低价值用户'
    
    def _generate_ltv_recommendations(self, ltv):
        """生成LTV优化建议"""
        recommendations = []
        if ltv < 100:
            recommendations.append('用户价值较低，建议优化首充引导')
            recommendations.append('增加新手礼包吸引力')
        elif ltv < 300:
            recommendations.append('用户有一定价值，建议提升付费频次')
            recommendations.append('推出订阅制会员服务')
        else:
            recommendations.append('高价值用户，重点维护')
            recommendations.append('提供VIP专属服务和活动')
        return recommendations
    
    def _identify_risk_factors(self, last_login, purchase_interval, level):
        """识别流失风险因素"""
        factors = []
        if last_login > 7:
            factors.append('长期未登录')
        if purchase_interval > 30:
            factors.append('付费间隔过长')
        if level < 10:
            factors.append('等级较低，可能流失')
        if not factors:
            factors.append('无明显风险')
        return factors
    
    def _generate_retention_suggestions(self, risk_level):
        """生成留存建议"""
        if risk_level == 'high':
            return ['发送召回邮件', '提供回归礼包', '推送限时活动']
        elif risk_level == 'medium':
            return ['增加活跃奖励', '推送新内容提醒', '社交功能引导']
        else:
            return ['保持现有运营策略', '持续提供优质内容']
    
    def _generate_high_value_recommendations(self, users):
        """生成高价值用户运营建议"""
        return [
            '建立VIP服务体系',
            '提供专属客服支持',
            '邀请参与新功能测试',
            '定期举办VIP专属活动'
        ]

class AnomalyDetector:
    """
    AI异常检测器
    - 实时异常检测
    - 统计基线计算
    - 智能告警
    """
    
    def __init__(self):
        self.baseline_stats = {}
        self.history_data = {}
        
    def initialize_baseline(self, metric_name: str, time_range: str = '30d'):
        """
        初始化统计基线
        """
        # 模拟历史数据
        data_points = []
        base_value = random.uniform(100, 500)
        
        for i in range(30):
            noise = random.normalvariate(0, 30)
            data_points.append(max(50, base_value + noise))
        
        self.history_data[metric_name] = data_points
        
        self.baseline_stats[metric_name] = {
            'mean': np.mean(data_points),
            'std': np.std(data_points),
            'min': np.min(data_points),
            'max': np.max(data_points),
            'threshold_high': np.mean(data_points) + 2 * np.std(data_points),
            'threshold_low': np.mean(data_points) - 2 * np.std(data_points)
        }
        
        return self.baseline_stats[metric_name]
    
    def detect_anomaly(self, metric_name: str, current_value: float):
        """
        检测异常
        - Z-Score 方法
        - 季节性调整
        """
        if metric_name not in self.baseline_stats:
            self.initialize_baseline(metric_name)
        
        stats = self.baseline_stats[metric_name]
        
        z_score = abs(current_value - stats['mean']) / stats['std']
        
        is_anomaly = bool(z_score > 2)  # 转换为 Python bool
        severity = 'high' if z_score > 3 else 'medium' if z_score > 2 else 'low'
        
        return {
            'is_anomaly': is_anomaly,
            'z_score': float(round(z_score, 2)),  # 转换为 Python float
            'severity': severity,
            'deviation': float(round((current_value - stats['mean']) / stats['mean'] * 100, 2)),
            'baseline_mean': float(round(stats['mean'], 2)),
            'current_value': float(current_value),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_active_alerts(self, products: List[str] = None):
        """
        获取当前活跃告警
        """
        if products is None:
            products = ['all']
        
        product_multiplier = len(products) if products != ['all'] else 1
        
        alerts = [
            {
                'id': 'alert_001',
                'type': 'revenue_drop',
                'severity': 'high',
                'title': '今日收入异常下降',
                'description': '与昨日相比下降 28%，请检查支付系统',
                'metric': 'revenue',
                'current_value': 3200 * product_multiplier,
                'expected_value': 4500 * product_multiplier,
                'timestamp': datetime.now().isoformat(),
                'status': 'active'
            },
            {
                'id': 'alert_002',
                'type': 'retention_spike',
                'severity': 'medium',
                'title': '3日留存异常上升',
                'description': '7日留存率从 22% 上升到 35%，请确认活动效果',
                'metric': 'retention_d7',
                'current_value': 35,
                'expected_value': 22,
                'timestamp': datetime.now().isoformat(),
                'status': 'active'
            }
        ]
        return alerts
    
    def generate_alert_notification(self, anomaly_data: Dict):
        """
        生成告警通知
        """
        if anomaly_data['is_anomaly']:
            return {
                'title': '异常检测告警',
                'message': f"指标异常！Z-Score = {anomaly_data['z_score']}",
                'severity': anomaly_data['severity'],
                'timestamp': datetime.now().isoformat()
            }
        return None

# 快捷访问函数
def get_advanced_analytics():
    """
    获取高级分析模块实例
    """
    return {
        'realtime': RealTimeDataStream(),
        'journey': UserJourneyAnalyzer(),
        'funnel': FunnelAnalyzer(),
        'cohort': CohortAnalyzer(),
        'anomaly': AnomalyDetector(),
        'predictive': PredictiveAnalyzer()
    }

if __name__ == '__main__':
    # 测试代码
    analytics = get_advanced_analytics()
    
    print("=== 实时数据流 ===")
    print(json.dumps(analytics['realtime'].calculate_real_time_metrics([]), indent=2, ensure_ascii=False))
    
    print("\n=== 用户行为路径 ===")
    journey = analytics['journey'].analyze_user_journey()
    print(f"发现 {len(journey['summary']['high_dropoff_points'])} 个高流失节点")
    
    print("\n=== 漏斗分析 ===")
    funnel = analytics['funnel'].create_funnel()
    print(f"整体转化率: {funnel['total_conversion_rate']}%")
    
    print("\n=== 群组分析 ===")
    cohort = analytics['cohort'].create_cohort()
    print(f"分析了 {len(cohort['cohorts'])} 个群组")
    
    print("\n=== 异常检测 ===")
    alert = analytics['anomaly'].detect_anomaly('revenue', 800)
    print(f"异常检测结果: {alert['is_anomaly']}")
    
    print("\n=== 预测分析 ===")
    ltv = analytics['predictive'].predict_ltv()
    print(f"LTV预测: {ltv['predicted_ltv_30d']}")
