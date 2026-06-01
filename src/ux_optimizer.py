"""
交互体验优化模块
提供快捷键支持和拖拽功能
"""
import os


def generate_keyboard_shortcuts_html() -> str:
    """生成快捷键说明HTML"""
    return """
    <div id="keyboard-shortcuts-modal" class="modal">
        <div class="modal-content" style="max-width: 600px;">
            <div class="modal-header">
                <h2 class="modal-title">⌨️ 键盘快捷键</h2>
                <button class="modal-close" onclick="closeKeyboardShortcuts()">&times;</button>
            </div>
            <div style="display: grid; gap: 16px;">
                <div style="display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 12px; background: #f5f5f7; border-radius: 8px;">
                    <kbd style="background: white; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">Ctrl + /</kbd>
                    <span style="color: #1d1d1f;">显示/隐藏快捷键帮助</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 12px; background: #f5f5f7; border-radius: 8px;">
                    <kbd style="background: white; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">Ctrl + A</kbd>
                    <span style="color: #1d1d1f;">打开高级分析面板</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 12px; background: #f5f5f7; border-radius: 8px;">
                    <kbd style="background: white; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">Ctrl + R</kbd>
                    <span style="color: #1d1d1f;">刷新当前数据</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 12px; background: #f5f5f7; border-radius: 8px;">
                    <kbd style="background: white; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">Ctrl + 1-6</kbd>
                    <span style="color: #1d1d1f;">切换高级分析标签页</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 12px; background: #f5f5f7; border-radius: 8px;">
                    <kbd style="background: white; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">Escape</kbd>
                    <span style="color: #1d1d1f;">关闭弹窗/面板</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 12px; background: #f5f5f7; border-radius: 8px;">
                    <kbd style="background: white; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">?</kbd>
                    <span style="color: #1d1d1f;">显示快捷键帮助</span>
                </div>
            </div>
            <div style="margin-top: 24px; padding: 16px; background: rgba(0, 113, 227, 0.1); border-radius: 12px; border-left: 4px solid #0071e3;">
                <strong style="color: #0071e3;">💡 提示</strong>
                <p style="margin-top: 8px; color: #86868b; font-size: 14px;">
                    Mac 用户可以使用 ⌘ 替代 Ctrl 键
                </p>
            </div>
        </div>
    </div>
    """


def get_all_ux_scripts() -> str:
    """获取所有UX优化脚本"""
    return generate_keyboard_shortcuts_html()
