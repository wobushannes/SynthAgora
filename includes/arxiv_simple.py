#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import xml.etree.ElementTree as ET

class ArxivPlugin:
    def __init__(self):
        self.name = "arXiv"
        self.description = "Wissenschaftliche Paper"
        self.enabled = False
        self.needs_server = False
        self.stats = {"searches": 0, "success": 0, "errors": 0}
    
    def search(self, query, max_results=3):
        print(f"🔍 arXiv sucht: {query}")
        results = []
        
        try:
            url = "http://export.arxiv.org/api/query"
            params = {
                "search_query": f"all:{query}",
                "max_results": max_results,
                "sortBy": "relevance"
            }
            
            r = requests.get(url, params=params, timeout=15)
            root = ET.fromstring(r.text)
            
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry")[:max_results]:
                title = entry.find("{http://www.w3.org/2005/Atom}title").text
                summary = entry.find("{http://www.w3.org/2005/Atom}summary").text
                paper_url = entry.find("{http://www.w3.org/2005/Atom}id").text
                
                results.append({
                    "source": self.name,
                    "title": title,
                    "url": paper_url,
                    "full_text": summary,
                    "snippet": summary[:200] + "...",
                    "relevance": 0.8,
                    "access_date": __import__('datetime').datetime.now().isoformat()
                })
            
            self.stats["success"] += 1
            print(f"✅ {len(results)} arXiv-Treffer")
            
        except Exception as e:
            print(f"❌ arXiv Fehler: {e}")
            self.stats["errors"] += 1
        
        self.stats["searches"] += 1
        return results