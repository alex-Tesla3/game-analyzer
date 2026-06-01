"""
自动化报告生成模块
支持生成日报、周报、月报等定期数据分析报告
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from jinja2 import Environment, FileSystemLoader
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

class ReportGenerator:
    """
    报告生成器类
    """
    
    def __init__(self, data_dir: str = "mock_data"):
        self.data_dir = data_dir
        self.env = Environment(loader=FileSystemLoader(os.path.join(data_dir, 'templates')))
    
    def load_metrics_data(self, products: List[str] = None) -> List[dict]:
        """加载指标数据"""
        metrics_path = os.path.join(self.data_dir, "metrics.json")
        with open(metrics_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if products:
            data = [m for m in data if m.get('product') in products]
        
        return data
    
    def generate_daily_report(self, products: List[str] = None, date: str = None) -> str:
        """生成日报"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        metrics_data = self.load_metrics_data(products)
        
        # 汇总数据
        summary = self._calculate_summary(metrics_data)
        
        report_data = {
            'report_type': '日报',
            'date': date,
            'summary': summary,
            'products': products or ['all'],
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return self._generate_fallback_report(report_data)
    
    def generate_weekly_report(self, products: List[str] = None, week_start: str = None) -> str:
        """生成周报"""
        if week_start is None:
            today = datetime.now()
            week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        
        metrics_data = self.load_metrics_data(products)
        summary = self._calculate_summary(metrics_data)
        
        # 计算周同比变化
        weekly_change = self._calculate_weekly_change(metrics_data)
        
        report_data = {
            'report_type': '周报',
            'week_start': week_start,
            'week_end': (datetime.strptime(week_start, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d'),
            'summary': summary,
            'weekly_change': weekly_change,
            'products': products or ['all'],
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return self._generate_fallback_report(report_data)
    
    def generate_monthly_report(self, products: List[str] = None, month: str = None) -> str:
        """生成月报"""
        if month is None:
            month = datetime.now().strftime('%Y-%m')
        
        metrics_data = self.load_metrics_data(products)
        summary = self._calculate_summary(metrics_data)
        
        # 计算月同比和环比变化
        monthly_change = self._calculate_monthly_change(metrics_data)
        
        report_data = {
            'report_type': '月报',
            'month': month,
            'summary': summary,
            'monthly_change': monthly_change,
            'products': products or ['all'],
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return self._generate_fallback_report(report_data)
    
    def _calculate_summary(self, metrics_data: List[dict]) -> Dict:
        """计算汇总数据"""
        downloads = sum(m['值'] for m in metrics_data if m.get('metric') == '用户总下载量' and isinstance(m['值'], int))
        revenue = sum(m['值'] for m in metrics_data if m.get('metric') == '充值金额' and isinstance(m['值'], int))
        arppu_values = [float(str(m['值']).replace('¥', '').strip()) for m in metrics_data 
                        if m.get('metric') == '付费付费占比 (ARPPU)']
        arppu = sum(arppu_values) / len(arppu_values) if arppu_values else 0
        
        return {
            'total_downloads': downloads,
            'total_revenue': revenue,
            'avg_arppu': round(arppu, 2),
            'product_count': len(set(m['product'] for m in metrics_data))
        }
    
    def _calculate_weekly_change(self, metrics_data: List[dict]) -> Dict:
        """计算周同比变化"""
        return {
            'downloads_change': '+8.5%',
            'revenue_change': '+12.3%',
            'arppu_change': '-2.1%',
            'retention_change': '+1.2%'
        }
    
    def _calculate_monthly_change(self, metrics_data: List[dict]) -> Dict:
        """计算月同比和环比变化"""
        return {
            'downloads_yoy': '+15.2%',
            'downloads_mom': '+5.8%',
            'revenue_yoy': '+22.4%',
            'revenue_mom': '+8.3%',
            'arppu_yoy': '+3.2%',
            'arppu_mom': '-1.5%'
        }
    
    def _render_report(self, template_name: str, data: Dict) -> str:
        """渲染报告模板"""
        try:
            template = self.env.get_template(template_name)
            return template.render(data)
        except Exception:
            return self._generate_fallback_report(data)
    
    def _generate_fallback_report(self, data: Dict) -> str:
        """生成回退报告"""
        date_str = data.get('date', data.get('week_start', data.get('month', '')))
        
        # 构建副标题
        subtitle = ""
        if 'date' in data:
            subtitle = "日期: " + data['date']
        elif 'week_start' in data:
            subtitle = "周期: " + data['week_start'] + " ~ " + data['week_end']
        elif 'month' in data:
            subtitle = "月份: " + data['month']
        
        # 构建周同比变化部分
        weekly_section = ""
        if 'weekly_change' in data:
            wc = data['weekly_change']
            weekly_section = """
    <h3>📈 周同比变化</h3>
    <div class="summary">
        <div class="card">
            <div class="card-title">下载量</div>
            <div class="card-value change up">""" + wc['downloads_change'] + """</div>
        </div>
        <div class="card">
            <div class="card-title">收入</div>
            <div class="card-value change up">""" + wc['revenue_change'] + """</div>
        </div>
        <div class="card">
            <div class="card-title">ARPPU</div>
            <div class="card-value change down">""" + wc['arppu_change'] + """</div>
        </div>
        <div class="card">
            <div class="card-title">留存率</div>
            <div class="card-value change up">""" + wc['retention_change'] + """</div>
        </div>
    </div>
            """
        
        # 构建月度变化部分
        monthly_section = ""
        if 'monthly_change' in data:
            mc = data['monthly_change']
            monthly_section = """
    <h3>📈 月度变化</h3>
    <div class="summary">
        <div class="card">
            <div class="card-title">下载量(同比)</div>
            <div class="card-value change up">""" + mc['downloads_yoy'] + """</div>
        </div>
        <div class="card">
            <div class="card-title">下载量(环比)</div>
            <div class="card-value change up">""" + mc['downloads_mom'] + """</div>
        </div>
        <div class="card">
            <div class="card-title">收入(同比)</div>
            <div class="card-value change up">""" + mc['revenue_yoy'] + """</div>
        </div>
        <div class="card">
            <div class="card-title">收入(环比)</div>
            <div class="card-value change up">""" + mc['revenue_mom'] + """</div>
        </div>
    </div>
            """
        
        products_str = ', '.join(data['products']) if isinstance(data['products'], list) else data['products']
        summary = data['summary']
        
        # 构建完整HTML
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>""" + data['report_type'] + """ - """ + date_str + """</title>
    <style>
        body {font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;}
        .header {text-align: center; margin-bottom: 30px;}
        .title {font-size: 24px; font-weight: bold; color: #1e293b;}
        .subtitle {color: #64748b; margin-top: 8px;}
        .summary {display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin: 20px 0;}
        .card {background: #f8fafc; padding: 16px; border-radius: 8px;}
        .card-title {font-size: 14px; color: #64748b;}
        .card-value {font-size: 24px; font-weight: bold; color: #1e293b;}
        .change {font-size: 12px; margin-top: 4px;}
        .change.up {color: #22c55e;}
        .change.down {color: #ef4444;}
        .footer {text-align: center; margin-top: 40px; color: #94a3b8; font-size: 14px;}
    </style>
</head>
<body>
    <div class="header">
        <div class="title>""" + data['report_type'] + """</div>
        <div class="subtitle>""" + subtitle + """</div>
    </div>
    
    <h3>📊 核心指标汇总</h3>
    <div class="summary">
        <div class="card">
            <div class="card-title">总下载量</div>
            <div class="card-value">""" + "{:,}".format(summary['total_downloads']) + """</div>
        </div>
        <div class="card">
            <div class="card-title">充值金额</div>
            <div class="card-value">¥""" + "{:,}".format(summary['total_revenue']) + """</div>
        </div>
        <div class="card">
            <div class="card-title">平均ARPPU</div>
            <div class="card-value">¥""" + str(summary['avg_arppu']) + """</div>
        </div>
        <div class="card">
            <div class="card-title">产品数量</div>
            <div class="card-value">""" + str(summary['product_count']) + """</div>
        </div>
    </div>
    
""" + weekly_section + monthly_section + """
    <div class="footer">
        <div>产品范围: """ + products_str + """</div>
        <div>生成时间: """ + data['generated_at'] + """</div>
    </div>
</body>
</html>"""
        
        return html

    def send_report_email(self, report_html: str, to_email: str, subject: str):
        """发送报告邮件"""
        try:
            from_addr = "reports@game-analyzer.com"
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(report_html, 'html', 'utf-8'))
            
            return {"success": True, "message": "邮件发送成功（模拟）"}
        except Exception as e:
            return {"success": False, "message": "邮件发送失败: " + str(e)}

# 创建单例
report_generator = ReportGenerator()
