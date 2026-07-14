# 配置参考 ⭐⭐

> **目标读者**：已完成 [快速开始](../01-getting-started/quickstart.md)，想自定义所有配置的高频使用者
> **核心问题**：每个配置项是什么、默认值多少、谁能覆盖谁、怎么改才生效
> **前置知识**：[快速开始](../01-getting-started/quickstart.md) ⭐、[CLI 交互式手册](cli-manual.md) ⭐⭐

---

## 本文解决什么问题

跑过几次 `tradingagents analyze` 后，你会冒出这些需求：把辩论轮数加大、换更便宜的模型、固定输出中文、把缓存目录挪到外置盘、用 Alpha Vantage 替掉 yfinance。这些都指向同一个地方——配置。

TradingAgents 的配置不是单一开关，而是四层来源叠加的结果。同一项配置，CLI flag、环境变量、交互式选择、代码默认值都能影响它，而且它们的优先级关系容易被误解。本文把 `tradingagents/default_config.py:71-164` 的 `DEFAULT_CONFIG` 全字段、`_ENV_OVERRIDES`（`default_config.py:10-28`）的全部环境变量、双层 vendor 配置和 benchmark 自动检测表一次列清，并给出可直接复制的典型配置。

读完本文，你应该能：说出任意一项配置被谁覆盖、写出自己的 `.env` 配置块、判断某个改动该落在哪一层。

---

## 配置优先级：四层叠加

理解配置的第一件事，是搞清楚四层来源谁压谁。从高到低：

```text
1. CLI flag (--checkpoint / --no-checkpoint)        ← 唯一的显式命令行覆盖
2. TRADINGAGENTS_* 环境变量                          ← 在 DEFAULT_CONFIG 构造时应用
3. DEFAULT_CONFIG 字面量                             ← default_config.py:71-164
4. 交互式选择                                        ← 仅当对应 env 未设置时才生效
```

对应的代码位置：

| 层 | 来源 | 应用位置 |
|----|------|----------|
| 1 | `--checkpoint` / `--no-checkpoint` | `cli/main.py:986-987`（仅 `checkpoint is not None` 时写入） |
| 2 | `TRADINGAGENTS_*` 环境变量 | `default_config.py:58-68` 的 `_apply_env_overrides`，在构造 `DEFAULT_CONFIG` 时就地应用 |
| 3 | `DEFAULT_CONFIG` 字面量 | `default_config.py:71-164` |
| 4 | 交互式选择 | `cli/main.py:961-988` 的 `_build_run_config` |

### 一个容易踩的坑：env 和交互选择不是"谁后写谁赢"

很多人以为交互式问卷是最后一步，所以"选了就生效"。这是错的。`_build_run_config`（`cli/main.py:961-988`）在写入选中的辩论轮数前，会先显式检查对应环境变量：

```python
# cli/main.py:971-974（节选）
if not os.environ.get("TRADINGAGENTS_MAX_DEBATE_ROUNDS"):
    config["max_debate_rounds"] = selections["research_depth"]
if not os.environ.get("TRADINGAGENTS_MAX_RISK_ROUNDS"):
    config["max_risk_discuss_rounds"] = selections["research_depth"]
```

含义是：**只要 `TRADINGAGENTS_MAX_DEBATE_ROUNDS` 已经设置，交互问卷里选的 Shallow/Medium/Deep 就不会写进去**，env 的值原样保留。`--checkpoint/--no-checkpoint` 是唯一一个能盖过 env 的命令行入口，其余交互项一律遵循"有 env 就跳过、且 env 值不被覆盖"的规则。

这条规则的实际后果：

- 想让交互问卷完全说了算 → 不要在 `.env` 里设对应的 `TRADINGAGENTS_*` 变量。
- 想让某项在所有运行里固定 → 把它写进 `.env`，问卷会自动跳过那一问。
- 想临时强制开关 checkpoint → 用 `--checkpoint` 或 `--no-checkpoint`，它比 env 优先级高。

> CLI 各步骤"什么情况下会跳过"的逐项清单，见 [CLI 交互式手册](cli-manual.md)。

---

## DEFAULT_CONFIG 全字段参考

下面按功能分组列出 `DEFAULT_CONFIG`（`default_config.py:71-164`）的全部字段。列名含义：**键名**是代码里访问用的字典键，**默认值**是未做任何覆盖时的值，**可覆盖**说明该字段能否被环境变量或 CLI flag 覆盖。

### 路径配置

| 键名 | 默认值 | 可覆盖 | 说明 |
|------|--------|--------|------|
| `project_dir` | 框架安装目录（`default_config.py:72`） | 否 | 框架自身代码所在路径，一般无需改 |
| `results_dir` | `~/.tradingagents/logs` | `TRADINGAGENTS_RESULTS_DIR` | 报告与运行日志根目录 |
| `data_cache_dir` | `~/.tradingagents/cache` | `TRADINGAGENTS_CACHE_DIR` | OHLCV 等数据缓存，加速重复查询 |
| `memory_log_path` | `~/.tradingagents/memory/trading_memory.md` | `TRADINGAGENTS_MEMORY_LOG_PATH` | 记忆日志路径，详见 [记忆系统](../06-internals/memory-system.md) |
| `memory_log_max_entries` | `None` | 否（仅代码改） | `None` 禁用轮转；设了整数后，超过限制会修剪最老的**已解决**条目，**pending 条目永不修剪** |

注意：这三个路径变量（`RESULTS_DIR` / `CACHE_DIR` / `MEMORY_LOG_PATH`）**不走** `_ENV_OVERRIDES` 机制，而是在 `DEFAULT_CONFIG` 字面量里直接 `os.getenv(...)`（`default_config.py:73-75`），类型只接受字符串。

### LLM 设置（`default_config.py:81-102`）

| 键名 | 默认值 | 可覆盖 | 说明 |
|------|--------|--------|------|
| `llm_provider` | `"openai"` | `TRADINGAGENTS_LLM_PROVIDER` | 20 个供应商之一，详见 [LLM 客户端](../05-data-and-llm/llm-clients.md) |
| `deep_think_llm` | `"gpt-5.5"` | `TRADINGAGENTS_DEEP_THINK_LLM` | 给两个裁判（Research Manager、Portfolio Manager）用的强模型 |
| `quick_think_llm` | `"gpt-5.4-mini"` | `TRADINGAGENTS_QUICK_THINK_LLM` | 给分析师和辩手用的快模型，省钱 |
| `backend_url` | `None` | `TRADINGAGENTS_LLM_BACKEND_URL` | `None` 时每个 provider 用各自默认端点；写死一个 provider 的 URL 会"泄漏"到别的 provider（`default_config.py:84-89` 注释） |
| `google_thinking_level` | `None` | `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` | Gemini 思考深度，如 `"high"`、`"minimal"` |
| `openai_reasoning_effort` | `None` | `TRADINGAGENTS_OPENAI_REASONING_EFFORT` | OpenAI 推理强度，`"low"` / `"medium"` / `"high"` |
| `anthropic_effort` | `None` | `TRADINGAGENTS_ANTHROPIC_EFFORT` | Anthropic 推理强度，`"low"` / `"medium"` / `"high"` |
| `temperature` | `None` | `TRADINGAGENTS_TEMPERATURE` | 采样温度。`default_config.py:96-98` 注释明确：推理模型基本忽略它，且没有任何设置能让 LLM 输出跨运行完全一致 |
| `llm_max_retries` | `None` | `TRADINGAGENTS_LLM_MAX_RETRIES` | SDK 重试预算。`None` 用 SDK 默认（通常 2）；提高以撑过限流部署下的 429 突发（`default_config.py:100-102`） |

### 运行设置

| 键名 | 默认值 | 可覆盖 | 说明 |
|------|--------|--------|------|
| `checkpoint_enabled` | `False`（`default_config.py:105`） | `TRADINGAGENTS_CHECKPOINT_ENABLED`、`--checkpoint`/`--no-checkpoint` | 断点续跑开关，详见 [断点续跑](../06-internals/checkpointing.md) |
| `output_language` | `"English"`（`default_config.py:108`） | `TRADINGAGENTS_OUTPUT_LANGUAGE` | 整条流水线的输出语言（含分析师报告、辩论、最终决策） |

### 辩论设置（`default_config.py:110-112`）

| 键名 | 默认值 | 可覆盖 | 说明 |
|------|--------|--------|------|
| `max_debate_rounds` | `1` | `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | 多空辩论轮数，Bull 和 Bear 各发言一次算一轮 |
| `max_risk_discuss_rounds` | `1` | `TRADINGAGENTS_MAX_RISK_ROUNDS` | 风控三方讨论轮数 |
| `max_recur_limit` | `100` | 否（仅代码改） | LangGraph 递归上限，超过会抛异常；一般不动 |

辩论机制的数学和状态机细节见 [辩论机制](../04-graph-and-agents/debate-mechanism.md)。

### 新闻与数据设置（`default_config.py:114-127`）

| 键名 | 默认值 | 可覆盖 | 说明 |
|------|--------|--------|------|
| `news_article_limit` | `20` | 否（仅代码改） | 单只 ticker 的新闻抓取上限 |
| `global_news_article_limit` | `10` | 否（仅代码改） | 宏观/全局新闻抓取上限 |
| `global_news_lookback_days` | `7` | 否（仅代码改） | 宏观新闻回看天数 |
| `global_news_queries` | 5 个宏观查询词（见下） | 否（仅代码改） | `get_global_news` 用的搜索词列表 |

`global_news_queries` 默认值（`default_config.py:121-127`）：

```python
"global_news_queries": [
    "Federal Reserve interest rates inflation",
    "S&P 500 earnings GDP economic outlook",
    "geopolitical risk trade war sanctions",
    "ECB Bank of England BOJ central bank policy",
    "oil commodities supply chain energy",
],
```

想扩展地理或行业覆盖，只能改代码——这些字段没有对应的环境变量。

### Data Vendor 配置（`default_config.py:128-144`）

这是双层结构：**类别级**（`data_vendors`）给一类工具设默认供应商，**工具级**（`tool_vendors`）给单个工具做更细的覆盖，工具级优先级高于类别级。

**`data_vendors`（类别级，`default_config.py:133-140`）**：

| 类别键 | 默认值 | 可选供应商 | 说明 |
|--------|--------|-----------|------|
| `core_stock_apis` | `yfinance` | `alpha_vantage`、`yfinance` | 核心股票数据接口 |
| `technical_indicators` | `yfinance` | `alpha_vantage`、`yfinance` | 技术指标 |
| `fundamental_data` | `yfinance` | `alpha_vantage`、`yfinance` | 基本面数据 |
| `news_data` | `yfinance` | `alpha_vantage`、`yfinance` | 新闻数据 |
| `macro_data` | `fred` | `fred`（需 `FRED_API_KEY`） | 宏观经济数据 |
| `prediction_markets` | `polymarket` | `polymarket`（免 Key） | 预测市场 |

**`tool_vendors`（工具级，`default_config.py:142-144`）**：默认是空 dict，留作覆盖入口：

```python
"tool_vendors": {
    # "get_stock_data": "alpha_vantage",  # 覆盖该工具的类别默认
},
```

#### 双层配置示例

下面三段展示同一类配置的三种写法，按需挑一种。配置块写在 Python 代码里（`DEFAULT_CONFIG` 字面量或运行前手动改 dict），不是 `.env`——`data_vendors` / `tool_vendors` 没有环境变量入口。

```python
# 写法 1：类别级，所有核心股票接口走 Alpha Vantage
config["data_vendors"] = {
    "core_stock_apis":   "alpha_vantage",
    "technical_indicators": "alpha_vantage",
    "fundamental_data":  "yfinance",      # 基本面仍用 yfinance
    "news_data":         "yfinance",
    "macro_data":        "fred",
    "prediction_markets": "polymarket",
}
```

```python
# 写法 2：有序 fallback 链。yfinance 失败时回退到 alpha_vantage
# 注意：框架不会把请求悄悄路由到你没列的供应商
config["data_vendors"] = {
    "core_stock_apis":      "yfinance,alpha_vantage",
    "technical_indicators": "yfinance,alpha_vantage",
    "fundamental_data":     "yfinance,alpha_vantage",
    "news_data":            "yfinance,alpha_vantage",
    "macro_data":           "fred",
    "prediction_markets":   "polymarket",
}
```

```python
# 写法 3：类别保持默认，仅对单个工具做工具级覆盖
config["data_vendors"] = {
    "core_stock_apis": "yfinance",
    "technical_indicators": "yfinance",
    "fundamental_data": "yfinance",
    "news_data": "yfinance",
    "macro_data": "fred",
    "prediction_markets": "polymarket",
}
config["tool_vendors"] = {
    "get_stock_data": "alpha_vantage",  # 只让这一个工具用 Alpha Vantage
}
```

一个关键行为（`default_config.py:130-132` 注释）：你填的值就是**确切的 vendor 链**，框架不会把请求悄悄路由到你没写的供应商。想要 fallback 就显式写成逗号分隔链，或写 `"default"` 用全部可用供应商。Vendor chain、fallback 和优雅降级的完整机制见 [数据供应商路由](../05-data-and-llm/data-vendors.md)。

### Benchmark 配置（`default_config.py:145-163`）

反思层在算 alpha 时需要一个基准指数。`benchmark_ticker` 优先级最高，设了就全局生效；不设（`None`）则按 ticker 的交易所后缀在 `benchmark_map` 里自动匹配。

| 键名 | 默认值 | 可覆盖 | 说明 |
|------|--------|--------|------|
| `benchmark_ticker` | `None`（`default_config.py:151`） | `TRADINGAGENTS_BENCHMARK_TICKER` | 设了就覆盖所有后缀检测，全局统一基准 |
| `benchmark_map` | 见下表 | 否（仅代码改） | 后缀 → 基准指数的自动映射 |

**`benchmark_map` 完整映射表**（`default_config.py:152-163`）：

| Ticker 后缀 | 基准 ticker | 代表指数 |
|------------|------------|---------|
| `.NS` | `^NSEI` | 印度 NSE（Nifty 50） |
| `.BO` | `^BSESN` | 印度 BSE（Sensex） |
| `.T` | `^N225` | 东京（日经 225） |
| `.HK` | `^HSI` | 香港（恒生指数） |
| `.L` | `^FTSE` | 伦敦（富时 100） |
| `.TO` | `^GSPTSE` | 多伦多（TSX 综合指数） |
| `.AX` | `^AXJO` | 澳大利亚（ASX 200） |
| `.SS` | `000001.SS` | 上海（上证综指） |
| `.SZ` | `399001.SZ` | 深圳（深证成指） |
| `""`（无后缀） | `SPY` | 美股默认，反思标签读作 "Alpha vs SPY" |

设计取舍（`default_config.py:146-150` 注释）：SPY 保留为美股默认，是为了让反思标签在美股上稳定显示 "Alpha vs SPY"；非美股 ticker 自动切到对应区域指数，不用手动改。

---

## 环境变量参考

环境变量分两组：走 `_ENV_OVERRIDES` 映射的，和在 `DEFAULT_CONFIG` 里直接 `os.getenv` 的。

### `_ENV_OVERRIDES` 映射（`default_config.py:10-28`）

共 14 个变量。类型强制（`_coerce`，`default_config.py:35-55`）按 `DEFAULT_CONFIG` 里现有默认值的类型推断：bool 默认就转 bool、int 转 int、float 转 float、其余当字符串。**非法值会直接报错，不会静默回退**——拼错的布尔（比如 `treu`）或非数字的 int 会在启动时抛出，避免无人值守运行被悄悄错误配置。

| 环境变量 | 对应配置键 | 类型 | 示例值 |
|---------|-----------|------|--------|
| `TRADINGAGENTS_LLM_PROVIDER` | `llm_provider` | str | `anthropic` |
| `TRADINGAGENTS_DEEP_THINK_LLM` | `deep_think_llm` | str | `claude-sonnet-4-5` |
| `TRADINGAGENTS_QUICK_THINK_LLM` | `quick_think_llm` | str | `gpt-5.4-mini` |
| `TRADINGAGENTS_LLM_BACKEND_URL` | `backend_url` | str | `http://localhost:11434/v1` |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | `output_language` | str | `Chinese` |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | `max_debate_rounds` | int | `3` |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | `max_risk_discuss_rounds` | int | `2` |
| `TRADINGAGENTS_CHECKPOINT_ENABLED` | `checkpoint_enabled` | bool | `true`（接受 `true/1/yes/on` 与 `false/0/no/off`） |
| `TRADINGAGENTS_BENCHMARK_TICKER` | `benchmark_ticker` | str | `SPY` |
| `TRADINGAGENTS_TEMPERATURE` | `temperature` | float | `0.0` |
| `TRADINGAGENTS_LLM_MAX_RETRIES` | `llm_max_retries` | int | `6` |
| `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` | `google_thinking_level` | str | `high` |
| `TRADINGAGENTS_OPENAI_REASONING_EFFORT` | `openai_reasoning_effort` | str | `medium` |
| `TRADINGAGENTS_ANTHROPIC_EFFORT` | `anthropic_effort` | str | `high` |

布尔值大小写不敏感，`_coerce` 会先 `.strip().lower()` 再比对（`default_config.py:42-50`）。

### 路径类环境变量（直接 `os.getenv`）

这三个不走 `_ENV_OVERRIDES`，而是直接写在 `DEFAULT_CONFIG` 字面量里（`default_config.py:73-75`），只接受字符串，没有类型强制：

| 环境变量 | 对应配置键 | 默认值 |
|---------|-----------|--------|
| `TRADINGAGENTS_RESULTS_DIR` | `results_dir` | `~/.tradingagents/logs` |
| `TRADINGAGENTS_CACHE_DIR` | `data_cache_dir` | `~/.tradingagents/cache` |
| `TRADINGAGENTS_MEMORY_LOG_PATH` | `memory_log_path` | `~/.tradingagents/memory/trading_memory.md` |

### LLM API Key（来自 `.env.example`）

`.env.example` 列了 16 个 provider 的 API Key，按你实际用的 provider 填一个或几个即可：

```env
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
XAI_API_KEY=
DEEPSEEK_API_KEY=
DASHSCOPE_API_KEY=
DASHSCOPE_CN_API_KEY=
ZHIPU_API_KEY=
ZHIPU_CN_API_KEY=
MINIMAX_API_KEY=
MINIMAX_CN_API_KEY=
OPENROUTER_API_KEY=
MISTRAL_API_KEY=
MOONSHOT_API_KEY=
GROQ_API_KEY=
NVIDIA_API_KEY=
```

数据供应商里，`FRED_API_KEY` 是免费的（[申请地址](https://fred.stlouisfed.org/docs/api/api_key.html)），想用 `macro_data: fred` 就必须配。

可选的几个非主流入口：

| 变量 | 用途 |
|------|------|
| `OPENAI_COMPATIBLE_API_KEY` | 自定义 OpenAI 兼容端点（vLLM、LM Studio、llama.cpp），配合 provider `openai_compatible` |
| `AWS_BEARER_TOKEN_BEDROCK` / `AWS_DEFAULT_REGION` / `AWS_PROFILE` | Bedrock 鉴权，Bearer token 优先于 AWS 凭证链 |
| `OLLAMA_BASE_URL` | 远程 Ollama 服务器，默认 `http://localhost:11434/v1` |

本地模型接入的完整步骤见 [本地模型部署](local-models.md)。

---

## 典型配置场景

### 场景 1：最小配置（刚装好，能跑就行）

目标：用默认值跑出第一份报告，只动必须动的。

```env
# .env
OPENAI_API_KEY=sk-...
```

只填一个 Key，其余全用 `DEFAULT_CONFIG` 默认值（`gpt-5.5` + `gpt-5.4-mini`、英文输出、Shallow 一轮辩论）。这一组适合先验证环境通不通，再逐步加配置。

### 场景 2：省钱配置（高频回测，控制 Token 成本）

目标：把模型换便宜、辩论轮数压到最低、新闻条数减半。

```env
# .env
OPENAI_API_KEY=sk-...

# 用最便宜的快模型做主力，deep 模型也降一档
TRADINGAGENTS_QUICK_THINK_LLM=gpt-5.4-mini
TRADINGAGENTS_DEEP_THINK_LLM=gpt-5.4

# 辩论各一轮就够了（其实这也是默认值，这里显式写出来便于后续调）
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1

# 限流严重的部署把重试预算拉高，避免跑一半因 429 中断
TRADINGAGENTS_LLM_MAX_RETRIES=6
```

想进一步省，可以把 `news_article_limit` 和 `global_news_article_limit` 在代码里调小（这两个没有环境变量）。注意 `max_debate_rounds` 和 `max_risk_discuss_rounds` 一旦在这里设了，CLI 问卷里的 Shallow/Medium/Deep 选择对它们就不再生效（参见前文"配置优先级"那节的坑）。

### 场景 3：中文输出配置（团队都看中文）

目标：整条流水线统一中文输出——分析师报告、多空辩论、风险辩论、最终决策。

```env
# .env
OPENAI_API_KEY=sk-...
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
```

设了之后，CLI 的步骤 3（输出语言）会自动跳过。`output_language` 对所有产出报告内容的 Agent 生效（分析师、研究员、辩手、裁判、交易员），非英文运行产出的是完全本地化的报告。多语言支持的完整说明见 [多语言输出](output-language.md)。

### 场景 4：无人值守 / CI 自动化

目标：脚本里一条命令跑完，不弹任何交互问卷。

```env
# .env
OPENAI_API_KEY=sk-...
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=gpt-5.5
TRADINGAGENTS_QUICK_THINK_LLM=gpt-5.4-mini
TRADINGAGENTS_OUTPUT_LANGUAGE=English
TRADINGAGENTS_CHECKPOINT_ENABLED=true
TRADINGAGENTS_OPENAI_REASONING_EFFORT=medium
```

把这些都设上，CLI 对应的交互步骤会全部跳过，`tradingagents analyze --checkpoint` 就能一条命令跑完。配合 `--clear-checkpoints` 可以在 CI 里每次干净起步。断点续跑的 thread_id 签名和恢复策略见 [断点续跑](../06-internals/checkpointing.md)。

---

## 常见误区

### 误区 1：在 `.env` 里写 `data_vendors`

**错误理解**：`data_vendors` 是配置项，应该能通过 `TRADINGAGENTS_DATA_VENDORS` 之类环境变量覆盖。

**实际情况**：`data_vendors` 和 `tool_vendors` 没有环境变量入口。`_ENV_OVERRIDES` 表（`default_config.py:10-28`）里压根没有它们，只能改 `DEFAULT_CONFIG` 字面量或在运行前改 config dict。想换数据源，要么改代码，要么用 Python API 传 config（见 [Python API](python-api.md)）。

### 误区 2：交互问卷选了就一定生效

**错误理解**：问卷是最后一步，选 Deep 就一定是 5 轮辩论。

**实际情况**：如果 `TRADINGAGENTS_MAX_DEBATE_ROUNDS` 已设，`_build_run_config`（`cli/main.py:971-972`）会跳过写入，env 值保留。想让问卷说了算，就别设这个 env。

### 误区 3：设了 `temperature=0` 就能复现

**错误理解**：把温度拉到 0，每次运行结果就完全一致。

**实际情况**：`default_config.py:96-98` 注释明确写了，推理模型基本忽略 `temperature`，而且没有任何设置能让 LLM 输出跨运行完全 bit 一致。降温度只能减少模型波动，不能保证复现。

### 误区 4：把一个 provider 的 `backend_url` 写死

**错误理解**：默认 `backend_url` 是 `None` 不方便，直接填一个 OpenAI 的 URL 省事。

**实际情况**：`default_config.py:84-89` 注释解释，写死一个 provider 的 URL 会"泄漏"到别的 provider（比如把 OpenAI 的 `/v1` 转发给 Gemini，导致请求 URL 畸形）。让 `backend_url` 保持 `None`，每个 provider 会用自己的默认端点；只有用 OpenAI 兼容端点这类场景才显式设。

---

## 总结速查

```bash
# 看当前生效的环境变量（启动前自检）
env | grep TRADINGAGENTS_

# 看某个 TRADINGAGENTS_* 是否会触发类型强制报错
# bool：只接受 true/1/yes/on 和 false/0/no/off（大小写不敏感）
# int/float：非数字会在启动时抛 ValueError
```

四条最常用的判断：

1. 想固定某项 → 写 `.env`，对应交互步骤自动跳过。
2. 想临时盖 checkpoint → `--checkpoint` / `--no-checkpoint`，优先级最高。
3. 想换数据源 → 改 `data_vendors`，没有环境变量入口。
4. 遇到限流 → 调高 `TRADINGAGENTS_LLM_MAX_RETRIES`。

---

## 下一步

| 推荐内容 | 难度 | 适合谁 |
|---------|------|-------|
| [Python API](python-api.md) | ⭐⭐ | 想编程方式传 config dict、做批量回测的开发者 |
| [CLI 交互式手册](cli-manual.md) | ⭐⭐ | 想逐项核对交互步骤跳过条件的使用者 |
| [数据供应商路由](../05-data-and-llm/data-vendors.md) | ⭐⭐⭐ | 想搞懂 vendor chain、fallback 和优雅降级机制的人 |
| [断点续跑](../06-internals/checkpointing.md) | ⭐⭐⭐ | 想理解 `checkpoint_enabled` 背后的 thread_id 与恢复策略 |

---

**文档元信息**
难度：⭐⭐ | 类型：核心概念参考 | 对应源码：`tradingagents/default_config.py`、`cli/main.py:961-988`、`.env.example`
