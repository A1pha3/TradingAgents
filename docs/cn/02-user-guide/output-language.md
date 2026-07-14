# 多语言输出 ⭐

> **目标读者**：想让报告输出中文或其他语言的使用者
> **预计时间**：5 分钟
> **前置知识**：[CLI 交互式手册](cli-manual.md) ⭐⭐

---

## 一句话说明

TradingAgents 支持让整条分析流水线（含分析师报告、多空辩论、风险辩论和最终决策）输出 **11 种语言**，配置方式有两种：CLI 交互选择，或环境变量固定。

---

## 两种配置方式

### 方式一：CLI 交互选择

在 CLI 步骤 3 选择输出语言：

```
Step 3: Output Language
> Chinese (中文)
```

支持的语言（`cli/utils.py:653-688`）：

| 语言 | 配置值 | CLI 显示标签 |
|------|--------|-------------|
| 英语 | `English` | English (default) |
| 简体中文 | `Chinese` | Chinese (中文) |
| 日语 | `Japanese` | Japanese (日本語) |
| 韩语 | `Korean` | Korean (한국어) |
| 印地语 | `Hindi` | Hindi (हिन्दी) |
| 西班牙语 | `Spanish` | Spanish (Español) |
| 葡萄牙语 | `Portuguese` | Portuguese (Português) |
| 法语 | `French` | French (Français) |
| 德语 | `German` | German (Deutsch) |
| 阿拉伯语 | `Arabic` | Arabic (العربية) |
| 俄语 | `Russian` | Russian (Русский) |

CLI 菜单存的是英文词（`Chinese`、`Japanese` 等），显示时附带原生文字。环境变量和 Python API 传入的值要和这个英文词对齐。另外有一个 `Custom` 选项，可以输入任意语言名称（比如 `Turkish`、`Vietnamese`）。

### 方式二：环境变量固定

如果你不想每次都选，用环境变量一劳永逸：

```env
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
```

写入 `.env` 文件后，CLI 的步骤 3 会自动跳过。这个环境变量在 `DEFAULT_CONFIG` 构造时就被应用，等价于把默认值改成中文。

---

## 作用范围：全链路本地化

`output_language` 影响的是**所有输出会进入报告的 Agent**——不只是分析师报告和最终决策，还包括多空辩论和风险辩论。设成中文后，整条流水线都用中文产出，不会出现英文辩论加中文摘要的混杂。

```
                      output_language 的作用范围
                    ┌─────────────────────────────┐
                    │                             │
  分析师报告         │  ← 受 output_language 影响   │
  Bull/Bear 辩论     │  ← 受 output_language 影响   │
  风险辩论           │  ← 受 output_language 影响   │
  最终决策           │  ← 受 output_language 影响   │
  Tool 调用参数      │  ← 始终英文，不受影响        │
                    │                             │
                    └─────────────────────────────┘
```

Tool 调用本身是结构化的（函数名、参数键值），不受语言设置影响；Agent 的文本输出则全部跟随 `output_language`。

### 技术实现

语言指令通过 `get_language_instruction`（`agent_utils.py:52-65`）注入 prompt。当 `output_language` 是 English 时返回空串，不额外消耗 token；非 English 时返回 `" Write your entire response in {lang}."`，拼接到每个产出报告内容的 Agent 的 prompt 末尾——分析师、研究员、辩手、研究经理、交易员、组合经理都会收到。

这个设计的目标是让非英文用户拿到一份**完全本地化**的报告：辩论过程、裁决理由、最终决策都是同一种语言。代价是主流 LLM 的训练语料以英文为主，非英文下推理质量可能略低，但框架选择优先保证报告的一致性和可读性，而不是让用户在英文辩论和中文摘要之间来回切换。

---

## 验证语言设置生效

运行分析后，检查报告里的语言：

```bash
# 查看最终决策
cat reports/NVDA_*/5_portfolio/decision.md | head -20
```

如果开头是中文摘要，说明设置生效。

---

## 常见问题

### Q：设置了中文，但报告里混了英文术语

这是正常现象。金融领域的专有名词（PE ratio、MACD、Bollinger Bands 等）在中文报告里保留英文是常见做法，因为它们的中文翻译不统一。框架不会强行翻译这些术语。

### Q：不同语言会影响分析质量吗

可能略有影响。非英文下，LLM 的推理质量取决于其训练语料覆盖——主流模型在英文下最稳定，中文、日文等大语种通常也表现良好，但生僻语种可能在金融术语和结构化输出上退化。框架选择把整条流水线（含辩论）都切到目标语言，优先保证报告的一致性和可读性。如果你对推理质量的敏感度高于可读性，可以保持英文输出。但如果你用非英文的分析师报告做下游处理，需要注意分词和 NLP 工具的语言兼容性。

### Q：可以只把最终报告切中文、辩论保持英文吗

不可以。语言设置是全链路的——设成中文后，分析师、研究员、辩手、裁判、交易员的文本输出全部用中文，不存在"英文辩论 + 中文报告"的拆分模式。如果需要英文 trace 做研究，直接保持 `output_language=English` 即可。

---

## 下一步

| 推荐内容 | 难度 | 说明 |
|---------|------|------|
| [配置参考](configuration.md) | ⭐⭐ | 所有 TRADINGAGENTS_* 变量 |
| [CLI 交互式手册](cli-manual.md) | ⭐⭐ | 8 步问卷全解 |
| [设计哲学](../03-architecture/design-philosophy.md) | ⭐⭐⭐ | 理解这个设计背后的权衡 |
