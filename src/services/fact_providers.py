"""
事実生成プロバイダ（Fact Providers）パッケージのプロキシ。
後方互換性のために残されています。新しいプロバイダは src/services/providers/ ディレクトリに追加してください。
"""

from .providers.base import BaseFactProvider
from .providers.shape import ShapeFactProvider
from .providers.stability import StabilityFactProvider
from .providers.endgame import EndgameFactProvider
from .providers.influence import InfluenceFactProvider
from .providers.urgency import UrgencyFactProvider
from .providers.ko import KoFactProvider
from .providers.quality import MoveQualityFactProvider
from .providers.strategy import StrategicFactProvider
from .providers.stats import BasicStatsFactProvider
