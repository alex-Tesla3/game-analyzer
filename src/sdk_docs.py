"""
SDK集成文档模块
提供游戏引擎SDK的集成文档和代码示例
"""
import json
from typing import Dict, Any, List


# SDK文档数据
SDK_DOCS = {
    'unity': {
        'name': 'Unity SDK',
        'version': '2.0.0',
        'description': 'Unity游戏引擎数据采集SDK',
        'download_url': '#',
        'installation': {
            'title': '安装指南',
            'steps': [
                {
                    'title': '下载SDK',
                    'description': '从下载页面获取Unity SDK包',
                    'code': None
                },
                {
                    'title': '导入包',
                    'description': '在Unity编辑器中导入SDK包',
                    'code': None
                },
                {
                    'title': '配置初始化',
                    'description': '在游戏启动时初始化SDK',
                    'code': '''using GameAnalytics;

public class GameAnalyticsManager : MonoBehaviour
{
    void Awake()
    {
        // 初始化SDK
        GameAnalytics.Init("YOUR_API_KEY", "YOUR_GAME_ID");
        
        // 可选：设置用户ID
        GameAnalytics.SetUserId(PlayerPrefs.GetString("PlayerId"));
    }
}'''
                }
            ]
        },
        'usage': {
            'title': '使用指南',
            'examples': [
                {
                    'title': '跟踪用户事件',
                    'description': '记录用户行为事件',
                    'code': '''// 记录简单事件
GameAnalytics.TrackEvent("level_start", new Dictionary<string, object> {
    { "level", "level_1" },
    { "difficulty", "normal" }
});

// 记录购买事件
GameAnalytics.TrackPurchase("gold_100", 1.99, "USD", new Dictionary<string, object> {
    { "item_type", "currency" }
});'''
                },
                {
                    'title': '跟踪用户属性',
                    'description': '设置用户属性用于分群分析',
                    'code': '''// 设置用户属性
GameAnalytics.SetUserProperty("level", 5);
GameAnalytics.SetUserProperty("vip_level", "gold");
GameAnalytics.SetUserProperty("first_purchase", true);'''
                },
                {
                    'title': '跟踪错误',
                    'description': '记录游戏中的错误和异常',
                    'code': '''try {
    // 游戏逻辑
} catch (Exception e) {
    GameAnalytics.TrackError("game_error", e.Message, ErrorLevel.Error);
}'''
                },
                {
                    'title': '跟踪自定义指标',
                    'description': '记录自定义业务指标',
                    'code': '''// 记录自定义指标
GameAnalytics.TrackMetric("daily_active_users", 1);
GameAnalytics.TrackMetric("session_duration", 120); // 秒
GameAnalytics.TrackMetric("completion_rate", 0.75); // 百分比'''
                }
            ]
        },
        'api_reference': {
            'title': 'API参考',
            'methods': [
                {
                    'name': 'GameAnalytics.Init',
                    'description': '初始化SDK',
                    'parameters': [
                        {'name': 'apiKey', 'type': 'string', 'description': '您的API密钥'},
                        {'name': 'gameId', 'type': 'string', 'description': '游戏ID'}
                    ],
                    'returns': 'void'
                },
                {
                    'name': 'GameAnalytics.TrackEvent',
                    'description': '跟踪事件',
                    'parameters': [
                        {'name': 'eventName', 'type': 'string', 'description': '事件名称'},
                        {'name': 'properties', 'type': 'Dictionary<string, object>', 'description': '事件属性（可选）'}
                    ],
                    'returns': 'void'
                },
                {
                    'name': 'GameAnalytics.TrackPurchase',
                    'description': '跟踪购买事件',
                    'parameters': [
                        {'name': 'itemId', 'type': 'string', 'description': '商品ID'},
                        {'name': 'price', 'type': 'double', 'description': '价格'},
                        {'name': 'currency', 'type': 'string', 'description': '货币代码'},
                        {'name': 'properties', 'type': 'Dictionary<string, object>', 'description': '附加属性（可选）'}
                    ],
                    'returns': 'void'
                },
                {
                    'name': 'GameAnalytics.SetUserProperty',
                    'description': '设置用户属性',
                    'parameters': [
                        {'name': 'key', 'type': 'string', 'description': '属性键'},
                        {'name': 'value', 'type': 'object', 'description': '属性值'}
                    ],
                    'returns': 'void'
                }
            ]
        },
        'best_practices': [
            '在游戏启动时尽早初始化SDK',
            '使用有意义的事件名称（如 "level_complete" 而非 "event_1"）',
            '避免在性能敏感代码中频繁调用TrackEvent',
            '定期清理不再需要的用户属性',
            '在发布前测试所有跟踪代码'
        ]
    },
    'unreal': {
        'name': 'Unreal Engine SDK',
        'version': '2.0.0',
        'description': 'Unreal Engine游戏引擎数据采集SDK',
        'download_url': '#',
        'installation': {
            'title': '安装指南',
            'steps': [
                {
                    'title': '下载SDK',
                    'description': '从下载页面获取Unreal SDK插件',
                    'code': None
                },
                {
                    'title': '启用插件',
                    'description': '在Unreal编辑器中启用GameAnalytics插件',
                    'code': None
                },
                {
                    'title': '配置初始化',
                    'description': '在游戏启动时初始化SDK',
                    'code': '''// 在GameInstance中初始化
void UMyGameInstance::Init()
{
    Super::Init();
    
    // 初始化SDK
    GameAnalytics::Init("YOUR_API_KEY", "YOUR_GAME_ID");
    
    // 可选：设置用户ID
    GameAnalytics::SetUserId(GetUniquePlayerId());
}'''
                }
            ]
        },
        'usage': {
            'title': '使用指南',
            'examples': [
                {
                    'title': '跟踪用户事件',
                    'description': '记录用户行为事件',
                    'code': '''// 记录简单事件
TMap<FString, FString> Properties;
Properties.Add("level", "level_1");
Properties.Add("difficulty", "normal");
GameAnalytics::TrackEvent("level_start", Properties);

// 记录购买事件
GameAnalytics::TrackPurchase("gold_100", 1.99f, "USD", Properties);'''
                },
                {
                    'title': '跟踪用户属性',
                    'description': '设置用户属性用于分群分析',
                    'code': '''// 设置用户属性
GameAnalytics::SetUserProperty("level", "5");
GameAnalytics::SetUserProperty("vip_level", "gold");
GameAnalytics::SetUserProperty("first_purchase", "true");'''
                },
                {
                    'title': '跟踪错误',
                    'description': '记录游戏中的错误和异常',
                    'code': '''try {
    // 游戏逻辑
} catch (const FException& e) {
    GameAnalytics::TrackError("game_error", e.what(), EErrorLevel::Error);
}'''
                }
            ]
        },
        'api_reference': {
            'title': 'API参考',
            'methods': [
                {
                    'name': 'GameAnalytics::Init',
                    'description': '初始化SDK',
                    'parameters': [
                        {'name': 'ApiKey', 'type': 'FString', 'description': '您的API密钥'},
                        {'name': 'GameId', 'type': 'FString', 'description': '游戏ID'}
                    ],
                    'returns': 'void'
                },
                {
                    'name': 'GameAnalytics::TrackEvent',
                    'description': '跟踪事件',
                    'parameters': [
                        {'name': 'EventName', 'type': 'FString', 'description': '事件名称'},
                        {'name': 'Properties', 'type': 'TMap<FString, FString>', 'description': '事件属性（可选）'}
                    ],
                    'returns': 'void'
                },
                {
                    'name': 'GameAnalytics::TrackPurchase',
                    'description': '跟踪购买事件',
                    'parameters': [
                        {'name': 'ItemId', 'type': 'FString', 'description': '商品ID'},
                        {'name': 'Price', 'type': 'float', 'description': '价格'},
                        {'name': 'Currency', 'type': 'FString', 'description': '货币代码'},
                        {'name': 'Properties', 'type': 'TMap<FString, FString>', 'description': '附加属性（可选）'}
                    ],
                    'returns': 'void'
                }
            ]
        },
        'best_practices': [
            '在GameInstance或GameMode中初始化SDK',
            '使用UTF-8编码的字符串',
            '避免在Tick函数中调用跟踪方法',
            '使用异步模式处理大量事件'
        ]
    },
    'cocos': {
        'name': 'Cocos Creator SDK',
        'version': '1.0.0',
        'description': 'Cocos Creator游戏引擎数据采集SDK',
        'download_url': '#',
        'installation': {
            'title': '安装指南',
            'steps': [
                {
                    'title': '安装依赖',
                    'description': '通过npm安装SDK',
                    'code': 'npm install @game-analytics/sdk --save'
                },
                {
                    'title': '导入模块',
                    'description': '在游戏代码中导入SDK',
                    'code': '''import GameAnalytics from '@game-analytics/sdk';'''
                },
                {
                    'title': '配置初始化',
                    'description': '在游戏启动时初始化SDK',
                    'code': '''// 在游戏启动时调用
GameAnalytics.init({
    apiKey: 'YOUR_API_KEY',
    gameId: 'YOUR_GAME_ID'
});

// 可选：设置用户ID
GameAnalytics.setUserId(playerId);'''
                }
            ]
        },
        'usage': {
            'title': '使用指南',
            'examples': [
                {
                    'title': '跟踪用户事件',
                    'description': '记录用户行为事件',
                    'code': '''// 记录简单事件
GameAnalytics.trackEvent('level_start', {
    level: 'level_1',
    difficulty: 'normal'
});

// 记录购买事件
GameAnalytics.trackPurchase('gold_100', 1.99, 'USD', {
    item_type: 'currency'
});'''
                },
                {
                    'title': '跟踪用户属性',
                    'description': '设置用户属性用于分群分析',
                    'code': '''// 设置用户属性
GameAnalytics.setUserProperty('level', 5);
GameAnalytics.setUserProperty('vip_level', 'gold');
GameAnalytics.setUserProperty('first_purchase', true);'''
                }
            ]
        },
        'api_reference': {
            'title': 'API参考',
            'methods': [
                {
                    'name': 'GameAnalytics.init',
                    'description': '初始化SDK',
                    'parameters': [
                        {'name': 'config', 'type': 'object', 'description': '配置对象'}
                    ],
                    'returns': 'Promise<void>'
                },
                {
                    'name': 'GameAnalytics.trackEvent',
                    'description': '跟踪事件',
                    'parameters': [
                        {'name': 'eventName', 'type': 'string', 'description': '事件名称'},
                        {'name': 'properties', 'type': 'object', 'description': '事件属性（可选）'}
                    ],
                    'returns': 'void'
                },
                {
                    'name': 'GameAnalytics.trackPurchase',
                    'description': '跟踪购买事件',
                    'parameters': [
                        {'name': 'itemId', 'type': 'string', 'description': '商品ID'},
                        {'name': 'price', 'type': 'number', 'description': '价格'},
                        {'name': 'currency', 'type': 'string', 'description': '货币代码'},
                        {'name': 'properties', 'type': 'object', 'description': '附加属性（可选）'}
                    ],
                    'returns': 'void'
                }
            ]
        },
        'best_practices': [
            '在onLoad或start生命周期中初始化',
            '使用Promise处理异步操作',
            '在beforeDestroy中调用flush确保数据发送'
        ]
    },
    'rest': {
        'name': 'REST API',
        'version': '1.0.0',
        'description': 'RESTful API接口文档',
        'base_url': 'https://api.game-analytics.cn/v1',
        'authentication': {
            'title': '认证方式',
            'description': '使用API密钥进行认证',
            'example': '''curl -X POST https://api.game-analytics.cn/v1/events \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"event_name": "level_start", "properties": {...}}' '''
        },
        'endpoints': [
            {
                'method': 'POST',
                'path': '/events',
                'description': '发送事件数据',
                'request': {
                    'event_name': {'type': 'string', 'required': True, 'description': '事件名称'},
                    'user_id': {'type': 'string', 'required': True, 'description': '用户ID'},
                    'properties': {'type': 'object', 'required': False, 'description': '事件属性'},
                    'timestamp': {'type': 'string', 'required': False, 'description': '时间戳(ISO格式)'}
                },
                'response': {
                    'success': {'type': 'boolean', 'description': '是否成功'},
                    'event_id': {'type': 'string', 'description': '事件ID'}
                }
            },
            {
                'method': 'POST',
                'path': '/purchases',
                'description': '发送购买数据',
                'request': {
                    'item_id': {'type': 'string', 'required': True, 'description': '商品ID'},
                    'price': {'type': 'number', 'required': True, 'description': '价格'},
                    'currency': {'type': 'string', 'required': True, 'description': '货币代码'},
                    'user_id': {'type': 'string', 'required': True, 'description': '用户ID'},
                    'properties': {'type': 'object', 'required': False, 'description': '附加属性'}
                },
                'response': {
                    'success': {'type': 'boolean', 'description': '是否成功'},
                    'purchase_id': {'type': 'string', 'description': '购买ID'}
                }
            },
            {
                'method': 'POST',
                'path': '/users/properties',
                'description': '设置用户属性',
                'request': {
                    'user_id': {'type': 'string', 'required': True, 'description': '用户ID'},
                    'properties': {'type': 'object', 'required': True, 'description': '用户属性'}
                },
                'response': {
                    'success': {'type': 'boolean', 'description': '是否成功'}
                }
            },
            {
                'method': 'GET',
                'path': '/events/types',
                'description': '获取支持的事件类型',
                'response': {
                    'types': {'type': 'array', 'description': '事件类型列表'}
                }
            }
        ],
        'rate_limits': [
            '免费版: 100请求/分钟',
            '专业版: 1000请求/分钟',
            '企业版: 无限制'
        ],
        'best_practices': [
            '使用批量接口减少请求次数',
            '设置合理的重试机制',
            '使用HTTPS协议',
            '在服务器端发送数据而非客户端'
        ]
    }
}


class SDKDocumentationManager:
    """SDK文档管理器"""
    
    def __init__(self):
        self.docs = SDK_DOCS
    
    def get_available_sdks(self) -> List[Dict]:
        """获取可用的SDK列表"""
        return [
            {
                'id': key,
                'name': doc['name'],
                'version': doc['version'],
                'description': doc['description'],
                'download_url': doc.get('download_url')
            }
            for key, doc in self.docs.items()
        ]
    
    def get_sdk_doc(self, sdk_id: str) -> Optional[Dict]:
        """获取SDK文档"""
        return self.docs.get(sdk_id)
    
    def get_sdk_installation(self, sdk_id: str) -> Optional[Dict]:
        """获取SDK安装指南"""
        doc = self.get_sdk_doc(sdk_id)
        return doc.get('installation') if doc else None
    
    def get_sdk_usage(self, sdk_id: str) -> Optional[Dict]:
        """获取SDK使用指南"""
        doc = self.get_sdk_doc(sdk_id)
        return doc.get('usage') if doc else None
    
    def get_sdk_api_reference(self, sdk_id: str) -> Optional[Dict]:
        """获取SDK API参考"""
        doc = self.get_sdk_doc(sdk_id)
        return doc.get('api_reference') if doc else None
    
    def get_sdk_best_practices(self, sdk_id: str) -> Optional[List[str]]:
        """获取SDK最佳实践"""
        doc = self.get_sdk_doc(sdk_id)
        return doc.get('best_practices') if doc else None


# 全局实例
sdk_docs_manager = SDKDocumentationManager()


def get_sdk_docs_manager() -> SDKDocumentationManager:
    """获取SDK文档管理器"""
    return sdk_docs_manager
