"""
A/B测试平台模块
支持创建、监控和分析A/B测试实验
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import random
import hashlib


class ABTestExperiment:
    """A/B测试实验类"""
    
    def __init__(self, experiment_id: str, name: str, description: str = "", 
                 variants: List[dict] = None, traffic_allocation: float = 1.0,
                 start_date: str = None, end_date: str = None,
                 filters: Dict = None, targeting: Dict = None):
        self.experiment_id = experiment_id
        self.name = name
        self.description = description
        self.variants = variants or []
        self.traffic_allocation = traffic_allocation
        self.start_date = start_date or datetime.now().strftime('%Y-%m-%d')
        self.end_date = end_date
        self.status = "running" if end_date is None else "completed"
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.results = {}
        
        # 新增：过滤条件
        self.filters = filters or {
            "regions": [],           # 地区过滤 ["CN", "US", "JP"]
            "servers": [],           # 区服过滤 ["server1", "server2"]
            "platforms": [],         # 平台过滤 ["ios", "android", "web"]
            "versions": [],          # 版本过滤 ["1.0.0", "1.1.0"]
            "channels": [],          # 渠道过滤 ["appstore", "google", "steam"]
            "user_segments": [],     # 用户分组 ["new", "active", "paying"]
            "level_range": [0, 999], # 等级范围 [min, max]
            "registration_date_range": [], # 注册日期范围 ["2024-01-01", "2024-12-31"]
            "device_types": []       # 设备类型 ["phone", "tablet", "pc"]
        }
        
        # 新增：定向配置
        self.targeting = targeting or {
            "enabled": False,
            "user_id_whitelist": [],  # 用户ID白名单
            "user_id_blacklist": [],  # 用户ID黑名单
            "custom_rules": []        # 自定义规则
        }
    
    def is_user_eligible(self, user_info: Dict) -> bool:
        """检查用户是否符合实验条件"""
        # 检查日期范围
        today = datetime.now().strftime('%Y-%m-%d')
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        
        # 检查用户ID白名单/黑名单
        user_id = user_info.get('user_id', '')
        if self.targeting.get('enabled', False):
            if self.targeting.get('user_id_blacklist') and user_id in self.targeting['user_id_blacklist']:
                return False
            if self.targeting.get('user_id_whitelist') and user_id not in self.targeting['user_id_whitelist']:
                return False
        
        # 检查地区过滤
        if self.filters.get('regions') and user_info.get('region') not in self.filters['regions']:
            return False
        
        # 检查区服过滤
        if self.filters.get('servers') and user_info.get('server') not in self.filters['servers']:
            return False
        
        # 检查平台过滤
        if self.filters.get('platforms') and user_info.get('platform') not in self.filters['platforms']:
            return False
        
        # 检查版本过滤
        if self.filters.get('versions') and user_info.get('version') not in self.filters['versions']:
            return False
        
        # 检查渠道过滤
        if self.filters.get('channels') and user_info.get('channel') not in self.filters['channels']:
            return False
        
        # 检查用户分组
        if self.filters.get('user_segments') and user_info.get('segment') not in self.filters['user_segments']:
            return False
        
        # 检查等级范围
        level_range = self.filters.get('level_range', [0, 999])
        user_level = user_info.get('level', 0)
        if user_level < level_range[0] or user_level > level_range[1]:
            return False
        
        # 检查注册日期范围
        reg_date_range = self.filters.get('registration_date_range', [])
        if len(reg_date_range) == 2:
            reg_date = user_info.get('registration_date', '')
            if reg_date and (reg_date < reg_date_range[0] or reg_date > reg_date_range[1]):
                return False
        
        # 检查设备类型
        if self.filters.get('device_types') and user_info.get('device_type') not in self.filters['device_types']:
            return False
        
        return True
    
    def allocate_user(self, user_id: str, user_info: Dict = None) -> str:
        """为用户分配变体（支持用户信息过滤）"""
        user_info = user_info or {}
        
        # 先检查用户是否符合条件
        if not self.is_user_eligible(user_info):
            return "ineligible"
        
        # 检查实验状态和流量分配
        if self.status != "running":
            return "not_running"
        
        # 流量分配检查
        if self.traffic_allocation < 1.0:
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            if hash_val % 100 >= self.traffic_allocation * 100:
                return "not_selected"
        
        # 根据用户ID的hash值分配变体
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        variant_index = hash_val % len(self.variants)
        return self.variants[variant_index]['id']
    
    def record_conversion(self, user_id: str, variant_id: str, conversion_type: str = "default",
                          additional_data: Dict = None):
        """记录转化事件（支持附加数据）"""
        if variant_id not in self.results:
            self.results[variant_id] = {"users": set(), "conversions": {}, "revenue": 0}
        
        self.results[variant_id]["users"].add(user_id)
        
        if conversion_type not in self.results[variant_id]["conversions"]:
            self.results[variant_id]["conversions"][conversion_type] = set()
        
        self.results[variant_id]["conversions"][conversion_type].add(user_id)
        
        # 记录收入数据
        if additional_data and additional_data.get('revenue'):
            self.results[variant_id]["revenue"] += additional_data['revenue']
    
    def get_results(self) -> Dict:
        """获取实验结果"""
        results = {}
        
        for variant in self.variants:
            vid = variant['id']
            data = self.results.get(vid, {"users": set(), "conversions": {}, "revenue": 0})
            
            total_users = len(data["users"])
            conversions = sum(len(v) for v in data["conversions"].values())
            conversion_rate = (conversions / total_users * 100) if total_users > 0 else 0
            avg_revenue_per_user = (data["revenue"] / total_users) if total_users > 0 else 0
            
            results[vid] = {
                "name": variant['name'],
                "total_users": total_users,
                "conversions": conversions,
                "conversion_rate": round(conversion_rate, 2),
                "revenue": round(data["revenue"], 2),
                "avg_revenue_per_user": round(avg_revenue_per_user, 2),
                "is_control": variant.get('is_control', False)
            }
        
        return results


class ABTestPlatform:
    """A/B测试平台类"""
    
    def __init__(self, data_dir: str = "mock_data"):
        self.data_dir = data_dir
        self.experiments = {}
        self._load_experiments()
    
    def _load_experiments(self):
        """加载已保存的实验"""
        try:
            path = os.path.join(self.data_dir, "ab_experiments.json")
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for exp_data in data:
                        exp = ABTestExperiment(**exp_data)
                        self.experiments[exp.experiment_id] = exp
        except Exception:
            self._create_default_experiments()
    
    def _create_default_experiments(self):
        """创建默认实验数据"""
        experiments = [
            {
                "experiment_id": "exp_001",
                "name": "新手引导优化测试",
                "description": "测试不同新手引导流程对用户留存的影响",
                "variants": [
                    {"id": "control", "name": "原有流程", "is_control": True},
                    {"id": "variant_a", "name": "简化流程", "is_control": False},
                    {"id": "variant_b", "name": "互动式引导", "is_control": False}
                ],
                "traffic_allocation": 0.5,
                "start_date": "2024-01-15",
                "filters": {
                    "regions": ["CN"],
                    "platforms": ["ios", "android"],
                    "user_segments": ["new"],
                    "level_range": [0, 5]
                },
                "results": {
                    "control": {"users": set([str(i) for i in range(1000)]), "conversions": {"retention": set([str(i) for i in range(350)])}, "revenue": 15000},
                    "variant_a": {"users": set([str(i) for i in range(1000, 2000)]), "conversions": {"retention": set([str(i) for i in range(1000, 1420)])}, "revenue": 18500},
                    "variant_b": {"users": set([str(i) for i in range(2000, 3000)]), "conversions": {"retention": set([str(i) for i in range(2000, 2510)])}, "revenue": 22000}
                }
            },
            {
                "experiment_id": "exp_002",
                "name": "付费按钮文案测试",
                "description": "测试不同付费按钮文案对转化率的影响",
                "variants": [
                    {"id": "control", "name": "立即购买", "is_control": True},
                    {"id": "variant_a", "name": "限时优惠", "is_control": False},
                    {"id": "variant_b", "name": "免费试用", "is_control": False}
                ],
                "traffic_allocation": 0.3,
                "start_date": "2024-01-20",
                "filters": {
                    "regions": ["CN", "US"],
                    "platforms": ["ios", "android"],
                    "user_segments": ["paying"],
                    "level_range": [10, 999]
                },
                "results": {
                    "control": {"users": set([str(i) for i in range(500)]), "conversions": {"purchase": set([str(i) for i in range(50)])}, "revenue": 50000},
                    "variant_a": {"users": set([str(i) for i in range(500, 1000)]), "conversions": {"purchase": set([str(i) for i in range(500, 580)])}, "revenue": 80000},
                    "variant_b": {"users": set([str(i) for i in range(1000, 1500)]), "conversions": {"purchase": set([str(i) for i in range(1000, 1120)])}, "revenue": 120000}
                }
            },
            {
                "experiment_id": "exp_003",
                "name": "新版本功能测试",
                "description": "测试新版本UI功能对用户活跃度的影响",
                "variants": [
                    {"id": "control", "name": "旧版本", "is_control": True},
                    {"id": "variant_a", "name": "新版本", "is_control": False}
                ],
                "traffic_allocation": 1.0,
                "start_date": datetime.now().strftime('%Y-%m-%d'),
                "filters": {
                    "regions": ["CN"],
                    "servers": ["server1", "server2"],
                    "platforms": ["ios", "android", "web"],
                    "versions": ["2.0.0"],
                    "user_segments": ["active"]
                },
                "results": {}
            }
        ]
        
        for exp_data in experiments:
            exp = ABTestExperiment(**exp_data)
            self.experiments[exp.experiment_id] = exp
    
    def create_experiment(self, name: str, description: str = "", 
                          variants: List[dict] = None, traffic_allocation: float = 1.0,
                          filters: Dict = None, targeting: Dict = None) -> ABTestExperiment:
        """创建新实验"""
        experiment_id = f"exp_{len(self.experiments) + 1:03d}"
        
        if not variants or len(variants) < 2:
            variants = [
                {"id": "control", "name": "对照组", "is_control": True},
                {"id": "variant_a", "name": "变体A", "is_control": False}
            ]
        
        exp = ABTestExperiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            variants=variants,
            traffic_allocation=traffic_allocation,
            filters=filters,
            targeting=targeting
        )
        
        self.experiments[experiment_id] = exp
        self._save_experiments()
        return exp
    
    def get_experiment(self, experiment_id: str) -> Optional[ABTestExperiment]:
        """获取实验"""
        return self.experiments.get(experiment_id)
    
    def list_experiments(self) -> List[ABTestExperiment]:
        """列出所有实验"""
        return list(self.experiments.values())
    
    def update_experiment(self, experiment_id: str, **kwargs):
        """更新实验"""
        if experiment_id not in self.experiments:
            raise ValueError("Experiment not found")
        
        exp = self.experiments[experiment_id]
        
        if 'name' in kwargs:
            exp.name = kwargs['name']
        if 'description' in kwargs:
            exp.description = kwargs['description']
        if 'traffic_allocation' in kwargs:
            exp.traffic_allocation = kwargs['traffic_allocation']
        if 'end_date' in kwargs:
            exp.end_date = kwargs['end_date']
            exp.status = "completed"
        if 'filters' in kwargs:
            exp.filters = kwargs['filters']
        if 'targeting' in kwargs:
            exp.targeting = kwargs['targeting']
        
        self._save_experiments()
        return exp
    
    def delete_experiment(self, experiment_id: str):
        """删除实验"""
        if experiment_id in self.experiments:
            del self.experiments[experiment_id]
            self._save_experiments()
    
    def track_user(self, experiment_id: str, user_id: str, user_info: Dict = None) -> str:
        """追踪用户并分配变体（支持用户信息）"""
        exp = self.get_experiment(experiment_id)
        if not exp:
            raise ValueError("Experiment not found")
        
        return exp.allocate_user(user_id, user_info)
    
    def track_conversion(self, experiment_id: str, user_id: str, 
                         variant_id: str, conversion_type: str = "default",
                         additional_data: Dict = None):
        """追踪转化（支持附加数据）"""
        exp = self.get_experiment(experiment_id)
        if not exp:
            raise ValueError("Experiment not found")
        
        exp.record_conversion(user_id, variant_id, conversion_type, additional_data)
        self._save_experiments()
    
    def get_experiment_results(self, experiment_id: str) -> Dict:
        """获取实验结果"""
        exp = self.get_experiment(experiment_id)
        if not exp:
            return {"error": "Experiment not found"}
        
        results = exp.get_results()
        
        control = results.get("control")
        if control:
            best_variant = None
            best_lift = 0
            best_revenue_lift = 0
            
            for vid, data in results.items():
                if vid != "control" and data['total_users'] > 0:
                    cr_lift = ((data['conversion_rate'] - control['conversion_rate']) / control['conversion_rate']) * 100
                    revenue_lift = ((data['revenue'] - control['revenue']) / control['revenue']) * 100 if control['revenue'] > 0 else 0
                    
                    results[vid]['cr_lift'] = round(cr_lift, 2)
                    results[vid]['revenue_lift'] = round(revenue_lift, 2)
                    
                    combined_lift = cr_lift + revenue_lift
                    if combined_lift > best_lift:
                        best_lift = combined_lift
                        best_variant = vid
            
            if best_variant:
                results[best_variant]['is_winner'] = True
        
        return {
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "status": exp.status,
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "traffic_allocation": exp.traffic_allocation,
            "filters": exp.filters,
            "results": results
        }
    
    def get_available_filters(self) -> Dict[str, List[str]]:
        """获取可用的过滤选项"""
        return {
            "regions": ["CN", "US", "JP", "KR", "EU", "Other"],
            "platforms": ["ios", "android", "web", "pc"],
            "user_segments": ["new", "active", "paying", "returning", "inactive"],
            "device_types": ["phone", "tablet", "pc", "console"],
            "channel_types": ["appstore", "google", "steam", "taptap", "huawei", "xiaomi"]
        }
    
    def _save_experiments(self):
        """保存实验数据"""
        try:
            path = os.path.join(self.data_dir, "ab_experiments.json")
            data = []
            for exp in self.experiments.values():
                exp_data = {
                    "experiment_id": exp.experiment_id,
                    "name": exp.name,
                    "description": exp.description,
                    "variants": exp.variants,
                    "traffic_allocation": exp.traffic_allocation,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "filters": exp.filters,
                    "targeting": exp.targeting
                }
                data.append(exp_data)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


ab_test_platform = ABTestPlatform()
