# 全维度工程化测试框架架构设计文档

# 1\. 项目简介

本项目是一套**工程化、模块化、配置驱动、多语言协同**的全场景自动化测试框架，统一支撑性能测试、接口测试、数据库测试、智能问答测试、安全测试等全类型测试能力。框架深度融合经典设计模式，采用分层解耦架构，支持 Python、Node\.js、Shell 三种语言独立运行与协同调度，具备高复用、高扩展、易维护、可插拔的工程特性，可适配各类后端、前端、中间件、智能应用的自动化测试与质量巡检场景。

# 2\. 核心能力与技术体系

## 2\.1 支持测试类型

框架标准化落地七大核心测试能力，覆盖性能、功能、安全三大测试领域，所有测试能力均基于统一抽象规范实现，支持配置化启用与参数自定义。

1. **网页性能测试**：基于 Playwright 实现网页自动化渲染、资源加载监控、Web Vitals 指标采集，集成 Lighthouse 完成综合性能评分与页面分析，全面覆盖前端性能评测场景。

2. **后端性能测试**：支持 Java、Go、Python、Node\.js 等多语言后端服务，提供 HTTP、gRPC 通用负载施压能力，可采集 CPU、内存、容器资源、JVM、Go pprof 等多维度运行指标。

3. **REST API 测试**：提供 Python、Node\.js 双引擎独立实现，支持接口自动构建、权限认证、限流控制、契约校验、Schema 验证，适配常规接口自动化与接口压测场景。

4. **数据库性能测试**：支持 MySQL、PostgreSQL、MongoDB、Redis 等主流数据库，内置数据库连接池、SQL 执行器、执行计划分析、索引优化建议能力，实现数据库查询性能专项测试。

5. **知识库问答测试**：面向 RAG 智能问答场景，提供检索效果测试、向量嵌入分析、问答质量评估、上下文有效性校验等专项评测能力。

6. **渗透测试**：内置 SQL 注入、XSS、路径遍历、命令注入、SSRF、XXE 等通用攻击载荷，实现自动化漏洞扫描、风险检测与安全测试报告生成。

7. **越权访问测试**：覆盖角色提升、会话固定、Token 重放、JWT 攻击、OAuth 攻击、IDOR 等主流越权漏洞检测场景，全方位校验系统权限控制安全性。

## 2\.2 核心技术栈

框架采用多语言分工协作架构，不同语言各司其职，支持独立运行与联动调用，兼顾开发效率与运行性能。

- **Python（核心主框架）**：承载框架核心抽象、测试引擎、工具封装、报告解析、插件管理、任务调度等主体能力，是框架的核心支撑语言。

- **Node\.js（高性能辅助引擎）**：独立实现高并发 API 测试、WebSocket 测试、gRPC 压测等高性能场景，可独立运行，也可被 Python 核心调度调用。

- **Shell（工程运维层）**：负责环境检测、依赖安装、进程管理、脚本调度、容器部署、资源监控等工程运维能力，支撑框架全流程自动化部署与运行。

## 2\.3 架构核心特性

- **设计模式工程化落地**：全框架统一应用单例、工厂、策略、适配器、观察者、责任链等十余种经典设计模式，代码结构规范统一。

- **分层解耦、职责单一**：严格按照分层架构设计，各层级独立迭代、独立替换，无强耦合依赖。

- **全量配置驱动**：测试场景、施压策略、校验规则、引擎参数均由配置控制，无需修改代码即可适配不同被测系统。

- **模块化高复用**：通用能力统一抽象封装，引擎、适配器、策略、报告器均可复用、可扩展、可替换。

- **可插拔扩展机制**：内置完整插件体系，支持用户自定义插件、自定义测试策略、自定义报告输出。

- **多语言协同兼容**：三种语言支持独立运行、互相调用、结果互通，适配不同业务技术栈。

# 3\. 完整工程目录结构

本章为框架**完整、无删减、原始工程目录**，所有文件夹、子目录、核心文件完整保留，层级对齐、注释规范，完整呈现框架工程化结构。

```Plain Text
uniplore-test-framework/
│
├── bootstrap/                                         # 启动引导层
│   ├── __init__.py
│   ├── bootstrapper.py                                # 启动器（单例模式）
│   ├── environment.py                                 # 环境检测与初始化
│   ├── dependency_checker.py                          # 依赖检查（Python/Node/Playwright）
│   └── classpath_loader.py                            # 动态类加载器
│
├── core/                                              # 核心抽象层（全部接口/抽象类）
│   ├── __init__.py
│   │
│   ├── container/                                     # IoC容器（依赖注入）
│   │   ├── __init__.py
│   │   ├── container.py                               # 核心容器（单例）
│   │   ├── service_registry.py                        # 服务注册
│   │   └── dependency_resolver.py                     # 依赖解析器
│   │
│   ├── interfaces/                                    # 所有接口定义（面向接口编程）
│   │   ├── __init__.py
│   │   ├── testable.py                                # 可测试接口（模板模式）
│   │   ├── adaptable.py                               # 可适配接口（适配器模式）
│   │   ├── reportable.py                              # 可报告接口
│   │   ├── configurable.py                            # 可配置接口
│   │   ├── executable.py                              # 可执行接口（命令模式）
│   │   ├── observable.py                              # 可观察接口（观察者模式）
│   │   ├── lifecycle.py                               # 生命周期接口
│   │   └── pluggable.py                               # 可插拔接口
│   │
│   ├── models/                                        # 领域模型（数据实体）
│   │   ├── __init__.py
│   │   ├── test_case.py                               # 测试用例模型
│   │   ├── test_suite.py                              # 测试套件模型（组合模式）
│   │   ├── test_plan.py                               # 测试计划
│   │   ├── test_result.py                             # 测试结果
│   │   ├── test_metrics.py                            # 测试指标
│   │   ├── test_report.py                             # 测试报告
│   │   ├── target_system.py                           # 被测系统模型
│   │   ├── execution_context.py                       # 执行上下文
│   │   └── enums.py                                   # 枚举定义
│   │
│   ├── pipeline/                                      # 管道执行引擎
│   │   ├── __init__.py
│   │   ├── pipeline.py                                # 管道（责任链模式）
│   │   ├── stage.py                                   # 管道阶段
│   │   ├── context.py                                 # 管道上下文
│   │   ├── filter.py                                  # 过滤器（过滤器模式）
│   │   └── hooks.py                                   # 钩子系统
│   │
│   ├── events/                                        # 事件系统（观察者模式）
│   │   ├── __init__.py
│   │   ├── event_bus.py                               # 事件总线（单例）
│   │   ├── event.py                                   # 事件基类
│   │   ├── listeners.py                               # 监听器注册
│   │   └── event_types.py                             # 事件类型定义
│   │
│   └── exceptions/                                    # 异常体系
│       ├── __init__.py
│       ├── base.py                                    # 基础异常
│       ├── config.py                                  # 配置异常
│       ├── execution.py                               # 执行异常
│       ├── adapter.py                                 # 适配器异常
│       └── plugin.py                                  # 插件异常
│
├── languages/                                         # 多语言桥接层（桥接模式）
│   ├── __init__.py
│   ├── bridge.py                                      # 桥接器基类
│   ├── bridge_factory.py                              # 桥接工厂（工厂模式）
│   │
│   ├── python/                                        # Python语言桥接
│   │   ├── __init__.py
│   │   ├── executor.py                                # Python执行器
│   │   ├── subprocess_runner.py                       # 子进程运行器
│   │   └── native_bridge.py                           # 原生桥接
│   │
│   ├── nodejs/                                        # Node.js语言桥接
│   │   ├── __init__.py
│   │   ├── executor.py                                # Node执行器
│   │   ├── node_runner.py                             # 运行Node脚本
│   │   ├── ipc_bridge.py                              # IPC通信桥接
│   │   ├── bridge.js                                  # Node端桥接脚本
│   │   └── package.json
│   │
│   └── shell/                                         # Shell语言桥接
│       ├── __init__.py
│       ├── executor.py                                # Shell执行器
│       ├── shell_runner.py                            # 运行Shell脚本
│       └── scripts/
│           └── common.sh
│
├── engines/                                           # 测试引擎层（策略模式）
│   ├── __init__.py
│   ├── base.py                                        # 引擎基类
│   ├── engine_factory.py                              # 引擎工厂（工厂模式）
│   ├── engine_registry.py                             # 引擎注册表
│   │
│   ├── web_performance/                               # ① 网页性能测试
│   │   ├── __init__.py
│   │   ├── engine.py                                  # 引擎主类（模板模式）
│   │   ├── playwright_client.py                       # Playwright客户端（适配器模式）
│   │   ├── page_analyzer.py                           # 页面分析器
│   │   ├── resource_monitor.py                        # 资源监控
│   │   ├── web_vitals.py                              # Web Vitals采集
│   │   ├── lighthouse_integration.py                  # Lighthouse集成
│   │   └── config_schema.py                           # 配置Schema
│   │
│   ├── backend_performance/                           # ② 后端性能测试（多语言）
│   │   ├── __init__.py
│   │   ├── engine.py                                  # 引擎主类
│   │   ├── http_loader.py                             # HTTP负载发生器
│   │   ├── grpc_loader.py                             # gRPC负载发生器
│   │   ├── resource_collector.py                      # 资源采集器（CPU/内存）
│   │   ├── jvm_monitor.py                             # JVM监控（Java）
│   │   ├── go_monitor.py                              # Go监控（pprof）
│   │   ├── node_monitor.py                            # Node.js监控
│   │   ├── python_monitor.py                          # Python监控
│   │   ├── container_monitor.py                       # 容器监控（Docker/K8s）
│   │   └── config_schema.py
│   │
│   ├── rest_api/                                      # ③ REST API测试
│   │   ├── __init__.py
│   │   ├── engine.py                                  # Python引擎
│   │   ├── engine.js                                  # Node.js引擎
│   │   ├── request_builder.py                         # 请求构建器（建造者模式）
│   │   ├── response_validator.py                      # 响应验证器（策略模式）
│   │   ├── auth_handler.py                            # 认证处理器
│   │   ├── rate_limiter.py                            # 限流器
│   │   ├── contract_tester.py                         # 契约测试
│   │   ├── schema_validator.py                        # Schema验证
│   │   └── config_schema.py
│   │
│   ├── database/                                      # ④ 数据库性能测试
│   │   ├── __init__.py
│   │   ├── engine.py                                  # 引擎主类
│   │   ├── connection_pool.py                         # 连接池管理（对象池模式）
│   │   ├── query_executor.py                          # 查询执行器
│   │   ├── explain_analyzer.py                        # 执行计划分析
│   │   ├── index_advisor.py                           # 索引建议
│   │   ├── dialect/                                   # 数据库方言（策略模式）
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── postgresql.py
│   │   │   ├── mysql.py
│   │   │   ├── mongodb.py
│   │   │   └── redis.py
│   │   └── config_schema.py
│   │
│   ├── knowledge_qa/                                  # ⑤ 知识库问答测试
│   │   ├── __init__.py
│   │   ├── engine.py                                  # 引擎主类
│   │   ├── qa_client.py                               # 问答客户端
│   │   ├── quality_evaluator.py                       # 质量评估器
│   │   ├── retrieval_tester.py                        # 检索测试
│   │   ├── embedding_analyzer.py                      # 嵌入向量分析
│   │   ├── rag_evaluator.py                           # RAG评估
│   │   ├── context_validator.py                       # 上下文验证
│   │   └── config_schema.py
│   │
│   ├── penetration/                                   # ⑥ 渗透测试
│   │   ├── __init__.py
│   │   ├── engine.py                                  # 引擎主类
│   │   ├── scanner.py                                 # 扫描器
│   │   ├── payloads/                                  # 攻击载荷（策略模式）
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── sql_injection.py
│   │   │   ├── xss.py
│   │   │   ├── path_traversal.py
│   │   │   ├── command_injection.py
│   │   │   ├── ssrf.py
│   │   │   └── xxe.py
│   │   ├── detector.py                                # 漏洞检测器
│   │   ├── reporter.py                                # 安全报告
│   │   └── config_schema.py
│   │
│   └── auth_bypass/                                   # ⑦ 越权访问测试
│       ├── __init__.py
│       ├── engine.py                                  # 引擎主类
│       ├── strategies/                                # 越权策略（策略模式）
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── role_escalation.py                     # 角色提升
│       │   ├── session_fixation.py                    # 会话固定
│       │   ├── token_replay.py                        # Token重放
│       │   ├── jwt_attack.py                          # JWT攻击
│       │   ├── oauth_attack.py                        # OAuth攻击
│       │   └── idor.py                                # IDOR
│       ├── auth_bypass_detector.py                    # 越权检测
│       └── config_schema.py
│
├── adapters/                                          # 适配器层（适配器模式）
│   ├── __init__.py
│   ├── base.py                                        # 适配器基类
│   ├── adapter_factory.py                             # 适配器工厂
│   │
│   ├── http/                                          # HTTP适配器
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── requests_impl.py                           # Requests实现
│   │   ├── httpx_impl.py                              # HTTPX实现
│   │   └── aiohttp_impl.py                            # aiohttp实现
│   │
│   ├── browser/                                       # 浏览器适配器
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── playwright_impl.py                         # Playwright实现
│   │   └── selenium_impl.py                           # Selenium实现（备用）
│   │
│   ├── database/                                      # 数据库适配器
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── asyncpg_impl.py                            # PostgreSQL
│   │   ├── aiomysql_impl.py                           # MySQL
│   │   ├── motor_impl.py                              # MongoDB
│   │   └── redis_impl.py                              # Redis
│   │
│   ├── messaging/                                     # 消息队列适配器
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── kafka_impl.py
│   │   └── rabbitmq_impl.py
│   │
│   └── load_generator/                                # 负载发生器适配器
│       ├── __init__.py
│       ├── adapter.py
│       ├── jmeter_impl.py                             # JMeter集成
│       ├── locust_impl.py                             # Locust集成
│       └── k6_impl.py                                 # K6集成
│
├── strategies/                                        # 策略层（策略模式）
│   ├── __init__.py
│   ├── base.py                                        # 策略基类
│   ├── strategy_factory.py                            # 策略工厂
│   │
│   ├── load/                                          # 负载策略
│   │   ├── __init__.py
│   │   ├── constant.py                                # 恒定负载
│   │   ├── ramp_up.py                                 # 逐步上升
│   │   ├── spike.py                                   # 尖峰负载
│   │   ├── soak.py                                    # 浸泡负载
│   │   ├── step.py                                    # 阶梯负载
│   │   └── wave.py                                    # 波浪负载
│   │
│   ├── validation/                                    # 验证策略
│   │   ├── __init__.py
│   │   ├── threshold.py                               # 阈值验证
│   │   ├── percentile.py                              # 百分位验证
│   │   ├── trend.py                                   # 趋势验证
│   │   └── custom.py                                  # 自定义验证
│   │
│   └── retry/                                         # 重试策略
│       ├── __init__.py
│       ├── fixed.py                                   # 固定间隔
│       ├── exponential.py                             # 指数退避
│       └── custom.py                                  # 自定义
│
├── reporters/                                         # 报告层（观察者模式）
│   ├── __init__.py
│   ├── base.py                                        # 报告器基类
│   ├── reporter_factory.py                            # 报告器工厂
│   ├── reporter_registry.py                           # 报告器注册表
│   │
│   ├── html/                                          # HTML报告
│   │   ├── __init__.py
│   │   ├── reporter.py
│   │   ├── templates/
│   │   │   ├── base.html
│   │   │   ├── summary.html
│   │   │   ├── detail.html
│   │   │   └── security.html
│   │   └── assets/
│   │       ├── css/
│   │       └── js/
│   │
│   ├── json/                                          # JSON报告
│   │   ├── __init__.py
│   │   └── reporter.py
│   │
│   ├── console/                                       # 控制台报告
│   │   ├── __init__.py
│   │   └── reporter.py
│   │
│   ├── allure/                                        # Allure集成
│   │   ├── __init__.py
│   │   └── reporter.py
│   │
│   └── external/                                      # 外部集成
│       ├── __init__.py
│       ├── grafana.py                                 # Grafana推送
│       ├── prometheus.py                              # Prometheus推送
│       ├── slack.py                                   # Slack推送
│       └── email.py                                   # 邮件报告
│
├── config/                                            # 配置管理层
│   ├── __init__.py
│   ├── manager.py                                     # 配置管理器（单例模式）
│   ├── loader.py                                      # 配置加载器（工厂模式）
│   ├── validator.py                                   # 配置验证器
│   ├── schema/                                        # 配置Schema定义
│   │   ├── __init__.py
│   │   ├── global.json
│   │   ├── test_type.json
│   │   ├── adapter.json
│   │   └── strategy.json
│   │
│   ├── environments/                                  # 环境配置
│   │   ├── __init__.py
│   │   ├── base.yaml
│   │   ├── dev.yaml
│   │   ├── test.yaml
│   │   ├── staging.yaml
│   │   └── production.yaml
│   │
│   ├── defaults/                                      # 默认配置
│   │   ├── __init__.py
│   │   ├── web.yaml
│   │   ├── backend.yaml
│   │   ├── api.yaml
│   │   ├── database.yaml
│   │   ├── knowledge.yaml
│   │   ├── penetration.yaml
│   │   └── auth_bypass.yaml
│   │
│   └── targets/                                       # 被测系统配置
│       ├── __init__.py
│       ├── system_a.yaml
│       ├── system_b.yaml
│       └── templates/
│           ├── web_target.yaml
│           ├── api_target.yaml
│           └── db_target.yaml
│
├── plugins/                                           # 插件系统（可插拔架构）
│   ├── __init__.py
│   ├── manager.py                                     # 插件管理器
│   ├── loader.py                                      # 插件加载器
│   ├── hook.py                                        # 插件钩子
│   ├── discovery.py                                   # 插件发现
│   │
│   ├── builtin/                                       # 内置插件
│   │   ├── __init__.py
│   │   ├── web_plugin.py
│   │   ├── api_plugin.py
│   │   └── security_plugin.py
│   │
│   └── custom/                                        # 用户自定义插件
│       └── .keep
│
├── schedulers/                                        # 调度层（命令模式）
│   ├── __init__.py
│   ├── base.py                                        # 调度器基类
│   ├── scheduler_factory.py                           # 调度器工厂
│   ├── sequential.py                                  # 顺序调度
│   ├── parallel.py                                    # 并行调度
│   ├── distributed.py                                 # 分布式调度
│   └── cron.py                                        # 定时调度
│
├── decorators/                                        # 装饰器层
│   ├── __init__.py
│   ├── timing.py                                      # @timing 计时
│   ├── retry.py                                       # @retry 重试
│   ├── rate_limit.py                                  # @rate_limit 限流
│   ├── circuit_breaker.py                             # @circuit_breaker 熔断
│   ├── cache.py                                       # @cache 缓存
│   ├── validate.py                                    # @validate 验证
│   ├── log.py                                         # @log 日志
│   └── metrics.py                                     # @metrics 指标
│
├── utils/                                             # 工具层
│   ├── __init__.py
│   ├── logger.py                                      # 日志工具
│   ├── logger.js                                      # Node日志
│   ├── metrics.py                                     # 指标工具
│   ├── data_factory.py                                # 数据工厂（工厂模式）
│   ├── file_handler.py                                # 文件处理
│   ├── network.py                                     # 网络工具
│   ├── async_utils.py                                 # 异步工具
│   ├── threading.py                                   # 线程/协程工具
│   ├── time_utils.py                                  # 时间工具
│   ├── crypto.py                                      # 加密工具
│   ├── validation.py                                  # 验证工具
│   └── shell_utils.sh                                 # Shell工具函数
│
├── extensions/                                        # 扩展层
│   ├── __init__.py
│   ├── service_discovery.py                           # 服务发现
│   ├── kubernetes.py                                  # K8s集成
│   ├── docker.py                                      # Docker集成
│   ├── service_mesh.py                                # Service Mesh集成
│   └── tracing.py                                     # 分布式追踪
│
├── scripts/                                           # 脚本层
│   ├── shell/                                         # Shell脚本
│   │   ├── run.sh                                     # 主入口
│   │   ├── setup.sh                                   # 环境安装
│   │   ├── cleanup.sh                                 # 清理
│   │   ├── health_check.sh                            # 健康检查
│   │   ├── monitor.sh                                 # 资源监控
│   │   ├── deploy.sh                                  # 部署
│   │   ├── backup.sh                                  # 备份
│   │   ├── docker_build.sh                            # Docker构建
│   │   └── k8s_deploy.sh                              # K8s部署
│   │
│   └── nodejs/                                        # Node.js脚本
│       ├── run.js                                     # Node主入口
│       ├── api_load_test.js                           # API负载测试
│       ├── websocket_test.js                          # WebSocket测试
│       ├── grpc_test.js                               # gRPC测试
│       └── performance_worker.js                      # 性能工作器
│
├── tests/                                             # 测试用例（框架自测）
│   ├── __init__.py
│   ├── unit/                                          # 单元测试
│   │   ├── __init__.py
│   │   ├── test_core/
│   │   ├── test_engines/
│   │   ├── test_adapters/
│   │   └── test_utils/
│   │
│   ├── integration/                                   # 集成测试
│   │   ├── __init__.py
│   │   └── test_end_to_end.py
│   │
│   └── fixtures/                                      # 测试数据
│       ├── __init__.py
│       ├── sample_configs/
│       └── mock_data/
│
├── docs/                                              # 文档
│   ├── architecture.md
│   ├── getting_started.md
│   ├── plugin_development.md
│   ├── api_reference.md
│   ├── configuration.md
│   ├── testing_guide.md
│   └── troubleshooting.md
│
├── logs/                                              # 日志
│   ├── .keep
│   ├── framework.log
│   └── execution/
│
├── reports/                                           # 报告输出
│   └── .keep
│
├── results/                                           # 测试结果
│   └── .keep
│
├── artifacts/                                         # 测试产物
│   └── .keep
│
├── nodejs_modules/                                    # Node.js模块
│   ├── package.json
│   ├── package-lock.json
│   ├── .eslintrc.js
│   ├── .prettierrc
│   └── node_modules/
│
├── python_modules/                                    # Python模块
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── setup.py
│   ├── pyproject.toml
│   └── .pylintrc
│
├── docker/                                            # Docker支持
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── .dockerignore
│
├── kubernetes/                                         # K8s支持
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
│
├── .env.example                                        # 环境变量示例
├── .gitignore
├── .flake8
├── .mypy.ini
├── CHANGELOG.md
├── LICENSE
└── README.md
```

# 4\. 设计模式落地体系

本框架深度落地软件工程经典设计模式，所有模式均对应具体代码模块，实现架构统一、代码解耦、逻辑复用，具体落地明细如下：

|设计模式|落地位置|核心用途|
|---|---|---|
|单例模式|core/container/container\.py、core/events/event\_bus\.py、config/manager\.py|保障容器、事件总线、配置管理器全局唯一，统一全局调度与配置|
|模板模式|core/interfaces/testable\.py、engines/base\.py|统一所有测试引擎的执行流程骨架，固定生命周期，子类仅实现差异化逻辑|
|策略模式|strategies/、engines/rest\_api/response\_validator\.py、各类引擎策略包|将可变算法独立封装，支持动态替换负载、校验、越权、攻击策略|
|工厂模式|engines/engine\_factory\.py、adapters/adapter\_factory\.py、reporters/reporter\_factory\.py|统一对象创建逻辑，屏蔽实例化细节，支持动态创建引擎、适配器、报告器|
|适配器模式|adapters/ 全目录|屏蔽不同中间件、工具、协议的接口差异，对外提供统一调用规范|
|观察者模式|core/events/、reporters/|实现事件驱动架构，测试执行事件自动触发报告、监控、日志等联动逻辑|
|责任链模式|core/pipeline/|将测试执行、过滤、钩子等流程串联，实现流程可扩展、可插拔、可拦截|
|命令模式|schedulers/|将测试任务封装为独立命令对象，支持顺序、并行、定时、分布式调度|
|建造者模式|engines/rest\_api/request\_builder\.py|封装复杂接口请求参数构建逻辑，支持灵活组装各类请求参数与请求头|
|组合模式|core/models/test\_suite\.py|支持测试套件嵌套组合，实现用例、套件、测试计划的层级结构化管理|
|桥接模式|languages/ 全目录|分离多语言抽象与具体实现，解耦语言类型与执行逻辑，便于扩展新语言|
|装饰器模式|decorators/|在不修改原有代码的前提下，动态新增计时、重试、限流、熔断、日志等切面能力|
|对象池模式|engines/database/connection\_pool\.py|实现数据库连接复用，减少频繁创建销毁连接的性能损耗|

# 5\. 多语言协同架构

框架采用**多语言解耦、可独立、可协同**的混合架构，三种语言各司其职，既可以独立运行完成专属任务，也可以互相调用、联动执行，最大化发挥各语言技术优势。

## 5\.1 各语言独立能力

|开发语言|核心入口|主要职责|独立运行能力|
|---|---|---|---|
|Shell|scripts/shell/run\.sh|环境初始化、依赖检测、进程管理、部署运维、资源监控、脚本调度|完全独立|
|Python|框架核心模块|核心引擎调度、全类型测试执行、插件管理、报告生成、规则校验|完全独立|
|Node\.js|scripts/nodejs/run\.js|高并发 API 压测、WebSocket 测试、gRPC 测试、异步高性能任务处理|完全独立|

## 5\.2 多语言协同机制

- Shell 作为总调度入口，可独立运维，也可按需调用 Python、Node\.js 执行对应测试任务

- Python 核心框架可通过子进程、IPC 通信调用 Node\.js 高性能引擎，弥补 Python 并发短板

- Node\.js 执行完成后输出标准化结果，由 Python 统一聚合、分析、生成完整测试报告

- 三种语言日志、执行上下文、配置体系完全统一，保证协同运行一致性

# 6\. 框架核心优势总结

- **极致工程化**：分层架构清晰、模块职责单一、目录规范统一，符合企业级工程落地标准

- **设计模式系统化**：十余种设计模式全覆盖，架构稳健、扩展性强、代码优雅可维护

- **高模块化解耦**：引擎、适配器、策略、插件完全解耦，支持单点替换与独立迭代

- **全配置驱动**：无需改代码，通过配置即可适配不同项目、不同环境、不同测试策略

- **可插拔扩展**：支持自定义插件、自定义测试策略、自定义报告输出，业务适配性极强

- **多语言最优协同**：扬长避短，Python 负责业务逻辑、Node 负责高并发、Shell 负责运维，架构最优

> （注：部分内容可能由 AI 生成）
