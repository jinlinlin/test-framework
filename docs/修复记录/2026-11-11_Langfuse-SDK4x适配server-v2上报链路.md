# 修复记录：Langfuse SDK 4.x 适配自托管 server v2 上报链路

## 元数据

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 类型 | fix |
| scope | agent |
| 关联 commit | 待提交 |
| 关联文档 | `docs/框架迁移过程文档/`（Langfuse 断链为源仓裸依赖隐雷在 4.x 环境引爆，非迁移引入） |

## 问题（为什么要动）

真实用例（INT-001 `test_paper_interpret_agent_trace`）在 Langfuse UI 中查不到任何轨迹。
前置探测确认两个独立断点：

1. **SDK API 断链**：源仓代码按 langfuse 2.x API 编写（`client.trace()` →
   `trace.span()/event()/generation()/score()/update()`），但源仓 `requirements.txt`
   中 langfuse 为裸条目无版本号，当前环境实装 **4.15.6**——`trace()`/`start_as_current_span()`
   均已不存在，上报调用点全部抛 `AttributeError` 被静默吞掉，写入量恒为 0。
2. **协议代差（写代码途中才暴露的架构级问题）**：4.x 高层 `start_observation` 走
   OTLP 导出（`/api/public/otel/v1/traces`），**要求 server v3**；而自托管 compose
   （`E:\uniresearch-test\agent-test\docker`）用的是 `langfuse/langfuse:2` 镜像，
   无 OTel 端点，节点会静默丢失。

影响面：trace 对象操作 100% 集中于 `core/clients/langfuse_integration.py` 单文件
（conftest 钩子与用例只透传句柄），故改造收敛在该文件，上层零改动。

## 修复（动了什么）

| 文件 | 变更 | 说明 |
|---|---|---|
| `test-cases/agent/core/clients/langfuse_integration.py` | 修改（+148/-16 中的主体） | 新增 `_utc_now_iso()` / `_make_ingestion_event()` / `_Trace2xHandle` 兼容层；重写 `start_trace`；`__init__` 加 `timeout=10` |
| `test-cases/agent/config/.env.example` | 修改 | Langfuse 配置注释更新：4.x 已适配 + 熔断行为说明 |

关键设计决策：

- **上报统一改走 `api.ingestion.batch` 五类事件**（trace-create / span-create /
  event-create / generation-create / score-create）——server v2 起就稳定的公开协议，
  4.15.6 SDK 内部（`create_score` → `add_score_task`）同样用它（源码实证）。
  否决第一版基于 `start_observation` 的 OTLP 方案（见「问题」第 2 点）。
- **事件用普通 dict 而非 pydantic 强类型类**：实测 `IngestionEvent` 的 pydantic 类
  序列化后缺 `type` 鉴别字段；SDK 内部就是 `{"id","timestamp","type","body"}` dict
  直送 batch，body 键用 camelCase（traceId/startTime/endTime）。
- **`_Trace2xHandle` 保留 2.x `StatefulTraceClient` 方法面**（span/event/generation/score/update），
  版本差异收敛于单类内，上层 add_*/report_trace/conftest 五钩子零改动。
- **trace 语义**：`create_trace_id()` 生成 id，节点以 body.traceId 跨调用关联同一 trace
  （trace 只是事件容器，实测根 span end 后仍可挂）；trace 级 name/tags/metadata 只能经
  trace-create 落库；`update()` 本地累积后整体重发 trace-create，防覆盖丢字段。
- **session 级熔断**：首版 `start_trace` 失败后下条重试，遇容器不可达时 fern 默认
  重试+退避把 164 条离线批拖到 8 分钟以上不完——改为一次失败即 `_enabled=False`
  并留痕打印（与 AttributeError 分支同「禁用必须留痕」原则）；`timeout=10` 兜底
  host 黑洞挂起（4.15.6 无 `max_retries` 参数）。

## 验证（怎么证明修好了）

| 命令 / 途径 | 结果 |
|---|---|
| 拦截式验证（mock ingestion.batch，断言 dict 事件形状） | 7/7 全绿；事件统计 trace-create 5 / span-create 5 / generation-create 1 / score-create 20 / event-create 3 |
| 离线回归 `python -m pytest -m offline -q` | 164 passed / 9 deselected / 2.24s，基线无损（熔断生效不再拖批） |
| 冒烟 `_smoke_v2.py`（五类事件真实发往容器） | accepted: 5, errors: 0 |
| INT-001 真实跑 `pytest test_cases/paper_interpret/test_single_round.py::TestSingleRound::test_paper_interpret_agent_trace -v` | PASSED 123.96s，无熔断触发，控制台「Trace 数据已上报」 |
| server 侧 REST 读回（requests + Basic auth 直打 `/api/public/traces`、`/observations`） | trace `test_paper_interpret_agent_trace` 落库，tags 全齐（agent / paper / env:pre / model / judge / dataset）；observations 7 条（测试输入→SSE调用→工具调用→Token用量→AI回答→生成文档→执行摘要）；scores 2 条（test_passed / attempt_count） |

## 遗留 / 后续

- **八维 Judge 分本批未落库**：归因是用例自身该轮 Judge 评估未执行
  （`test_output/paper_interpret/*_judge.json` 记录「前置断言失败或代码未到达」），
  属用例评估路径问题，与上报链路无关（score-create 协议已由冒烟证明可用）。待另批深查。
- 4.x SDK 的 `auth_check()` / `api.trace.list` 读模型与 v2 server 响应结构不兼容，
  读回验证须走原始 REST。
- agent 依赖清单文件缺位：`langfuse>=4,<5` 的版本钉目前仅记录于本文件 docstring 与
  `.env.example` 注释，待补充到依赖清单。
- `test_cases/robust/test_agent_robust.py` 5 条真实用例未打 `agent` 标记，
  精确离线口径暂须用 `-m offline` 而非 `-m "not agent"`。
