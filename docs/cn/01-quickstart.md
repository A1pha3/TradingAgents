---
难度：⭐
类型：入门教程
预计时间：25 分钟
前置知识：
  - Python 基础
后续推荐：
  - [04-usage-and-configuration.md](04-usage-and-configuration.md)
  - [02-principles-and-workflow.md](02-principles-and-workflow.md)
学习路径：
  - 用户路径：第 1 阶段
  - 开发路径：第 1 阶段
---

# TradingAgents 快速开始

## 这篇文档解决什么问题

这篇文档只做一件事：帮助你在最短时间内成功跑通 TradingAgents，并知道“跑通”到底意味着什么。

如果你现在最关心的是：

1. 怎么安装。
2. 怎么配 Key。
3. 怎么启动 CLI。
4. 怎么用 Python API 执行一个最小示例。
5. 跑完之后该看哪里判断系统有没有正常工作。

那么先读完这一篇，再考虑深入原理和架构。

## 学习目标

读完本文后，你应该能够：

1. 在本地完成安装与依赖准备。
2. 正确配置至少一组 LLM Key。
3. 启动 CLI 并完成一次交互式分析。
4. 通过 Python API 执行一个最小可运行示例。
5. 找到系统输出的关键结果和日志文件。

## 第一步：准备环境

项目要求 Python 版本不低于 3.10。仓库示例环境使用 Python 3.13。为了减少依赖差异，建议直接使用较新的 Python 版本。

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents

conda create -n tradingagents python=3.13
conda activate tradingagents

pip install .
```

如果你不使用 conda，也可以换成 venv、virtualenv、poetry 或其他环境管理器。重点不是工具本身，而是保证依赖隔离。

如果你还没决定用哪种环境管理器，可以先按下面的标准选：

| 方案 | 适合谁 | 优点 | 代价 |
| ---- | ---- | ---- | ---- |
| conda | 想快速得到一套稳定环境的使用者 | 创建环境和切换环境直观 | 环境通常更重 |
| venv | 已经有系统 Python 的轻量用户 | 标准库自带、依赖少 | 需要自己管理 Python 版本 |
| virtualenv | 习惯纯 pip 工作流的用户 | 与 venv 体验接近，兼容面广 | 本质收益和 venv 接近 |
| poetry | 想顺带管理依赖锁定的开发者 | 环境与依赖声明更统一 | 首次上手成本更高 |

如果你只是第一次验证项目能不能跑通，优先选 conda 或 venv，不要一开始就把环境管理也变成研究课题。

## 第二步：配置访问凭证

TradingAgents 支持多种 LLM 供应商。你至少需要为自己计划使用的模型后端配置访问凭证。

```bash
export OPENAI_API_KEY=your_openai_key
export GOOGLE_API_KEY=your_google_key
export ANTHROPIC_API_KEY=your_anthropic_key
export XAI_API_KEY=your_xai_key
export OPENROUTER_API_KEY=your_openrouter_key
export ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

常见理解误区有两个：

1. 不是所有 Key 都必须配齐。你只配置自己要用到的供应商即可。
2. Alpha Vantage 是数据供应商，不是 LLM 供应商。只有当你把部分数据能力切到它时才需要对应 Key。

更具体地说，可以按下面的规则理解“缺哪个 Key 会发生什么”：

| 你缺少的 Key | 在什么情况下会出问题 | 典型现象 |
| ---- | ---- | ---- |
| OPENAI_API_KEY | 你选择 openai 作为 llm_provider 时 | 模型初始化失败，CLI 或 API 在启动早期报错 |
| GOOGLE_API_KEY | 你选择 google 作为 llm_provider 时 | Google 客户端无法创建 |
| ANTHROPIC_API_KEY | 你选择 anthropic 作为 llm_provider 时 | Anthropic 客户端无法创建 |
| ALPHA_VANTAGE_API_KEY | 你把某些 data_vendors 或 tool_vendors 切到 alpha_vantage 时 | 工具调用失败或频繁回退到其他供应商 |

这也是为什么“不是所有 Key 都必须配齐”不等于“可以随便缺”。你只要缺的是当前执行路径上会用到的那个 Key，系统就会在运行前或工具调用阶段报错。

如果你使用本地 Ollama，则不需要远程模型 Key，但要确保 Ollama 服务已启动，且需要的模型已经拉取完成。

## 第三步：启动 CLI

安装完成后，可以直接运行：

```bash
tradingagents
```

如果你希望从源码目录直接启动，也可以使用：

```bash
python -m cli.main
```

CLI 启动后，系统会引导你选择：

1. 股票代码。
2. 分析日期。
3. 启用的分析师组合。
4. 研究深度。
5. LLM 供应商。
6. 快速模型和深度模型。

这里的“研究深度”会直接影响辩论轮数，所以它不仅仅是一个展示用标签，而是实实在在的执行复杂度控制项。

如果这是你第一次上手，建议把研究深度理解成“系统愿意花多少轮讨论成本来换取更充分的结论”。第一轮先保守，不要一上来就追求最高深度。

## 第四步：运行最小示例

如果你更偏向脚本化使用，可以先执行下面的最小示例：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4"
config["quick_think_llm"] = "gpt-5.4-mini"

graph = TradingAgentsGraph(debug=True, config=config)
final_state, decision = graph.propagate("NVDA", "2024-05-10")

print(decision)
print(final_state["final_trade_decision"])
```

这个示例会触发完整工作流：Analyst 分析、研究辩论、Trader 规划、风险讨论和最终拍板。

## 第五步：判断是否跑通

成功运行之后，建议检查下面 4 个信号：

1. 终端没有在中途报错退出。
2. 你能看到最终决策文本，而不只是中间推理。
3. final_state 中包含 market_report、news_report 等中间产物。
4. eval_results 下出现了对应标的的状态日志文件。

这里有一个容易踩坑的工程细节：默认配置里有 results_dir，但当前图执行落盘仍直接写入 eval_results。也就是说，判断“有没有跑通”时，请优先检查 eval_results，而不是只盯着 results_dir。

这 4 个信号组合起来，才算真正跑通，而不是“命令执行过”。

## 一个稳妥的首次配置

第一次运行时，建议不要一上来把系统复杂度拉满。更稳妥的方式是：

1. 先只启用 market 和 news 两个 Analyst。
2. 研究深度保持在较低水平。
3. 数据供应商保持默认的 yfinance。
4. 先验证主链路稳定，再逐步增加角色和回合数。

这样做的原因很直接：你要先验证“系统有没有正常工作”，再追求“系统能不能做更复杂的工作”。

## CLI 与 Python API 该先学哪个

可以这样理解：

1. 如果你希望看到系统实时进展，先学 CLI。
2. 如果你希望把系统嵌入自己的实验脚本，先学 Python API。
3. 如果你是第一次接触项目，建议先用 CLI 建立直觉，再转向 API。

## 首次上手最常见的问题

### 启动很慢

常见原因包括：

1. 模型响应慢。
2. 研究深度过高。
3. 角色开得太多。
4. 数据供应商接口限流。

### 有输出，但质量不稳定

先检查：

1. 选择的模型是否擅长工具调用。
2. 数据源是否足够稳定。
3. 研究深度是否和模型能力匹配。

如果你看到的是“有结论，但中间报告明显空洞”，通常不是框架完全坏了，而是以下几类问题之一：

1. 模型能回答，但不擅长稳定地产生工具调用。
2. 某个数据供应商返回为空，导致 Analyst 只能基于很弱的上下文写报告。
3. 辩论轮数和模型能力不匹配，导致系统在冗余讨论中漂移。

这时先不要急着换一堆配置。更有效的做法是先检查中间报告和工具调用链路，再决定是换模型、减轮数，还是切换供应商。

### 模型返回格式异常或工具调用失败

这类问题通常表现为：

1. 模型有响应，但报告字段没有稳定写回。
2. 工具节点反复尝试，流程迟迟不收敛。
3. 某个 Analyst 阶段停留过久，或者直接跳过有效数据。

优先排查顺序建议是：

1. 检查是否选了当前 provider 明确支持的模型。
2. 降低研究深度，先验证主链路是否能稳定结束。
3. 改用默认的 yfinance 供应商，排除 Alpha Vantage 限流和回退因素。
4. 查看 [06-testing-and-evolution.md](06-testing-and-evolution.md) 中关于“静默错误”和“供应商回退”的说明。

如果你想更快定位，可以先套用这棵最小诊断树：

1. 一启动就报 provider 或 key 错误：先回看“第二步：配置访问凭证”。
2. 能跑但没有稳定报告：先检查模型选择和工具调用，再看供应商数据。
3. 有报告但找不到日志：优先检查 eval_results，而不是只看 results_dir。

### 日志找不到

当前实现会把状态日志落到 eval_results 目录。不要只根据默认配置中的 results_dir 推断实际日志路径。

## 完成后的下一步

如果你已经跑通，建议按下面的顺序继续：

1. 读 [04-usage-and-configuration.md](04-usage-and-configuration.md)，学会系统化调参。
2. 读 [02-principles-and-workflow.md](02-principles-and-workflow.md)，理解为什么系统要这样组织多 Agent。
3. 如果你准备做二次开发，再读 [03-architecture.md](03-architecture.md) 和 [05-extension-guide.md](05-extension-guide.md)。

## 自测检查清单

- [ ] 我已经能成功启动 CLI。
- [ ] 我已经能用 Python API 执行最小示例。
- [ ] 我知道最终决策输出在哪。
- [ ] 我知道状态日志默认写到哪里。
- [ ] 我知道首次运行不应把复杂度开满。
- [ ] 我知道为什么 quick_think_llm 和 deep_think_llm 要分开配置。

---

__文档元信息__
难度：⭐ | 类型：入门教程 | 更新日期：2026-03-29 | 预计阅读时间：25 分钟
