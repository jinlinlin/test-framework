# Phase 0 补充修复：Reporter 运行维度契约 + 引擎构造签名（P0-10、P0-6）

- **日期**: 2026-11-06
- **类型**: bugfix
- **scope**: framework
- **关联 commit**: 60bb92d fix(framework): P0-10/P0-6 补齐 Reporter 运行维度与引擎构造契约
- **关联文档**: `docs/框架迁移过程文档/phase-0-fixes.md` §八、§十二（含 §12.3.1 方案 A）

## 问题

1. **Reporter 层拿不到运行维度**：`BaseReporter.on_plan_completed(plan_name, results)`
   无 engine/run_id 参数，多引擎并行时报告无法区分来源；Layer 2 引擎级
   `summary.json`（Phase C 验收项 `artifacts/agent/{run_id}/summary.json`）没有框架侧出口；
   Layer 3 聚合器没有收集各引擎 summary 的回调入口。
2. **引擎构造契约与测试全面脱节**：`BaseEngine.__init__(config, container)` 是依赖注入
   必填参数，但 7 个引擎单测全部无参构造（`KnowledgeQAEngine()`），运行时
   `TypeError: missing 2 required positional arguments`。Phase A 的 AgentBehaviorEngine
   若照抄测试范式会延续错误构造姿势。

## 修复

**P0-10（Reporter 契约扩展，零破坏）**：

- `reporters/base.py`：`on_plan_completed` 新增 `run_id`/`engine` 两个 `Optional=None` 参；
  新增 `on_engine_completed` 默认 no-op 回调（仅 Layer 3 聚合器需覆盖）。
- `reporters/reporter_registry.py`：按 §12.3.1 **方案 A（inspect.signature 签名探测）**
  改造 `generate_all_reports`——声明了 `run_id` 或 `**kwargs` 的新 Reporter 透传新参数，
  旧签名 Reporter（含第三方/成员已写子类）只收旧参数，探测结果按类缓存；
  新增 `notify_engine_completed` 通知链。未采用无脑 kwargs 透传（会打破旧签名 override）。
- `reporters/json/reporter.py`：构造器新增实例级 `engine`/`run_id` 回退值；
  `on_plan_completed` 优先用透传值；engine+run_id 齐备时额外产出
  `artifacts/{engine}/{run_id}/summary.json`（Layer 2 契约，schema_version 1.0，
  含 totals/failures）；不提供运行维度时输出结构与旧版逐字段一致。
- allure/html/console 三个内置实现未改（旧签名走探测回退，特性不受影响；
  后续需要 engine/run 标签时按需升签名即可）。

**P0-6（改测试不改实现）**：

- 新增 `tests/unit/test_engines/conftest.py`：`mock_container`（MagicMock 模拟 IoC 容器，
  resolve 可用）与 `minimal_config` 两个夹具。
- 7 个引擎测试的 `test_engine_creation` 统一改为
  `Engine(config=minimal_config, container=mock_container)`，注释写明构造契约。
- 顺带修正 `test_rest_api.py` 的类名笔误：`RestApiEngine` → 实现中的真实类名 `RestAPIEngine`。

## 验证

- 新增回归 `tests/unit/test_reporters/test_registry_backward_compat.py`：**7 passed**，
  覆盖 Legacy/Modern/Kwargs 三签名并存分发、旧调用方不传新参、探测缓存、
  notify_engine_completed 链、JsonReporter 无运行维度时结构逐字段不变、
  summary.json 产出内容、经注册表透传的端到端路径。
- `pytest tests/unit/test_engines -k test_engine_creation`：**7/7 passed**
  （修复前 7/7 TypeError）。
- 六个 reporter 模块 import 健全；探测精确性实测：`probe json = True`、
  `probe allure = False`（未升签名的内置 Reporter 正确走旧路径）。
- 已知残留：`tests/unit/test_engines/` 全量仍有 19 failed，全部是**组件级**
  构造/import 问题（如 `PageAnalyzer()` 缺 page 参数、`WebVitals` 类名不存在），
  不在 P0-6"引擎构造签名"范围内，留待 CI 门槛建立时一并清理（见遗留）。

## 遗留

- 引擎测试目录剩余 19 个组件级失败：属"测试假设组件可无参构造"的另一层脱节，
  触发器为 CI 全量测试门槛（与 P0-4/5 同期），不阻塞 Agent 迁移。
- allure/html/console 未消费 run_id/engine：需要按运行分目录或打标签时再升签名
  （升级即自动生效，注册表探测已就绪）。
- `notify_engine_completed` 的调用方（编排器）在 Phase A/D 落地，本项只建通道。
- Layer 2 summary.json 的 schema 校验（`config/schema/`）按 phase-0-fixes §12.6
  缓解措施留待 Phase A 补充。
