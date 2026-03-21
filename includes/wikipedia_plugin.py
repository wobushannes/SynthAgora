#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import urllib.parse
from datetime import datetime

class WikipediaPlugin:
    def __init__(self):
        self.name = "Wikipedia"
        self.description = "Wikipedia-Volltext"
        self.enabled = False
        self.needs_server = False
        self.stats = {"searches": 0, "success": 0, "errors": 0}
    
    def search(self, query, max_results=3):
        print(f"🔍 Wikipedia sucht: {query}")
        results = []
        
        try:
            # 1. Suche nach Artikeln
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results
            }
            
            headers = {"User-Agent": "SynthAgora/1.0"}
            r = requests.get("https://de.wikipedia.org/w/api.php", 
                           params=search_params, headers=headers)
            data = r.json()
            
            # 2. Für jeden Treffer den VOLLTEXT holen
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                
                # Volltext abrufen
                content_params = {
                    "action": "query",
                    "titles": title,
                    "prop": "extracts",
                    "explaintext": True,  # WICHTIG: reiner Text, kein HTML!
                    "format": "json",
                    "exintro": False,  # Ganzer Artikel, nicht nur Einleitung
                    "exlimit": 1
                }
                
                r2 = requests.get("https://de.wikipedia.org/w/api.php",
                                 params=content_params, headers=headers)
                content_data = r2.json()
                
                # Text extrahieren
                pages = content_data.get("query", {}).get("pages", {})
                full_text = ""
                for page_id, page in pages.items():
                    if page_id != "-1":
                        full_text = page.get("extract", "")
                
                # Zitierfähige Quelle
                citation = f"Wikipedia: '{title}' (abgerufen am {datetime.now().strftime('%d.%m.%Y')})"
                url = f"https://de.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                
                results.append({
                    "source": "Wikipedia",
                    "title": title,
                    "url": url,
                    "citation": citation,
                    "full_text": full_text,  # ← VOLLTEXT für Agenten
                    "snippet": full_text[:200] + "..." if full_text else "",
                    "relevance": 0.9,
                    "access_date": datetime.now().isoformat()
                })
            
            self.stats["success"] += 1
            print(f"✅ {len(results)} Artikel mit Volltext")
            
        except Exception as e:
            print(f"❌ Fehler: {e}")
            self.stats["errors"] += 1
        
        self.stats["searches"] += 1
        return results