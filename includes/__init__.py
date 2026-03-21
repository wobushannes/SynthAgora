# includes/__init__.py
"""
SynthAgora Core Modules
------------------------
Enthält alle Kernmodule für die Agenten-Simulation:
- config: Konfiguration
- database: SQLite-Datenbank
- agent: Agenten-Klasse mit Persönlichkeit und Lernen
- agent_factory: Massengenerierung von Agenten
- knowledge_graph: Knowledge Graph für Beziehungen
- task_manager: Analyse-Jobs
- migrate: Migration von JSON zu SQLite
- plugins: Externe Recherche (Wikipedia, arXiv)
"""

from .config import Config
from .database import SynthAgoraDB
from .agent import Agent
from .agent_factory import AgentFactory
from .knowledge_graph import KnowledgeGraph
from .task_manager import TaskManager, AnalysisJob, Task
from .migrate import MigrationTool, MigrationWindow
from .plugins import PluginManager, BasePlugin

# Versuche Wikipedia und arXiv Plugins zu importieren (optional)
try:
    from .wikipedia_plugin import WikipediaPlugin
except ImportError:
    WikipediaPlugin = None

try:
    from .arxiv_simple import ArxivPlugin
except ImportError:
    ArxivPlugin = None

__version__ = "4.0"
__author__ = "SynthAgora Team"

# Exportiere öffentliche Schnittstelle
__all__ = [
    "Config",
    "SynthAgoraDB",
    "Agent",
    "AgentFactory",
    "KnowledgeGraph",
    "TaskManager",
    "AnalysisJob",
    "Task",
    "MigrationTool",
    "MigrationWindow",
    "PluginManager",
    "BasePlugin",
    "WikipediaPlugin",
    "ArxivPlugin",
    "__version__"
]

# Initialisierungs-Log
print(f"📦 SynthAgora Core Modules v{__version__} geladen")