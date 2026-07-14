# Python API ⭐⭐

> **目标读者**：想把 TradingAgents 嵌进自己脚本、回测或 Pipeline 的开发者
> **核心问题**：怎么不靠 CLI，只用几行 Python 拿到一个交易决策？
> **前置知识**：[快速开始](../01-getting-started/quickstart.md) ⭐、[安装](../01-getting-started/installation.md) ⭐

---

## 这篇文档解决什么问题

CLI 适合一次性提问，但当你想做下面这些事时，命令行就不够用了：

- 把 50 只股票批量跑一遍，挑出"买入"信号
- 接进回测框架，按日推进、逐日产出决策
- 在自己的日志系统里记录每次调用的 token 消耗
- 只跑部分分析师（比如只看新闻和基本面），跳过情绪分析

这些场景的共同点是：你需要拿到决策之后继续写代码，而不是停在终端输出上。TradingAgents 的全部能力都封装在 `TradingAgentsGraph` 这一个类里，本文档讲清楚怎么构造它、怎么调它、怎么改它的行为。

阅读前你需要知道一件事：包根 `tradingagents/__init__.py` 只负责自动加载 `.env` 和抑制无害告警，**不导出任何业务符号**。所以下面两条 import 是固定写法，不要写成 `from tradingagents import ...`：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
```

---

## 最小可运行示例

项目根目录的 `main.py` 就是官方的最短示例，全部逻辑只有三步：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

# DEFAULT_CONFIG 已经叠加了 TRADINGAGENTS_* 环境变量覆盖，
# 所以你可以纯靠 .env 切换模型或端点，不必改这段代码。
config = DEFAULT_CONFIG.copy()

ta = TradingAgentsGraph(debug=True, config=config)

# 推进一次分析，返回 (final_state, decision_signal)
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

`propagate` 的完整签名是：

```python
ta.propagate(company_name, trade_date, asset_type="stock")
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `company_name` | `str` | Ticker 符号，如 `"NVDA"`、`"0700.HK"`、`"BTC-USD"` |
| `trade_date` | `str` | 分析日期，格式 `"YYYY-MM-DD"` |
| `asset_type` | `str` | `"stock"`（默认）或 `"crypto"`。CLI 会按 ticker 自动判断，编程调用时请显式传 |

返回值是一个元组 `(final_state, decision_signal)`：

- `final_state`：完整状态字典，包含四份分析师报告、辩论历史、交易员计划、风险讨论、最终决策等全部字段
- `decision_signal`：从 `final_state["final_trade_decision"]` 里抽出的精简信号，通常是 `Buy` / `Overweight` / `Hold` / `Underweight` / `Sell` 之一

如果你只关心结论，像上面那样用 `_` 丢掉 `final_state` 即可；想要报告内容就保留它。

---

## 构造参数详解

`TradingAgentsGraph` 的构造函数：

```python
TradingAgentsGraph(
    selected_analysts=("market", "social", "news", "fundamentals"),
    debug=False,
    config=None,
    callbacks=None,
)
```

| 参数 | 默认值 | 作用 |
|------|--------|------|
| `selected_analysts` | `("market", "social", "news", "fundamentals")` | 选哪些分析师参与本轮分析，详见下一节 |
| `debug` | `False` | `True` 时逐节点流式打印消息，返回的 `final_state` 与非 debug 路径一致 |
| `config` | `None` | 配置字典。`None` 时用 `DEFAULT_CONFIG`；传入前通常会 `.copy()` 再改键 |
| `callbacks` | `None` | 回调处理器列表，传给 LLM 构造器，用于统计 token、记录日志等 |

`config=None` 会直接落到 `DEFAULT_CONFIG`，所以下面两种写法等价：

```python
ta = TradingAgentsGraph()                              # 用默认配置
ta = TradingAgentsGraph(config=DEFAULT_CONFIG)         # 显式传同一份
```

---

## 场景 1：自定义分析师组合

`selected_analysts` 决定本轮跑哪几类分析师。四个可选键：

| 键 | 实际创建的分析师 | 数据工具 |
|----|----------------|---------|
| `"market"` | Market Analyst | 股价、技术指标、市场快照 |
| `"social"` | **Sentiment Analyst**（情绪分析师） | 新闻类工具 |
| `"news"` | News Analyst | 新闻、内部交易、宏观指标、预测市场 |
| `"fundamentals"` | Fundamentals Analyst | 基本面、资产负债表、现金流、利润表 |

注意 `"social"` 这个键是历史遗留的向后兼容名，框架内部实际调用的是 `create_sentiment_analyst`，对应的是 Sentiment Analyst。写代码时仍用 `"social"` 这个字符串。

只跑新闻和基本面，跳过市场和情绪：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(
    selected_analysts=["news", "fundamentals"],   # 注意是列表/元组
    debug=False,
    config=config,
)

_, decision = ta.propagate("AAPL", "2024-05-10")
print(decision)
```

分析师按你给的顺序依次执行，最后一个跑完后进入多空辩论环节。顺序不同不会改变结论方向，但会影响中间报告的拼接次序。

---

## 场景 2：自定义配置

`DEFAULT_CONFIG` 是个普通字典，复制一份再改键是推荐做法。下面把辩论轮数从默认的 1 调到 3，让多空双方多交锋几轮：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["max_debate_rounds"] = 3                     # 多空辩论轮数
config["max_risk_discuss_rounds"] = 2               # 风险讨论轮数

ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("TSLA", "2024-05-10")
```

常用配置键（完整列表见 `tradingagents/default_config.py`）：

| 键 | 默认值 | 含义 |
|----|--------|------|
| `llm_provider` | `"openai"` | LLM 提供商，详见 [本地模型部署](local-models.md) |
| `deep_think_llm` | `"gpt-5.5"` | 深度思考模型，用于研究经理、组合经理 |
| `quick_think_llm` | `"gpt-5.4-mini"` | 快速思考模型，用于分析师、辩论者 |
| `backend_url` | `None` | 自定义模型端点 |
| `max_debate_rounds` | `1` | 多空辩论轮数 |
| `max_risk_discuss_rounds` | `1` | 风险讨论轮数 |
| `output_language` | `"English"` | 报告输出语言，设成 `"中文"` 可得中文报告（CLI 菜单值，见 [多语言输出](output-language.md)） |
| `checkpoint_enabled` | `False` | 断点续跑开关 |

**环境变量也能改这些键**。`DEFAULT_CONFIG` 在加载时已经把 `TRADINGAGENTS_*` 环境变量叠加上去了，所以你既可以在代码里改 `config["..."]`，也可以在 `.env` 里写 `TRADINGAGENTS_MAX_DEBATE_ROUNDS=3`。两种方式的区别：代码里的硬编码会忽略环境变量，`.env` 的方式可以被运行时覆盖。`main.py` 顶部的注释把这层取舍写得很清楚。

---

## 场景 3：用回调统计 token

`callbacks` 接收一个回调处理器列表，会原样传给底层 LLM 构造器。框架自带一个 `StatsCallbackHandler`，能统计 LLM 调用次数、工具调用次数、输入输出 token：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from cli.stats_handler import StatsCallbackHandler

stats = StatsCallbackHandler()

config = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(
    config=config,
    callbacks=[stats],
)

_, decision = ta.propagate("MSFT", "2024-05-10")

print("决策:", decision)
print("统计:", stats.get_stats())
# 示例输出：
# 决策: 买入
# 统计: {'llm_calls': 28, 'tool_calls': 14, 'tokens_in': 52000, 'tokens_out': 3100}
```

`StatsCallbackHandler` 实现了 LangChain 的 `BaseCallbackHandler` 接口，统计字段：

| 字段 | 含义 |
|------|------|
| `llm_calls` | LLM 调用次数 |
| `tool_calls` | 工具调用次数 |
| `tokens_in` | 累计输入 token |
| `tokens_out` | 累计输出 token |

想要更细的日志（比如每次请求的完整 prompt），自己实现一个 `BaseCallbackHandler` 子类传进来即可。回调是线程安全的，`StatsCallbackHandler` 内部用锁保护计数器。

---

## 场景 4：批量分析多只股票

`propagate` 一次只处理一个 ticker，批量分析就是在外层套个循环。关键点：**复用同一个 `TradingAgentsGraph` 实例**，不要每次循环都新建。因为实例里挂着 `memory_log`，历史决策会通过 `get_past_context` 注入到下一轮分析，让框架积累对同一只股票的记忆。

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(config=config)

tickers = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"]
trade_date = "2024-05-10"

results = {}
for ticker in tickers:
    _, decision = ta.propagate(ticker, trade_date)
    results[ticker] = decision
    print(f"{ticker}: {decision}")
```

批量运行要注意两点：

1. **同一 ticker 多次调用会触发历史反思**。`propagate` 开头会先调 `_resolve_pending_entries`，检查这只股票之前有没有还没结算的决策（pending），如果有且行情数据已经够，就先反思那次决策对不对，写回记忆，再开始本轮分析。
2. **耗时会线性增长**。单次分析涉及多次 LLM 调用和数据抓取，云端模型下一次通常在几十秒到几分钟，本地模型更慢。50 只股票串行跑可能要几小时，必要时考虑并行或缩短研究深度。

---

## 场景 5：把报告写到磁盘

`propagate` 只返回内存里的状态，不自动写文件。想要和 CLI 一样的磁盘报告，调 `save_reports`：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(config=config)

final_state, decision = ta.propagate("NVDA", "2024-05-10")

# 写报告树。不传 save_path 会落到 config["results_dir"] 下的带时间戳子目录
report_path = ta.save_reports(final_state, "NVDA")
print("报告目录:", report_path)
```

`save_reports(final_state, ticker, save_path=None)` 的行为：

- `save_path=None`：在 `results_dir/reports/{ticker}_{时间戳}/` 下生成报告树，和 CLI 产物一致
- `save_path=Path(...)`：写到指定目录
- 返回值是写好的目录路径（`Path` 对象）

注意 `propagate` 内部已经把完整状态以 JSON 形式记到 `results_dir/{ticker}/TradingAgentsStrategy_logs/full_states_log_{日期}.json`，那是给框架自己回看用的原始日志；`save_reports` 产出的是给人读的 Markdown 报告，两者不冲突。

---

## 一次调用内部发生了什么

理解内部流程有助于调试。`propagate("NVDA", "2024-05-10")` 的执行顺序：

```
propagate
  ├─ _resolve_pending_entries("NVDA")
  │    反思这只 ticker 历史 pending 决策，写回记忆
  ├─ [若 checkpoint_enabled] 重编译图，挂上 SqliteSaver
  └─ _run_graph("NVDA", "2024-05-10")
       ├─ memory_log.get_past_context("NVDA")   注入历史上下文
       ├─ resolve_instrument_context("NVDA")    解析标的真实身份
       ├─ propagator.create_initial_state(...)  构造初始状态
       └─ graph.stream() 或 graph.invoke()      执行图
            └─ 返回 (final_state, decision_signal)
```

两个细节值得记住：

- **`resolve_instrument_context`** 用 yfinance 做一次确定性的身份解析（NVDA 到底是哪家公司、哪个交易所），把结果塞进所有 agent 共享的上下文，避免模型从价格曲线"猜"公司。
- **`get_past_context`** 注入的是同一只股票的历史决策记忆。这就是为什么批量分析时复用实例更划算——记忆是跨调用累积的。

如果开了 `checkpoint_enabled`，崩溃后下次用同样的 `ticker + date` 再调 `propagate`，会从上一个成功节点续跑，而不是从头开始。

---

## 常见问题

**`from tradingagents import TradingAgentsGraph` 报 `ImportError`？**
包根 `__init__.py` 不导出业务符号。必须写完整路径 `from tradingagents.graph.trading_graph import TradingAgentsGraph`。

**`debug=True` 和 `debug=False` 返回的 `final_state` 一样吗？**
一样。debug 路径用流式 chunk 逐节点打印消息，再把 chunk 合并成完整状态，合并结果与非 debug 的 `invoke` 等价。

**`asset_type` 不传会怎样？**
默认 `"stock"`，走股票 Pipeline。分析加密货币要显式传 `asset_type="crypto"`，此时 Fundamentals Analyst 会自动跳过。

**怎么清掉记忆从头来？**
记忆文件默认在 `~/.tradingagents/memory/trading_memory.md`，删掉或清空它即可。配置键 `memory_log_path` 可以改位置。

---

## 下一步

| 推荐内容 | 难度 | 说明 |
|---------|------|------|
| [配置参考](configuration.md) | ⭐⭐ | 搞懂所有配置项和优先级 |
| [本地模型部署](local-models.md) | ⭐⭐ | 零成本用 Ollama / vLLM 跑起来 |
| [CLI 交互式手册](cli-manual.md) | ⭐⭐ | 对照 CLI 的交互选项理解每个参数 |
| [Graph 编排](../04-graph-and-agents/graph-orchestration.md) | ⭐⭐⭐ | 理解 `propagate` 背后的图是怎么搭的 |
