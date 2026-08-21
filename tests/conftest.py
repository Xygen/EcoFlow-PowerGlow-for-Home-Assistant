"""Load pure protocol modules without requiring a full Home Assistant install."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "ecoflow_powerglow"

custom_components = ModuleType("custom_components")
custom_components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components)

powerglow = ModuleType("custom_components.ecoflow_powerglow")
powerglow.__path__ = [str(COMPONENT)]
sys.modules.setdefault("custom_components.ecoflow_powerglow", powerglow)
