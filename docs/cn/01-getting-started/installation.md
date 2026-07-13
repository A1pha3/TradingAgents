# 安装指南 ⭐

> **目标读者**：第一次接触 TradingAgents 的用户
> **预计时间**：10 分钟
> **完成后你能**：成功安装 TradingAgents 并验证环境就绪

---

## 环境要求

| 项目 | 要求 | 说明 |
|------|------|------|
| Python | ≥ 3.10（推荐 3.12） | `pyproject.toml` 声明 `>=3.10`，3.12 在 CI 中验证 |
| 操作系统 | macOS / Linux / Windows | Windows 建议 WSL2，部分依赖（yfinance 网络层）在原生 Windows 偶发问题 |
| 网络访问 | 能访问 GitHub 和 PyPI | 数据源（yfinance、Alpha Vantage）和 LLM API 都需要外网 |
| 磁盘空间 | ~500 MB | 含依赖库和数据缓存目录 |

TradingAgents 的核心依赖包括：

- **langgraph ≥ 0.4.8**：状态图编排引擎
- **langchain-core ≥ 0.3.81**：LLM 抽象层
- **yfinance ≥ 1.4.1**：默认金融数据源
- **stockstats ≥ 0.6.5**：技术指标计算
- 完整依赖见 `pyproject.toml` 的 `[project.dependencies]`

---

## 三种安装方式

### 方式一：pip 安装（推荐大多数用户）

从 PyPI 安装稳定版本：

```bash
pip install tradingagents
```

安装后，`tradingagents` 命令行工具和 Python 包都可用。

### 方式二：从源码安装（适合想跟踪最新代码或参与贡献）

```bash
git clone https://github.com/A1pha3/TradingAgents.git
cd TradingAgents
pip install -e .
```

`-e`（editable）表示以可编辑模式安装，修改源码后立即生效，不用重新安装。

### 方式三：带可选依赖安装

TradingAgents 把一些非核心依赖拆成可选 extras，按需安装：

```bash
# Amazon Bedrock 支持（需要 boto3 / langchain-aws）
pip install tradingagents[bedrock]

# 开发依赖（ruff、pytest 等，贡献者用）
pip install tradingagents[dev]
```

---

## 验证安装

安装完成后，跑一行命令验证核心模块能正常加载：

```bash
python3 -c "import tradingagents; from tradingagents.graph.trading_graph import TradingAgentsGraph; print('OK')"
```

预期输出：

```
OK
```

如果看到 `ImportError` 或 `ModuleNotFoundError`，回到 [安装方式](#三种安装方式) 检查是否装对。

验证命令行工具：

```bash
tradingagents --help
```

预期看到 Typer 生成的帮助信息，列出 `analyze` 子命令。

---

## 配置 LLM API Key

TradingAgents 需要至少一个 LLM 供应商的 API Key 才能运行分析。最常见的选择是 OpenAI：

### 创建环境变量文件

在项目根目录创建 `.env` 文件（TradingAgents 在包导入时会自动加载它）：

```bash
# 复制示例文件
cp .env.example .env
```

然后用编辑器打开 `.env`，填入你的 Key：

```env
# 最小配置：一个 Key 就能跑
OPENAI_API_KEY=sk-你的真实key
```

`.env.example` 列出了所有支持的供应商 Key。你不需要全部配置——配一个就够跑通基础流程。

### 不想写文件？

也可以直接 export 环境变量：

```bash
export OPENAI_API_KEY=sk-你的真实key
```

两种方式等价。`.env` 文件的好处是配置持久化，不用每次开新终端都重新 export。

> 📖 完整的 API Key 配置（20 个供应商）参见 [LLM 客户端](../05-data-and-llm/llm-clients.md)。完整的 `TRADINGAGENTS_*` 配置项参见 [配置参考](../02-user-guide/configuration.md)。

---

## 配置数据源 Key（可选）

默认数据源 yfinance **不需要 Key**，开箱即用。以下数据源可选配置：

| 数据源 | 用途 | Key 获取 | 是否必须 |
|--------|------|---------|---------|
| yfinance | 股价、财报、新闻（默认） | 无需 Key | 默认启用 |
| FRED | 宏观经济指标（CPI、利率、就业） | [免费申请](https://fredaccount.stlouisfed.org/apikeys) | 可选 |
| Alpha Vantage | 备用价格/基本面源 | [免费申请](https://www.alphavantage.co/support/#api-key) | 可选 |
| Polymarket | 预测市场概率 | 无需 Key | 默认启用 |
| Reddit / StockTwits | 社交情绪 | 无需 Key | 默认启用 |

想启用 FRED 宏观数据，在 `.env` 里加：

```env
FRED_API_KEY=你的fred-key
```

---

## 常见安装问题

### 问题 1：`pip install` 报 yfinance 版本冲突

```
ERROR: Cannot install tradingagents because these package versions have conflicting dependencies.
```

**原因**：系统里已有的 yfinance 版本太旧。TradingAgents 要求 `yfinance >= 1.4.1`（修复了非 Date 索引列的兼容问题）。

**解决**：

```bash
pip install --upgrade yfinance
```

### 问题 2：`langgraph` 相关 ImportError

```
ImportError: cannot import name 'StateGraph' from 'langgraph'
```

**原因**：langgraph 版本低于 0.4.8，缺少 TradingAgents 依赖的 StateGraph API。

**解决**：

```bash
pip install --upgrade "langgraph>=0.4.8"
```

### 问题 3：命令行工具 `tradingagents` 找不到

**原因**：pip 安装后，console script 入口没被加入 PATH。

**解决**：确认 Python 的 Scripts 目录（Windows）或 bin 目录（macOS/Linux）在 PATH 中。或直接用模块方式调用：

```bash
python3 -m cli.main analyze
```

### 问题 4：`load_dotenv` 找不到 `.env`

TradingAgents 在 `tradingagents/__init__.py` 里用 `find_dotenv(usecwd=True)` 从当前工作目录向上查找 `.env`。如果你在项目外目录运行，它找不到你的 `.env`。

**解决**：`cd` 到你的项目目录（`.env` 所在目录）再运行，或者用绝对路径 export 环境变量。

---

## 卸载

```bash
pip uninstall tradingagents
```

TradingAgents 会在用户目录下创建数据和缓存目录（默认 `~/.tradingagents/`），卸载不会自动删除它们。如果要彻底清理：

```bash
rm -rf ~/.tradingagents
```

> ⚠️ 这会删除你的记忆日志（`~/.tradingagents/memory/trading_memory.md`），其中记录了历史决策和反思。删除前如有需要请先备份。

---

## 下一步

环境装好了，去 [快速开始](quickstart.md) 跑出你的第一份分析报告。

| 推荐内容 | 难度 | 说明 |
|---------|------|------|
| [快速开始](quickstart.md) ⭐ | ⭐ | 5 分钟跑通第一次分析 |
| [CLI 交互式手册](../02-user-guide/cli-manual.md) | ⭐⭐ | 搞懂每个交互选项 |
| [配置参考](../02-user-guide/configuration.md) | ⭐⭐ | 自定义所有配置项 |
