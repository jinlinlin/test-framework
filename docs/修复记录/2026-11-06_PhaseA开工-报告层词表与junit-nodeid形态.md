# 修复记录：报告层状态词表错位与 junit nodeid 形态适配（Phase A 开工暴露）

## 元数据

| 项 | 值 |
|---|---|
| 日期 | 2026-11-06 |
| 类型 | fix |
| scope | framework |
| 关联 commit | `505cead`（feat(engines): Agent 行为测试薄壳引擎开工） |
| 关联文档 | `docs/框架迁移过程文档/agent-migration-plan.md` §六/§十（仅本地） |

## 问题（为什么要动）

薄壳引擎 AgentBehaviorEngine 首次把真实 `TestResult` 送入报告层时，
端到端测试暴露两处既有原型从未走过的接口裂缝：

1. **状态词表错位**：`JSONReporter.on_plan_completed` 统计只认
   `passed/failed/skipped`，而全链路 `TestResult.to_dict()` 输出的是
   `TestStatus` 枚举值 `pass/fail/skip/error`。引擎结果一进报告器，
   `totals` 中 passed/failed/skipped 静默归零——不崩溃、不报错，是
   Layer 2 契约产物最危险的失效形态。此错位自 P0-10 落地即存在，
   因当时回归用的是手写 `passed` 词表的桩数据而未暴露。
2. **junit 缺 `file` 属性**：实测 pytest 9（xunit2 family）的 junit.xml
   testcase 元素仅带 `classname`/`name`/`time`，无 `file` 属性；
   引擎按 `file::name` 匹配 nodeid 全部脱靶，批量执行 3 条用例收口
   结果 passed==0。

另有一处路径基准错位：pytest 子进程 `cwd=cases_dir`，相对 junit 路径
在子进程基准下解析、父进程按自身 CWD 查找，两端错位找不到文件。

## 修复（动了什么）

| 文件 | 变更 | 说明 |
|---|---|---|
| `test_framework/reporters/json/reporter.py` | 修改 | 统计改双词表兼容（`pass`/`passed` 等计入同一计数），`failures` 过滤同步补 `fail`；不改公开签名、旧调用方行为不变 |
| `test_framework/engines/agent_behavior/engine.py` | 新增 | `_match_case` 按三类候选形态匹配 nodeid：`file::name`（xunit1）、`classname 点路径→斜杠路径.py::name`（函数式）、`pkg/mod.py::Cls::name`（类式）；否决"只支持单一形态"（pytest 版本/family 输出本就不一致） |
| `test_framework/engines/agent_behavior/engine.py` | 新增 | `setup()` 中产物目录 `.resolve()` 绝对化，注释写明父子进程 cwd 错位根因 |
| `tests/unit/test_engines/test_agent_behavior.py` | 新增 | 含真实拉起 pytest 子进程的端到端用例（2 pass 1 fail），持续看住词表与形态两条缝 |

设计取舍：词表兼容而非统一到枚举值词表——报告层历史调用方可能已按
过去式词表传 dict，双词表是零破坏方案；单出口原则保持不变，summary.json
仍只由 JSONReporter 产出，引擎侧 `summary_writer.py` 仅薄封装。

## 验证（怎么证明修好了）

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/unit/test_engines/test_agent_behavior.py tests/unit/test_reporters -q` | 18 passed（含端到端 1 项、词表断言 `totals.passed==1` 用枚举值数据） |
| `python -m pytest tests/unit/test_engines tests/unit/test_reporters -q` | 19 failed / 31 passed，与既有基线完全一致，零新增失败 |
| `python -c "EngineFactory.create(TestType.AGENT_BEHAVIOR, …)"` | 创建 `AgentBehaviorEngine agent_behavior` 冒烟通过 |

## 遗留 / 后续

- 语言服务与 flake8 本机均不可用，静态检查由测试实测路径覆盖替代；
  CI 门槛期需恢复。
- 类式 classname 与包目录同名歧义（`a.b` 既是包也可能是模块）未穷尽
  区分，A′-3 移植真实 rag 用例如遇脱靶再补。
- pytest-xdist 并行下 junit 条目顺序/归属未实测（`use_xdist` 默认关）。
- `reports/json/report_{timestamp}.json` 与 summary.json 同批写出，
  Layer 3 聚合器接入时只消费后者。
