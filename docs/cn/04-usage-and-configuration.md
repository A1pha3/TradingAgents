---
难度：⭐⭐⭐
类型：核心概念
预计时间：35 分钟
前置知识：
  - [01-quickstart.md](01-quickstart.md)
后续推荐：
  - [05-extension-guide.md](05-extension-guide.md)
学习路径：
  - 用户路径：第 2 阶段
  - 开发路径：第 2 阶段
---

# TradingAgents 使用说明与配置详解

## 本文重点

如果说快速开始解决的是“怎么跑起来”，那么这篇文档解决的是“跑起来之后怎么用得更稳、更准、更可控”。

重点包括：

1. CLI 与 Python API 分别适合什么场景。
2. 默认配置里的关键字段各自影响什么。
3. 如何调整模型、数据供应商和辩论轮数。
4. 实验时应该如何做对比，而不是盲目堆复杂度。

## 使用方式概览

### CLI 适合什么场景

CLI 适合：

1. 第一次体验项目。
2. 观察实时进度。
3. 人工监督中间结果。
4. 演示系统工作方式。

它的强项是可视化反馈更好，便于建立对系统流程的直觉。

### Python API 适合什么场景

Python API 适合：

1. 批量实验。
2. 自定义脚本集成。
3. 接入自己的回测或评估框架。
4. 程序化比较多个配置版本。

它的强项是自动化程度更高，便于做可重复实验。

## CLI 的关键选择项

| 选择项 | 作用 | 对系统的影响 |
| ---- | ---- | ---- |
| 股票代码 | 指定分析对象 | 决定 company_of_interest |
| 分析日期 | 指定观察时点 | 决定 trade_date |
| Analyst 组合 | 控制启用哪些分析师 | 决定 GraphSetup 动态创建哪些节点 |
| 研究深度 | 控制讨论回合数 | 映射到 max_debate_rounds 与 max_risk_discuss_rounds |
| LLM Provider | 指定模型供应商 | 决定工厂返回哪个客户端实现 |
| quick_think_llm | 高频分析节点模型 | 影响运行速度和基础分析质量 |
| deep_think_llm | 关键裁决节点模型 | 影响最终仲裁质量 |

## 默认配置解读

默认配置位于 tradingagents/default_config.py，核心字段包括：

```python
DEFAULT_CONFIG = {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {},
}
```

### llm_provider

控制底层模型供应商。当前支持 openai、anthropic、google、xai、openrouter、ollama。

### quick_think_llm 与 deep_think_llm

这两个字段是系统最值得认真对待的配置之一：

1. quick_think_llm 影响高频节点的大盘体验。
2. deep_think_llm 影响关键裁决节点的收敛质量。

如果你预算有限，优先保证 deep_think_llm 的稳定性，再考虑 quick_think_llm 的成本优化。

### max_debate_rounds 与 max_risk_discuss_rounds

这两个字段影响的不只是耗时，还影响系统输出风格：

1. 轮数低，结论更快，但可能不够全面。
2. 轮数高，讨论更充分，但也更慢、更贵。

### data_vendors 与 tool_vendors

data_vendors 用于按能力类别设置默认供应商，tool_vendors 用于按具体工具覆写类别默认值。

这意味着你可以：

1. 大多数工具走 yfinance。
2. 仅把少数关键工具切到 Alpha Vantage。
3. 甚至给某个工具配置供应商回退链。

## 一个稳妥的配置思路

对于大多数研究型使用场景，推荐采用分层调参法：

1. 先固定角色组合和辩论轮数。
2. 再比较不同模型组合。
3. 最后再比较不同数据源组合。

如果你一开始同时改模型、数据源和工作流结构，几乎无法判断结果变化来自哪里。

## 配置决策矩阵

| 你的目标 | quick_think_llm 策略 | deep_think_llm 策略 | 辩论轮数建议 | 数据源建议 |
| ---- | ---- | ---- | ---- | ---- |
| 先跑通 | 低成本、稳定即可 | 与 quick 保持一致也可以 | 1 / 1 | 全部先用 yfinance |
| 做日常研究 | 兼顾成本和稳定性 | 选择更强、更稳的模型 | 2 / 2 | 先固定一套主供应商 |
| 对比模型效果 | 固定一个基线模型 | 每次只替换一个关键模型 | 保持不变 | 保持不变 |
| 对比数据质量 | 保持不变 | 保持不变 | 保持不变 | 只替换一个类别或一个工具 |
| 做复杂实验 | 高频节点控制成本 | 仲裁节点优先质量 | 2 或更高 | 采用主供应商加回退链 |

## 配置示例一：低成本试跑

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5-mini"
config["deep_think_llm"] = "gpt-5-mini"
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
```

适合首次验证链路，但不适合追求高质量最终裁决。

## 配置示例二：平衡型研究配置

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5-mini"
config["deep_think_llm"] = "gpt-5.2"
config["max_debate_rounds"] = 2
config["max_risk_discuss_rounds"] = 2
```

适合做更稳定的研究结论比较。

## 配置示例三：混合数据源策略

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["data_vendors"] = {
    "core_stock_apis": "yfinance",
    "technical_indicators": "yfinance",
    "fundamental_data": "alpha_vantage",
    "news_data": "yfinance",
}

config["tool_vendors"] = {
    "get_news": "yfinance,alpha_vantage",
}
```

这种方式适合在数据质量与可用性之间做更细粒度的平衡。

## 使用策略建议

### 第一步：先验证稳定性

不要刚开始就追求“最强配置”。先确认：

1. 模型能稳定调用。
2. 数据源能稳定返回。
3. 图能完整收敛。

### 第二步：再追求信息充分性

稳定之后，再增加：

1. Analyst 数量。
2. 辩论轮数。
3. 更强 deep_think_llm。

### 第三步：最后做供应商与成本优化

当你已经有一个相对稳定的基线配置时，再去优化成本、吞吐和回退链，效率会更高。

## Python API 的一个推荐模式

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5-mini"
config["deep_think_llm"] = "gpt-5.2"

graph = TradingAgentsGraph(
    selected_analysts=["market", "news", "fundamentals"],
    debug=False,
    config=config,
)

final_state, decision = graph.propagate("AAPL", "2024-05-10")
print(decision)
```

这个模式比直接修改全局默认配置更稳，因为实验配置的意图更显式。

## 使用中的常见误区

1. 把研究深度当成装饰性选项。
2. 只看最终 BUY 或 SELL，不看中间报告。
3. 同时更换多个变量，导致实验结果不可解释。
4. 以为改了 results_dir 就能改变全部输出路径。

## 一套推荐的实验记录模板

为了让你的实验可比较，建议每次至少记录以下信息：

1. 标的与日期。
2. selected_analysts。
3. quick_think_llm 与 deep_think_llm。
4. max_debate_rounds 与 max_risk_discuss_rounds。
5. data_vendors 与 tool_vendors。
6. 最终决策和关键中间报告摘要。

这样做的意义在于，你后续复盘时不会只剩下一个 BUY 或 SELL，而能追溯结论是如何形成的。

## 小结

正确使用 TradingAgents 的关键，不在于找到某个“神奇配置”，而在于建立一套可比较、可复现、可解释的配置方法。

---

__文档元信息__
难度：⭐⭐⭐ | 类型：核心概念 | 更新日期：2026-03-29 | 预计阅读时间：35 分钟
