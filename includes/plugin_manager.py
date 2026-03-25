#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin Manager für SynthAgora - MIT SYNTHESIS UNTERORDNER, LEGAL PLUGINS UND LM-INTEGRATION"""

import os
import sys
import importlib
import inspect
import importlib.util
from typing import Dict, List, Any, Optional


class PluginManager:
    """Verwaltet alle Plugins"""
    
    def __init__(self, plugins_dir: str = None):
        if plugins_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            plugins_dir = os.path.join(base_dir, "plugins")
        
        self.plugins_dir = plugins_dir
        self._plugins = {}
        self._synthesis_plugins = {}
        self._task_plugins = {}
        self._export_plugins = {}
        self._legal_plugins = {}
        self.use_external = True
        self._lm = None
        
        self._load_plugins()
    
    def set_lm(self, lm):
        """Setzt LM-Client für alle Plugins"""
        self._lm = lm
        for plugin in self._synthesis_plugins.values():
            if hasattr(plugin, 'set_lm'):
                try:
                    plugin.set_lm(lm)
                except Exception as e:
                    print(f"⚠️ Fehler beim Setzen von LM für {plugin.metadata.name}: {e}")
        for plugin in self._legal_plugins.values():
            if hasattr(plugin, 'set_lm'):
                try:
                    plugin.set_lm(lm)
                except Exception as e:
                    print(f"⚠️ Fehler beim Setzen von LM für {plugin.metadata.name}: {e}")
        for plugin in self._plugins.values():
            if hasattr(plugin, 'set_lm'):
                try:
                    plugin.set_lm(lm)
                except:
                    pass
    
    def _load_plugins(self):
        """Lädt alle Plugins aus dem plugins-Verzeichnis (inkl. Unterordner)"""
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            self._create_example_plugins()
            return
        
        if self.plugins_dir not in sys.path:
            sys.path.insert(0, self.plugins_dir)
        
        search_dirs = [self.plugins_dir]
        for item in os.listdir(self.plugins_dir):
            subdir = os.path.join(self.plugins_dir, item)
            if os.path.isdir(subdir) and not item.startswith('__'):
                search_dirs.append(subdir)
        
        from .plugin_base import SynthesisPlugin, TaskPlugin, ExportPlugin, LegalAnalysisPlugin
        
        for search_dir in search_dirs:
            for file in os.listdir(search_dir):
                if file.endswith('.py') and not file.startswith('__'):
                    module_name = file[:-3]
                    full_module_path = os.path.join(search_dir, file)
                    folder_name = os.path.basename(search_dir)
                    
                    try:
                        # Modul laden
                        if search_dir != self.plugins_dir:
                            # Unterordner-Modul
                            spec = importlib.util.spec_from_file_location(
                                f"{folder_name}.{module_name}",
                                full_module_path
                            )
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                        else:
                            # Hauptordner-Modul
                            spec = importlib.util.spec_from_file_location(
                                module_name,
                                full_module_path
                            )
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                        
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and hasattr(obj, 'metadata'):
                                try:
                                    metadata = obj.metadata if hasattr(obj, 'metadata') else None
                                    if not metadata:
                                        from .plugin_base import PluginMetadata
                                        metadata = PluginMetadata(
                                            id=module_name,
                                            name=getattr(obj, 'name', module_name),
                                            version="1.0",
                                            description=getattr(obj, 'description', ""),
                                            author="Unknown",
                                            category="synthesis"
                                        )
                                    
                                    # Plugin instanziieren
                                    if hasattr(obj, '__init__') and 'metadata' in inspect.signature(obj.__init__).parameters:
                                        plugin = obj(metadata)
                                    else:
                                        plugin = obj()
                                        plugin.metadata = metadata
                                    
                                    self._plugins[metadata.id] = plugin
                                    
                                    # Nach Typ sortieren
                                    if isinstance(plugin, SynthesisPlugin):
                                        self._synthesis_plugins[metadata.id] = plugin
                                        print(f"✅ Synthesis-Plugin geladen: {metadata.name}")
                                    elif isinstance(plugin, TaskPlugin):
                                        self._task_plugins[metadata.id] = plugin
                                        print(f"✅ Task-Plugin geladen: {metadata.name}")
                                    elif isinstance(plugin, ExportPlugin):
                                        self._export_plugins[metadata.id] = plugin
                                        print(f"✅ Export-Plugin geladen: {metadata.name}")
                                    elif isinstance(plugin, LegalAnalysisPlugin):
                                        self._legal_plugins[metadata.id] = plugin
                                        print(f"✅ Legal-Plugin geladen: {metadata.name}")
                                    
                                    if self._lm and hasattr(plugin, 'set_lm'):
                                        try:
                                            plugin.set_lm(self._lm)
                                        except:
                                            pass
                                    
                                except Exception as e:
                                    print(f"⚠️ Fehler bei Plugin {module_name} in {search_dir}: {e}")
                                    
                    except Exception as e:
                        print(f"⚠️ Fehler beim Laden von {file} aus {search_dir}: {e}")
    
    def _create_example_plugins(self):
        """Erstellt Beispiel-Plugins"""
        example_path = os.path.join(self.plugins_dir, "example_synthesis.py")
        if not os.path.exists(example_path):
            with open(example_path, 'w', encoding='utf-8') as f:
                f.write('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beispiel Synthesis-Plugin"""

from includes.plugin_base import SynthesisPlugin, PluginMetadata


class ExampleSynthesisPlugin(SynthesisPlugin):
    """Beispiel-Plugin für Synthese"""
    
    metadata = PluginMetadata(
        id="example_synthesis",
        name="Beispiel Synthese",
        version="1.0",
        description="Ein einfaches Beispiel-Plugin für Synthese",
        author="SynthAgora",
        category="synthesis"
    )
    
    def __init__(self, metadata):
        super().__init__(metadata)
        self.lm = None
    
    def set_lm(self, lm):
        self.lm = lm
    
    def get_output_formats(self) -> list:
        return ["json", "markdown"]
    
    def synthesize(self, debate_data: dict, documents: list, config: dict = None) -> dict:
        return {
            "title": "Beispiel-Synthese",
            "description": "Dies ist ein Beispiel für ein Synthesis-Plugin",
            "debate_topic": debate_data.get("topic", ""),
            "contributions": len(debate_data.get("log", [])),
            "message": "Plugin funktioniert!"
        }
    
    def get_info(self) -> dict:
        return {
            "id": self.metadata.id,
            "name": self.metadata.name,
            "version": self.metadata.version,
            "description": self.metadata.description
        }
''')
    
    def get_all_plugins(self) -> Dict:
        return self._plugins
    
    def get_all_synthesis_plugins(self) -> Dict:
        return self._synthesis_plugins
    
    def get_all_task_plugins(self) -> Dict:
        return self._task_plugins
    
    def get_all_export_plugins(self) -> Dict:
        return self._export_plugins
    
    def get_all_legal_plugins(self) -> Dict:
        return self._legal_plugins
    
    def get_legal_plugin(self, plugin_id: str) -> Optional[Any]:
        return self._legal_plugins.get(plugin_id)
    
    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        return (self._plugins.get(plugin_id) or 
                self._synthesis_plugins.get(plugin_id) or 
                self._legal_plugins.get(plugin_id))
    
    def enable_plugin(self, plugin_id: str, enabled: bool):
        if plugin_id in self._plugins:
            self._plugins[plugin_id].enabled = enabled
        elif plugin_id in self._synthesis_plugins:
            self._synthesis_plugins[plugin_id].enabled = enabled
        elif plugin_id in self._legal_plugins:
            self._legal_plugins[plugin_id].enabled = enabled
    
    def reload_plugins(self):
        self._plugins.clear()
        self._synthesis_plugins.clear()
        self._task_plugins.clear()
        self._export_plugins.clear()
        self._legal_plugins.clear()
        self._load_plugins()
        if self._lm:
            self.set_lm(self._lm)
    
    def reload_legal_plugins(self):
        """Lädt nur Legal-Plugins neu"""
        self._legal_plugins.clear()
        legal_dir = os.path.join(self.plugins_dir, "legal")
        if os.path.exists(legal_dir):
            for file in os.listdir(legal_dir):
                if file.endswith('.py') and not file.startswith('__'):
                    module_name = file[:-3]
                    full_path = os.path.join(legal_dir, file)
                    try:
                        spec = importlib.util.spec_from_file_location(
                            f"legal.{module_name}",
                            full_path
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and hasattr(obj, 'metadata'):
                                from .plugin_base import LegalAnalysisPlugin
                                if issubclass(obj, LegalAnalysisPlugin) and obj is not LegalAnalysisPlugin:
                                    if hasattr(obj, '__init__') and 'metadata' in inspect.signature(obj.__init__).parameters:
                                        plugin = obj(obj.metadata)
                                    else:
                                        plugin = obj()
                                    self._legal_plugins[plugin.metadata.id] = plugin
                                    if self._lm and hasattr(plugin, 'set_lm'):
                                        plugin.set_lm(self._lm)
                                    print(f"✅ Legal-Plugin neu geladen: {plugin.metadata.name}")
                    except Exception as e:
                        print(f"⚠️ Fehler beim Neuladen von {file}: {e}")
    
    def run_synthesis(self, plugin_id: str, debate_data: Dict, documents: List[Dict], 
                      config: Dict = None) -> Dict:
        plugin = self._synthesis_plugins.get(plugin_id)
        if not plugin:
            return {"error": f"Plugin {plugin_id} nicht gefunden", "title": "Fehler"}
        try:
            return plugin.synthesize(debate_data, documents, config)
        except Exception as e:
            return {"error": str(e), "title": "Fehler bei Synthese"}
    
    def run_legal_analysis(self, plugin_id: str, debate_data: Dict, documents: List[Dict],
                           config: Dict = None) -> Dict:
        plugin = self._legal_plugins.get(plugin_id)
        if not plugin:
            return {"error": f"Legal-Plugin {plugin_id} nicht gefunden", "title": "Fehler"}
        try:
            return plugin.analyze(debate_data, documents, config)
        except Exception as e:
            return {"error": str(e), "title": "Fehler bei Analyse"}
    
    def search_all(self, query: str, limit: int = 5) -> Dict[str, Any]:
        return {}
    
    def format_all_results(self, results: Dict) -> str:
        return "Keine externen Quellen aktiv."
    
    def search(self, query: str, limit: int = 3) -> List[Dict]:
        return []
    
    def search_wikipedia(self, query: str, limit: int = 3) -> List[Dict]:
        return []
    
    def search_arxiv(self, query: str, limit: int = 3) -> List[Dict]:
        return []
    
    def get_citations(self, query: str, limit: int = 3) -> str:
        return ""
    
    def get_web_search(self, query: str, limit: int = 3) -> str:
        return ""