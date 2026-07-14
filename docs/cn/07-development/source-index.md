# 源码索引

> 难度 ⭐⭐（参考） · 面向想快速定位源码的贡献者 · 查阅用，不需要顺序阅读

## 这份索引怎么用

这是一张"我想理解 X → 该看哪个文件 → 入口函数在哪一行"的查找表，不是教程。所有路径都相对于项目根目录（`TradingAgents/`）。每个条目列出关键文件、核心类/函数、源码行号。

如果你要找的是"怎么改"，看 [扩展指南](./extension-guide.md)；如果要找的是"为什么这么设计"，看 [设计哲学](../03-architecture/design-philosophy.md)。

---

## Graph 编排层

`tradingagents/graph/` 下。一次分析从 CLI 进入后，全部由这一层编排。

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| 整个流水线的入口类 | `tradingagents/graph/trading_graph.py` | `TradingAgentsGraph`（L65）、`propagate`（L362）、`_run_graph`（L419）、`_create_tool_nodes`（L188） |
| 图怎么建出来 | `tradingagents/graph/setup.py` | `GraphSetup`（L45）、`setup_graph`（L61） |
| 条件路由（Analyst 收尾、辩论、风险） | `tradingagents/graph/conditional_logic.py` | `ConditionalLogic`（L6） |
| 状态初始化、图参数 | `tradingagents/graph/propagation.py` | `Propagator`（L11）、`create_initial_state`（L18） |
| Analyst 节点的标准结构 | `tradingagents/graph/analyst_execution.py` | `AnalystNodeSpec`（L6）、`ANALYST_NODE_SPECS`（L20）、`build_analyst_execution_plan`（L56）、`AnalystWallTimeTracker`（L76） |
| 断点续跑（checkpoint） | `tradingagents/graph/checkpointer.py` | `get_checkpointer` / `checkpoint_step` / `clear_checkpoint` / `thread_id` |
| 反思（已实现决策的复盘） | `tradingagents/graph/reflection.py` | `Reflector`（L6） |
| 最终信号解析（从决策文本提取 BUY/HOLD/SELL） | `tradingagents/graph/signal_processing.py` | `SignalProcessor`（L20） |

`AnalystNodeSpec` 是 frozen dataclass，五个字段（`key / agent_node / clear_node / tool_node / report_key`）描述了图里每个 Analyst 的标准形态。新增 Analyst 必须在这里加一行，详见 [扩展指南](./extension-guide.md#扩展一新增-analyst分析师)。

---

## Agent 系统

`tradingagents/agents/` 下。12 个 LLM 角色按职责分布在五个子目录。

### 分析师（`agents/analysts/`）

每个文件结构相同：`create_xxx_analyst(llm)` 返回一个 `xxx_analyst_node(state)` 函数，函数返回 `{messages: [...], xxx_report: ...}`。

| 我想理解 | 看哪个文件 | 入口函数 |
|---------|-----------|---------|
| 技术面分析 | `agents/analysts/market_analyst.py` | `create_market_analyst` |
| 情绪面（新闻 + StockTwits + Reddit） | `agents/analysts/sentiment_analyst.py` | `create_sentiment_analyst` |
| 新闻面与宏观 | `agents/analysts/news_analyst.py` | `create_news_analyst` |
| 基本面 | `agents/analysts/fundamentals_analyst.py` | `create_fundamentals_analyst` |
| 社交媒体（旧文件，参考用） | `agents/analysts/social_media_analyst.py` | `create_social_media_analyst` |

### 研究员与风险辩手

| 我想理解 | 看哪个文件 |
|---------|-----------|
| 多头研究员 | `agents/researchers/bull_researcher.py`（`create_bull_researcher`） |
| 空头研究员 | `agents/researchers/bear_researcher.py`（`create_bear_researcher`） |
| 激进风险辩手 | `agents/risk_mgmt/aggressive_debator.py`（`create_aggressive_debator`） |
| 保守风险辩手 | `agents/risk_mgmt/conservative_debator.py`（`create_conservative_debator`） |
| 中性风险辩手 | `agents/risk_mgmt/neutral_debator.py`（`create_neutral_debator`） |

### 管理层与 Trader

| 我想理解 | 看哪个文件 | 核心 class / 函数 |
|---------|-----------|----------------|
| 研究经理（5 级评级裁判） | `agents/managers/research_manager.py` | `create_research_manager` |
| 组合经理（最终裁决） | `agents/managers/portfolio_manager.py` | `create_portfolio_manager` |
| 交易员（Buy/Hold/Sell 提案） | `agents/trader/trader.py` | `create_trader` |

### 工具与状态

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| 所有数据工具的统一 import 入口 | `agents/utils/agent_utils.py` | `__all__`（L29）、`get_language_instruction`（L52）、`resolve_instrument_identity`（L78）、`build_instrument_context`（L122）、`get_instrument_context_from_state`（L172）、`create_msg_delete`（L190） |
| AgentState 字段定义 | `agents/utils/agent_states.py` | `AgentState`（L47）、`InvestDebateState`（L8）、`RiskDebateState`（L22） |
| 工具按数据领域分组 | `agents/utils/core_stock_tools.py`、`fundamental_data_tools.py`、`macro_data_tools.py`、`market_data_validation_tools.py`、`news_data_tools.py`、`prediction_markets_tools.py`、`technical_indicators_tools.py` | 各自 `@tool` 装饰的函数 |
| 记忆日志 | `agents/utils/memory.py` | `TradingMemoryLog`（L9） |
| 评分逻辑（5 级评级） | `agents/utils/rating.py` | — |

---

## 结构化输出

LLM 结构化输出（让模型按 schema 填字段）的入口。

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| Pydantic schema 定义 | `agents/schemas.py` | `PortfolioRating`（L44）、`ResearchPlan`（L73）、`TraderProposal`（L121）、`PortfolioDecision`（L188） |
| 结构化 / 自由文本回退 | `agents/utils/structured.py` | `invoke_structured_or_freetext`（L49） |

`invoke_structured_or_freetext` 是"先用 structured output 试，模型不支持就回退到自由文本"的统一入口。配合 `capabilities.py` 的能力表，决定每个模型用哪种方法。

---

## 数据流层

`tradingagents/dataflows/` 下。所有外部数据通过 `route_to_vendor` 统一调度。

### 核心调度与错误体系

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| vendor 路由（中央调度） | `dataflows/interface.py` | `TOOLS_CATEGORIES`（L36）、`OPTIONAL_CATEGORIES`（L92）、`VENDOR_METHODS`（L95）、`get_vendor`（L153）、`route_to_vendor`（L168） |
| 错误体系 | `dataflows/errors.py` | `VendorError`、`NoMarketDataError`、`VendorRateLimitError`、`VendorNotConfiguredError` |
| 全局配置 | `dataflows/config.py` | `get_config` / `set_config` |
| ticker 归一化 | `dataflows/symbol_utils.py` | `normalize_symbol`（L104） |
| 路径安全组件 | `dataflows/utils.py` | `safe_ticker_component`（L13） |
| 市场数据校验（防前视偏差） | `dataflows/market_data_validator.py` | — |

### 各家 Vendor 实现

| Vendor | 文件 |
|--------|------|
| yfinance（行情、基本面、新闻） | `dataflows/y_finance.py`、`dataflows/yfinance_news.py` |
| Alpha Vantage（多模块） | `dataflows/alpha_vantage.py`、`alpha_vantage_common.py`、`alpha_vantage_stock.py`、`alpha_vantage_indicator.py`、`alpha_vantage_fundamentals.py`、`alpha_vantage_news.py` |
| FRED（宏观） | `dataflows/fred.py` |
| Polymarket（预测市场） | `dataflows/polymarket.py` |
| Reddit | `dataflows/reddit.py` |
| StockTwits | `dataflows/stocktwits.py` |
| 技术指标计算 | `dataflows/stockstats_utils.py` |

新增 vendor 的完整流程见 [扩展指南](./extension-guide.md#扩展二新增-data-vendor数据供应商)。

---

## LLM 客户端层

`tradingagents/llm_clients/` 下。20 个 provider 的统一入口是 `create_llm_client` 工厂。

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| 工厂入口（按 provider 路由） | `llm_clients/factory.py` | `create_llm_client`（L5） |
| 抽象基类 + 输出归一化 | `llm_clients/base_client.py` | `BaseLLMClient`（L25）、`normalize_content`（L6） |
| OpenAI-compatible provider 注册表 | `llm_clients/openai_client.py` | `OPENAI_COMPATIBLE_PROVIDERS`（L212）、`ProviderSpec`（L183）、`OpenAIClient`（L257） |
| provider → API key env 映射 | `llm_clients/api_key_env.py` | `PROVIDER_API_KEY_ENV`（L14）、`get_api_key_env`（L47） |
| 模型能力表（quirk 处理） | `llm_clients/capabilities.py` | `ModelCapabilities`（L29）、`get_capabilities`（L119）、`_BY_ID`（L94）、`_BY_PATTERN`（L112） |
| CLI 模型选项列表 | `llm_clients/model_catalog.py` | `_CUSTOM_ONLY`、`_GLM_MODELS`、`_QWEN_MODELS` 等 |
| 模型名校验 | `llm_clients/validators.py` | `validate_model` |

### 原生 Provider 客户端

| Provider | 文件 | 核心 class |
|----------|------|-----------|
| Anthropic | `llm_clients/anthropic_client.py` | `AnthropicClient`、`NormalizedChatAnthropic` |
| Google Gemini | `llm_clients/google_client.py` | `GoogleClient`、`NormalizedChatGoogleGenerativeAI` |
| AWS Bedrock | `llm_clients/bedrock_client.py` | `BedrockClient` |
| Azure OpenAI | `llm_clients/azure_client.py` | `AzureOpenAIClient` |

新增 Provider 的两种情况（OpenAI-compatible / 原生）见 [扩展指南](./extension-guide.md#扩展三新增-llm-provider)。

---

## 配置

| 我想理解 | 看哪个文件 | 关键位置 |
|---------|-----------|---------|
| 默认配置 + env 覆盖映射 | `tradingagents/default_config.py` | `_ENV_OVERRIDES`（L10）、`DEFAULT_CONFIG`（L71）、`_coerce`（L35）、`_apply_env_overrides`（L58） |

`_ENV_OVERRIDES` 是"环境变量 → 配置键"的唯一映射表。`_coerce` 根据现有默认值的类型把字符串 env 转成正确的 Python 类型——加新的 env override 只需要在表里加一行，不用改入口脚本。

---

## 记忆与反思

| 我想理解 | 看哪个文件 | 核心 class（行号） |
|---------|-----------|----------------|
| 交易记忆日志（同 ticker 决策 + 跨 ticker 教训） | `agents/utils/memory.py` | `TradingMemoryLog`（L9） |
| 反思逻辑（已实现决策的复盘） | `graph/reflection.py` | `Reflector`（L6） |

记忆系统是横向贯穿机制，不归属任何一层，但在 PM 的 prompt 注入和延迟反思中起作用。设计动机见 [设计哲学](../03-architecture/design-philosophy.md)。

---

## 报告

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| 报告树写盘（CLI 和编程式 API 共用） | `tradingagents/reporting.py` | `write_report_tree`（L13） |

`write_report_tree` 是 CLI 和 `TradingAgentsGraph.save_reports` 的共用入口，保证两种调用方式写出同一份盘上报告（#1037 的回归测试就校验这一点）。

---

## CLI

`cli/` 下。CLI 是用户交互入口，但只编排，不含业务逻辑。

| 我想理解 | 看哪个文件 | 核心 class / 函数（行号） |
|---------|-----------|------------------------|
| CLI 主入口（Typer app） | `cli/main.py` | `app`（L55）、`MessageBuffer`（L63）、`ANALYST_MAPPING`（L73）、`REPORT_SECTIONS`（L83） |
| CLI 工具函数（key 检查、provider 选择、URL 解析） | `cli/utils.py` | `_llm_provider_table`（L338）、`ensure_api_key`（L603）、`select_analysts`（L135）、`resolve_backend_url`（L378）、`prompt_openai_compatible_url`（L391） |
| 枚举（AnalystType / AssetType） | `cli/models.py` | `AnalystType`（L4）、`AssetType`（L13） |
| LLM 调用统计回调 | `cli/stats_handler.py` | `StatsCallbackHandler` |
| 启动公告 | `cli/announcements.py` | — |
| CLI 配置 | `cli/config.py` | — |

---

## 测试

| 我想理解 | 看哪个文件 | 关键位置 |
|---------|-----------|---------|
| 共享 fixture（防 CI 无 key 卡住） | `tests/conftest.py` | `_dummy_api_keys`（L32）、`_isolate_config`（L40）、`mock_llm_client`（L59）、`pytest_configure`（L9） |

测试套件的整体设计、按主题分组的 71 个测试文件清单、运行方式见 [测试体系](./testing.md)。

---

## 快速定位：常见问题

| 问题 | 直接答案 |
|------|--------|
| 一次 `propagate()` 经历了什么 | `trading_graph.py:_run_graph`（L419） |
| 为什么只调 2 个 LLM 却有 12+ 个角色 | `trading_graph.py:101-115`（`deep_client` / `quick_client`），传给 `GraphSetup`（L127） |
| Analyst 何时算"完成"、写最终 report | `agents/analysts/market_analyst.py:87`（`if len(result.tool_calls) == 0`） |
| vendor 失败后怎么决定降级还是上抛 | `dataflows/interface.py:route_to_vendor`（L168），核心逻辑在 L196-262 |
| 缺 key 时哪个错误会被抛 | `dataflows/errors.py:VendorNotConfiguredError`，由 `interface.py:206` 捕获 |
| 模型拒绝 `tool_choice` 怎么办 | `capabilities.py:_BY_ID` + `openai_client.py:with_structured_output`（L38） |
| env 变量怎么映射到配置 | `default_config.py:_ENV_OVERRIDES`（L10） |
| ticker 归一化（如 XAUUSD → GC=F）在哪 | `dataflows/symbol_utils.py:normalize_symbol`（L104） |
| 状态里有哪些字段 | `agents/utils/agent_states.py:AgentState`（L47） |
| 检查点续跑怎么失效 | `trading_graph.py:_run_signature`（L348），签名变了就重跑 |
| 报告写到哪里 | `trading_graph.py:_log_state`（L484）+ `reporting.py:write_report_tree`（L13） |

---

## 下一步

- 想改代码：[扩展指南](./extension-guide.md)。
- 想跑测试：[测试体系](./testing.md)。
- 想理解整体设计：[系统架构总览](../03-architecture/overview.md)。
- 想理解设计动机：[设计哲学](../03-architecture/design-philosophy.md)。
