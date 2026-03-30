---
难度：⭐⭐⭐⭐
类型：专家设计
预计时间：45 分钟
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

在 tradingagents/agents/analysts 下新建 macro_analyst.py，并仿照现有 Analyst 工厂写法实现 create_macro_analyst(llm)。

如果你想先做一个“最小可运行 Analyst”，至少要具备 3 个元素：

1. 接收统一的 llm。
2. 有明确的系统提示词和输出目标。
3. 在结束时把结果写回专属 state 字段。

下面这个骨架比“仿照现有写法”更容易落地：

```python
def create_macro_analyst(llm):
  def macro_analyst_node(state):
    # 1. 读取 state 中已经存在的上下文
    # 2. 如有需要，先走工具调用
    # 3. 生成宏观分析文本
    # 4. 返回 {"macro_report": report}
    ...

  return macro_analyst_node
```

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
2. 新增 Provider 时，最容易遗漏的是 normalize_content 或模型校验，而不是认证参数本身。
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

## 小结

TradingAgents 的扩展能力不错，但前提是你尊重它现有的边界设计。最好的扩展方式不是“哪能跑通改哪”，而是沿着状态、节点、边界层和 CLI 暴露四条主线做闭环修改。

---

__文档元信息__
难度：⭐⭐⭐⭐ | 类型：专家设计 | 更新日期：2026-03-29 | 预计阅读时间：45 分钟
