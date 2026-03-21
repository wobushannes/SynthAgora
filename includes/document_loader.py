#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document Loader für SynthAgora
- Unterstützt: URL (Webseiten), PDF, TXT, mehrere Dokumente
- Extrahiert Text, Metadaten, Zusammenfassung
- Caching für wiederholte Ladevorgänge
"""

import os
import re
import hashlib
import tempfile
import requests
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import threading
import time

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from .config import Config


class DocumentLoader:
    """Lädt und verarbeitet Dokumente für Diskussionen"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600  # 1 Stunde
        self._lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SynthAgora/1.0 (Document Loader)"
        })
        
        # Unterstützte Formate
        self.supported_formats = {
            ".txt": self._load_text,
            ".pdf": self._load_pdf,
            ".html": self._load_html,
            ".htm": self._load_html,
            ".md": self._load_text,
            ".json": self._load_json
        }
    
    def load_document(self, source: str, source_type: str = "auto") -> Dict:
        """
        Lädt ein Dokument von verschiedenen Quellen.
        
        Args:
            source: URL, Dateipfad oder Text
            source_type: "url", "file", "text", "auto"
        
        Returns:
            {
                "content": str,           # Volltext
                "title": str,             # Titel/Name
                "source": str,            # Original-Quelle
                "type": str,              # url/file/text
                "metadata": dict,         # Zusatzinfos
                "summary": str,           # Kurze Zusammenfassung (optional)
                "sections": list,         # Abschnitte (optional)
                "loaded_at": str
            }
        """
        # Cache prüfen
        cache_key = hashlib.md5(f"{source}_{source_type}".encode()).hexdigest()
        with self._lock:
            if cache_key in self.cache:
                cached_time, cached_data = self.cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                    print(f"📦 Cache-Treffer: {source[:50]}...")
                    return cached_data
        
        # Typ automatisch erkennen
        if source_type == "auto":
            if source.startswith(("http://", "https://")):
                source_type = "url"
            elif os.path.isfile(source):
                source_type = "file"
            else:
                source_type = "text"
        
        # Laden
        if source_type == "url":
            result = self._load_url(source)
        elif source_type == "file":
            result = self._load_file(source)
        elif source_type == "text":
            result = self._load_text_direct(source)
        else:
            raise ValueError(f"Unbekannter Quelltyp: {source_type}")
        
        # Cachen
        with self._lock:
            self.cache[cache_key] = (datetime.now(), result)
        
        return result
    
    def load_multiple(self, sources: List[Dict]) -> Dict:
        """
        Lädt mehrere Dokumente und kombiniert sie.
        
        Args:
            sources: Liste von {"source": str, "type": str, "weight": float}
        
        Returns:
            Kombiniertes Dokument mit Quellen-Angaben
        """
        documents = []
        total_weight = 0
        
        for src in sources:
            try:
                doc = self.load_document(src["source"], src.get("type", "auto"))
                weight = src.get("weight", 1.0)
                doc["weight"] = weight
                documents.append(doc)
                total_weight += weight
            except Exception as e:
                print(f"⚠️ Fehler beim Laden {src.get('source')}: {e}")
        
        if not documents:
            return {
                "content": "",
                "title": "Keine Dokumente geladen",
                "source": "multiple",
                "type": "multiple",
                "metadata": {"errors": True},
                "sections": [],
                "loaded_at": datetime.now().isoformat()
            }
        
        # Kombinieren
        combined_content = ""
        combined_sections = []
        
        for doc in documents:
            combined_content += f"\n\n--- {doc['title']} ---\n\n{doc['content']}"
            combined_sections.append({
                "title": doc['title'],
                "content": doc['content'],
                "source": doc['source'],
                "weight": doc.get('weight', 1.0)
            })
        
        return {
            "content": combined_content.strip(),
            "title": f"{len(documents)} Dokumente",
            "source": "multiple",
            "type": "multiple",
            "metadata": {
                "documents": documents,
                "total_weight": total_weight,
                "count": len(documents)
            },
            "sections": combined_sections,
            "loaded_at": datetime.now().isoformat()
        }
    
    def _load_url(self, url: str) -> Dict:
        """Lädt eine URL und extrahiert Text"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            if "application/pdf" in content_type:
                # PDF direkt laden
                return self._load_pdf_from_bytes(response.content, url)
            elif "text/html" in content_type:
                return self._load_html_from_text(response.text, url)
            else:
                # Als Text behandeln
                return self._load_text_direct(response.text, url)
                
        except requests.RequestException as e:
            raise Exception(f"URL konnte nicht geladen werden: {e}")
    
    def _load_file(self, filepath: str) -> Dict:
        """Lädt eine Datei basierend auf Erweiterung"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")
        
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext in self.supported_formats:
            return self.supported_formats[ext](filepath)
        else:
            # Fallback: als Text versuchen
            return self._load_text(filepath)
    
    def _load_text(self, filepath: str) -> Dict:
        """Lädt eine Textdatei"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        
        return {
            "content": content,
            "title": os.path.basename(filepath),
            "source": filepath,
            "type": "file",
            "metadata": {
                "size": os.path.getsize(filepath),
                "extension": os.path.splitext(filepath)[1]
            },
            "sections": self._split_sections(content),
            "loaded_at": datetime.now().isoformat()
        }
    
    def _load_pdf(self, filepath: str) -> Dict:
        """Lädt eine PDF-Datei"""
        if PyPDF2 is None:
            raise ImportError("PyPDF2 nicht installiert. Bitte installieren: pip install PyPDF2")
        
        content = ""
        metadata = {}
        
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            metadata = {
                "pages": len(reader.pages),
                "author": reader.metadata.get("/Author", "") if reader.metadata else "",
                "title": reader.metadata.get("/Title", "") if reader.metadata else ""
            }
            
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    content += page_text + "\n\n"
        
        title = metadata.get("title") or os.path.basename(filepath)
        
        return {
            "content": content.strip(),
            "title": title,
            "source": filepath,
            "type": "pdf",
            "metadata": metadata,
            "sections": self._split_sections(content),
            "loaded_at": datetime.now().isoformat()
        }
    
    def _load_pdf_from_bytes(self, data: bytes, source: str) -> Dict:
        """Lädt PDF aus Bytes (z.B. von URL)"""
        if PyPDF2 is None:
            raise ImportError("PyPDF2 nicht installiert")
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        
        try:
            result = self._load_pdf(tmp_path)
            result["source"] = source
            result["type"] = "url_pdf"
            return result
        finally:
            os.unlink(tmp_path)
    
    def _load_html(self, filepath: str) -> Dict:
        """Lädt eine HTML-Datei"""
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
        return self._load_html_from_text(html, filepath)
    
    def _load_html_from_text(self, html: str, source: str) -> Dict:
        """Extrahiert Text aus HTML"""
        if BeautifulSoup is None:
            raise ImportError("BeautifulSoup4 nicht installiert. Bitte installieren: pip install beautifulsoup4")
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Titel extrahieren
        title_tag = soup.find('title')
        title = title_tag.string.strip() if title_tag and title_tag.string else source
        
        # Hauptinhalt extrahieren
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        content = soup.get_text()
        content = re.sub(r'\n\s*\n', '\n\n', content).strip()
        
        return {
            "content": content,
            "title": title,
            "source": source,
            "type": "html",
            "metadata": {"url": source},
            "sections": self._split_sections(content),
            "loaded_at": datetime.now().isoformat()
        }
    
    def _load_json(self, filepath: str) -> Dict:
        """Lädt eine JSON-Datei (z.B. vorbereitete Diskussionsgrundlage)"""
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        content = ""
        if isinstance(data, dict):
            # Versuche, relevanten Text zu extrahieren
            if "content" in data:
                content = data["content"]
            elif "text" in data:
                content = data["text"]
            elif "body" in data:
                content = data["body"]
            else:
                content = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            content = str(data)
        
        return {
            "content": content,
            "title": data.get("title", os.path.basename(filepath)) if isinstance(data, dict) else os.path.basename(filepath),
            "source": filepath,
            "type": "json",
            "metadata": data if isinstance(data, dict) else {},
            "sections": self._split_sections(content),
            "loaded_at": datetime.now().isoformat()
        }
    
    def _load_text_direct(self, text: str, source: str = "text_input") -> Dict:
        """Lädt direkt eingegebenen Text"""
        return {
            "content": text,
            "title": "Direkte Texteingabe",
            "source": source,
            "type": "text",
            "metadata": {"length": len(text)},
            "sections": self._split_sections(text),
            "loaded_at": datetime.now().isoformat()
        }
    
    def _split_sections(self, text: str) -> List[Dict]:
        """
        Teilt Text in Abschnitte (für strukturierte Diskussion)
        """
        sections = []
        
        # Nach Überschriften suchen (Markdown oder Nummerierung)
        lines = text.split('\n')
        current_section = {"title": "Einleitung", "content": []}
        
        for line in lines:
            # Prüfe auf Überschrift
            if line.startswith('#'):
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section)
                current_section = {"title": line.lstrip('#').strip(), "content": []}
            elif re.match(r'^\d+\.', line):
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section)
                current_section = {"title": line.strip(), "content": []}
            else:
                current_section["content"].append(line)
        
        # Letzte Section speichern
        if current_section["content"]:
            current_section["content"] = '\n'.join(current_section["content"])
            sections.append(current_section)
        
        return sections if len(sections) > 1 else []
    
    def generate_summary(self, document: Dict, lm_client=None) -> str:
        """
        Generiert eine Zusammenfassung des Dokuments (optional mit LLM)
        """
        content = document["content"]
        
        if lm_client and len(content) > 200:
            prompt = f"""Fasse folgenden Text in 2-3 Sätzen zusammen. Sei präzise und objektiv:

{content[:2000]}"""
            try:
                summary = lm_client.ask(prompt, "Dokument-Zusammenfassung", max_tokens=100)
                document["summary"] = summary
                return summary
            except:
                pass
        
        # Fallback: erste 300 Zeichen
        summary = content[:300] + "..." if len(content) > 300 else content
        document["summary"] = summary
        return summary
    
    def clear_cache(self):
        """Leert den Cache"""
        with self._lock:
            self.cache.clear()
        print("🧹 DocumentLoader-Cache geleert")
    
    def get_stats(self) -> Dict:
        """Gibt Cache-Statistiken zurück"""
        with self._lock:
            return {
                "cache_size": len(self.cache),
                "supported_formats": list(self.supported_formats.keys())
            }


# ==================== HILFSKLASSEN ====================

class DocumentCache:
    """Einfacher Cache für häufig verwendete Dokumente"""
    
    def __init__(self, max_size=50):
        self.cache = {}
        self.max_size = max_size
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Dict]:
        with self._lock:
            if key in self.cache:
                return self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        with self._lock:
            if len(self.cache) >= self.max_size:
                # Entferne ältesten Eintrag
                oldest = min(self.cache.keys(), key=lambda k: self.cache[k].get("_timestamp", 0))
                del self.cache[oldest]
            self.cache[key] = value
    
    def clear(self):
        with self._lock:
            self.cache.clear()


# ==================== TEST ====================

if __name__ == "__main__":
    loader = DocumentLoader()
    
    # Test: Text laden
    doc = loader.load_document("Das ist ein Testdokument. Es enthält wichtige Informationen.", "text")
    print(f"✅ Text geladen: {doc['title']} ({len(doc['content'])} Zeichen)")
    
    # Test: Datei laden (falls vorhanden)
    test_file = os.path.join(Config.EXAMPLES_FOLDER, "example.txt")
    if os.path.exists(test_file):
        doc = loader.load_document(test_file, "file")
        print(f"✅ Datei geladen: {doc['title']} ({len(doc['content'])} Zeichen)")
    
    print(f"📊 Stats: {loader.get_stats()}")