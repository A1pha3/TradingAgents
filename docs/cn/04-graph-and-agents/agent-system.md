---
难度：⭐⭐⭐
类型：进阶分析
预计时间：40 分钟
前置知识：
  - [Graph 编排](graph-orchestration.md) ⭐⭐⭐
  - [状态模型](state-model.md) ⭐⭐⭐
后续推荐：
  - [辩论机制](debate-mechanism.md) ⭐⭐⭐
  - [结构化输出](../06-internals/structured-output.md) ⭐⭐⭐
学习路径：
  - 开发路径：第 3 阶段
  - 进阶路径：第 2 阶段
---

# Agent 团队：13 个角色的职责、Prompt 与工具

## 引言：不是 13 个 LLM，是 13 套不同的契约

读 TradingAgents 的代码容易产生一个错觉："13 个角色不就是 13 个 LLM 实例各跑一次？"。但只要看一下角色目录，差别立刻浮现：分析师调工具、辩手不调工具；裁判输出结构化 JSON、辩手输出纯文本；Sentiment Analyst 干脆不用 tool-calling，改用 prompt 注入。同样是"调一次 LLM"，背后是完全不同的契约模式。

这篇文档把这些差异系统化拆开。先按职责把 13 个角色分成 4 类（分析师 / 研究员 / 管理层 / 风险辩手），讲每类的共性；再用对照表横向对比 prompt 结构、工具使用、输出形态；最后讲三个跨角色的横切关注点：工具注册、标的身份解析、消息清理。读完这一篇，再去读 prompt 模板时，看到的就不再是 13 段散乱的文本，而是 4 套有规律的设计模式。

## 总览：13 个角色的分类与契约

```mermaid
flowchart TD
    subgraph AN["分析师（4 个，quick LLM）"]
        direction TB
        MA["Market Analyst<br/>ReAct + 工具循环"]
        SE["Sentiment Analyst<br/>预取数据 + 结构化输出"]
        NA["News Analyst<br/>ReAct + 工具循环"]
        FA["Fundamentals Analyst<br/>ReAct + 工具循环"]
    end

    subgraph RE["研究员（2 个，quick LLM）"]
        direction LR
        BU["Bull Researcher<br/>纯 prompt，无工具"]
        BE["Bear Researcher<br/>纯 prompt，无工具"]
    end

    subgraph MG["管理层（2 个，deep LLM）"]
        direction LR
        RM["Research Manager<br/>结构化输出 ResearchPlan"]
        PM["Portfolio Manager<br/>结构化输出 PortfolioDecision"]
    end

    subgraph TR["交易员（1 个，quick LLM）"]
        TR_"Trader<br/>结构化输出 TraderProposal"
    end

    subgraph RD["风险辩手（3 个，quick LLM）"]
        direction LR
        AG["Aggressive<br/>纯 prompt，无工具"]
        CO["Conservative<br/>纯 prompt，无工具"]
        NE["Neutral<br/>纯 prompt，无工具"]
    end

    AN --> RE
    RE --> MG
    RM --> TR
    TR --> RD
    RD --> PM
```

四种契约的横向对比：

| 维度 | 分析师 | 研究员/风险辩手 | 管理层 | 交易员 |
|------|--------|----------------|--------|--------|
| LLM 档位 | quick | quick | deep | quick |
| 用工具 | 是（ReAct 循环） | 否 | 否 | 否 |
| 结构化输出 | 仅 Sentiment | 否 | 是（5 级评级） | 是（3 级方向） |
| Prompt 来源 | 通用模板 + role-specific system | 纯 f-string | 纯 f-string | role list |
| 写 messages | 是（带 tool_calls） | 否 | 否 | 是（最终提案） |

这张表回答了几个高频疑问：

- 为什么研究员不用工具？因为它们的输入是分析师已经产出的 4 份报告 + 对方论点，所有上下文都在 prompt 里，不需要再调外部数据。
- 为什么管理层用 deep LLM？因为它们要给出最终评级，判断密度高。
- 为什么 Trader 用结构化输出但只是 3 级？因为它把 5 级的 `ResearchPlan` 翻译成 3 级的具体动作（Buy/Hold/Sell），更细的 sizing 留给 Portfolio Manager。

## 分析师：4 个数据采集者

### Market Analyst：典型的 ReAct 工具循环

`market_analyst.py` 是 4 个分析师里 prompt 最重的一个，因为它的 system message 内嵌了一份指标百科。从 `market_analyst.py:25-53` 可以看到，system message 列出了 5 大类共 12 个技术指标（移动平均、MACD、动量、波动率、成交量），每个指标都有用途说明。

这个角色的几个关键约束：

1. **必须先调 `get_stock_data`** 拿 K 线 CSV，因为 `get_indicators` 依赖这份 CSV 来计算技术指标。
2. **写报告前必须调 `get_verified_market_snapshot`** 作为真值源。`market_analyst.py:51` 的原话是：

   > Before writing the final report, call get_verified_market_snapshot for this ticker and the current date, and treat it as the source of truth for any exact OHLCV, price-level, or indicator-value claim. If another tool's output conflicts with the verified snapshot, flag the discrepancy rather than inventing a reconciled number.

   这条约束是为了对抗 LLM 在工具结果之间编造"调和数字"的倾向。如果 `get_stock_data` 和 `get_verified_market_snapshot` 给出的收盘价不一致，分析师应该报告矛盾，而不是自己捏一个中间值。
3. **报告末尾必须附 Markdown 表格**，便于下游读取。

节点函数的返回值（`market_analyst.py:90-93`）：

```python
return {
    "messages": [result],
    "market_report": report,
}
```

`result` 是 LLM 返回的 AIMessage（可能带 `tool_calls`），驱动 ReAct 循环；`report` 是无 tool_calls 时的最终报告内容。注意只有当 `len(result.tool_calls) == 0` 时 `report` 才会被赋值（`market_analyst.py:87-88`）——这意味着 ReAct 循环中的中间步 report 为空，路由器仍然会把它发回 `tools_market` 执行工具，直到模型不调工具为止。

### Sentiment Analyst：唯一的"不用工具"分析师

`sentiment_analyst.py` 的开头 docstring 解释了这个角色的来历——它就是为了修一个真实踩过的坑而重新设计的：

> Previously named `social_media_analyst`. Renamed and redesigned because the old version had a prompt that demanded social-media analysis but the only tool available was Yahoo Finance news — which led LLMs to fabricate Reddit/X/StockTwits content under prompt pressure (verified live).

旧版 prompt 要求分析师分析社交媒体，但唯一可用的工具是 Yahoo Finance 新闻。模型在"必须有社交媒体数据"的 prompt 压力下，开始编造 Reddit/X/StockTwits 的内容——这是真实观察到的现象（issue #557/#796）。

重设计的方案不是"加更多工具"，而是反过来：**不用 tool-calling，直接在 prompt 里预取好三源数据**。`sentiment_analyst.py:69-71`：

```python
news_block = get_news.func(ticker, start_date, end_date)
stocktwits_block = fetch_stocktwits_messages(ticker, limit=30)
reddit_block = fetch_reddit_posts(ticker)
```

三个数据源在节点函数体里同步预取，作为结构化 block 注入 system message（`sentiment_analyst.py:121-183`）。模型看到的是 `<start_of_news>...<end_of_news>` 这种带标签的真实数据，而不是被诱导去"想象"。

三个源的失败行为各不相同，但有一个共同点：**都不抛异常，都返回字符串**（docstring 原话 "no exceptions surface from here"）。具体差异：

| 数据源 | 失败时的行为 | 代码位置 |
|--------|------------|---------|
| Yahoo 新闻 | 走 `route_to_vendor`，返回 `NO_DATA_AVAILABLE: ...` 哨兵 | `get_news.func(...)`（注意用的是 `.func` 裸函数，绕过 `@tool` 包装以拿到哨兵而非被吞掉） |
| StockTwits | 返回 `<stocktwits unavailable: {异常类型}>` 占位字符串 | `stocktwits.py:54-58`，覆盖 `OSError`/`HTTPException`/`JSONDecodeError` |
| Reddit | 429 时按 `Retry-After` 退避重试一次，仍失败返回空 | `reddit.py`，走 RSS feed（JSON 端点被 WAF 403） |

这样设计保证 LLM 永远能看到"有数据"或"明确不可用"的信号，不会因为某个源暂时挂了导致整个分析师节点崩溃。

输出用结构化模式（`sentiment_analyst.py:58`）：

```python
structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")
```

`SentimentReport` 是一个 6 级 `SentimentBand` 加 0-10 数值分数加置信度的 schema（详见 [状态模型](state-model.md) 的 schema 章节）。这样下游 agent 读 sentiment 报告时，不需要正则解析散文，直接读 `overall_band` 字段。

`invoke_structured_or_freetext`（`sentiment_analyst.py:105-111`）是优雅降级——provider 支持结构化输出就走原生模式（OpenAI 的 json_schema、Gemini 的 response_schema、Anthropic 的 tool-use），不支持就退化为散文生成。这层封装在 [结构化输出](../06-internals/structured-output.md) 详解。

### News Analyst 与 Fundamentals Analyst：两个 ReAct 模板

这两个角色和 Market Analyst 共享同一份 prompt 模板，只是工具列表和 system message 不同。

News Analyst（`news_analyst.py:20-25`）的工具：

```python
tools = [
    get_news,
    get_global_news,
    get_macro_indicators,
    get_prediction_markets,
]
```

它的 system message（`news_analyst.py:27-30`）专门提示模型区分"ticker 新闻"（`get_news`）和"宏观新闻"（`get_global_news`），并强调用 `get_macro_indicators` 从 FRED 拿真实宏观数据（CPI、core_pce、失业率、联邦基金利率、10 年国债、收益率曲线），用 `get_prediction_markets` 拿预测市场的隐含概率（比如 "Fed rate cut"、"recession 2026"）。

Fundamentals Analyst（`fundamentals_analyst.py:18-23`）的工具：

```python
tools = [
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
]
```

注意它没有调用宏观数据的工具——基本面是公司层面的，宏观是 News Analyst 的领地。这种工具分配在 prompt 层就划清了角色边界，避免两个分析师重复跑同一份数据。

### 三个分析师共享的 prompt 模板

`market_analyst.py:58-74`、`news_analyst.py:33-49`、`fundamentals_analyst.py:32-48` 用的是几乎一样的 ChatPromptTemplate。Sentiment Analyst 不在这三人之列——它不用 tool-calling，prompt 模板（`sentiment_analyst.py:82-94`）省掉了工具相关的部分：

```python
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful AI assistant, collaborating with other assistants."
            " Use the provided tools to progress towards answering the question."
            " If you are unable to fully answer, that's OK; another assistant with different tools"
            " will help where you left off. Execute what you can to make progress."
            " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
            " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
            " You have access to the following tools: {tool_names}."
            " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
            "{system_message}",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)
```

这套模板的设计要点：

- **协作语调**："collaborating with other assistants"、"another assistant will help" 让模型理解自己是流水线一环，没答全也没关系。
- **停止信号**：`FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` 是整个系统的停止锚字符串。Trader 渲染结构化输出时（`schemas.py:178`）会保留这个尾部标记，外部代码 grep 它就能拿到最终方向。
- **当前日期**：`{current_date}` 让模型知道"现在"是什么时候，避免拿未来数据或过期数据。所有工具调用涉及日期范围时都以此为基准。
- **标的身份**：`{instrument_context}` 是预解析的 ticker 身份描述，避免模型把 `AAPL` 误读成别的公司（详见横切关注点章节）。
- **角色专属**：`{system_message}` 是每个分析师自己的指令（指标百科、数据源说明等）。
- **消息占位符**：`MessagesPlaceholder(variable_name="messages")` 接收状态里的对话历史——配合 [Graph 编排](graph-orchestration.md) 讲的消息清理机制，每个分析师起手看到的 messages 都很短。

`prompt.partial(...)` 把模板变量提前绑定，让 chain 构造时只接 `messages` 一个变量。最终 `chain = prompt | llm.bind_tools(tools)` 是标准的 LCEL（LangChain Expression Language）管道。

## 研究员：Bull vs Bear 的纯 prompt 设计

Bull Researcher（`bull_researcher.py`）和 Bear Researcher（`bear_researcher.py`）是镜像对称的两个角色。它们都不用工具、不绑结构化输出，靠纯 f-string prompt。

`bull_researcher.py:27-45` 的 prompt 结构：

```python
prompt = f"""You are a Bull Analyst advocating for investing in the {target_label}. ...

Resources available:
{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
...
""" + get_language_instruction()
```

5 类输入：标的身份、4 份分析师报告、辩论历史、对方最新论点。这些信息让 Bull 能直接引用 Bear 的具体观点来反驳——这是辩论质量的基础。

调用方式是裸 `llm.invoke(prompt)`，返回纯文本。注意发言会加前缀：

```python
argument = f"Bull Analyst: {response.content}"
```

这个前缀是辩论路由的判断依据。`should_continue_debate` 通过 `current_response.startswith("Bull")` 判断下一个发言者，加前缀让路由能从发言内容里反推发言者。

状态更新的关键代码（`bull_researcher.py:51-57`）：

```python
new_investment_debate_state = {
    "history": history + "\n" + argument,
    "bull_history": bull_history + "\n" + argument,
    "bear_history": investment_debate_state.get("bear_history", ""),
    "current_response": argument,
    "count": investment_debate_state["count"] + 1,
}
```

五个字段更新中，三个值得注意：

- `count` 自增 1，驱动辩论终止条件。
- `current_response` 设为当前发言，驱动路由交替。
- `bear_history` 从原 state 原样拷贝，**没有**追加。这一点是 LangGraph 的 reducer 语义要求的——`investment_debate_state` 是嵌套 TypedDict 无显式 reducer，整个子字典会被整体覆盖。如果 Bull 只返回 `bull_history` 而不拷贝 `bear_history`，Bear 之前累积的发言就丢了。详见 [状态模型](state-model.md) 的 reducer 章节。

Bear Researcher 的代码是 Bull 的镜像，只是 prompt 角色颠倒、追加 `bear_history` 而非 `bull_history`。

## 管理层：两个用结构化输出的 deep LLM 裁判

### Research Manager：5 级投资评级

`research_manager.py:17` 绑定 `ResearchPlan` 结构化输出：

```python
structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")
```

`ResearchPlan` schema（`schemas.py:73-102`）有三个字段：

- `recommendation`：5 级 `PortfolioRating`（Buy / Overweight / Hold / Underweight / Sell）
- `rationale`：对话式总结，说明辩论哪一方胜出
- `strategic_actions`：给交易员的具体指令，含仓位 sizing

prompt（`research_manager.py:25-43`）的关键部分是评级 scale 的明确定义：

```
- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position
- **Overweight**: Constructive view; recommend gradually increasing exposure
- **Hold**: Balanced view; recommend maintaining the current position
- **Underweight**: Cautious view; recommend trimming exposure
- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position
```

把 5 级的具体语义写进 prompt，是为了让模型不会把 Overweight 和 Buy 混淆——schema 字段 description 会成为模型的输出指令，但 scale 含义是 prompt 才能传达的语义层信息。

`invoke_structured_or_freetext`（`research_manager.py:45-51`）调用并降级渲染：

```python
investment_plan = invoke_structured_or_freetext(
    structured_llm,
    llm,
    prompt,
    render_research_plan,
    "Research Manager",
)
```

返回的 `investment_plan` 是渲染好的 markdown 字符串（`render_research_plan`，`schemas.py:105-113`），同时写入两个状态字段（`research_manager.py:62-65`）：`investment_debate_state.judge_decision` 和顶层 `investment_plan`。前者是辩论历史的一部分，后者是 Trader 的输入。

### Portfolio Manager：最终决策 + 记忆系统注入点

`portfolio_manager.py` 是整个流水线的终点，也是记忆系统接入的地方。`portfolio_manager.py:35-40`：

```python
past_context = state.get("past_context", "")
lessons_line = (
    f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
    if past_context
    else ""
)
```

`past_context` 是 `TradingMemoryLog` 在运行开始时格式化好的经验字符串。这里有个关键区分：**同 ticker 的历史注入完整决策 + 反思（最近 5 条），跨 ticker 的历史只注入反思而不注入原始决策（最近 3 条）**。这样设计的意图是——同标的的完整决策有直接参考价值（同一只股票上次为什么看错），跨标的的原始决策没有可比性，但反思提取的教训（如"忽略了宏观环境"）是可迁移的。如果非空，就以 "Lessons from prior decisions and outcomes:" 的格式注入 prompt。这是框架唯一的记忆注入点——所有过去的经验都通过这一行进入 LLM 上下文。详见 [记忆与反思](../06-internals/memory-system.md)。

输出绑定 `PortfolioDecision` schema（`schemas.py:188-228`），含 5 级 `rating`、`executive_summary`、`investment_thesis`、可选的 `price_target` 和 `time_horizon`。prompt 接收四类输入（`portfolio_manager.py:55-60`）：

```
- Research Manager's investment plan: **{research_plan}**
- Trader's transaction proposal: **{trader_plan}**
{lessons_line}
**Risk Analysts Debate History:**
{history}
```

研究计划、交易提案、过去经验、风险辩论历史——Portfolio Manager 在所有信息之上做出最终裁决，结果写入 `final_trade_decision`。

注意 `portfolio_manager.py:74-85` 返回的 `new_risk_debate_state` 把所有字段都拷贝了，并设 `latest_speaker="Judge"`。这是辩论结束的标记，但因为后面没有路由判断了（直接 `add_edge("Portfolio Manager", END)`），这个标记主要是为日志和可观察性服务的。

## Trader：把评级翻译成动作

Trader 是流水线中最后一个往 `messages` 写内容的节点。它的特殊之处是用 role list 而非 ChatPromptTemplate（`trader.py:28-49`）：

```python
messages = [
    {
        "role": "system",
        "content": (
            "You are a trading agent analyzing market data to make investment decisions. "
            "Based on your analysis, provide a specific recommendation to buy, sell, or hold. "
            "Anchor your reasoning in the analysts' reports and the research plan."
            + get_language_instruction()
        ),
    },
    {
        "role": "user",
        "content": (
            f"Based on a comprehensive analysis by a team of analysts, here is an investment "
            f"plan tailored for {company_name}. {instrument_context} ..."
            f"\n\nProposed Investment Plan: {investment_plan}\n\n"
            ...
        ),
    },
]
```

输出绑定 `TraderProposal` schema（`schemas.py:121-156`），含 3 级 `TraderAction`（Buy/Hold/Sell）、`reasoning`、可选的 `entry_price`、`stop_loss`、`position_sizing`。

为什么 Trader 是 3 级而 Research Manager 是 5 级？`schemas.py:54-65` 的 docstring 给出答案：

> The Trader's job is to translate the Research Manager's investment plan into a concrete transaction proposal: should the desk execute a Buy, a Sell, or sit on Hold this round. Position sizing and the nuanced Overweight / Underweight calls happen later at the Portfolio Manager.

Trader 只管方向（Buy/Sell/Hold），仓位细节留给 Portfolio Manager。这是一个职责分解：5 级评级的语义在 Trader 处被压缩成 3 个可执行动作，再在 Portfolio Manager 处被还原成 5 级的最终评级。

`trader.py:59-63` 的返回值：

```python
return {
    "messages": [AIMessage(content=trader_plan)],
    "trader_investment_plan": trader_plan,
    "sender": name,
}
```

注意它写了 `messages`——这是流水线中最后一个往 `messages` 写内容的节点（4 个分析师也会写 messages，但它们之后都被 Msg Clear 清空）。Trader 之后的风险辩手和管理层都只更新各自的子状态字段，不再写 messages。这也是为什么 Portfolio Manager 不需要 `MessagesPlaceholder`——到它这一步，messages 已经不重要了。

`functools.partial(trader_node, name="Trader")`（`trader.py:65`）是个小技巧：让节点函数签名兼容 LangGraph 的 `(state)` 调用约定，但内部仍能拿到 `name` 参数。

## 风险辩手：三方轮流发言

Aggressive / Conservative / Neutral 三个风控辩手（`aggressive_debator.py` / `conservative_debator.py` / `neutral_debator.py`）是镜像设计，只是 prompt 角色定位不同。它们都：

- 不调工具
- 不绑结构化输出
- 用纯 f-string prompt
- 输入是 4 份 report + 标的 + Trader 决策 + 辩论历史 + 其他两方论点

`aggressive_debator.py:43-55` 的状态更新展示了三方辩论的字段管理：

```python
new_risk_debate_state = {
    "history": history + "\n" + argument,
    "aggressive_history": aggressive_history + "\n" + argument,
    "conservative_history": risk_debate_state.get("conservative_history", ""),
    "neutral_history": risk_debate_state.get("neutral_history", ""),
    "latest_speaker": "Aggressive",
    "current_aggressive_response": argument,
    "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
    "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
    "count": risk_debate_state["count"] + 1,
}
```

对比 Bull/Bear 的 6 字段子状态，RiskDebateState 有 10 个字段。每方发言都要把自己 history 追加、把另外两方 history 和 current_*_response 原样拷贝、设 `latest_speaker` 驱动轮转、自增 `count` 驱动终止。这里的"原样拷贝"比 Bull/Bear 更繁琐，但底层原因一样：嵌套 TypedDict 整体覆盖，必须把所有字段带上。

`latest_speaker` 用 "Aggressive" / "Conservative" / "Neutral" 这种短前缀（不是节点名 "Aggressive Analyst"），匹配 `should_continue_risk_analysis` 里的 `startswith` 判断。轮转规则（详见 [辩论机制](debate-mechanism.md)）：Aggressive → Conservative → Neutral → 循环。

prompt 内容上，三方有明确的角色定位：

- **Aggressive**：积极为高风险高回报辩护，挑战保守和中立的"过度谨慎"
- **Conservative**：保护资产、降波动、控风险，挑战激进和中立的"忽视威胁"
- **Neutral**：平衡视角，挑战两边的"过度乐观或过度悲观"

每个 prompt 末尾都有 "Output conversationally as if you are speaking without any special formatting" 这句话，让辩手输出更像口语化的辩论而不是格式化报告。

## 横切关注点

### 工具注册：集中再导出

`agent_utils.py:9-25` 集中从各工具模块导入所有数据获取函数：

```python
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.fundamental_data_tools import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
)
from tradingagents.agents.utils.macro_data_tools import get_macro_indicators
from tradingagents.agents.utils.market_data_validation_tools import get_verified_market_snapshot
from tradingagents.agents.utils.news_data_tools import (
    get_global_news,
    get_insider_transactions,
    get_news,
)
...
```

`__all__`（`agent_utils.py:29-47`）列出所有公开符号。这个设计让 agents 包外只看到一个入口——`from tradingagents.agents.utils.agent_utils import get_stock_data`——而不必知道实际定义在哪个子模块。工具的实现按数据类型分散在 `core_stock_tools.py`、`fundamental_data_tools.py`、`news_data_tools.py` 等文件里，但调用方不需要关心。

这种"外观模式"（facade pattern）让工具的物理组织（按数据源分文件）和逻辑接口（一个统一入口）解耦，新增工具只需要在子模块加函数、在 agent_utils 重新导出，调用点不变。

### 标的身份解析：防止模型认错公司

`agent_utils.py:78-119` 的 `resolve_instrument_identity` 是一个常被忽略但极其重要的函数。它做的是给定 ticker，用 yfinance 查询公司名、行业、板块、交易所、报价类型，返回确定性 identity 字典。

`agent_utils.py:79-95` 的 docstring 解释了为什么需要它：

> This exists to stop the pipeline from hallucinating a *different* company when a chart pattern suggests a different industry than the real one (#814): without a ground-truth name, the market analyst would pattern-match the price action to a narrative and invent an identity that then cascaded through every downstream agent.

具体场景：假设分析一只矿业股，K 线形态像科技股，Market Analyst 可能就"看图说话"误判它是科技公司。这种错认一旦发生，会污染下游所有 agent 的报告。提前注入 ground-truth 身份信息能锁死这个变量。

实现上的几个关键设计：

- `@functools.lru_cache(maxsize=256)` 缓存。同一进程内同 ticker 只查一次，节省 API 调用。
- `fail-open` 设计（`agent_utils.py:100-102`）：任何异常都返回 `{}`，让流程继续。yfinance 不可用、被限流、不识别 ticker 都不能阻塞整次分析。
- 先调 `normalize_symbol(ticker)`（`agent_utils.py:99`），把 `XAUUSD` 这种交易员符号转成 `GC=F` 这种 yfinance 符号，保证查到的身份跟实际拿到 K 线的是同一只票。
- `_clean_identity_value`（`agent_utils.py:68-75`）把空串、`"none"`、`"n/a"`、`"nan"`、`"null"` 都当作 None，避免把占位字符串当真。

`build_instrument_context`（`agent_utils.py:122-169`）把 identity 字典格式化成 prompt 字符串：

```
The instrument to analyze is `NVDA`. Use this exact ticker in every tool call, report,
and recommendation, preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`).
Resolved identity: Name: NVIDIA Corporation; Business classification: Technology /
Semiconductors; Exchange: NQM. Do not substitute a different company or ticker unless
a tool result explicitly disproves this resolved identity.
```

几个有意思的细节：

- "Use this exact ticker in every tool call" 是强约束，防止模型把 `BRK.B` 写成 `BRK` 或 `BRK-B`。
- crypto 模式（`agent_utils.py:164-168`）额外提示 "Treat it as a crypto asset rather than a company, and do not assume company fundamentals are available"，因为基本面工具对加密资产没数据。
- "Do not substitute a different company or ticker unless a tool result explicitly disproves this resolved identity" 留了一个出口——如果工具结果显式证伪了 identity，模型应该信工具。但这种例外需要明确的工具输出支持，不能凭 K 线"觉得像"就改。

`get_instrument_context_from_state`（`agent_utils.py:172-187`）是 agent 调用入口，优先读 state 里预解析的 `instrument_context`，缺失时退化为只 ticker 的最简版本。这层封装让 agent 永远不必在图执行中做 yfinance 调用——identity 在 `_run_graph` 启动时就解析好了。

### 消息清理与占位注入

`create_msg_delete`（`agent_utils.py:190-214`）在 [Graph 编排](graph-orchestration.md) 已经详细讲过。这里补充它对 prompt 设计的影响：因为每个分析师之间消息会被清空，分析师的 prompt 模板不能依赖"前面分析师留下的消息"——所有需要的上下文（4 份 report）都是通过状态字段传递的，不是通过 messages。这是 TradingAgents 区别于一般 LangGraph demo 的一个关键设计选择：messages 是 ReAct 工作内存，report 才是阶段产出。

## 四类角色的工程模式归纳

| 模式 | 适用角色 | 核心组件 |
|------|---------|---------|
| ReAct 工具循环 | Market/News/Fundamentals | `prompt \| llm.bind_tools(tools)` + 三节点链 |
| 预取 + 结构化 | Sentiment | 节点内预取数据 + `bind_structured` |
| 纯 prompt 辩手 | Bull/Bear/Aggressive/Conservative/Neutral | f-string + `llm.invoke(prompt)` |
| 结构化裁判 | Research Manager/Portfolio Manager/Trader | `bind_structured` + `invoke_structured_or_freetext` |

这四套模式覆盖了所有 12 个 LLM 角色（第 13 个 Msg Clear 是无 prompt 的横切节点）。理解了它们，再去看任何一个 agent 的源码，都能迅速定位它属于哪类、关键代码在哪几行。

## 下一步

- [辩论机制](debate-mechanism.md)：研究员和风险辩手的具体循环规则、轮次数学
- [状态模型](state-model.md)：4 类角色写入的状态字段、嵌套子状态的 reducer 语义
- [结构化输出](../06-internals/structured-output.md)：`bind_structured` / `invoke_structured_or_freetext` 的 Provider 适配细节
- [记忆与反思](../06-internals/memory-system.md)：`past_context` 是怎么构造和注入 Portfolio Manager 的

---

**文档元信息**
难度：⭐⭐⭐ | 类型：进阶分析 | 预计阅读时间：40 分钟
