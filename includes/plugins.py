#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plugin-Manager für SynthAgora
- Verwaltung externer Recherche-Quellen
- Wikipedia, arXiv, etc.
- Einfache Erweiterbarkeit
"""

import threading
import time
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta

# Plugin-Import versuchen
try:
    from .wikipedia_plugin import WikipediaPlugin
except ImportError:
    WikipediaPlugin = None

try:
    from .arxiv_simple import ArxivPlugin
except ImportError:
    ArxivPlugin = None


class BasePlugin:
    """Basis-Klasse für alle Plugins"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = False
        self.needs_server = False
        self.stats = {"searches": 0, "success": 0, "errors": 0}
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Führt eine Suche durch - muss überschrieben werden"""
        return []
    
    def format_result(self, result: Dict) -> str:
        """Formatiert ein einzelnes Ergebnis für den Prompt"""
        return f"[{result.get('source', self.name)}] {result.get('title', '')}: {result.get('snippet', '')}"
    
    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück"""
        return self.stats


class PluginManager:
    """Verwaltet alle Plugins und externe Recherche"""
    
    def __init__(self):
        self.plugins = {}
        self.use_external = True
        self._cache = {}
        self._cache_ttl = 3600  # 1 Stunde
        self._lock = threading.Lock()
        
        self._load_plugins()
    
    def _load_plugins(self):
        """Lädt verfügbare Plugins"""
        if WikipediaPlugin:
            self.plugins["wikipedia"] = WikipediaPlugin()
            print("✅ Wikipedia-Plugin geladen")
        else:
            print("⚠️ Wikipedia-Plugin nicht verfügbar")
        
        if ArxivPlugin:
            self.plugins["arxiv"] = ArxivPlugin()
            print("✅ arXiv-Plugin geladen")
        else:
            print("⚠️ arXiv-Plugin nicht verfügbar")
    
    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """Gibt alle Plugins zurück"""
        return self.plugins
    
    def enable_plugin(self, name: str, enabled: bool):
        """Aktiviert/deaktiviert ein Plugin"""
        if name in self.plugins:
            self.plugins[name].enabled = enabled
            print(f"{'✅' if enabled else '⏸️'} Plugin {name} {'aktiviert' if enabled else 'deaktiviert'}")
    
    def is_plugin_available(self, name: str) -> bool:
        """Prüft ob ein Plugin verfügbar und aktiv ist"""
        return name in self.plugins and self.plugins[name].enabled
    
    def search_all(self, query: str, max_results: int = 5) -> Dict[str, List[Dict]]:
        """
        Sucht mit allen aktiven Plugins.
        
        Returns:
            {plugin_name: [results]}
        """
        results = {}
        
        for name, plugin in self.plugins.items():
            if not plugin.enabled:
                continue
            
            # Cache prüfen
            cache_key = f"{name}_{query}_{max_results}"
            with self._lock:
                if cache_key in self._cache:
                    cached_time, cached_results = self._cache[cache_key]
                    if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                        results[name] = cached_results
                        continue
            
            # Suche ausführen
            try:
                plugin_results = plugin.search(query, max_results)
                results[name] = plugin_results
                
                # Cache aktualisieren
                with self._lock:
                    self._cache[cache_key] = (datetime.now(), plugin_results)
                    
            except Exception as e:
                print(f"❌ Plugin {name} Fehler: {e}")
                results[name] = []
        
        return results
    
    def format_all_results(self, results: Dict[str, List[Dict]]) -> str:
        """Formatiert alle Ergebnisse für den Prompt"""
        if not results:
            return "Keine externen Informationen gefunden."
        
        formatted = []
        for plugin_name, plugin_results in results.items():
            if not plugin_results:
                continue
            
            plugin = self.plugins.get(plugin_name)
            formatted.append(f"\n--- {plugin_name.upper()} ---")
            
            for i, res in enumerate(plugin_results[:3], 1):
                if plugin:
                    formatted.append(f"{i}. {plugin.format_result(res)}")
                else:
                    formatted.append(f"{i}. [{res.get('source', plugin_name)}] {res.get('title', '')}: {res.get('snippet', '')}")
        
        return "\n".join(formatted) if formatted else "Keine externen Informationen gefunden."
    
    def search(self, query: str, max_results: int = 3, progress_callback=None) -> List[Dict]:
        """
        Sucht mit allen aktiven Plugins und gibt kombinierte Ergebnisse zurück.
        """
        all_results = []
        
        if progress_callback:
            progress_callback(f"🔍 Recherchiere '{query}'...")
        
        for name, plugin in self.plugins.items():
            if not plugin.enabled:
                continue
            
            try:
                results = plugin.search(query, max_results)
                all_results.extend(results)
                
                if progress_callback and results:
                    progress_callback(f"📚 {name}: {len(results)} Ergebnisse")
                    
            except Exception as e:
                print(f"❌ Plugin {name} Fehler: {e}")
        
        # Nach Relevanz sortieren
        all_results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        
        return all_results[:max_results]
    
    def should_search(self, topic: str) -> bool:
        """
        Entscheidet ob für dieses Thema gesucht werden soll.
        Vermeidet unnötige API-Calls.
        """
        if not self.use_external:
            return False
        
        # Keine aktiven Plugins
        if not any(p.enabled for p in self.plugins.values()):
            return False
        
        # Zu kurze Themen
        if len(topic) < 3:
            return False
        
        # Stoppwörter
        stop_words = {"hallo", "hi", "ja", "nein", "ok", "danke", "bitte", "gut", "schlecht"}
        if topic.lower().strip() in stop_words:
            return False
        
        return True
    
    def clear_cache(self):
        """Leert den Cache"""
        with self._lock:
            self._cache.clear()
        print("🧹 Plugin-Cache geleert")
    
    def get_stats(self) -> Dict:
        """Gibt Statistiken aller Plugins zurück"""
        stats = {
            "total_searches": 0,
            "total_success": 0,
            "total_errors": 0,
            "plugins": {}
        }
        
        for name, plugin in self.plugins.items():
            stats["plugins"][name] = plugin.get_stats()
            stats["total_searches"] += plugin.stats.get("searches", 0)
            stats["total_success"] += plugin.stats.get("success", 0)
            stats["total_errors"] += plugin.stats.get("errors", 0)
        
        return stats