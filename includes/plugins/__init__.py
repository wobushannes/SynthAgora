#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from .wikipedia_plugin import WikipediaPlugin
from .arxiv_simple import ArxivPlugin

class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.use_external = False
        
        # Wikipedia
        wiki = WikipediaPlugin()
        self.plugins["wikipedia"] = wiki
        print(f"✅ {wiki.name} geladen")
        
        # arXiv
        arxiv = ArxivPlugin()
        self.plugins["arxiv"] = arxiv
        print(f"✅ {arxiv.name} geladen")
    
    def get_all_plugins(self):
        return self.plugins
    
    def get_enabled_plugins(self):
        return [p for p in self.plugins.values() if p.enabled]
    
    def enable_plugin(self, name, enabled=True):
        if name in self.plugins:
            self.plugins[name].enabled = enabled
    
    def search_all(self, query, max_results=3):
        results = []
        for plugin in self.get_enabled_plugins():
            try:
                r = plugin.search(query, max_results)
                results.extend(r)
            except Exception as e:
                print(f"Fehler bei {plugin.name}: {e}")
        return results
    
    def format_all_results(self, results):
        if not results:
            return ""
        text = "\n📚 EXTERNE RECHERCHE:\n"
        for i, r in enumerate(results[:5], 1):
            text += f"\n{i}. [{r['source']}] {r['title']}\n   {r['url']}\n"
            if r.get('snippet'):
                text += f"   {r['snippet'][:100]}...\n"
        return text
    
    def get_plugin_info(self):
        info = []
        for key, p in self.plugins.items():
            info.append({
                "key": key,
                "name": p.name,
                "description": p.description,
                "enabled": p.enabled,
                "needs_server": getattr(p, 'needs_server', False),
                "available": True,
                "stats": getattr(p, 'stats', {})
            })
        return info