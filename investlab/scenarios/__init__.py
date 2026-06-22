from investlab.scenarios.registry import (
    SCENARIO_REGISTRY,
    ScenarioEntry,
    UnknownScenarioError,
)
from investlab.scenarios.annual_matrix import (
    apply_known_adjustments,
    build_matrix,
    year_end_closes,
)
from investlab.scenarios.dca_matrix import (
    build_dca_matrices,
    periodic_irr,
)
from investlab.scenarios import framework_scenario  # noqa: F401 — triggers registration
from investlab.scenarios import rolling_returns_scenario  # noqa: F401 — triggers registration
from investlab.scenarios import dca_comparison_scenario  # noqa: F401 — triggers registration

__all__ = [
    "SCENARIO_REGISTRY",
    "ScenarioEntry",
    "UnknownScenarioError",
    "apply_known_adjustments",
    "build_dca_matrices",
    "build_matrix",
    "periodic_irr",
    "year_end_closes",
]

from investlab.scenarios import rebalance_scenario  # noqa: F401
