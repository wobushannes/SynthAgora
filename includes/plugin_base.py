#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plugin-Basisklassen für SynthAgora
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PluginMetadata:
    """Metadaten für ein Plugin"""
    id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BasePlugin(ABC):
    """Basisklasse für alle Plugins"""
    
    def __init__(self, metadata: PluginMetadata):
        self.metadata = metadata
        self._enabled = metadata.enabled
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        self.metadata.enabled = value
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        pass
    
    def configure(self, config: Dict[str, Any]) -> bool:
        self.metadata.config.update(config)
        return True


class TaskPlugin(BasePlugin):
    """Task-Plugin für Agenten-Aufgaben"""
    
    @abstractmethod
    def get_variants(self) -> List[str]:
        pass
    
    @abstractmethod
    def generate_prompt(self, variant: str, target: str, documents: List[Dict]) -> str:
        pass
    
    @abstractmethod
    def evaluate(self, response: str, expected: Dict) -> Dict:
        pass
    
    def get_points(self, score: float) -> int:
        if score >= 0.9:
            return 50
        elif score >= 0.7:
            return 30
        elif score >= 0.5:
            return 15
        else:
            return 5


class SynthesisPlugin(BasePlugin):
    """Synthesis-Plugin für Marketing-Assets"""
    
    @abstractmethod
    def get_output_formats(self) -> List[str]:
        pass
    
    @abstractmethod
    def synthesize(self, debate_data: Dict, documents: List[Dict], 
                   config: Dict = None) -> Dict[str, Any]:
        pass
    
    def format_output(self, result: Dict, format_type: str = "json") -> str:
        import json
        if format_type == "json":
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif format_type == "markdown":
            return self._to_markdown(result)
        elif format_type == "html":
            return self._to_html(result)
        return str(result)
    
    def _to_markdown(self, result: Dict) -> str:
        import json
        return f"# {result.get('title', 'Ergebnis')}\n\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
    
    def _to_html(self, result: Dict) -> str:
        import json
        return f"<h1>{result.get('title', 'Ergebnis')}</h1><pre>{json.dumps(result, indent=2, ensure_ascii=False)}</pre>"


class ExportPlugin(BasePlugin):
    """Export-Plugin für Ergebnisse"""
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        pass
    
    @abstractmethod
    def export(self, data: Dict, format_type: str, options: Dict = None) -> bytes:
        pass
    
    def get_extension(self, format_type: str) -> str:
        extensions = {"json": ".json", "markdown": ".md", "html": ".html", "pdf": ".pdf", "txt": ".txt"}
        return extensions.get(format_type, ".txt")


# ===================== NEU: LEGAL ANALYSIS PLUGIN =====================

class LegalAnalysisPlugin(BasePlugin):
    """Legal Analysis Plugin für Dokumentenanalyse und Rechtsvergleich"""
    
    @abstractmethod
    def get_output_formats(self) -> List[str]:
        """Unterstützte Ausgabeformate (json, markdown, html)"""
        pass
    
    @abstractmethod
    def analyze(self, debate_data: Dict, documents: List[Dict], config: Dict = None) -> Dict[str, Any]:
        """
        Führt die Analyse durch.
        
        Args:
            debate_data: Debatten-Daten mit:
                - topic: Thema
                - log: Diskussionsverlauf
                - rounds: Anzahl Runden
                - pro_agents: Liste der Pro-Agenten
                - contra_agents: Liste der Contra-Agenten
                - timestamp: Zeitstempel
            documents: Liste der in der Debatte verwendeten Dokumente
            config: Plugin-spezifische Konfiguration
            
        Returns:
            Dict mit Analyse-Ergebnissen
        """
        pass
    
    def format_output(self, result: Dict, format_type: str = "json") -> str:
        import json
        if format_type == "json":
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif format_type == "markdown":
            return self._to_markdown(result)
        elif format_type == "html":
            return self._to_html(result)
        return str(result)
    
    def _to_markdown(self, result: Dict) -> str:
        import json
        return f"# {result.get('title', 'Analyse-Ergebnis')}\n\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
    
    def _to_html(self, result: Dict) -> str:
        import json
        return f"<h1>{result.get('title', 'Analyse-Ergebnis')}</h1><pre>{json.dumps(result, indent=2, ensure_ascii=False)}</pre>"