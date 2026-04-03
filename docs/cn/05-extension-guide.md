---
难度：⭐⭐⭐⭐
类型：专家设计
预计时间：55 分钟
前置知识：
  - [03-architecture.md](03-architecture.md)
  - [04-usage-and-configuration.md](04-usage-and-configuration.md)
后续推荐：
  - [06-testing-and-evolution.md](06-testing-and-evolution.md)
学习路径：
  - 开发路径：第 4 阶段
---

# TradingAgents 开发扩展指南

## 这篇文档适合谁

如果你的目标是：

1. 新增一个 Analyst。
2. 新增一个数据供应商。
3. 新增一个 LLM Provider。
4. 调整图结构。
5. 替换记忆实现。

那么这篇文档就是开发入口。

## 开发扩展的基本原则

在进入具体步骤之前，先记住 4 条原则：

1. 先补状态契约，再补节点逻辑。
2. 先保证图能编译，再追求行为完美。
3. 所有供应商差异尽量收敛在边界层。
4. 每次只扩展一个维度，便于验证问题来源。

## 扩展前准备清单

在你开始改代码之前，建议先回答下面几个问题：

1. 这次扩展主要改的是角色、流程、模型边界，还是数据边界。
2. 需要新增哪些 state 字段。
3. 需要改哪些 CLI 暴露。
4. 需要补哪些最小验证路径。

如果这四个问题没有提前想清楚，扩展过程通常会退化成“哪里报错修哪里”。

## 扩展一：新增一个 Analyst

以新增 Macro Analyst 为例，建议按下面的顺序操作。

### 第 1 步：新增节点实现

在 tradingagents/agents/analysts 下新建 macro_analyst.py。以下是一个完整可运行的模板，遵循现有 Analyst 的标准写法：

```python
# tradingagents/agents/analysts/macro_analyst.py
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_global_news,        # 定义于 agents/utils/news_data_tools.py，由 agent_utils 重新导出
    get_language_instruction,
)


def create_macro_analyst(llm):
    def macro_analyst_node(state):
        current_date = state[“trade_date”]
        instrument_context = build_instrument_context(
            state[“company_of_interest”]
        )

        # 1. 定义该角色可用的工具集合
        tools = [
            get_global_news,
        ]

        # 2. 编写角色特化的 system message
        system_message = (
            “You are a macro economics analyst tasked with analyzing “
            “macroeconomic trends, monetary policy, fiscal policy, “
            “global trade dynamics, and their impact on financial markets. “
            “Focus on interest rates, GDP growth, inflation, employment data, “
            “central bank decisions, and geopolitical risks. “
            “Use the available tools to gather relevant data. “
            “Provide specific, actionable insights with supporting evidence “
            “to help traders make informed decisions.”
            + “ Make sure to append a Markdown table at the end of the “
            “report to organize key points.”
            + get_language_instruction()  # 支持多语言输出
        )

        # 3. 构建 Prompt 模板（与其他 Analyst 保持一致的结构）
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    “system”,
                    “You are a helpful AI assistant, collaborating with “
                    “other assistants. Use the provided tools to progress “
                    “towards answering the question. If you are unable to “
                    “fully answer, that's OK; another assistant with “
                    “different tools will help where you left off. Execute “
                    “what you can to make progress. If you or any other “
                    “assistant has the FINAL TRANSACTION PROPOSAL: “
                    “**BUY/HOLD/SELL** or deliverable, prefix your response “
                    “with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so “
                    “the team knows to stop. You have access to the “
                    “following tools: {tool_names}.\n{system_message}”
                    “For your reference, the current date is {current_date}. “
                    “{instrument_context}”,
                ),
                MessagesPlaceholder(variable_name=”messages”),
            ]
        )

        # 4. 注入变量
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(
            tool_names=”, “.join([tool.name for tool in tools])
        )
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # 5. 构建链并执行
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state[“messages”])

        # 6. 只有不再调用工具时才写回报告
        report = “”
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            “messages”: [result],
            “macro_report”: report,  # 写入专属 state 字段
        }

    return macro_analyst_node
```

**关键设计点**：

| 设计选择 | 原因 |
| ---- | ---- |
| `ChatPromptTemplate + MessagesPlaceholder` | 与现有 Analyst 保持一致，支持工具循环 |
| `llm.bind_tools(tools)` | 只暴露该角色需要的最小工具集合 |
| `get_language_instruction()` | 用户可见输出，必须支持多语言 |
| `build_instrument_context()` | 保留 ticker 后缀（如 `.TO`, `.T`） |
| `if len(result.tool_calls) == 0` | 只在不继续调用工具时才写报告 |
| 返回 `”messages”` 键 | LangGraph 要求消息流通过 messages 字段传递 |

### 第 2 步：导出符号

在 tradingagents/agents/__init__.py 中导出 create_macro_analyst。如果你额外维护 analysts 子目录自己的导出，也应保持两处入口一致，避免上层装配时找不到符号。

### 第 3 步：新增状态字段

在 AgentState 中增加 macro_report，保证后续节点和日志系统有地方承接新报告。

### 第 4 步：接入工具节点

在 TradingAgentsGraph._create_tool_nodes 中新增 macro 对应工具集合。如果新 Analyst 用的是现有工具，也要明确它的最小工具边界，不要把所有工具都暴露给它。

判断“最小工具集合”时，可以按下面顺序收敛：

1. 先列出这个角色必须回答的 2 到 3 个问题。
2. 再反推每个问题需要哪一个工具，而不是从工具列表里往角色身上塞能力。
3. 能复用现有工具就不要新增；能少暴露一个工具就不要多暴露一个。

### 第 5 步：修改图构建逻辑

在 GraphSetup.setup_graph 中让 macro 成为可选 Analyst 之一，并为它添加：

1. Analyst 节点。
2. 工具节点。
3. 消息清理节点。
4. 条件边。

### 第 6 步：增加条件逻辑

在 ConditionalLogic 中补充 should_continue_macro。

### 第 7 步：更新 CLI 暴露

不要漏掉 CLI 相关改动：

1. 在 cli/models.py 中加入新的 AnalystType。
2. 在 cli/main.py 中更新 MessageBuffer 的 ANALYST_MAPPING。
3. 更新 REPORT_SECTIONS 和展示逻辑。
4. 在交互式选择项中暴露新 Analyst。

这里最容易漏的是“类型枚举、状态展示、报告展示”三者不同步。可以直接把下面这份检查表当成操作清单：

- 新 Analyst 是否出现在 [cli/models.py](../../cli/models.py) 的 AnalystType。
- CLI 是否能选中它。
- [cli/main.py](../../cli/main.py) 的 MessageBuffer 是否知道如何显示它的名称。
- [cli/main.py](../../cli/main.py) 的 REPORT_SECTIONS 是否知道它会产出哪份报告。
- 最终报告拼装逻辑是否会展示这份新报告。

### 第 8 步：验证执行顺序

selected_analysts 不只是开关，也是顺序定义。如果你把 macro 放在第一个，它就会最先执行。这个顺序变化会影响后续消息上下文，所以必须有意识地设计。

## 扩展二：新增一个数据供应商

如果你要接入 Finnhub、Polygon 或内部数据服务，建议按这个顺序：

1. 在 tradingagents/dataflows 下新增供应商实现文件。
2. 为现有抽象方法补齐新供应商实现。
3. 在 dataflows/interface.py 的 VENDOR_METHODS 注册映射。
4. 确保返回格式与上层工具约定一致。
5. 明确异常语义，必要时补充回退策略。

这里最容易出问题的并不是函数能不能调用，而是返回结构和异常行为是否与现有抽象一致。

## 扩展三：新增一个 LLM Provider

新增 Provider 的推荐路径是：

1. 在 llm_clients 下新增 xxx_client.py。
2. 继承 BaseLLMClient，实现 get_llm 和 validate_model。
3. 在工厂里注册新的 provider 分支。
4. 处理内容归一化问题。
5. 增加认证、base_url 和 provider 特定参数透传。

最关键的原则是：不要把 Provider 差异泄漏到 Agent 节点内部。Agent 层应尽量只关心“我拿到的是统一 LLM 接口”。

## 扩展四：调整工作流结构

可能的改动包括：

1. 让 Analyst 并行执行。
2. 在 Trader 前增加策略综合节点。
3. 把风险辩论提前。
4. 在最终决策后增加合规审查。

这类变更主要集中在 GraphSetup.setup_graph 和 ConditionalLogic。建议的操作顺序是：

1. 明确新状态字段。
2. 增加新节点。
3. 增加新边和条件边。
4. 让图先 compile 成功。
5. 再验证节点行为是否符合预期。

## 扩展五：替换记忆系统

当前 FinancialSituationMemory 基于 BM25。如果你要改成向量检索或混合检索，最稳妥的方式不是直接改调用方，而是：

1. 保留 add_situations 和 get_memories 这类外部接口。
2. 只替换内部索引结构与检索实现。
3. 逐步比较旧实现和新实现的输出差异。

这样能最大限度降低对研究员、Trader 和 Manager 节点的冲击。

更具体地说，接口兼容性至少要守住两层：

1. 方法名和调用签名不要轻易变化，否则调用侧会在运行时静默漂移。
2. 返回值语义要保持一致，否则上层节点虽然还能运行，但记忆内容会悄悄失真。

## 扩展时最常见的漏改点

1. 只改了 Agent 文件，没改 AgentState。
2. 只改了 GraphSetup，没改 CLI 暴露。
3. 新增数据源时没统一异常模型。
4. 新 Provider 接入后忘了做内容归一化。
5. 修改结果输出逻辑时，没有同步日志消费方。

检测这些漏改点时，可以直接按这份最小检查表走：

1. grep 新字段名，确认它至少出现在 state、graph、日志消费或展示层。
2. grep 新角色名，确认它至少出现在 Agent、GraphSetup、CLI 映射和报告展示里。
3. grep 新 provider 名，确认它至少出现在 client、factory、验证逻辑和文档示例里。

## 常见卡点

1. 新增 Analyst 时，不是所有工具都必须实现，只需要覆盖这个角色最小必要的问题空间。
2. 新增 Provider 时，最常见的遗漏点是 normalize_content 或模型校验，而不是认证参数本身。
3. 改 Graph 时，先追求 compile 成功和状态闭合，再追求输出质量优化。

## 一个推荐的扩展验证顺序

当你完成一个扩展后，建议按下面顺序验证：

1. 图能否 compile。
2. 最小路径能否执行。
3. 新字段是否正确写回 state。
4. CLI 是否正确显示。
5. 最终日志是否保留了新产物。

如果你时间很紧，至少保住下面这条 MVP 验证路径：图能编译 -> 最小执行路径能跑通 -> 新字段成功写回 state -> CLI 或日志能看到新产物。没有这 4 步，扩展最多只能算“局部代码写完”，还不能算“能力落地”。

## 扩展完成后的验收清单

- [ ] 新能力已经接入 state，而不是只停留在消息文本里。
- [ ] Graph 能在启用和禁用该能力两种情况下都正常收敛。
- [ ] CLI 和 Python API 对新能力的暴露一致。
- [ ] 日志与结果文件能看到新产物。
- [ ] 至少有一条最小测试路径覆盖了这次扩展。

## output_language 在新 Agent 中的传播

当你新增一个用户可见输出的 Agent（如 Analyst 或 Portfolio Manager），必须追加 `get_language_instruction()` 以支持多语言：

```python
from tradingagents.agents.utils.agent_utils import get_language_instruction

system_message = (
    "Your specialized prompt here..."
    + get_language_instruction()  # 追加语言指令
)
```

**判断规则**：

| 角色 | 是否追加 `get_language_instruction()` | 原因 |
| ---- | ---- | ---- |
| Analyst（新） | 是 | 用户可见的分析报告 |
| Portfolio Manager（新） | 是 | 用户可见的最终决策 |
| Researcher（Bull/Bear） | 否 | 内部辩论保持英文 |
| Risk Debator | 否 | 内部辩论保持英文 |
| Trader | 否 | 中间层，非用户直接可见 |

## 扩展验证的测试模板

完成扩展后，建议至少编写以下两类测试：

### 结构验证测试

```python
# tests/test_macro_extension.py
"""验证 Macro Analyst 扩展的结构完整性"""

def test_macro_report_in_state():
    """验证 macro_report 字段存在于初始状态"""
    from tradingagents.graph.propagation import Propagator
    p = Propagator()
    state = p.create_initial_state("AAPL", "2024-05-10")
    assert "macro_report" in state
    assert state["macro_report"] == ""

def test_graph_compiles_with_macro():
    """验证启用 macro 后图能编译"""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    config = DEFAULT_CONFIG.copy()
    ta = TradingAgentsGraph(
        selected_analysts=["market", "news", "macro"],
        config=config,
    )
    assert ta.graph is not None

def test_graph_compiles_without_macro():
    """验证不启用 macro 时图仍能编译"""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    config = DEFAULT_CONFIG.copy()
    ta = TradingAgentsGraph(
        selected_analysts=["market", "news"],
        config=config,
    )
    assert ta.graph is not None
```

### 边界验证测试

```python
def test_macro_analyst_factory_returns_callable():
    """验证 create_macro_analyst 返回可调用函数"""
    from unittest.mock import MagicMock
    from tradingagents.agents.analysts.macro_analyst import create_macro_analyst

    mock_llm = MagicMock()
    node = create_macro_analyst(mock_llm)
    assert callable(node)

def test_macro_tool_node_contains_expected_tools():
    """验证 macro 的 ToolNode 包含预期工具"""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    ta = TradingAgentsGraph(
        selected_analysts=["macro"],
        config=config,
    )
    assert "macro" in ta.tool_nodes
```

## 小结

TradingAgents 的扩展能力不错，但前提是你尊重它现有的边界设计。最好的扩展方式不是”哪能跑通改哪”，而是沿着状态、节点、边界层和 CLI 暴露四条主线做闭环修改。

## 自测问题

1. 如果你在新增 Analyst 时忘了在 `propagation.py` 的 `create_initial_state` 中添加对应字段的空字符串初始化，会发生什么？
2. `output_language` 的 `get_language_instruction()` 在 English 时返回空字符串——为什么要这样设计而不是返回一个空格？
3. 新增 Provider 时，如果你的客户端没有在 `factory.py` 中注册，系统会在什么时候报错？是初始化阶段还是运行阶段？
4. 为什么记忆系统的接口兼容性（`add_situations` 和 `get_memories` 的签名）比内部实现更重要？

## 练习题

1. 按照本文的 Macro Analyst 模板，创建一个 `sentiment_analyst.py`（与现有 `social_media_analyst` 类似但专注于情绪量化），列出你需要修改的所有文件清单。
2. 编写一个测试用例，验证当你同时传入 `google_thinking_level` 和 `openai_reasoning_effort` 时，只有与当前 `llm_provider` 匹配的参数会生效。

---

__文档元信息__
难度：⭐⭐⭐⭐ | 类型：专家设计 | 更新日期：2026-04-01 | 预计阅读时间：55 分钟
