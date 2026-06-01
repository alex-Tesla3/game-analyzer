import json
from typing import List, Dict, Any
import pandas as pd

# --- 1. 数据加载函数 ---
def load_data(file_path: str) -> Any:
    """加载模拟数据文件。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                raise ValueError("Data loaded is not a list.")
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"错误：JSON解析失败，请检查 {file_path} 文件。错误信息: {e}")
        return None

# --- 2. 核心分析引擎 ---
def run_business_intelligence_report(comments_data: List[Dict], metrics_data: List[Dict]) -> Dict:
    """
    核心 BI 报告生成器。
    输入：原始评论数据和关键业务KPI数据。
    输出：包含可执行建议的结构化洞察报告。
    """
    print("--- 🚀 正在运行 AI 洞察分析引擎... ---")

    # --- A. 评论分析 (战术痛点提取) ---
    comments_df = pd.DataFrame(comments_data or [])
    sentiment_col = None
    for candidate in ("情绪", "sentiment"):
        if candidate in comments_df.columns:
            sentiment_col = candidate
            break
    content_col = "内容" if "内容" in comments_df.columns else ("content" if "content" in comments_df.columns else None)

    if sentiment_col and content_col and not comments_df.empty:
        negative_topics = comments_df[comments_df[sentiment_col] == "negative"][content_col].astype(str).str.cat(sep="; ")
        positive_topics = comments_df[comments_df[sentiment_col] == "positive"][content_col].astype(str).str.cat(sep="; ")
    else:
        negative_topics = ""
        positive_topics = ""
    
    # 2. 关键冲突点识别 (矛盾点)
    # 模拟识别出“战斗系统赞，但付费限制了体验”的冲突
    conflict_summary = (
        "✅ **正面肯定洞察**：用户高度肯定核心机制（如：战斗系统、角色个性化），这表明产品的核心体验是成功的。\n"
        "⚠️ **最大的用户冲突點**：大部分负面评论集中在'付费限制'和'流程复杂'。用户感受到的核心矛盾是：**核心机制很棒，但被上锁了（内容受限）**。"
    )

    # --- B. 业务指标分析 (量化证据) ---
    metrics_df = pd.DataFrame(metrics_data or [])
    metric_col = None
    for candidate in ("metric", "指标"):
        if candidate in metrics_df.columns:
            metric_col = candidate
            break
    critical_decline = ""
    if metric_col and not metrics_df.empty:
        metric_text = metrics_df[metric_col].astype(str).str.cat(sep=",")
        if "付费付费占比 (ARPPU)" in metric_text:
            critical_decline = "🔴 **付费变现警报**：ARPPU下降15%是非常危险的信号。这证明了用户行为已经改变，且付费意愿受到影响。"
        if "平均用户留存率" in metric_text:
            critical_decline += "\n🔴 **留存失血预警**：留存率下降5个百分点，是短期用户群体健康状况急剧恶化的信号，需要立即干预。"
    
    # --- C. 汇总报告与可操作建议 (最具商业价值部分) ---
    
    report = {
        "ReportTitle": "市场洞察报告：付费限制与流程复杂性引发的关键警报",
        "Summary": "本次分析的核心结论是：用户对产品的核心乐趣机制认可度高，但当前的产品设计和变现流程正在扼杀用户满意度和消费意愿。",
        "AnalysisSections": {
            "痛点报告 (The Pain)": {
                "证据A_来自评论": f"--- {conflict_summary}",
                "证据B_来自指标": critical_decline,
                "痛点摘要": "付费壁垒过高导致初体验受限。当用户发现核心fun（乐趣点）很难免费体验时，立即产生离开和抱怨情绪。"
            },
            "改进产品建议 (Solution)": {
                "建议优先级1 (A/B Test核心)：": "将核心的、用户反馈积极的机制（如：战斗系统）的关键体验流程，改为免费用户也能接触的『限时/限次数』体验。",
                "建议优先级2 (UI/UX)：": "根据用户反馈，简化新手教程和UI流程，必须降低初次使用用户的心理门槛。",
                "建议优先级3 (机制优化)：": "参考竞品，在资源获取（素材）方面提供更直观的反馈和引导。"
            },
            "未来产品方向 (Strategy)": {
                "机会点": "围绕‘专业化’和‘深度定制’切入：推出一个仅做『资源/角色深度定制化』的付费工具/模块，避开与现有核心流程的正面冲突。",
                "市场信号": "用户对『个性化展现』需求的增长，预示着‘虚拟形象商店’或‘荣誉展示系统’是可预期的成功品类。"
            }
        }
    }
    return report

# --- 3. 主执行函数 ---
def main():
    """主流程：加载数据 -> 分析 -> 输出报告"""
    
    # 1. 加载模拟数据
    comments = load_data("mock_data/comments.json")
    metrics = load_data("mock_data/metrics.json")

    if comments and metrics:
        # 2. 运行分析
        report = run_business_intelligence_report(comments, metrics)
        
        # 3. 输出结构化报告（本次演示直接打印，在Web应用中会渲染）
        print("\n" + "="*60)
        print("          🎉 商业洞察分析报告 (Mock Run) 🎉")
        print("="*60 + "\n")
        
        print(f"【报告标题】: {report['ReportTitle']}")
        print(f"【核心摘要】: {report['Summary']}\n")

        print("==================================================")
        print("🔍 一、 痛点报告 (数据驱动的警报)")
        print("--------------------------------------------------")
        for key, value in report['AnalysisSections']['痛点报告 (The Pain)'].items():
            print(f"\n--- {key} ---")
            print(value)

        print("\n\n==================================================")
        print("💡 二、 改进产品建议 (Actionable Plan)")
        print("--------------------------------------------------")
        for key, value in report['AnalysisSections']['改进产品建议 (Solution)'].items():
            print(f"\n👉 {key}: {value}")
        
        print("\n\n==================================================")
        print("🚀 三、 未来探索方向 (Long-term Strategy)")
        print("==================================================")
        for key, value in report['AnalysisSections']['未来产品方向 (Strategy)'].items():
            print(f"\n🌐 {key}")
            print(f"   结论: {value}")

if __name__ == "__main__":
    main()
