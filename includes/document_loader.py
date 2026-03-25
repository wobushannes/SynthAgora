#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document Loader für SynthAgora
- Lädt Dokumente aus Dateien, URLs, Ordnern
- Extrahiert Text aus PDF, HTML, TXT, etc.
"""

import os
import re
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse


class DocumentLoader:
    """Lädt und extrahiert Text aus verschiedenen Quellen"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def load_document(self, source: str, source_type: str = "auto") -> Dict[str, Any]:
        """
        Lädt ein Dokument.
        source: Dateipfad oder URL
        source_type: 'file', 'url', 'auto'
        Returns: Dict mit title, content, source, loaded_at, hash
        """
        if source_type == "auto":
            if source.startswith(('http://', 'https://')):
                source_type = "url"
            else:
                source_type = "file"
        
        if source_type == "url":
            return self._load_url(source)
        elif source_type == "file":
            return self._load_file(source)
        else:
            raise ValueError(f"Unbekannter Quelltyp: {source_type}")
    
    def _load_file(self, filepath: str) -> Dict[str, Any]:
        """Lädt eine Datei"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")
        
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == '.txt':
            content = self._load_text(filepath)
        elif ext == '.pdf':
            content = self._load_pdf(filepath)
        elif ext in ['.html', '.htm']:
            content = self._load_html_file(filepath)
        elif ext == '.json':
            content = self._load_json(filepath)
        elif ext == '.csv':
            content = self._load_csv(filepath)
        elif ext == '.md':
            content = self._load_text(filepath)
        elif ext == '.xml':
            content = self._load_text(filepath)
        else:
            # Fallback: als Text versuchen
            try:
                content = self._load_text(filepath)
            except:
                content = f"[Kann Dateiformat {ext} nicht lesen]"
        
        # Hash berechnen
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        return {
            "title": os.path.basename(filepath),
            "content": content,
            "source": filepath,
            "source_type": "file",
            "loaded_at": datetime.now().isoformat(),
            "hash": content_hash,
            "size": len(content),
            "extension": ext
        }
    
    def _load_url(self, url: str) -> Dict[str, Any]:
        """Lädt eine URL"""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            # Content-Type bestimmen
            content_type = resp.headers.get('content-type', '').lower()
            
            if 'text/html' in content_type:
                content = self._extract_html_text(resp.text)
                title = self._extract_html_title(resp.text) or os.path.basename(urlparse(url).path) or urlparse(url).netloc
            elif 'application/pdf' in content_type:
                # PDF von URL speichern und laden
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
                    f.write(resp.content)
                    content = self._load_pdf(f.name)
                os.unlink(f.name)
                title = os.path.basename(urlparse(url).path) or "PDF Dokument"
            elif 'text/plain' in content_type:
                content = resp.text
                title = os.path.basename(urlparse(url).path) or "Text Dokument"
            elif 'application/json' in content_type:
                content = resp.text
                title = os.path.basename(urlparse(url).path) or "JSON Dokument"
            else:
                content = resp.text[:100000]
                title = os.path.basename(urlparse(url).path) or "Dokument"
            
            # Hash berechnen
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            return {
                "title": title,
                "content": content,
                "source": url,
                "source_type": "url",
                "loaded_at": datetime.now().isoformat(),
                "hash": content_hash,
                "size": len(content),
                "content_type": content_type
            }
            
        except requests.exceptions.Timeout:
            raise Exception(f"Zeitüberschreitung beim Laden von: {url}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Netzwerkfehler: {e}")
        except Exception as e:
            raise Exception(f"URL konnte nicht geladen werden: {e}")
    
    def _load_text(self, filepath: str) -> str:
        """Lädt reine Textdatei"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(filepath, 'r', encoding='latin-1') as f:
                    return f.read()
            except:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
    
    def _load_pdf(self, filepath: str) -> str:
        """Extrahiert Text aus PDF"""
        try:
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"[Seite {page_num + 1}]\n{page_text}")
                    except Exception as e:
                        text_parts.append(f"[Seite {page_num + 1}: Fehler bei Extraktion - {e}]")
            return "\n\n".join(text_parts)
        except ImportError:
            return "[PyPDF2 nicht installiert. Bitte ausführen: pip install PyPDF2]"
        except Exception as e:
            return f"[PDF-Fehler: {e}]"
    
    def _load_html_file(self, filepath: str) -> str:
        """Extrahiert Text aus HTML-Datei"""
        try:
            from bs4 import BeautifulSoup
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
                # Entferne Script und Style
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                text = soup.get_text()
                # Clean up
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                return "\n".join(lines)
        except ImportError:
            # Fallback: einfaches Regex
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content)
                return content.strip()
        except Exception as e:
            return f"[HTML-Fehler: {e}]"
    
    def _load_json(self, filepath: str) -> str:
        """Lädt JSON-Datei"""
        try:
            import json
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"[JSON-Fehler: {e}]"
    
    def _load_csv(self, filepath: str) -> str:
        """Lädt CSV-Datei"""
        try:
            import csv
            rows = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0:
                        rows.append("Spalten: " + ", ".join(row))
                    else:
                        rows.append(", ".join(row))
            return "\n".join(rows)
        except Exception as e:
            return f"[CSV-Fehler: {e}]"
    
    def _extract_html_text(self, html: str) -> str:
        """Extrahiert Text aus HTML-String"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            text = soup.get_text()
            # Clean up
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
        except ImportError:
            # Fallback
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
    
    def _extract_html_title(self, html: str) -> Optional[str]:
        """Extrahiert Titel aus HTML"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                return title_tag.get_text().strip()
        except:
            pass
        return None
    
    def load_multiple(self, sources: List[Dict]) -> Dict[str, Any]:
        """
        Lädt mehrere Dokumente.
        sources: [{"source": "pfad", "type": "auto", "weight": 1.0}, ...]
        """
        documents = []
        total_weight = 0
        
        for item in sources:
            try:
                doc = self.load_document(item["source"], item.get("type", "auto"))
                doc["weight"] = item.get("weight", 1.0)
                documents.append(doc)
                total_weight += doc["weight"]
            except Exception as e:
                print(f"⚠️ Fehler bei {item['source']}: {e}")
        
        if not documents:
            raise Exception("Keine Dokumente konnten geladen werden")
        
        # Kombinierter Inhalt
        combined_content = ""
        for doc in documents:
            weight = doc["weight"]
            combined_content += f"\n\n--- {doc['title']} (Gewicht: {weight}) ---\n"
            combined_content += doc["content"]
        
        # Hash aus Kombination
        combined_hash = hashlib.md5(combined_content.encode('utf-8')).hexdigest()
        
        return {
            "title": f"Kombiniert ({len(documents)} Dokumente)",
            "content": combined_content,
            "source": "multiple",
            "source_type": "multiple",
            "loaded_at": datetime.now().isoformat(),
            "hash": combined_hash,
            "size": len(combined_content),
            "documents": documents,
            "total_weight": total_weight,
            "document_count": len(documents)
        }
    
    def load_folder(self, folder_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Lädt alle unterstützten Dateien aus einem Ordner.
        """
        supported_extensions = ['.txt', '.pdf', '.html', '.htm', '.json', '.csv', '.md', '.xml']
        results = []
        
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Ordner nicht gefunden: {folder_path}")
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_extensions:
                    filepath = os.path.join(root, file)
                    try:
                        doc = self.load_document(filepath, "file")
                        results.append(doc)
                        print(f"  ✅ {file}")
                    except Exception as e:
                        print(f"  ❌ {file}: {e}")
            
            if not recursive:
                break
        
        return results
    
    def get_supported_extensions(self) -> List[str]:
        """Gibt Liste der unterstützten Dateierweiterungen zurück"""
        return ['.txt', '.pdf', '.html', '.htm', '.json', '.csv', '.md', '.xml']
    
    def is_supported(self, filepath: str) -> bool:
        """Prüft ob Datei unterstützt wird"""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in self.get_supported_extensions()