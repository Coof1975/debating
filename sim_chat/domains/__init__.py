"""Register built-in simulation domains."""

from __future__ import annotations

from ..domain import register_domain
from .enterprise import ENTERPRISE_DOMAIN, load_enterprise_participants
from .securities import SECURITIES_DOMAIN, load_securities_demo_participants
from .tutoring import TUTORING_DOMAIN, load_tutoring_demo_participants


def register_builtin_domains() -> None:
    register_domain(ENTERPRISE_DOMAIN, loader=load_enterprise_participants)
    register_domain(TUTORING_DOMAIN, loader=load_tutoring_demo_participants)
    register_domain(SECURITIES_DOMAIN, loader=load_securities_demo_participants)


register_builtin_domains()
