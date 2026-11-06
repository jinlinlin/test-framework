# 修复记录：{一句话标题}

> 命名规则：`YYYY-MM-DD_{主题}.md`，与版本记录（`docs/版本记录/`，里程碑级）互补：
> 本目录记录**单次修复/改造**的过程与证据，版本记录汇总归纳已提交的历史。
> 本模板是框架级唯一模板，全测试类型共用，各分组不重复放置。

## 分组与命名约定

**分组 key 直接复用 commit scope 词表**（与 `version-record-generator` Skill 第二部分的
scope → 影响模块映射表同源），保证「commit scope → 记录分组 → 版本文档影响范围」三者
一一对应，不另造第二套分类法。

| 分组 | 含义 | 典型对象 |
|---|---|---|
| `framework` | 跨引擎的框架层改动 | `core/models/`、`engines/base.py`、`Container`/`EventBus`、`reporters/`、Phase 0 的 P0 项；过程规范与 Skill/文档治理亦归此类（类型记 `chore`/`docs`） |
| `agent` | Agent 行为测试 | `engines/agent_behavior/`、`adapters/sse/`、Judge/DeepEval |
| `api` | 接口自动化 | `engines/rest_api/` |
| `ui` | UI 自动化 | `engines/ui_automation/`、Playwright |
| `perf` | 性能测试 | `strategies/load/`、k6/Locust 转换器 |
| `security` | 越权/渗透 | `engines/auth_bypass/`、`engines/penetration/` |

**分层时机（攒够再拆，勿过度设计）**：当前阶段一律**平铺在本目录根**，靠文件名与下表
字段区分归属；当单个分组累积约 20 条以上、或根目录条目多到无法翻阅时，再用 `git mv`
升级为 `{group}/` 子目录——git 保留历史与 blame，属无损重构。

| 字段 | 取值 | 说明 |
|---|---|---|
| 类型 | `fix` / `feat` / `refactor` / `docs` / `chore` | 与 commit type 一致 |
| scope | 上表分组名之一 | 与 commit scope 一致，供版本记录归并 |

## 元数据

| 项 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| 类型 | fix |
| scope | framework |
| 关联 commit | `abc1234`（未提交则填「待提交」） |
| 关联文档 | `docs/框架迁移过程文档/phase-0-fixes.md` §P0-N（无则删本行） |

## 问题（为什么要动）

> 现象 + 根因 + 影响面。有产物/日志的贴路径，有历史误报的写明第几次运行暴露。

## 修复（动了什么）

> 文件级变更清单（新增/修改/删除），关键设计决策及理由（为什么这么做、否决过什么方案）。

| 文件 | 变更 | 说明 |
|---|---|---|
| `path/to/file.py` | 修改 | … |

## 验证（怎么证明修好了）

> 实测命令 + 结果证据（通过数/耗时/产物路径）。离线改动必须附离线回归结果。

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/unit -q` | … |

## 遗留 / 后续

> 未覆盖场景、已知风险、后续计划（无则写「无」）。
