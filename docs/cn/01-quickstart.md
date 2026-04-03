---
难度：⭐
类型：入门教程
预计时间：35 分钟
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
| uv | 追求安装速度和现代工作流的用户 | 极快的依赖解析与安装，支持 lockfile | 生态相对较新，部分 CI 需额外配置 |

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
config["deep_think_llm"] = "gpt-5.4"       # 替换为你的 Provider 实际支持的模型名，如 "gpt-4o"
config["quick_think_llm"] = "gpt-5.4-mini"  # 替换为你的 Provider 实际支持的模型名，如 "gpt-4o-mini"

print(decision)
print(final_state["final_trade_decision"])
```

这个示例会触发完整工作流：Analyst 分析、研究辩论、Trader 规划、风险讨论和最终拍板。

### 使用 Ollama 本地模型（不需要 API Key）

如果你想完全离线运行，或者不想依赖任何云端 API，可以使用 Ollama 作为本地模型后端。完整步骤如下：

1. 安装 Ollama：

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

2. 拉取你需要的模型：

```bash
ollama pull qwen3:latest
```

3. 确认 Ollama 服务已启动（安装后通常会自动启动，也可以手动执行 `ollama serve`）。

4. 修改配置，指向本地 Ollama：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "ollama"
config["backend_url"] = "http://localhost:11434/v1"
config["quick_think_llm"] = "qwen3:latest"
config["deep_think_llm"] = "qwen3:latest"

graph = TradingAgentsGraph(debug=True, config=config)
final_state, decision = graph.propagate("NVDA", "2024-05-10")
```

使用 Ollama 时不需要配置任何远程 API Key。需要注意几点：

1. `backend_url` 必须指向 Ollama 的 OpenAI 兼容接口（`http://localhost:11434/v1`），而不是默认的 OpenAI 地址。
2. 本地模型的推理能力通常弱于云端旗舰模型，可能导致报告质量下降或格式不稳定。建议先用默认参数验证主链路可用，再根据效果决定是否长期使用本地模型。
3. 如果你的机器显存有限，可以给 `quick_think_llm` 和 `deep_think_llm` 分别指定不同大小的模型。

### 配置中文输出

默认情况下，所有报告和决策输出都是英文。如果你希望分析师报告和最终决策输出为中文，可以通过 `output_language` 参数控制：

```python
config["output_language"] = "中文"  # 默认为 "English"
```

这个配置的工作方式需要理解以下几点：

1. `output_language` 通过 `get_language_instruction()` 函数注入到 Analyst 和 Portfolio Manager 的 prompt 中。该函数通过全局配置（`get_config()`）读取此字段——`TradingAgentsGraph` 初始化时会自动将 config 写入全局，因此直接在 config 中设置 `output_language` 即可生效，无需额外操作。
2. 内部的辩论环节（Bull/Bear 研究员、风险讨论等）始终保持英文，以保证推理质量不受语言切换影响。
3. 支持任意自然语言描述，例如 `"中文"`、`"日本語"`、`"Français"` 均可。

## 第五步：判断是否跑通

成功运行之后，建议检查下面 4 个信号：

1. 终端没有在中途报错退出。
2. 你能看到最终决策文本，而不只是中间推理。
3. final_state 中包含 market_report、news_report 等中间产物。
4. eval_results 下出现了对应标的的状态日志文件。

这里有一个容易踩坑的工程细节：默认配置里有 results_dir，但当前图执行落盘仍直接写入 eval_results。也就是说，判断“有没有跑通”时，请优先检查 eval_results，而不是只盯着 results_dir。

这 4 个信号组合起来，才算真正跑通，而不是”命令执行过”。

### 运行结果示例与解读

下面是一个成功运行后的典型输出，帮助你理解 `propagate()` 的两个返回值分别代表什么。

`propagate()` 返回一个元组 `(final_state, decision)`：

- `decision` 是一个**单个评级词**，由 `SignalProcessor` 从完整决策文本中提取。它只可能是以下五个值之一：`BUY`、`OVERWEIGHT`、`HOLD`、`UNDERWEIGHT`、`SELL`。这个值适合用于程序化判断和回测信号记录。

- `final_state[“final_trade_decision”]` 是 **Portfolio Manager 的完整决策文本**，包含投资评级、执行摘要、投资论点和风险因素等完整分析内容。

一个典型的运行结果如下：

```text
# decision（SignalProcessor 提取的单个评级词）
decision: “BUY”

# final_state[“final_trade_decision”]（Portfolio Manager 的完整决策文本）
包含以下主要部分：
  Rating: Buy
  Executive Summary: NVDA 在 AI 芯片市场持续占据主导地位...
  Investment Thesis: 数据中心营收同比增长，推理侧需求加速...
  Risk Factors: 中国市场出口管制风险、竞争加剧...
  Position Suggestion: 建议配置比例为组合的 5-8%...
```

此外，`final_state` 中还包含以下中间产物，你可以按需检查每个环节的输出质量：

| 字段 | 含义 |
| ---- | ---- |
| `market_report` | Market Analyst 的市场技术面分析报告 |
| `sentiment_report` | Social Analyst 的社交媒体情绪报告 |
| `news_report` | News Analyst 的新闻与 insider 交易分析报告 |
| `fundamentals_report` | Fundamentals Analyst 的基本面分析报告 |
| `investment_debate_state` | Bull/Bear 辩论的完整历史和 Judge 裁决 |
| `trader_investment_plan` | Trader 的交易规划 |
| `risk_debate_state` | Aggressive/Conservative/Neutral 风险讨论的完整历史和 Judge 裁决 |
| `final_trade_decision` | Portfolio Manager 的最终决策文本 |

### 日志文件结构

成功运行后，系统会在 `eval_results/` 目录下生成 JSON 日志文件，路径格式为：

```text
eval_results/{ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json
```

以运行 `graph.propagate(“NVDA”, “2024-05-10”)` 为例，日志文件位于：

```text
eval_results/NVDA/TradingAgentsStrategy_logs/full_states_log_2024-05-10.json
```

这个 JSON 文件记录了该次运行的完整状态，包含所有 Analyst 报告、辩论历史、Trader 规划和最终决策，可用于后续回溯和审计。

## 利用记忆系统持续优化

TradingAgents 内置了基于 BM25 的记忆系统，支持在多轮运行中积累经验。核心方法是 `reflect_and_remember()`，它接收一个 `returns_losses` 参数，表示持仓收益率（正数表示盈利，负数表示亏损）。

```python
# 第一次运行
final_state, decision = graph.propagate(“NVDA”, “2024-05-10”)

# 假设后续实际收益为 +1000（正数表示盈利）
graph.reflect_and_remember(returns_losses=1000)

# 如果亏损，传入负数
# graph.reflect_and_remember(returns_losses=-500)
```

调用 `reflect_and_remember()` 后，系统会：

1. 对 Bull 研究员、Bear 研究员、Trader、投资 Judge、Portfolio Manager 五个角色的决策分别进行反思。
2. 将市场环境和反思结论存入各自的 BM25 记忆库。
3. 后续运行时，这些角色会自动检索相似历史场景，将相关经验注入分析上下文。

这意味着你跑的轮次越多、反馈越准确，系统的决策质量就有机会逐步提升。记忆检索基于词汇相似度（BM25），不需要额外的向量数据库或 API 调用。

典型的多轮使用模式如下：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config[“llm_provider”] = “openai”
config[“deep_think_llm”] = “gpt-5.4”       # 替换为你的 Provider 实际支持的模型名，如 “gpt-4o”
config[“quick_think_llm”] = “gpt-5.4-mini”  # 替换为你的 Provider 实际支持的模型名，如 “gpt-4o-mini”

# 同一个 graph 实例保持记忆
graph = TradingAgentsGraph(debug=True, config=config)

# 第一轮分析
final_state, decision = graph.propagate(“NVDA”, “2024-05-10”)
# ... 等待实际收益结果后进行反思
graph.reflect_and_remember(returns_losses=1000)

# 第二轮分析（会自动利用上一轮的记忆）
final_state, decision = graph.propagate(“NVDA”, “2024-06-10”)
graph.reflect_and_remember(returns_losses=-200)
```

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
- [ ] 我知道 `decision` 返回的是单个评级词（BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL），`final_state["final_trade_decision"]` 返回的是完整决策文本。
- [ ] 我知道状态日志默认写到 `eval_results/{ticker}/TradingAgentsStrategy_logs/` 目录。
- [ ] 我知道首次运行不应把复杂度开满。
- [ ] 我知道为什么 quick_think_llm 和 deep_think_llm 要分开配置。
- [ ] 我知道如何通过 `output_language` 配置中文输出，以及内部辩论不受此影响。
- [ ] 我知道如何使用 Ollama 本地模型运行，且不需要远程 API Key。
- [ ] 我知道 `reflect_and_remember()` 的参数含义（正数盈利、负数亏损），以及记忆系统会自动在后续运行中检索相似场景。

---

__文档元信息__
难度：⭐ | 类型：入门教程 | 更新日期：2026-04-01 | 预计阅读时间：35 分钟
