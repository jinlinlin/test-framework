"""engines.auth_bypass.strategies 包 — 越权访问策略（策略模式）。"""
from .base import AuthBypassStrategy
from .role_escalation import RoleEscalationStrategy
from .session_fixation import SessionFixationStrategy
from .token_replay import TokenReplayStrategy
from .jwt_attack import JWTAttackStrategy
from .oauth_attack import OAuthAttackStrategy
from .idor import IDORStrategy

__all__ = [
    "AuthBypassStrategy",
    "RoleEscalationStrategy",
    "SessionFixationStrategy",
    "TokenReplayStrategy",
    "JWTAttackStrategy",
    "OAuthAttackStrategy",
    "IDORStrategy",
]
