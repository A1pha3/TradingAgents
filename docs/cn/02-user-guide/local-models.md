# 本地模型部署 ⭐⭐

> **目标读者**：想用 Ollama / vLLM / LM Studio 在本机跑模型，不付 API 费用的用户
> **核心问题**：怎么让 TradingAgents 调本地模型，而不是云端 API？
> **前置知识**：[快速开始](../01-getting-started/quickstart.md) ⭐、[CLI 交互式手册](cli-manual.md) ⭐⭐

---

## 这篇文档解决什么问题

TradingAgents 默认走云端 LLM（OpenAI、Anthropic 等），跑一次完整分析要花真金白银的 token 费用，而且把代码和数据发到境外服务器。如果你的诉求是下面任一种，就需要切到本地模型：

- 零成本反复实验，调参、改 prompt、跑回测
- 数据不能出本机（公司内网、敏感标的）
- 只想看看这套多智能体框架到底怎么运转

TradingAgents 内置两种本地接入方式：**Ollama** 和 **openai_compatible**（vLLM、LM Studio、llama.cpp 等任何兼容 OpenAI Chat Completions API 的本地服务器）。两者都不需要 API key，差别在于 Ollama 有专门的集成路径，openai_compatible 是通用兜底。

先说清楚一条总原则，免得后面踩坑：**本地模型比云端慢，而且 tool-calling 支持参差不齐**。框架为此做了降级处理，但效果通常不如云端模型稳定。建议第一次跑用 Shallow 研究深度，跑通了再往深处调。

---

## 两种本地接入方式的区别

| 维度 | Ollama | openai_compatible |
|------|--------|-------------------|
| 适用服务器 | Ollama 官方客户端 | vLLM、LM Studio、llama.cpp 等任意 OpenAI 兼容服务器 |
| 默认端点 | `http://localhost:11434/v1` | 无默认，必须手动填 |
| 是否需要 base URL | 可选（有默认值） | **必填**（不填会报错） |
| 是否需要 API key | 否（自动填占位符 `"ollama"`） | 否（自动填占位符） |
| 模型选择 | 目录里有建议项 + Custom | 只能填 Custom model ID |
| tool-calling 处理 | 不强制 `tool_choice` | 不强制 `tool_choice` |

两者都属于"key optional"——本地服务器不验 key，框架会塞一个占位符进去让请求格式合法。真正决定行为的是 base URL 怎么填，下面分开讲。

---

## 方式一：Ollama

Ollama 是最省事的本地方案，框架给了它专门的处理逻辑。

### 1. 安装并拉模型

按 Ollama 官方文档装好 `ollama`，然后拉一个支持 tool-calling 的模型。TradingAgents 的分析师要调用工具，模型必须支持 function calling：

```bash
# 启动服务（默认监听 11434）
ollama serve

# 另开一个终端，拉模型。qwen2.5 支持 tool-calling，体积适中
ollama pull qwen2.5:32b
```

不是所有模型都支持 tool-calling。纯对话模型（如某些 base model）会卡在分析师环节，因为分析师要调工具拿行情。挑模型时确认 Ollama 文档里标注了 tool / function calling 支持。

### 2. 配置 .env

```bash
# .env
TRADINGAGENTS_LLM_PROVIDER=ollama
TRADINGAGENTS_DEEP_THINK_LLM=qwen2.5:32b
TRADINGAGENTS_QUICK_THINK_LLM=qwen2.5:32b
OLLAMA_BASE_URL=http://localhost:11434/v1
```

`OLLAMA_BASE_URL` 不写也行，框架会落到默认的 `http://localhost:11434/v1`。但如果你的 Ollama 跑在别的机器或端口（比如反代后改了路径），就靠这个变量指过去。

### 3. Ollama 端点的解析优先级

框架解析 Ollama 端点时按三级优先级取值：

```
OLLAMA_BASE_URL 环境变量  >  CLI 菜单里选的 URL  >  provider 默认 http://localhost:11434/v1
```

也就是说：环境变量最优先，设了就用环境变量的值；没设才看 CLI 菜单；菜单也没给就用默认。这正是 CLI 的"环境变量优先，有则跳过交互"原则的体现。

### 4. CLI 里的确认提示

走 CLI 选 Ollama 时，框架会打印一行确认，告诉你最终用的是哪个端点、来源是哪里：

```
✓ Using Ollama at http://localhost:11434/v1 (from OLLAMA_BASE_URL)
```

如果 URL 缺了协议头（`http://`）或端口，会给一个软提示但不阻断——你可能确实在用反代，框架不替你做决定。

### 5. 模型目录的行为

Ollama 的模型目录里，`ollama` 这个 provider 下 quick 和 deep 两档都给了几个建议模型，但**最后一项永远是 "Custom model ID"**。本地模型版本变得快，框架不维护固定列表，你 `ollama pull` 了什么就填什么。选 Custom 后输入你 pull 的完整 tag（比如 `qwen2.5:32b`、`llama3.1:8b-instruct`）。

### 6. 用 Python API 调

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
# .env 里设了 TRADINGAGENTS_LLM_PROVIDER=ollama，DEFAULT_CONFIG 已经叠加
# 这里硬编码会覆盖环境变量，按需选择
ta = TradingAgentsGraph(config=config)

_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

---

## 方式二：vLLM

vLLM 是高吞吐的推理服务器，适合有 GPU、想自己 host 开源模型的场景。它暴露的是 OpenAI 兼容 API，所以走 `openai_compatible` provider。

### 1. 启动 vLLM 服务

按 vLLM 文档装好后，启动一个 OpenAI 兼容服务器。下面以 Qwen2.5 为例，监听 8000 端口：

```bash
vllm serve Qwen/Qwen2.5-32B-Instruct \
    --served-model-name qwen2.5-32b \
    --host 0.0.0.0 --port 8000 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
```

两个关键 flag：

- `--enable-auto-tool-choice`：开启 tool-calling 支持，TradingAgents 的分析师必须靠它调工具
- `--tool-call-parser hermes`：指定 tool 调用的解析格式，不同模型要选对应的 parser（Qwen 用 hermes，Llama 系列看模型文档）

不开这两个 flag，分析师会卡住——模型返回的是纯文本，框架识别不出工具调用。

### 2. 配置 .env

```bash
# .env
TRADINGAGENTS_LLM_PROVIDER=openai_compatible
TRADINGAGENTS_LLM_BACKEND_URL=http://localhost:8000/v1
TRADINGAGENTS_DEEP_THINK_LLM=qwen2.5-32b
TRADINGAGENTS_QUICK_THINK_LLM=qwen2.5-32b
```

注意 `openai_compatible` **没有默认端点**，`TRADINGAGENTS_LLM_BACKEND_URL` 必填，不填启动时会报：

```
Provider 'openai_compatible' requires a base_url. Set it via backend_url /
TRADINGAGENTS_LLM_BACKEND_URL to your endpoint, e.g. http://localhost:8000/v1
(vLLM) or http://localhost:1234/v1 (LM Studio).
```

`served-model-name` 必须和 `TRADINGAGENTS_*_LLM` 里填的一致，否则 vLLM 找不到模型。

### 3. 走 CLI 时的交互

如果不用 `.env` 而是交互式跑 CLI，选 `openai_compatible` 后框架会单独问你一次 base URL：

```
Enter the OpenAI-compatible base URL
(e.g. http://localhost:8000/v1 for vLLM, http://localhost:1234/v1 for LM Studio):
> http://localhost:8000/v1
```

这个 URL 必须以 `http://` 或 `https://` 开头，否则校验不过。

---

## 方式三：LM Studio

LM Studio 是桌面应用，自带图形界面管理本地模型，对不熟命令行的人友好。它也能开一个 OpenAI 兼容服务器，同样走 `openai_compatible`。

### 1. 启动本地服务器

在 LM Studio 里：

1. 下载并装一个支持 tool-calling 的模型（比如 Qwen2.5 系列）
2. 切到 "Developer" 或 "Local Server" 标签页
3. 点 "Start Server"，默认监听 `http://localhost:1234/v1`
4. 记下页面顶部显示的模型名（LM Studio 会用它作为 API 里的 model 字段）

### 2. 配置 .env

```bash
# .env
TRADINGAGENTS_LLM_PROVIDER=openai_compatible
TRADINGAGENTS_LLM_BACKEND_URL=http://localhost:1234/v1
TRADINGAGENTS_DEEP_THINK_LLM=<LM Studio 里显示的模型名>
TRADINGAGENTS_QUICK_THINK_LLM=<LM Studio 里显示的模型名>
```

vLLM 和 LM Studio 在 TradingAgents 眼里没区别——都是 `openai_compatible`，差别只在端口号和模型名。llama.cpp 的 server 模式同理，照着填 base URL 即可。

---

## 关键技术细节：为什么本地模型用 `LocalCompatibleChatOpenAI`

本地服务器的 tool-calling 支持差异很大，框架用一个专门的客户端类来兜底。源码在 `tradingagents/llm_clients/openai_client.py`：

```python
class LocalCompatibleChatOpenAI(NormalizedChatOpenAI):
    """OpenAI-compatible client for arbitrary local servers."""

    def with_structured_output(self, schema, *, method=None, **kwargs):
        resolved = method or get_capabilities(self.model_name).preferred_structured_method
        if resolved == "function_calling":
            kwargs.setdefault("tool_choice", None)
        return super().with_structured_output(schema, method=method, **kwargs)
```

这段代码解决的问题：LangChain 在做结构化输出（function-calling 方式）时，默认会发送一个 object 形式的 `tool_choice` 参数，强制模型调用指定工具。很多本地服务器（vLLM、LM Studio、llama.cpp）不支持这种 object 形式的 `tool_choice`，直接返回 400 错误。

`LocalCompatibleChatOpenAI` 的做法是：仍然把 schema 绑定为工具，但不发 `tool_choice`（设成 `None`）。这样结构化输出在大多数本地服务器上都能跑，代价是模型偶尔可能不按 schema 回。

provider 注册表里 `openai_compatible` 显式指定了这个类：

```python
"openai_compatible": ProviderSpec(
    require_base_url=True, key_optional=True, chat_class=LocalCompatibleChatOpenAI
),
```

而 Ollama 走的是默认的 `NormalizedChatOpenAI`。Ollama 模型不在能力表里（`_BY_ID` 和 `_BY_PATTERN` 只收录了 DeepSeek 和 MiniMax），所以 `get_capabilities` 一律返回默认值（`supports_tool_choice=True`）。

---

## 本地模型的局限性

把预期摆清楚，免得跑完才发现不对劲。

### 1. 速度慢

本地模型推理速度取决于硬件。一张消费级显卡跑 32B 模型，单次 LLM 调用可能要十几秒到一分钟，而一次完整分析要调二三十次 LLM。串起来跑一次可能要十几分钟甚至更久，对比云端模型的几十秒到两分钟，差一个数量级。

应对办法：第一次跑用 **Shallow** 研究深度。研究深度对应 `max_debate_rounds` 和 `max_risk_discuss_rounds` 两个键，Shallow 都是 1，Deep 都是 5。Shallow 能把 LLM 调用次数压到最少：

```bash
# .env
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1
```

跑通流程、确认端点配置没问题之后，再按需调高。

### 2. tool-calling 支持不稳定

分析师环节（Market、News、Fundamentals 等）必须调工具拿行情和新闻。如果模型 tool-calling 能力弱，会出现：

- 模型返回纯文本，框架识别不出工具调用，分析师卡住
- 模型调了工具但参数填错（比如 ticker 写成公司名），工具报错
- 结构化输出字段缺失，下游节点拿到空值

挑模型时优先选 tool-calling 评测强的。Qwen2.5 系列、Llama 3.1+ 的 instruct 版本通常表现尚可。base 模型（非 instruct / chat 版）基本不能用。

### 3. 推理质量

本地开源模型在多轮辩论、风险讨论这类需要复杂推理的环节，表现通常弱于 GPT-5 级别的云端模型。最终决策的可信度要打个折扣。如果是认真做交易参考，建议至少对比一下云端模型的结果。

### 4. 能力表（capabilities）的影响

框架内部有一张模型能力表（`tradingagents/llm_clients/capabilities.py`），记录每个已知模型支持哪些结构化输出方式、要不要抑制 `tool_choice`。**本地模型往往不在表里**，框架会走默认行为，可能不是最优。这也是为什么 `LocalCompatibleChatOpenAI` 默认不强制 `tool_choice`——宁可保守一点，先让它能跑。

---

## 排查清单

跑不起来时按这个顺序查：

| 现象 | 排查方向 |
|------|---------|
| 启动报 `requires a base_url` | `openai_compatible` 没填 `TRADINGAGENTS_LLM_BACKEND_URL` |
| 连接超时 / 拒绝 | 服务器没起、端口不对、防火墙。`curl http://localhost:11434/v1/models` 测一下 |
| 分析师环节卡住 | 模型不支持 tool-calling，换个模型或开 `--enable-auto-tool-choice` |
| 报 400 tool_choice 错 | 理论上 `LocalCompatibleChatOpenAI` 已经处理，确认 provider 选的是 `openai_compatible` 或 `ollama` |
| 决策质量差 | 换更大的模型，或先用云端模型跑通看基线 |
| 速度慢到无法接受 | 用 Shallow 深度，或换更小的模型 |

---

## 下一步

| 推荐内容 | 难度 | 说明 |
|---------|------|------|
| [Python API](python-api.md) | ⭐⭐ | 编程方式调用，配合本地模型做批量分析 |
| [配置参考](configuration.md) | ⭐⭐ | 所有配置项的完整说明 |
| [CLI 交互式手册](cli-manual.md) | ⭐⭐ | 交互式选择 provider 和模型的完整流程 |
| [LLM 客户端](../05-data-and-llm/llm-clients.md) | ⭐⭐⭐ | provider 注册表和 capability 表的内部机制 |
