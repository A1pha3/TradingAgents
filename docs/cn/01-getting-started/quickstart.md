# 快速开始 ⭐

> **目标读者**：已完成安装，想尽快跑出第一份报告
> **预计时间**：15 分钟
> **前置要求**：已完成 [安装指南](installation.md)，至少配置了一个 LLM API Key
> **完成后你能**：独立运行一次完整的交易分析，读懂输出报告

---

## 你将做什么

我们用 CLI 分析 **NVDA（英伟达）** 在 **2024-05-10** 的交易前景。整个过程会经过 13 个 AI 角色协作，最终给出一个 5 级评级（Buy / Overweight / Hold / Underweight / Sell）和完整报告。

选 NVDA 是因为：它是高流动性美股，yfinance 数据完整，分析过程能充分展示框架能力。

---

## 准备工作

确认环境就绪：

```bash
# 1. 确认在项目目录
cd /path/to/TradingAgents

# 2. 确认 .env 存在且配了 Key
cat .env | grep API_KEY
# 预期看到至少一行 OPENAI_API_KEY=sk-...

# 3. 确认命令行工具可用
tradingagents --help
```

如果任何一步失败，回到 [安装指南](installation.md)。

---

## 启动分析

```bash
tradingagents analyze
```

你会看到一个 ASCII 欢迎界面，然后进入 8 步交互问卷。下面逐项说明怎么填——第一次跟着选就行。

### 步骤 1：输入 Ticker

```
Step 1: Ticker Symbol
Enter the ticker, with exchange suffix when needed (e.g. SPY, 0700.HK, BTC-USD)
> NVDA
```

输入 `NVDA`。

Ticker 格式说明：
- 美股直接写代码：`AAPL`、`NVDA`、`SPY`
- 美股以外的需要交易所后缀：`0700.HK`（港股腾讯）、`7203.T`（丰田）、`600519.SS`（A股茅台）
- 加密货币：`BTC-USD`、`ETH-USD`
- 外汇/大宗商品：`EURUSD=X`、`GC=F`（黄金）——框架会自动归一化你输入的券商风格符号

### 步骤 2：分析日期

```
Step 2: Analysis Date
> 2024-05-10
```

输入一个**过去**的日期（不能用未来日期）。选 2024-05-10 的好处是：距今够久，yfinance 有完整的历史数据；同时框架的记忆系统能在 5 天后回测这个决策的实际收益。

### 步骤 3：输出语言

```
Step 3: Output Language
> 中文
```

选 `中文`。这会让最终报告和分析师报告用中文输出。注意：**Agent 之间的内部辩论始终保持英文**，这是为了保证 LLM 推理质量。

### 步骤 4：选择分析师

```
Step 4: Select Analysts (space to toggle, enter to confirm)
[x] Market Analyst
[x] Sentiment Analyst
[x] News Analyst
[x] Fundamentals Analyst
```

第一次全选（默认就是全选）。空格切换选中，回车确认。

如果你分析的是加密货币（如 `BTC-USD`），Fundamentals Analyst 会自动剔除——加密货币没有财报。

### 步骤 5：研究深度

```
Step 5: Research Depth
> Shallow (1 round)
  Medium (3 rounds)
  Deep   (5 rounds)
```

选 `Shallow`。这控制辩论轮数：`max_debate_rounds=1` 意味着多空双方各发言 1 次。第一次跑选 Shallow，省时间省 Token；熟悉后想看更充分辩论再选 Medium 或 Deep。

### 步骤 6：LLM 供应商

```
Step 6: LLM Provider
> OpenAI
```

选你配了 Key 的供应商。第一次建议 OpenAI（如果你配的是 `OPENAI_API_KEY`）。

完整列表有 20 个供应商（OpenAI / Anthropic / Google / xAI / DeepSeek / Qwen 双区 / GLM 双区 / MiniMax 双区 / OpenRouter / Mistral / Kimi / Groq / NVIDIA / Azure / Bedrock / Ollama / OpenAI-compatible）。

### 步骤 7：选择模型

```
Step 7: Deep Thinking Model (for judges)
> gpt-5.5

Step 7b: Quick Thinking Model (for analysts and researchers)
> gpt-5.4-mini
```

Deep 模型给两个裁判（Research Manager、Portfolio Manager）用，负责复杂裁决；Quick 模型给分析师和辩手用，省钱。第一次用默认值。

### 步骤 8：思考配置

```
Step 8: Reasoning Effort
> medium
```

控制推理模型的思考深度（low / medium / high）。影响延迟和成本。第一次用默认值。

---

## 运行过程

选完所有选项后，分析开始。你会看到一个实时更新的面板，显示当前哪个 Agent 在工作：

```
┌─────────────────────────────────────────────────────┐
│ TradingAgents — Analyzing NVDA @ 2024-05-10         │
├─────────────────────────────────────────────────────┤
│ Analyst Team                                        │
│   ✓ Market Analyst        completed (12.3s)         │
│   → Sentiment Analyst     in progress...            │
│     News Analyst          pending                   │
│     Fundamentals Analyst  pending                   │
│                                                     │
│ Research Team                                       │
│     Bull Researcher      pending                    │
│     ...                                             │
├─────────────────────────────────────────────────────┤
│ Stats: LLM calls 5 | Tool calls 12 | Tokens 8.4k    │
└─────────────────────────────────────────────────────┘
```

这个过程通常需要 **2-5 分钟**（取决于模型速度和辩论轮数）。期间会实时显示每个 Agent 的状态变化和它们调用的工具。

不需要干预，等它跑完。

---

## 读懂结果

运行结束后，你会看到两个东西：终端打印的完整报告，和询问是否保存的提示。

### 终端报告

报告分五部分，对应五个团队：

```
I. Analyst Team（分析师团队）
   - Market Report：技术面分析（均线、MACD、RSI 等指标解读）
   - Sentiment Report：情绪面（StockTwits、Reddit 多空情绪）
   - News Report：新闻与宏观事件
   - Fundamentals Report：基本面（PE、现金流、营收）

II. Research Team（研究团队）
   - Bull Argument：看多方论点
   - Bear Argument：看空方论点
   - Manager Judgment：研究经理的裁决和 5 级评级

III. Trading Team（交易团队）
   - Trader Proposal：具体的 Buy/Hold/Sell + 入场价/止损/仓位建议

IV. Risk Management（风险管理）
   - Aggressive / Conservative / Neutral：三方风险辩论

V. Portfolio Management（组合管理）
   - Final Decision：最终决策，含 5 级评级、投资逻辑、目标价、时间窗口
```

### 保存报告

```
Save the complete report to disk? [Y/n]: Y
```

输入 `Y` 保存。报告会写到默认路径：

```
./reports/NVDA_20260713_193015/
├── complete_report.md          # 合并版完整报告
├── 1_analysts/                 # 四个分析师报告
│   ├── market.md
│   ├── sentiment.md
│   ├── news.md
│   └── fundamentals.md
├── 2_research/                 # 多空辩论
├── 3_trading/                  # 交易提案
├── 4_risk/                     # 风险辩论
└── 5_portfolio/                # 最终决策
```

这个目录结构是 [报告系统](../06-internals/reporting.md) 的统一输出，CLI 和 Python API 共享同一套格式。

### 评级信号

`tradingagents analyze` 命令最后会在终端打印一行：

```
Final Decision: Buy
```

这是从 `final_trade_decision` 文本里提取的 5 级评级信号。5 级体系：

| 评级 | 含义 |
|------|------|
| **Buy** | 强烈看多，建议买入 |
| **Overweight** | 偏多，建议超配 |
| **Hold** | 中性，维持现状 |
| **Underweight** | 偏空，建议低配 |
| **Sell** | 强烈看空，建议卖出 |

---

## 文件位置速查

分析过程中，TradingAgents 会在用户目录下生成几类文件：

| 路径 | 内容 | 说明 |
|------|------|------|
| `./reports/{TICKER}_{时间戳}/`（当前工作目录下） | 完整报告树 | 每次分析一个目录 |
| `~/.tradingagents/logs/{TICKER}/{日期}/` | 运行日志、消息记录 | 调试用 |
| `~/.tradingagents/cache/` | 数据缓存（OHLCV 等） | 加速重复查询 |
| `~/.tradingagents/memory/trading_memory.md` | 记忆日志 | 历史决策和反思，详见 [记忆系统](../06-internals/memory-system.md) |
| `~/.tradingagents/cache/checkpoints/{TICKER}.db` | Checkpoint（如启用） | 断点续跑用 |

这些都是可配置的，详见 [配置参考](../02-user-guide/configuration.md)。

---

## 常见问题

### Q1：运行报错 `OPENAI_API_KEY not set`

你的 `.env` 文件没被加载，或 Key 没填对。检查：

```bash
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY', 'NOT FOUND'))"
```

如果输出 `NOT FOUND`，说明 `.env` 路径或内容有问题。

### Q2：卡在某个 Analyst 很久

可能是 LLM API 限流（429）或网络慢。框架内置了重试和退避机制，通常会自己恢复。如果超过 5 分钟没动静，Ctrl+C 中断后重试。

### Q3：报告里出现 `DATA_UNAVAILABLE` 或 `NO_DATA_AVAILABLE`

这是数据供应商的优雅降级信号，表示某个数据源（如 Alpha Vantage）当时不可用。框架会用其他源兜底，或在报告里如实标注"数据不可用"而非编造数字。详见 [数据供应商路由](../05-data-and-llm/data-vendors.md)。

### Q4：分析加密货币时报错

加密货币（如 `BTC-USD`）会自动剔除 Fundamentals Analyst。如果你手动选了它，框架会忽略。确认你的 Ticker 格式正确：`BTC-USD`（中划线），不是 `BTCUSD`。

### Q5：想用中文但报告还是英文

检查步骤 3 是否真的选了 `中文`。也可以用环境变量固定语言，免去每次选择：

```bash
export TRADINGAGENTS_OUTPUT_LANGUAGE=中文
```

---

## 你刚刚经历了什么

回顾一下这 15 分钟里发生的事：

1. **4 个分析师**分别从技术、情绪、新闻、基本面四个维度调研 NVDA，各自调用工具拉取真实市场数据，产出 4 份报告
2. **多空研究员**基于这 4 份报告辩论——Bull 找看多理由，Bear 找看空理由
3. **研究经理**（用更强的模型）裁决辩论，给出 5 级评级
4. **交易员**把评级转成具体操作建议
5. **3 个风险分析师**从激进、保守、中立三个立场审视这笔交易
6. **组合经理**（用更强的模型）综合所有信息，给出最终决策

这不是一个 LLM 一次性回答，而是 13 个角色经过严格编排的多轮协作。想理解每个环节的内部机制，从这里继续：

---

## 下一步

| 推荐内容 | 难度 | 适合谁 |
|---------|------|-------|
| [CLI 交互式手册](../02-user-guide/cli-manual.md) | ⭐⭐ | 想搞懂每个选项含义的使用者 |
| [系统架构总览](../03-architecture/overview.md) | ⭐⭐⭐ | 想理解整个流程怎么编排的研究者 |
| [Python API](../02-user-guide/python-api.md) | ⭐⭐ | 想编程集成的开发者 |
| [配置参考](../02-user-guide/configuration.md) | ⭐⭐ | 想自定义所有参数的高频使用者 |
