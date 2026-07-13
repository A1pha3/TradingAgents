# CLI 交互式手册 ⭐⭐

> **目标读者**：能跑通基础分析，想搞懂每个交互选项含义的使用者
> **核心问题**：CLI 每一步在问什么？每个选项怎么影响结果？
> **前置知识**：[快速开始](../01-getting-started/quickstart.md) ⭐

---

## CLI 的设计原则

TradingAgents 的 CLI 不是简单的问答程序，它遵循一条贯穿全部交互的原则：**环境变量优先，有则跳过交互**。

这条原则的含义是：如果某个配置项已经通过环境变量（`TRADINGAGENTS_*`）或 `.env` 文件设置，CLI 就不会再问你这一个问题。这让 CLI 既能给新手提供友好的引导，又能让老手通过 `.env` 实现完全自动化运行——同一个 `tradingagents analyze` 命令，两种用法。

```
配置优先级（高 → 低）：
CLI flag (--checkpoint) > TRADINGAGENTS_* 环境变量 > 交互式选择 > DEFAULT_CONFIG 字面量
```

理解了这条原则，下面的 8 步问卷就很好读了：每一步都标注了"什么情况下会跳过"。

---

## 启动命令

```bash
tradingagents analyze
```

`analyze` 是主子命令（`cli/main.py:1270`），两个可选 flag：

| Flag | 作用 | 默认 |
|------|------|------|
| `--checkpoint` / `--no-checkpoint` | 强制启用/禁用断点续跑 | None（尊重 `TRADINGAGENTS_CHECKPOINT_ENABLED`） |
| `--clear-checkpoints` | 运行前清空所有 checkpoint | False |

```bash
# 强制启用断点续跑
tradingagents analyze --checkpoint

# 清空旧 checkpoint 后重新开始
tradingagents analyze --clear-checkpoints
```

断点续跑的机制详见 [断点续跑](../06-internals/checkpointing.md)。

---

## 8 步交互问卷详解

### 步骤 1：Ticker 符号

```
Step 1: Ticker Symbol
Enter the ticker, with exchange suffix when needed (e.g. SPY, 0700.HK, BTC-USD)
> NVDA
```

**跳过条件**：无（必填）。

**输入规则**：

- 允许字符：字母、数字、`.`、`-`、`_`、`^`、`=`（`cli/utils.py:26-34` 的 `is_valid_ticker_input`）
- 最大长度：32
- 空输入默认 `SPY`

**为什么允许这些字符**：

| 字符 | 用途 | 示例 |
|------|------|------|
| `.` | 交易所后缀分隔 | `0700.HK`、`7203.T` |
| `-` | 加密货币对 | `BTC-USD` |
| `^` | Yahoo 指数前缀 | `^GSPC` |
| `=` | 外汇后缀 | `EURUSD=X` |
| `_` | 部分特殊符号 | `_XXX` |

**你不需要记住这些规则**。输入后框架会自动做两件事：

1. **符号归一化**：把你输入的券商风格符号转成数据源认识的格式。比如你输入 `XAUUSD`（黄金），框架自动转成 `GC=F`（Yahoo 黄金期货代码）。详见 [符号归一化](../05-data-and-llm/symbol-normalization.md)。
2. **资产类型检测**：判断是 stock 还是 crypto，影响后续分析师选择。

### 步骤 2：分析日期

```
Step 2: Analysis Date (YYYY-MM-DD)
> 2024-05-10
```

**跳过条件**：无（必填）。

**验证规则**（`cli/main.py:731-747`）：

- 必须是 `YYYY-MM-DD` 格式（`strptime` 校验）
- 不能是未来日期

**为什么要用过去的日期**：TradingAgents 的记忆系统会在 5 天后用实际价格回测你的决策（算 raw 收益和相对 benchmark 的 alpha）。选近期日期会导致回测时价格数据不足——这时决策会以 `pending` 状态存在记忆日志里，等数据够了再反思。

### 步骤 3：输出语言

```
Step 3: Output Language
> 中文
```

**跳过条件**：设置了 `TRADINGAGENTS_OUTPUT_LANGUAGE`。

支持 11 种语言 + Custom（`cli/utils.py:653-688`）：English、中文、Español、Français、Deutsch、日本語、한국어、Русский、Português、Italiano、Nederlands。

**重要细节**：输出语言只影响**分析师报告和最终决策的呈现语言**，不影响 Agent 之间的内部辩论。辩论保持英文，因为这是 LLM 推理质量最稳定的语言。这个设计决策的动机详见 [设计哲学](../03-architecture/design-philosophy.md)。

详见 [多语言输出](output-language.md)。

### 步骤 4：选择分析师

```
Step 4: Select Analysts (space to toggle, enter to confirm)
[x] Market Analyst
[x] Sentiment Analyst
[x] News Analyst
[x] Fundamentals Analyst
```

**跳过条件**：无。

四个分析师的职责：

| 分析师 | 数据维度 | 工具 |
|--------|---------|------|
| **Market Analyst** | 技术面（均线、MACD、RSI 等） | `get_stock_data`、`get_indicators`、`get_verified_market_snapshot` |
| **Sentiment Analyst** | 社交情绪（Reddit、StockTwits） | 预取数据，不调工具 |
| **News Analyst** | 新闻、宏观指标、预测市场 | `get_news`、`get_global_news`、`get_macro_indicators`、`get_prediction_markets` |
| **Fundamentals Analyst** | 基本面（财报、PE、ROE） | `get_fundamentals`、`get_balance_sheet`、`get_cashflow`、`get_income_statement` |

**自动行为**：如果你分析的是加密货币，Fundamentals Analyst 会被自动剔除（`cli/utils.py:90-99` 的 `filter_analysts_for_asset_type`）——加密货币没有传统财报。

### 步骤 5：研究深度

```
Step 5: Research Depth
> Shallow (1 round)
  Medium (3 rounds)
  Deep   (5 rounds)
```

**跳过条件**：同时设置了 `TRADINGAGENTS_MAX_DEBATE_ROUNDS` **和** `TRADINGAGENTS_MAX_RISK_ROUNDS`。

三个选项对应辩论轮数（`cli/utils.py:167-196`）：

| 选项 | `max_debate_rounds` | `max_risk_discuss_rounds` | 投资辩论发言数 | 风险辩论发言数 |
|------|---------------------|--------------------------|--------------|--------------|
| Shallow | 1 | 1 | 2（多空各 1 次） | 3（三方各 1 次） |
| Medium | 3 | 3 | 6 | 9 |
| Deep | 5 | 5 | 10 | 15 |

辩论轮数越多，讨论越充分，但 Token 消耗和延迟也线性增长。第一次用 Shallow，熟悉后根据需要调高。

辩论轮数的数学和控制逻辑详见 [辩论机制](../04-graph-and-agents/debate-mechanism.md)。

### 步骤 6：LLM 供应商

```
Step 6: LLM Provider
> OpenAI
```

**跳过条件**：设置了 `TRADINGAGENTS_LLM_PROVIDER`。

支持 19 个供应商（`cli/utils.py:338-366`）：

| 类别 | 供应商 |
|------|--------|
| 国际大厂 | OpenAI、Anthropic、Google、xAI |
| 国内大厂 | DeepSeek、Qwen（国际/中国）、GLM（国际/中国）、MiniMax（国际/中国） |
| 聚合平台 | OpenRouter、Mistral、Kimi、Groq、NVIDIA |
| 企业云 | Azure OpenAI、Amazon Bedrock |
| 本地部署 | Ollama、OpenAI-compatible（vLLM/LM Studio） |

**区域分流**（`cli/main.py:636-657`）：选 Qwen / MiniMax / GLM 时，第二步会追问"国际账户还是中国大陆账户"——两边的 API 端点和 Key 不互通。选 `openai_compatible` 会单独问 base URL；选 `ollama` 会打印当前 endpoint 确认。

供应商的技术实现详见 [LLM 客户端](../05-data-and-llm/llm-clients.md)。

### 步骤 7：选择模型

```
Step 7: Deep Thinking Model (for judges)
> gpt-5.5

Step 7b: Quick Thinking Model (for analysts and researchers)
> gpt-5.4-mini
```

**跳过条件**：设置了 `TRADINGAGENTS_DEEP_THINK_LLM` 或 `TRADINGAGENTS_QUICK_THINK_LLM`。

TradingAgents 用**两个模型**分工（`trading_graph.py:101-115`）：

| 模型角色 | 给谁用 | 默认（OpenAI） | 选型逻辑 |
|---------|--------|---------------|---------|
| **Deep（深度思考）** | Research Manager、Portfolio Manager（两个裁判） | `gpt-5.5` | 裁决需要强推理，用旗舰 |
| **Quick（快速思考）** | 4 个分析师、2 个研究员、Trader、3 个风险辩手 | `gpt-5.4-mini` | 大量调用，用小模型省钱 |

**省钱的诀窍**：Deep 模型只被调用 2 次（两个裁判），Quick 模型被调用 11+ 次。所以 Deep 用贵的旗舰模型成本可控，Quick 必须用便宜的。

### 步骤 8：思考配置（部分供应商）

```
Step 8: Reasoning Effort (for thinking models)
> medium
```

**跳过条件**：设置了对应的 `TRADINGAGENTS_*_EFFORT` 或 `_LEVEL`。

这一步只在选了支持"思考强度"的供应商时出现，三个供应商各有自己的参数名：

| 供应商 | 参数名 | 可选值 |
|--------|--------|--------|
| OpenAI（gpt-5/o 系列） | `reasoning_effort` | low / medium / high |
| Anthropic（Claude 4.5+） | `effort` | low / medium / high |
| Google（Gemini 3.x） | `thinking_level` | minimal / low / medium / high |

**注意**：并非所有模型都接受这些参数。框架的能力表（`capabilities.py`）会判断模型是否支持，不支持的会自动跳过，不会报错。

---

## 运行后的交互

分析完成后，CLI 会问两个问题：

### 保存报告

```
Save the complete report to disk? [Y/n]:
```

默认 `Y`。报告写到 `~/.tradingagents/logs/reports/{TICKER}_{时间戳}/`，结构详见 [报告系统](../06-internals/reporting.md)。

### 查看完整报告

```
Display the complete report on screen? [Y/n]:
```

默认 `Y`。用 Rich Panel 分五部分打印，避免一次性输出被截断。

---

## 用环境变量跳过交互

如果你不想每次都回答 8 个问题，把配置写进 `.env`：

```env
# 跳过步骤 3、5、6、7、8 的最小配置
TRADINGAGENTS_OUTPUT_LANGUAGE=中文
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=gpt-5.5
TRADINGAGENTS_QUICK_THINK_LLM=gpt-5.4-mini
```

配好后，`tradingagents analyze` 只会问 Ticker 和日期两步，其余全部自动填充。

完整的 `TRADINGAGENTS_*` 变量列表见 [配置参考](configuration.md)。

---

## 实时显示面板解读

运行过程中，你会看到一个 Rich Live 面板（`cli/main.py:252-265` 的 `create_layout`）。理解它的状态标记有助于判断进度：

| 标记 | 含义 |
|------|------|
| `→` | in progress（正在运行） |
| `✓` | completed（已完成） |
| 空白 | pending（等待中） |

面板分三块：

- **Header**：当前分析的 Ticker 和日期
- **Main**：上半部是 Agent 进度，下半部是实时消息流
- **Footer**：统计信息（LLM 调用数、工具调用数、Token 数）

**报告完成度的判断**（`cli/main.py:139-158` 的 `get_completed_reports_count`）：只有当某个报告段"有内容 **且** 对应的 Agent 已完成"才算完成。这防止辩论中间态被误当成最终报告。

---

## CLI 的 API Key 持久化

第一次运行时，如果你选了某个供应商但没配 Key，CLI 会交互式提示输入：

```
OpenAI API Key not found. Enter your key (input hidden):
> sk-...
```

输入后，CLI 会：

1. 用 `python-dotenv.set_key` 把 Key 写入 `.env` 文件（持久化）
2. 写入 `os.environ`（本次运行立即生效）

下次运行就不会再问了。Key 以 password 模式输入，终端不显示。详见 `cli/utils.py:603-650` 的 `ensure_api_key`。

**安全提示**：`.env` 文件应该加入 `.gitignore`（框架默认已配置）。不要把含真实 Key 的 `.env` 提交到版本控制。

---

## 常见用法场景

### 场景 1：分析 A 股

```bash
tradingagents analyze
# Ticker: 600519.SS（贵州茅台，上交所）
# Ticker: 000001.SZ（平安银行，深交所）
```

A 股用 `.SS`（上海）或 `.SZ`（深圳）后缀。框架的 benchmark 自动映射：`.SS → 000001.SS`（上证综指），`.SZ → 399001.SZ`（深证成指）。

### 场景 2：分析加密货币

```bash
tradingagents analyze
# Ticker: BTC-USD
```

Fundamentals Analyst 会自动剔除。情绪数据（Reddit、StockTwits）会用归一化后的 base symbol（BTC）搜索。

### 场景 3：分析外汇 / 大宗

```bash
tradingagents analyze
# Ticker: XAUUSD（黄金，自动归一化为 GC=F）
# Ticker: EURUSD（欧元美元，自动归一化为 EURUSD=X）
```

输入券商常用的符号即可，框架会自动转成 Yahoo Finance 认识的格式。

### 场景 4：本地模型零成本运行

```bash
# .env
TRADINGAGENTS_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1

tradingagents analyze
```

详见 [本地模型部署](local-models.md)。

---

## 下一步

| 推荐内容 | 难度 | 说明 |
|---------|------|------|
| [配置参考](configuration.md) | ⭐⭐ | 搞懂所有配置项和优先级 |
| [Python API](python-api.md) | ⭐⭐ | 编程方式调用 |
| [Graph 编排](../04-graph-and-agents/graph-orchestration.md) | ⭐⭐⭐ | 理解 CLI 背后的图执行 |
