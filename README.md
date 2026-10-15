# HDU 发票工作台

基于 Python 和 PySide6 的 Windows 发票报销整理工具。

## 功能

- 读取电子发票 PDF 的金额、号码、代码和开票信息，按发票号码查重。
- 按每叠张数、金额上限自动分叠，支持手动拖动排序和调整。
- 识别订单截图的实付款金额，自动或手动绑定到发票。
- 按日期管理已有叠，支持锁定保护及变化对比。
- 导出整理后的发票、订单截图、Excel 和工作区状态文件。
- 支持撤销、重做、主题切换及 GitHub Release 更新检查。

## 运行

建议使用 Windows 和 Python 3.11：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

也可以在安装依赖后运行 `run.bat`。程序会在需要时创建本机的
`settings.json`；仓库内的 `settings.example.json` 仅提供无个人信息的配置示例。

## 基本操作

1. 选择输出目录，填写预约人和实际报销人。
2. 拖入发票 PDF 和 JPG/PNG 订单截图，等待识别。
3. 点击“一键分叠”，或选择目标叠后手动加入。
4. 检查分叠和截图匹配结果，点击“保存并输出”。

右侧选择发票按 Delete 会将发票及绑定截图退回左侧；左侧按 Delete
只移除工作区项目，保留源文件。Ctrl+Z 撤销，Ctrl+Y 重做。
程序内“使用说明”包含完整操作规则。

## 隐私与发布

发票与截图的识别在本地进行。检查更新时访问 GitHub，下载新版安装包
也需要网络。应用不会将发票、截图或报销人名单上传到 GitHub。

个人设置、发票、导出结果、编辑器配置、缓存和调试截图均不应提交。
`.gitignore` 已覆盖这些常见文件；分享文件前仍需确认其中没有个人信息。

当前版本由 `app_version.py` 统一定义。Windows 安装包和 Release 发布方式
见 [发布说明](packaging/RELEASES.md)。

## 测试

```powershell
python -B -m unittest discover -s tests -v
```

测试默认使用 Qt 离屏模式，不需要操作桌面窗口。
