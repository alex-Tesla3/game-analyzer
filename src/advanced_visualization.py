"""
高级数据可视化模块
包含桑基图、地理热力图等高级可视化组件
"""
import json


def generate_sankey_diagram_html(journey_data: dict) -> str:
    """
    生成桑基图HTML组件
    
    Args:
        journey_data: 用户路径数据
    
    Returns:
        HTML字符串
    """
    return """
    <div id="sankey-chart" style="width: 100%; height: 500px; background: #f5f5f7; border-radius: 12px; padding: 20px;">
        <div id="sankey-container" style="width: 100%; height: 100%;"></div>
    </div>
    
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        function renderSankeyChart(data) {
            const nodes = data.nodes || [];
            const links = data.links || [];
            
            const nodeLabels = nodes.map(n => n.name);
            const nodeColors = nodes.map(n => n.color || '#0071e3');
            
            const sankeyData = [{
                type: "sankey",
                orientation: "h",
                node: {
                    pad: 15,
                    thickness: 20,
                    line: {
                        color: "black",
                        width: 0.5
                    },
                    label: nodeLabels,
                    color: nodeColors,
                    hoverinfo: 'all'
                },
                link: {
                    source: links.map(l => l.source),
                    target: links.map(l => l.target),
                    value: links.map(l => l.value),
                    color: links.map(l => l.color || 'rgba(0, 113, 227, 0.3)'),
                    hoverinfo: 'all'
                }
            }];
            
            const layout = {
                title: "用户路径流向图",
                font: {
                    size: 14,
                    color: '#1d1d1f'
                },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent'
            };
            
            Plotly.newPlot('sankey-container', sankeyData, layout);
        }
    </script>
    """


def generate_geographic_heatmap_html() -> str:
    """生成地理热力图HTML组件"""
    return """
    <div id="geo-heatmap" style="width: 100%; height: 500px; background: #f5f5f7; border-radius: 12px; padding: 20px;">
        <div id="map-container" style="width: 100%; height: 100%;"></div>
    </div>
    
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        function renderGeoHeatmap(data) {
            const trace = {
                type: 'choropleth',
                locationmode: 'country names',
                locations: data.locations || [],
                z: data.values || [],
                text: data.labels || [],
                autocolorscale: true,
                colorscale: [
                    [0, '#f7fbff'],
                    [0.25, '#6baed6'],
                    [0.5, '#2171b5'],
                    [0.75, '#084594'],
                    [1, '#08306b']
                ],
                marker: {
                    line: {
                        color: 'rgb(255,255,255)',
                        width: 2
                    }
                }
            };
            
            const layout = {
                title: '用户地理分布热力图',
                geo: {
                    scope: 'world',
                    showocean: true,
                    oceancolor: '#cce5ff',
                    showland: true,
                    landcolor: '#f5f5f5',
                    showlakes: true,
                    lakecolor: '#cce5ff',
                    showcountries: true,
                    countrycolor: '#d1d1d1',
                    showcoastlines: true,
                    coastlinecolor: '#666666'
                },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent'
            };
            
            Plotly.newPlot('map-container', [trace], layout);
        }
    </script>
    """


def generate_gauge_chart_html(value: float, max_value: float, label: str) -> str:
    """
    生成仪表盘图HTML组件
    
    Args:
        value: 当前值
        max_value: 最大值
        label: 标签
    """
    percentage = (value / max_value) * 100
    
    # 根据百分比确定颜色
    color = '#34c759'  # 绿色
    if percentage >= 80:
        color = '#34c759'  # 绿色
    elif percentage >= 50:
        color = '#ff9500'  # 橙色
    else:
        color = '#ff3b30'  # 红色
    
    return f"""
    <div class="gauge-chart" style="width: 200px; height: 200px; margin: 0 auto;">
        <svg viewBox="0 0 200 200" style="transform: rotate(-90deg);">
            <circle cx="100" cy="100" r="80" fill="none" stroke="#e5e5e7" stroke-width="20"/>
            <circle cx="100" cy="100" r="80" fill="none" stroke="{color}" stroke-width="20"
                    stroke-dasharray="{2 * 3.14159 * 80}" 
                    stroke-dashoffset="{2 * 3.14159 * 80 * (1 - {percentage}/100)}"
                    style="transition: stroke-dashoffset 0.5s ease;"/>
        </svg>
        <div style="text-align: center; margin-top: -140px; position: relative;">
            <div style="font-size: 32px; font-weight: bold; color: {color};">{percentage:.1f}%</div>
            <div style="font-size: 14px; color: #86868b;">{label}</div>
        </div>
    </div>
    """


def generate_pie_chart_html(data: list, title: str) -> str:
    """
    生成饼图HTML组件
    
    Args:
        data: 数据列表 [{label, value, color}]
        title: 图表标题
    """
    labels = [d['label'] for d in data]
    values = [d['value'] for d in data]
    colors = [d.get('color', '#0071e3') for d in data]
    
    return f"""
    <div id="pie-chart" style="width: 100%; height: 400px;"></div>
    
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        const data = [{{
            values: {json.dumps(values)},
            labels: {json.dumps(labels)},
            type: 'pie',
            marker: {{
                colors: {json.dumps(colors)}
            }},
            textinfo: 'label+percent',
            textposition: 'outside',
            automargin: true
        }}];
        
        const layout = {{
            title: '{title}',
            showlegend: true,
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {{
                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                size: 14,
                color: '#1d1d1f'
            }}
        }};
        
        Plotly.newPlot('pie-chart', data, layout);
    </script>
    """


def generate_treemap_chart_html(data: list, title: str) -> str:
    """
    生成树形图HTML组件
    
    Args:
        data: 数据列表 [{label, value, color, parent}]
        title: 图表标题
    """
    return f"""
    <div id="treemap-chart" style="width: 100%; height: 500px;"></div>
    
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        const data = [{{
            type: "treemap",
            labels: {json.dumps([d['label'] for d in data])},
            parents: {json.dumps([d.get('parent', '') for d in data])},
            values: {json.dumps([d['value'] for d in data])},
            textinfo: "label+value+percent entry",
            textposition: 'middle center',
            hovertemplate: '<b>%{{label}}</b><br>值: %{{value}}<br>占比: %{{percentEntry}}<extra></extra>',
            marker: {{
                colors: {json.dumps([d.get('color', '#0071e3') for d in data])}
            }}
        }}];
        
        const layout = {{
            title: '{title}',
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent'
        }};
        
        Plotly.newPlot('treemap-chart', data, layout);
    </script>
    """


def generate_funnel_chart_html(steps: list) -> str:
    """
    生成漏斗图HTML组件
    
    Args:
        steps: 漏斗步骤列表 [{name, value, color}]
    """
    labels = [s['name'] for s in steps]
    values = [s['value'] for s in steps]
    colors = [s.get('color', '#0071e3') for s in steps]
    
    return f"""
    <div id="funnel-chart" style="width: 100%; height: 500px;"></div>
    
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        const data = [{{
            type: "funnel",
            y: {json.dumps(labels)},
            x: {json.dumps(values)},
            marker: {{
                color: {json.dumps(colors)}
            }},
            textinfo: "label+value+percent",
            textposition: 'inside',
            automargin: true
        }}];
        
        const layout = {{
            title: '转化漏斗',
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {{
                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                size: 14,
                color: '#1d1d1f'
            }}
        }};
        
        Plotly.newPlot('funnel-chart', data, layout);
    </script>
    """


def generate_bubble_map_html(geo_data: list, metric_data: list) -> str:
    """
    生成气泡地图HTML组件
    
    Args:
        geo_data: 地理位置数据 [{lat, lon, label}]
        metric_data: 指标数据 [{label, value, size, color}]
    """
    return f"""
    <div id="bubble-map" style="width: 100%; height: 600px;"></div>
    
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        const trace = {{
            type: 'scattergeo',
            mode: 'markers',
            lat: {json.dumps([g['lat'] for g in geo_data])},
            lon: {json.dumps([g['lon'] for g in geo_data])},
            text: {json.dumps([m['label'] for m in metric_data])},
            marker: {{
                size: {json.dumps([m.get('size', 10) for m in metric_data])},
                color: {json.dumps([m.get('color', '#0071e3') for m in metric_data])},
                sizemode: 'diameter',
                sizemin: 5,
                cmin: 0,
                cmax: 100,
                colorscale: 'Viridis',
                colorbar: {{
                    title: '值',
                    ticksuffix: '%'
                }}
            }},
            hoverinfo: 'text'
        }};
        
        const layout = {{
            title: '用户分布气泡图',
            showlegend: false,
            geo: {{
                scope: 'world',
                showocean: true,
                oceancolor: '#cce5ff',
                showland: true,
                landcolor: '#f5f5f5',
                showcountries: true,
                countrycolor: '#d1d1d1'
            }},
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent'
        }};
        
        Plotly.newPlot('bubble-map', [trace], layout);
    </script>
    """
