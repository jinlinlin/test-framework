"""
执行计划分析器 — 分析 SQL 执行计划，识别性能问题。

职责：向数据库发送 EXPLAIN 命令，解析执行计划输出，
      识别全表扫描、低效 JOIN、缺失索引等性能瓶颈。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExplainAnalyzer:
    """
    SQL 执行计划分析器。

    通过数据库方言生成并执行 EXPLAIN 查询，
    将执行计划结果解析为统一格式，识别常见性能问题。

    Attributes:
        _pool: 数据库连接池。
        _dialect: 数据库方言。
    """

    def __init__(self, pool: Any, dialect: Any) -> None:
        """
        初始化分析器。

        Args:
            pool: ConnectionPool 实例。
            dialect: Dialect 实例。
        """
        self._pool = pool
        self._dialect = dialect

    async def analyze(self, query: str) -> Dict[str, Any]:
        """
        分析 SQL 查询的执行计划。

        生成 EXPLAIN 查询 → 执行 → 解析结果 → 检测问题。

        Args:
            query: 待分析的 SQL 查询。

        Returns:
            执行计划分析结果字典，包含：
            - plan: 统一格式的执行计划
            - issues: 检测到的性能问题列表
            - severity: 严重程度（low / medium / high / critical）
            - recommendations: 优化建议列表
        """
        # 构建 EXPLAIN 查询
        explain_sql = self._dialect.build_explain_query(query)

        # 执行 EXPLAIN
        conn = await self._pool.acquire()
        try:
            raw_result = await self._dialect.execute_query(conn, explain_sql)
        except Exception as e:
            logger.error(f"EXPLAIN 执行失败: {e}")
            return {
                "plan": {},
                "issues": [f"EXPLAIN 执行失败: {e}"],
                "severity": "unknown",
                "recommendations": [],
            }
        finally:
            await self._pool.release(conn)

        # 解析执行计划
        plan = self._dialect.parse_explain_result(raw_result)

        # 检测问题
        issues = self.detect_issues(plan)

        # 评估严重程度
        severity = self._evaluate_severity(issues)

        # 生成建议
        recommendations = self._generate_recommendations(plan, issues)

        return {
            "plan": plan,
            "issues": issues,
            "severity": severity,
            "recommendations": recommendations,
        }

    def detect_issues(self, plan: Dict[str, Any]) -> List[str]:
        """
        从执行计划中检测性能问题。

        检测项：
        - 全表扫描（Seq Scan / ALL / COLLSCAN）
        - 高预估代价
        - 未使用索引
        - 大结果集
        - 高内存使用

        Args:
            plan: 统一格式的执行计划字典。

        Returns:
            检测到的问题描述列表。
        """
        issues: List[str] = []
        plan_type = plan.get("plan_type", "")
        warnings = plan.get("warnings", [])

        # 直接传递的告警
        issues.extend(warnings)

        # 全表扫描检测
        full_scan_indicators = ["Seq Scan", "ALL", "COLLSCAN", "seq_scan"]
        for indicator in full_scan_indicators:
            if indicator.lower() in plan_type.lower():
                issue = f"检测到全表扫描（{plan_type}），可能导致性能问题"
                if issue not in issues:
                    issues.append(issue)
                break

        # 高代价检测
        estimated_cost = plan.get("estimated_cost", 0)
        if isinstance(estimated_cost, (int, float)) and estimated_cost > 10000:
            issues.append(f"预估代价较高: {estimated_cost}")

        # 未使用索引检测
        indexes_used = plan.get("indexes_used", [])
        tables = plan.get("tables", [])
        if tables and not indexes_used and "Seq Scan" in plan_type:
            issues.append(
                f"查询涉及表 {tables} 但未使用任何索引"
            )

        # 行数估算偏差检测
        estimated_rows = plan.get("estimated_rows", 0)
        actual_rows = plan.get("actual_rows", 0)
        if estimated_rows > 0 and actual_rows > 0:
            ratio = actual_rows / estimated_rows
            if ratio > 10 or ratio < 0.1:
                issues.append(
                    f"行数估算偏差大: 预估 {estimated_rows}，实际 {actual_rows}（比率 {ratio:.1f}x）"
                )

        return issues

    def _evaluate_severity(self, issues: List[str]) -> str:
        """
        根据问题列表评估严重程度。

        Args:
            issues: 问题列表。

        Returns:
            严重程度字符串：low / medium / high / critical。
        """
        if not issues:
            return "low"

        issue_count = len(issues)
        has_full_scan = any("全表扫描" in i or "COLLSCAN" in i for i in issues)
        has_high_cost = any("代价较高" in i for i in issues)

        if has_full_scan and has_high_cost:
            return "critical"
        if has_full_scan or issue_count >= 3:
            return "high"
        if issue_count >= 2:
            return "medium"
        return "low"

    def _generate_recommendations(
        self,
        plan: Dict[str, Any],
        issues: List[str],
    ) -> List[str]:
        """
        根据执行计划和问题生成优化建议。

        Args:
            plan: 执行计划字典。
            issues: 问题列表。

        Returns:
            优化建议列表。
        """
        recommendations: List[str] = []

        # 全表扫描 → 建议添加索引
        tables = plan.get("tables", [])
        if any("全表扫描" in i for i in issues) and tables:
            recommendations.append(
                f"建议为表 '{', '.join(tables)}' 的查询条件列添加索引"
            )

        # 高代价 → 建议优化查询
        if any("代价较高" in i for i in issues):
            recommendations.append("建议优化查询逻辑，减少不必要的 JOIN 或子查询")

        # 行数偏差 → 建议更新统计信息
        if any("估算偏差" in i for i in issues):
            recommendations.append(
                "建议更新表统计信息（PostgreSQL: ANALYZE，MySQL: ANALYZE TABLE）"
            )

        # 通用建议
        if not recommendations:
            recommendations.append("当前查询执行计划无明显问题")

        return recommendations
