#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Projekt-Management mit Vektordatenbank
"""

import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any

from .config import Config
from .vector_store import VectorStore
from .document_loader import DocumentLoader
from .database import SynthAgoraDB


class Project:
    """Ein Projekt mit Dokumenten und Vektorstore"""
    
    def __init__(self, name: str, project_path: str):
        self.name = name
        self.path = project_path
        self.metadata_path = os.path.join(project_path, "metadata.json")
        self.documents_path = os.path.join(project_path, "documents")
        self.original_path = os.path.join(self.documents_path, "original")
        self.parsed_path = os.path.join(self.documents_path, "parsed")
        
        os.makedirs(self.original_path, exist_ok=True)
        os.makedirs(self.parsed_path, exist_ok=True)
        
        self.metadata = self._load_metadata()
        self.vector_store = VectorStore(project_path)
        self.documents = self._load_documents()
    
    def _load_metadata(self) -> Dict:
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "name": self.name,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "document_count": 0,
            "chunk_count": 0
        }
    
    def _load_documents(self) -> List[Dict]:
        docs = []
        if os.path.exists(self.parsed_path):
            for f in os.listdir(self.parsed_path):
                if f.endswith('.json'):
                    try:
                        with open(os.path.join(self.parsed_path, f), 'r', encoding='utf-8') as fp:
                            docs.append(json.load(fp))
                    except:
                        pass
        return docs
    
    def save_metadata(self):
        self.metadata["updated"] = datetime.now().isoformat()
        self.metadata["chunk_count"] = self.vector_store.size()
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def add_document(self, source: str, source_type: str = "auto") -> Dict:
        loader = DocumentLoader()
        doc = loader.load_document(source, source_type)
        
        doc_hash = hashlib.md5(doc['content'].encode()).hexdigest()[:16]
        
        parsed_path = os.path.join(self.parsed_path, f"{doc_hash}.json")
        with open(parsed_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        
        chunks = self._chunk_document(doc['content'])
        
        chunk_items = []
        for i, chunk in enumerate(chunks):
            chunk_items.append((
                chunk,
                {
                    "source": doc['source'],
                    "document": doc['title'],
                    "chunk_index": i,
                    "project": self.name,
                    "doc_hash": doc_hash
                }
            ))
        
        added = self.vector_store.add_chunks(chunk_items)
        
        self.documents.append(doc)
        self.metadata["document_count"] = len(self.documents)
        self.save_metadata()
        
        return {"title": doc['title'], "source": doc['source'], "chunks": added}
    
    def _chunk_document(self, content: str) -> List[str]:
        chunk_size = self.metadata.get("chunk_size", 1000)
        chunk_overlap = self.metadata.get("chunk_overlap", 200)
        
        chunks = []
        start = 0
        content_len = len(content)
        
        while start < content_len:
            end = min(start + chunk_size, content_len)
            chunks.append(content[start:end])
            if end >= content_len:
                break
            start = end - chunk_overlap
        
        return chunks
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        return self.vector_store.search(query, k)
    
    def get_context(self, query: str, k: int = 5) -> str:
        results = self.search(query, k)
        if not results:
            return ""
        
        context = "\n\n[RELEVANTE DOKUMENTE]\n"
        for r in results:
            context += f"📄 {r.get('source', '?')} - {r.get('document', '?')}:\n{r['text'][:500]}\n\n"
        return context


class ProjectManager:
    """Verwaltet alle Projekte"""
    
    def __init__(self):
        self.projects_folder = getattr(Config, 'PROJECTS_FOLDER', 'projects')
        self.projects: Dict[str, Project] = {}
        self._load_all_projects()
    
    def _load_all_projects(self):
        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder, exist_ok=True)
            return
        
        for item in os.listdir(self.projects_folder):
            project_path = os.path.join(self.projects_folder, item)
            if os.path.isdir(project_path):
                try:
                    self.projects[item] = Project(item, project_path)
                    print(f"📁 Projekt geladen: {item} ({self.projects[item].vector_store.size()} Chunks)")
                except Exception as e:
                    print(f"⚠️ Fehler beim Laden von {item}: {e}")
    
    def create_project(self, name: str) -> Project:
        if name in self.projects:
            raise ValueError(f"Projekt {name} existiert bereits")
        
        project_path = os.path.join(self.projects_folder, name)
        os.makedirs(project_path, exist_ok=True)
        
        project = Project(name, project_path)
        project.save_metadata()
        self.projects[name] = project
        
        print(f"✅ Projekt erstellt: {name}")
        return project
    
    def get_project(self, name: str) -> Optional[Project]:
        return self.projects.get(name)
    
    def get_or_create(self, name: str) -> Project:
        if name in self.projects:
            return self.projects[name]
        return self.create_project(name)
    
    def list_projects(self) -> List[Dict]:
        projects = []
        for name, project in self.projects.items():
            projects.append({
                "name": name,
                "created": project.metadata.get("created"),
                "document_count": project.metadata.get("document_count", 0),
                "chunk_count": project.vector_store.size()
            })
        return projects
    
    def delete_project(self, name: str):
        if name not in self.projects:
            raise ValueError(f"Projekt {name} nicht gefunden")
        shutil.rmtree(self.projects[name].path)
        del self.projects[name]
        print(f"🗑️ Projekt gelöscht: {name}")
    
    def add_document_to_project(self, project_name: str, source: str, source_type: str = "auto") -> Dict:
        project = self.get_or_create(project_name)
        try:
            return project.add_document(source, source_type)
        except Exception as e:
            print(f"❌ Fehler beim Hinzufügen von {source}: {e}")
            raise
    
    def add_folder_to_project(self, project_name: str, folder_path: str) -> List[Dict]:
        project = self.get_or_create(project_name)
        results = []
        
        extensions = ['.txt', '.pdf', '.md', '.html', '.htm', '.json', '.csv']
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    filepath = os.path.join(root, file)
                    try:
                        result = project.add_document(filepath, "file")
                        results.append(result)
                        print(f"  ✅ {file}")
                    except Exception as e:
                        print(f"  ❌ {file}: {e}")
        
        return results
    
    def search_projects(self, query: str, projects: List[str] = None, k: int = 5) -> List[Dict]:
        all_results = []
        target_projects = projects or list(self.projects.keys())
        
        for proj_name in target_projects:
            project = self.projects.get(proj_name)
            if project:
                try:
                    results = project.search(query, k)
                    for r in results:
                        r["project"] = proj_name
                    all_results.extend(results)
                except Exception as e:
                    print(f"⚠️ Fehler bei Suche in {proj_name}: {e}")
        
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return all_results[:k * len(target_projects)]
    
    def get_context(self, query: str, projects: List[str] = None, k: int = 5) -> str:
        results = self.search_projects(query, projects, k)
        if not results:
            return ""
        
        context = "\n\n[RELEVANTE DOKUMENTE]\n"
        for r in results:
            project = r.get("project", "?")
            source = r.get("source", "?")
            doc = r.get("document", "?")
            context += f"📄 [{project}] {source} - {doc}:\n{r['text'][:500]}\n\n"
        
        return context