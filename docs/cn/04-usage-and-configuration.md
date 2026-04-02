---
难度：⭐⭐⭐
类型：核心概念
预计时间：50 分钟
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
3. 如何调整模型、数据供应商、输出语言和辩论轮数。
4. 如何配置后端地址以适配 OpenRouter、Ollama 等非官方端点。
5. 实验时应该如何做对比，而不是盲目堆复杂度。

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
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    "backend_url": "https://api.openai.com/v1",
    # Provider 专属参数（仅对应 Provider 被选中时生效）
    "google_thinking_level": None,      # 可选: "high", "minimal" 等
    "openai_reasoning_effort": None,    # 可选: "medium", "high", "low"
    "anthropic_effort": None,           # 可选: "high", "medium", "low"
    # 输出语言（仅影响用户可见输出，内部辩论始终英文）
    "output_language": "English",
    # 辩论与讨论设置
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # 数据供应商配置
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {},
}
```

### backend_url

控制 LLM API 的后端地址。默认值为 `https://api.openai.com/v1`，即 OpenAI 官方端点。当你使用非官方端点时需要修改此字段。

常见的替代配置：

| 场景 | backend_url 值 | 说明 |
| ---- | ---- | ---- |
| OpenAI 官方 | `https://api.openai.com/v1` | 默认值 |
| OpenRouter | `https://openrouter.ai/api/v1` | 聚合多家模型供应商 |
| Ollama 本地 | `http://localhost:11434/v1` | 零成本本地推理 |
| 自定义代理 | `https://your-proxy.example.com/v1` | 自建代理或企业网关 |

```python
# OpenRouter 示例
config["llm_provider"] = "openrouter"
config["backend_url"] = "https://openrouter.ai/api/v1"

# Ollama 本地示例
config["llm_provider"] = "ollama"
config["backend_url"] = "http://localhost:11434/v1"
```

实现原理：`backend_url` 在 `TradingAgentsGraph` 构造函数中传递给 `create_llm_client()`，作为 `base_url` 参数注入到底层 LLM 客户端。

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

如果你在意的是实验可比性，而不是单次“看起来更聪明”的输出，那么这两个参数最好成对记录。因为它们不只是性能参数，更是系统行为风格参数。

### max_recur_limit

max_recur_limit 对应图执行时的 recursion_limit。它的作用不是改善结论质量，而是防止异常循环把图执行无限拉长。

可以这样理解它：

1. 太低，复杂流程可能还没走完整就被截断。
2. 太高，异常条件边或工具循环会更难被及时发现。
3. 默认值 100 对当前主流程是偏保守的安全上限，通常不需要在首次使用时调整。

### output_language

控制用户可见输出的语言。默认值为 `"English"`。

```python
config["output_language"] = "中文"  # 或 "日本語"、"Français" 等
```

需要注意以下几点：

1. **只影响用户可见输出**。此配置作用于 Analyst 报告和 Portfolio Manager 最终决策，使这些内容以指定语言呈现。
2. **内部辩论始终使用英文**。Research Debate（Bull/Bear 辩论）和 Risk Debate（风险讨论）不受此配置影响，始终保持英文以保证推理质量。
3. **无额外 token 开销（默认情况）**。实现原理是 `get_language_instruction()` 函数在 `output_language` 为 `"English"` 时返回空字符串，不消耗任何额外 token；仅在设置为非 English 时追加 `" Write your entire response in {lang}."` 指令。

具体应用于以下 Agent（源码位置：各 Analyst 和 Portfolio Manager 的 prompt 构造处）：

| Agent | 源码位置 |
| ---- | ---- |
| market_analyst | `tradingagents/agents/analysts/market_analyst.py` |
| social_media_analyst | `tradingagents/agents/analysts/social_media_analyst.py` |
| news_analyst | `tradingagents/agents/analysts/news_analyst.py` |
| fundamentals_analyst | `tradingagents/agents/analysts/fundamentals_analyst.py` |
| portfolio_manager | `tradingagents/agents/managers/portfolio_manager.py` |

### Provider 专属参数

这三个参数分别控制对应 Provider 底层模型的推理深度/思考力度。只有在对应的 `llm_provider` 被选中时才会生效，不影响 Agent 逻辑本身。

```python
# Google 专用 —— 控制 Gemini 模型的 thinking level
config["google_thinking_level"] = "high"     # 可选: "high", "minimal" 等

# OpenAI 专用 —— 控制 o 系列模型的 reasoning effort
config["openai_reasoning_effort"] = "medium" # 可选: "medium", "high", "low"

# Anthropic 专用 —— 控制 Claude 模型的推理力度
config["anthropic_effort"] = "high"          # 可选: "high", "medium", "low"
```

默认值均为 `None`，表示不传递额外参数，使用模型自身的默认推理强度。实现原理是 `trading_graph.py` 的 `_get_provider_kwargs()` 方法根据当前 `llm_provider` 读取对应参数，仅在有值时才注入到 LLM 客户端构造函数中。

使用建议：

1. 通常不需要主动设置这些参数，模型默认表现已经足够。
2. 如果发现推理质量不足，可以尝试调高对应参数（如 `"high"`）。
3. 如果需要控制成本和延迟，可以尝试调低（如 `"low"` 或 `"minimal"`）。
4. 一次只调整一个 Provider 的参数，便于对比效果。

### data_vendors 与 tool_vendors

data_vendors 用于按能力类别设置默认供应商，tool_vendors 用于按具体工具覆写类别默认值。

当前能力类别定义在 [tradingagents/dataflows/interface.py](../../tradingagents/dataflows/interface.py)，可直接对应为：

| 类别 | 典型工具 | 作用 |
| ---- | ---- | ---- |
| core_stock_apis | get_stock_data | 股票价格与基础行情 |
| technical_indicators | get_indicators | 技术指标计算 |
| fundamental_data | get_fundamentals、get_balance_sheet、get_cashflow、get_income_statement | 公司财务与基本面数据 |
| news_data | get_news、get_global_news、get_insider_transactions | 新闻、全局事件与内幕交易数据 |

tool_vendors 的优先级高于 data_vendors，而且支持逗号分隔的回退链。例如：

```python
config["tool_vendors"] = {
  "get_news": "yfinance,alpha_vantage",
}
```

这表示 get_news 会先尝试 yfinance，只有主供应商失败时才回退到 alpha_vantage。

这意味着你可以：

1. 大多数工具走 yfinance。
2. 仅把少数关键工具切到 Alpha Vantage。
3. 甚至给某个工具配置供应商回退链。

需要注意的是，当前回退逻辑只会在特定异常路径上触发，最典型的是 AlphaVantageRateLimitError。不要把“配置了两个供应商”理解成“任何失败都会自动无损切换”。

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
config["quick_think_llm"] = "gpt-5.4-mini"
config["deep_think_llm"] = "gpt-5.4-mini"
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
```

适合首次验证链路，但不适合追求高质量最终裁决。

## 配置示例二：平衡型研究配置

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5.4-mini"
config["deep_think_llm"] = "gpt-5.4"
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

如果你只有一组可用 API Key，建议优先把它花在最稳定的主路径上，而不是同时追求“多供应商”“多模型”“高轮数”三件事。对大多数用户来说，单供应商 + 低轮数 + 清晰日志，比复杂但难复现实验更有价值。

## Python API 的一个推荐模式

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5.4-mini"
config["deep_think_llm"] = "gpt-5.4"

graph = TradingAgentsGraph(
    selected_analysts=["market", "news", "fundamentals"],
    debug=False,
    config=config,
)

final_state, decision = graph.propagate("AAPL", "2024-05-10")
print(decision)
```

这个模式比直接修改全局默认配置更稳，因为实验配置的意图更显式。

## Callbacks 回调机制

`TradingAgentsGraph` 构造函数接受一个可选的 `callbacks` 参数，用于注入回调处理器来追踪运行时统计信息。

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from cli.stats_handler import StatsCallbackHandler

config = DEFAULT_CONFIG.copy()

# 创建统计回调处理器
stats_handler = StatsCallbackHandler()

graph = TradingAgentsGraph(
    config=config,
    callbacks=[stats_handler],  # 传入回调处理器
)

final_state, decision = graph.propagate("AAPL", "2024-05-10")

# 获取运行统计
print(stats_handler.get_stats())
# {'llm_calls': 42, 'tool_calls': 15, 'tokens_in': 85000, 'tokens_out': 12000}
```

`StatsCallbackHandler`（源码：`cli/stats_handler.py`）继承自 LangChain 的 `BaseCallbackHandler`，追踪以下指标：

| 指标 | 说明 |
| ---- | ---- |
| `llm_calls` | LLM 调用次数 |
| `tool_calls` | 工具调用次数 |
| `tokens_in` | 输入 token 总量 |
| `tokens_out` | 输出 token 总量 |

使用场景：

1. **成本估算**：通过 token 统计估算每次分析的实际成本。
2. **性能分析**：通过调用次数定位瓶颈节点。
3. **实验对比**：不同配置下的 token 消耗差异。

注意事项：callbacks 被注入到 LLM 客户端层面（构造函数中传递给 `create_llm_client()`），因此能捕获所有 LLM 交互。CLI 模式下默认会启用 `StatsCallbackHandler`。

## 配置场景速查

以下是针对不同使用目标的具体配置模板，可直接复制使用。

### 场景一：本地 Ollama 零成本研究

适合没有 API 预算、希望本地体验完整流程的用户。

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "ollama"
config["backend_url"] = "http://localhost:11434/v1"
config["quick_think_llm"] = "llama3"
config["deep_think_llm"] = "llama3"
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
```

前置条件：本地已安装并运行 Ollama，且已拉取对应模型。注意本地模型的推理质量通常弱于云端大模型，建议降低辩论轮数以减少幻觉累积。

### 场景二：多语言报告（中文输出）

适合需要中文研究报告的用户。

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["output_language"] = "中文"
# 其他配置按需调整
```

要点：仅修改 `output_language` 一个字段即可。Analyst 报告和最终决策会以中文输出，但内部 Bull/Bear 辩论和 Risk 讨论仍然使用英文，确保推理链路不受语言切换影响。

### 场景三：OpenRouter 混合模型

适合想组合不同供应商模型、按节点类型分配的用户。

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openrouter"
config["backend_url"] = "https://openrouter.ai/api/v1"
config["quick_think_llm"] = "meta-llama/llama-3-70b-instruct"
config["deep_think_llm"] = "anthropic/claude-sonnet-4-20250514"
config["max_debate_rounds"] = 2
config["max_risk_discuss_rounds"] = 2
```

要点：`llm_provider` 设为 `openrouter`，`backend_url` 指向 OpenRouter 端点，模型名称使用 OpenRouter 格式（`供应商/模型名`）。

### 场景四：高强度推理模式

适合追求最高推理质量、对成本不敏感的用户。

```python
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4"
config["quick_think_llm"] = "gpt-5.4"
config["openai_reasoning_effort"] = "high"
config["max_debate_rounds"] = 3
config["max_risk_discuss_rounds"] = 3
config["max_recur_limit"] = 200
```

要点：所有节点都使用最强模型，推理力度调至最高，辩论轮数增加以获得更充分的讨论。注意 token 消耗会显著增加，建议配合 `StatsCallbackHandler` 监控成本。

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

进一步地，建议把实验迭代固定成一轮只改一个变量：

1. 先固定 Analyst 组合和轮数，比较不同模型。
2. 再固定模型，只比较数据供应商或回退链。
3. 最后在已有基线之上调整辩论轮数。

如果你一轮实验同时改 3 个变量，得到的不是“结论”，而是新的解释难题。

## 小结

正确使用 TradingAgents 的关键，不在于找到某个“神奇配置”，而在于建立一套可比较、可复现、可解释的配置方法。

## 自测检查清单

- [ ] 我知道 llm_provider、quick_think_llm 和 deep_think_llm 分别解决什么问题。
- [ ] 我知道 backend_url 的作用，以及如何配置 OpenRouter 或 Ollama。
- [ ] 我知道 output_language 只影响用户可见输出，不影响内部辩论。
- [ ] 我知道 Provider 专属参数（google_thinking_level、openai_reasoning_effort、anthropic_effort）各自对应哪个供应商。
- [ ] 我知道 data_vendors 和 tool_vendors 的优先级关系。
- [ ] 我知道 max_debate_rounds、max_risk_discuss_rounds 和 max_recur_limit 各自控制什么。
- [ ] 我知道回退链不是”任何失败都会自动切换”。
- [ ] 我知道一次实验最好只改一个变量。
- [ ] 我知道如何使用 callbacks 追踪 LLM 调用次数和 token 消耗。

---

__文档元信息__
难度：⭐⭐⭐ | 类型：核心概念 | 更新日期：2026-04-01 | 预计阅读时间：50 分钟
