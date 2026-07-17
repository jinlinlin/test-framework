"""
索引建议器 — 基于执行计划生成索引优化建议。

职责：分析执行计划结果，识别缺失索引和低效索引，
      生成具体的索引创建建议及预估改善幅度。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IndexSuggestion:
    """
    索引建议数据对象。

    Attributes:
        table: 涉及的表名。
        columns: 建议索引的列名列表。
        index_type: 索引类型（btree / hash / gin / gist / compound）。
        reason: 建议原因。
        estimated_improvement: 预估性能改善百分比。
        priority: 优先级（high / medium / low）。
        sql: 建议的 CREATE INDEX 语句。
    """

    table: str = ""
    columns: List[str] = field(default_factory=list)
    index_type: str = "btree"
    reason: str = ""
    estimated_improvement: str = ""
    priority: str = "medium"
    sql: str = ""


class IndexAdvisor:
    """
    索引建议器。

    基于执行计划分析结果，识别全表扫描、低效扫描等场景，
    生成具体的索引创建建议。

    Attributes:
        _dialect: 数据库方言（用于生成方言化的 SQL）。
        _config: 索引建议器配置。
    """

    def __init__(self, dialect: Any, config: Dict[str, Any]) -> None:
        """
        初始化索引建议器。

        配置格式::

            {
                "enabled": True,
                "min_improvement_threshold": 10,  # 最低改善百分比阈值
                "max_suggestions": 10,             # 最大建议数
            }

        Args:
            dialect: Dialect 实例。
            config: 索引建议器配置。
        """
        self._dialect = dialect
        self._enabled: bool = config.get("enabled", True)
        self._min_threshold: int = config.get("min_improvement_threshold", 10)
        self._max_suggestions: int = config.get("max_suggestions", 10)

    def analyze(self, explain_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基于执行计划分析结果生成索引建议。

        Args:
            explain_result: ExplainAnalyzer.analyze() 返回的结果字典。

        Returns:
            索引建议列表，每个建议为字典：
            {
                "table": "users",
                "columns": ["email"],
                "index_type": "btree",
                "reason": "全表扫描",
                "estimated_improvement": "60-80%",
                "priority": "high",
                "sql": "CREATE INDEX idx_users_email ON users (email);"
            }
        """
        if not self._enabled:
            return []

        plan = explain_result.get("plan", {})
        issues = explain_result.get("issues", [])

        suggestions: List[IndexSuggestion] = []

        # 分析执行计划，生成建议
        suggestions.extend(self._check_full_table_scan(plan, issues))
        suggestions.extend(self._check_missing_indexes(plan))
        suggestions.extend(self._check_inefficient_joins(plan))

        # 按优先级排序并截断
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 2))
        suggestions = suggestions[: self._max_suggestions]

        # 转为字典
        return [self._to_dict(s) for s in suggestions]

    def _check_full_table_scan(
        self, plan: Dict[str, Any], issues: List[str]
    ) -> List[IndexSuggestion]:
        """
        检查全表扫描并生成索引建议。

        Args:
            plan: 执行计划字典。
            issues: 问题列表。

        Returns:
            索引建议列表。
        """
        suggestions: List[IndexSuggestion] = []
        plan_type = plan.get("plan_type", "").lower()

        full_scan_keywords = ["seq scan", "all", "collscan"]
        is_full_scan = any(kw in plan_type for kw in full_scan_keywords)

        if is_full_scan:
            tables = plan.get("tables", [])
            for table in tables:
                if table:
                    suggestions.append(IndexSuggestion(
                        table=table,
                        columns=["<查询条件列>"],
                        index_type="btree",
                        reason=f"全表扫描（{plan.get('plan_type', '')}），"
                               f"预估扫描 {plan.get('estimated_rows', '?')} 行",
                        estimated_improvement="60-90%",
                        priority="high",
                        sql=self._build_create_index_sql(table, ["<查询条件列>"]),
                    ))

        return suggestions

    def _check_missing_indexes(self, plan: Dict[str, Any]) -> List[IndexSuggestion]:
        """
        检查缺失索引的情况。

        Args:
            plan: 执行计划字典。

        Returns:
            索引建议列表。
        """
        suggestions: List[IndexSuggestion] = []
        tables = plan.get("tables", [])
        indexes_used = plan.get("indexes_used", [])

        # 有表但未使用索引
        if tables and not indexes_used:
            for table in tables:
                if table:
                    suggestions.append(IndexSuggestion(
                        table=table,
                        columns=["<高频查询列>"],
                        index_type="btree",
                        reason=f"表 '{table}' 在查询中未使用任何索引",
                        estimated_improvement="40-70%",
                        priority="medium",
                        sql=self._build_create_index_sql(table, ["<高频查询列>"]),
                    ))

        return suggestions

    def _check_inefficient_joins(self, plan: Dict[str, Any]) -> List[IndexSuggestion]:
        """
        检查低效 JOIN 操作。

        Args:
            plan: 执行计划字典。

        Returns:
            索引建议列表。
        """
        suggestions: List[IndexSuggestion] = []

        # 检查嵌套循环 JOIN
        if "Nested Loop" in plan.get("plan_type", ""):
            tables = plan.get("tables", [])
            estimated_cost = plan.get("estimated_cost", 0)

            if len(tables) >= 2 and isinstance(estimated_cost, (int, float)) and estimated_cost > 5000:
                # 内表建议添加索引
                inner_table = tables[-1] if tables else ""
                if inner_table:
                    suggestions.append(IndexSuggestion(
                        table=inner_table,
                        columns=["<JOIN 条件列>"],
                        index_type="btree",
                        reason=f"嵌套循环 JOIN 代价较高（{estimated_cost}），内表缺少索引",
                        estimated_improvement="50-80%",
                        priority="high",
                        sql=self._build_create_index_sql(inner_table, ["<JOIN 条件列>"]),
                    ))

        return suggestions

    def _build_create_index_sql(self, table: str, columns: List[str]) -> str:
        """
        生成 CREATE INDEX SQL 语句。

        Args:
            table: 表名。
            columns: 列名列表。

        Returns:
            CREATE INDEX SQL 语句。
        """
        col_str = "_".join(c.strip("<>") for c in columns)
        index_name = f"idx_{table}_{col_str}"
        col_list = ", ".join(columns)
        return f"CREATE INDEX {index_name} ON {table} ({col_list});"

    @staticmethod
    def _to_dict(suggestion: IndexSuggestion) -> Dict[str, Any]:
        """
        将 IndexSuggestion 转为字典。

        Args:
            suggestion: 索引建议对象。

        Returns:
            字典格式的建议。
        """
        return {
            "table": suggestion.table,
            "columns": suggestion.columns,
            "index_type": suggestion.index_type,
            "reason": suggestion.reason,
            "estimated_improvement": suggestion.estimated_improvement,
            "priority": suggestion.priority,
            "sql": suggestion.sql,
        }
