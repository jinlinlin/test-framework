# 黄金评测集（Golden Dataset）格式说明

黄金评测集用于 `judge` 质量评测：向被测 AI 接口发送 `question`，将回答与 `expected_points` 对照，由 Judge 模型按评分标准打分。

## 文件列表

| 文件 | 场景 | 样本数 | 说明 |
|------|------|--------|------|
| `paper_golden_v1.json` | 论文解读 | 20 | 覆盖 2 篇论文、8 种问题类型 + OOC 拒答口径；13 条通用评测样本 + 7 条用例锚点样本（note 字段标注所属用例） |
| `robust_golden_v1.json` | 鲁棒性测试 | 13 | 覆盖越权边界、提示词注入、异常输入 3 类场景 |

## 文件格式（论文解读场景）

评测集文件放置于本目录，使用 **JSON 数组**（`.json`），每个元素为一条评测样本：

```json
[
  {
    "id": "rag-001",
    "question": "本文献的研究方法是什么？",
    "expected_points": [
      "指出研究方法名称",
      "说明数据来源或实验对象",
      "提及研究的主要结论"
    ],
    "dataset_id": "1000000000",
    "pdf_path": "test_data/pdfs/sample-paper.pdf"
  }
]
```

### 字段说明（论文解读）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 样本唯一标识，建议 `<场景>-<序号>`（如 `rag-001`、`paper-002`），便于报告定位 |
| `question` | string | 是 | 发送给 AI 接口的用户提问 |
| `expected_points` | string[] | 是 | 期望回答覆盖的要点列表，Judge 模型逐条核对评分 |
| `dataset_id` | string | 条件必填 | 知识库 ID；`rag` 场景必填（对应 `.env` 的 `DATASET_ID`），其余场景可省略或为 `"0"` |
| `pdf_path` | string | 条件必填 | 测试论文 PDF 相对路径；`paper` 文献解读场景必填，指向 `test_data/pdfs/` 下素材 |

## 文件格式（鲁棒性测试场景）

鲁棒性黄金集使用扩展格式，包含场景分类和预期行为描述：

```json
[
  {
    "id": "robust-auth-001",
    "scenario": "越权边界",
    "description": "使用无效 token 创建论文会话",
    "input": "",
    "expected_behavior": "返回 HTTP 401 或 403 状态码，拒绝创建会话",
    "expected_points": [
      "服务端返回 401 或 403 状态码",
      "响应体不包含有效的 conversationId"
    ],
    "test_type": "negative",
    "category": "authorization"
  }
]
```

### 字段说明（鲁棒性测试）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 样本唯一标识，格式 `robust-<类型>-<序号>` |
| `scenario` | string | 是 | 场景大类：`越权边界` / `异常输入` / `正常成功` |
| `description` | string | 是 | 场景描述 |
| `input` | string | 条件必填 | 用户输入（提示词注入、异常输入场景必填） |
| `expected_behavior` | string | 是 | 预期行为描述 |
| `expected_points` | string[] | 是 | 预期检查点列表 |
| `test_type` | string | 是 | 测试类型：`positive` / `negative` / `edge_case` / `recovery` |
| `category` | string | 是 | 细分分类：`authorization` / `prompt_injection` / `abnormal_input` / `normal_success` |
| `verified_note` | string | 否 | 该预期对应的线上实测契约与校准时间，用于区分“已实测验证”与“仅凭设计推演”的验收标准 |

## 场景覆盖统计

| 场景类型 | 样本数 | 说明 |
|----------|--------|------|
| 正常成功（论文解读） | 13 | 覆盖核心贡献、方法、结论、数据、架构等 8 种问题 |
| 用例锚点（论文解读） | 7 | 逐字对齐 INT-002/003、E2E-P2~P5、INT-005 实际提问（含 OOC 拒答口径样本） |
| 越权边界 | 4 | 无效 token、伪造/不存在会话 ID、跨账号访问对端真实会话 |
| 提示词注入 | 3 | 忽略指令、角色扮演、结构化输出 |
| 异常输入 | 4 | 空输入、空白、特殊字符、超长文本 |
| 正常成功（SSE） | 2 | 流正常完成、断流恢复 |
| **合计** | **33** | **覆盖 3 大类场景** |

## 维护约定

- 一条样本只评测一个明确问题，避免多问题混合导致评分不可归因。
- `expected_points` 应客观可核验（事实性要点），避免主观表述（如"回答得好"）。
- 新增样本时保持 `id` 全局唯一；同场景编号连续递增。
- **用例锚点样本**（note 字段标注所属用例）：问题必须与用例代码中的提问逐字一致，改用例提问须同步改黄金集，否则 `get_expected_points` 未命中（会打印 `[黄金集] 警告`）并回退用例内置默认要点；拒答类样本的 expected_points 为拒答行为口径（标注【拒答口径】），Judge 在 instruction_follow 维度按此核对。
- 用例未命中黄金集的排查命令：临时脚本调 `get_expected_points(pdf, question)`，注意问题须逐字一致（含标点）。
- 鲁棒性场景的 `test_type` 用于区分正向测试（positive）和负向测试（negative/edge_case）。

## 加载与降级语义

- 统一加载入口：`core/utils/golden_dataset.py`（`read_golden_file` / `norm_pdf_path` / `find_golden_samples` / `warn_golden_miss`），paper 侧封装在 `test_cases/paper_interpret/test_paper_common.py`，robust 侧封装在 `test_cases/robust/test_agent_robust.py`，Langfuse 上报侧（`core/clients/langfuse_integration.py`）直接调 `find_golden_samples`。
- **匹配规则只有一份**：`find_golden_samples` 按「归一化 PDF 路径 + 问题逐字相等」筛选，用例侧 Judge 与 Langfuse 报告共用。不得在任一侧自行放宽（仅问题、问题子串）：问题文本在同一黄金集内会跨论文重复，放宽后一侧会拿到另一篇论文的 expected_points，或报告展示 Judge 从未用过的要点。
- `pdf_path` 与 `question` 缺一即视为未命中（空值在筛选语义下等于不筛选，会退化为“该论文/黄金集的第一条样本”）。
- 未命中黄金集时不再静默回退：默认打印 `[黄金集] 警告` 后回退用例内置默认值。
- 严格模式：`GOLDEN_STRICT=true`（config/.env 或环境变量）时，黄金集文件缺失或样本未命中直接抛错使用例失败，适用于回归门禁等不允许降级的场景。
- paper 样本的 `pdf_path` 匹配前会归一化为项目根下绝对路径（相对/绝对、正反斜杠、大小写差异均可命中）。
