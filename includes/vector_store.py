#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAISS-Vektordatenbank für Projekte
"""

import os
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
import pickle

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("⚠️ FAISS nicht installiert. pip install faiss-cpu")

from .config import Config
from .embedding_client import EmbeddingClient


class VectorStore:
    """FAISS-basierte Vektordatenbank"""
    
    def __init__(self, project_path: str, dimension: int = None):
        self.project_path = project_path
        self.dimension = dimension or Config.EMBEDDING_DIMENSION
        self.index_path = os.path.join(project_path, "vector_store", "index.faiss")
        self.meta_path = os.path.join(project_path, "vector_store", "metadata.pkl")
        self.embedder = EmbeddingClient()
        
        self.index = None
        self.metadata = []  # [(text, source, chunk_hash), ...]
        
        self._ensure_dir()
        self._load_or_create()
    
    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
    
    def _load_or_create(self):
        """Lädt vorhandenen Index oder erstellt neuen"""
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.meta_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                print(f"📚 Vektorstore geladen: {len(self.metadata)} Chunks")
            except Exception as e:
                print(f"⚠️ Fehler beim Laden: {e}, erstelle neu")
                self._create_new()
        else:
            self._create_new()
    
    def _create_new(self):
        """Erstellt neuen leeren Index"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        print(f"🆕 Neuer Vektorstore erstellt (Dimension {self.dimension})")
    
    def add_chunks(self, chunks: List[Tuple[str, Dict]]) -> int:
        """
        Fügt Chunks hinzu.
        chunks: [(text, metadata), ...]
        metadata muss 'source' und 'chunk_hash' enthalten
        """
        if not chunks:
            return 0
        
        # Texte extrahieren
        texts = [c[0] for c in chunks]
        
        # Embeddings generieren
        embeddings = self.embedder.embed_batch(texts)
        
        # Zu FAISS hinzufügen
        vectors = np.array(embeddings, dtype=np.float32)
        current_count = self.index.ntotal
        self.index.add(vectors)
        
        # Metadaten speichern
        for i, (text, meta) in enumerate(chunks):
            self.metadata.append({
                "id": current_count + i,
                "text": text,
                "source": meta.get("source", "unknown"),
                "document": meta.get("document", "unknown"),
                "chunk_hash": meta.get("chunk_hash", ""),
                "project": meta.get("project", ""),
                "metadata": meta
            })
        
        self.save()
        return len(chunks)
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Sucht ähnliche Chunks"""
        if self.index.ntotal == 0:
            return []
        
        # Query embedden
        query_vec = self.embedder.embed(query)
        query_array = np.array([query_vec], dtype=np.float32)
        
        # Suchen
        distances, indices = self.index.search(query_array, min(k, self.index.ntotal))
        
        # Ergebnisse sammeln
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx >= 0 and idx < len(self.metadata):
                meta = self.metadata[idx].copy()
                meta["distance"] = float(dist)
                meta["similarity"] = 1.0 / (1.0 + dist)
                results.append(meta)
        
        return results
    
    def search_by_texts(self, texts: List[str], k: int = 5) -> List[List[Dict]]:
        """Sucht für mehrere Texte gleichzeitig"""
        embeddings = self.embedder.embed_batch(texts)
        vectors = np.array(embeddings, dtype=np.float32)
        
        distances, indices = self.index.search(vectors, min(k, self.index.ntotal))
        
        results = []
        for i in range(len(texts)):
            row = []
            for j, idx in enumerate(indices[i]):
                if idx >= 0 and idx < len(self.metadata):
                    meta = self.metadata[idx].copy()
                    meta["distance"] = float(distances[i][j])
                    meta["similarity"] = 1.0 / (1.0 + distances[i][j])
                    row.append(meta)
            results.append(row)
        
        return results
    
    def get_all_chunks(self) -> List[Dict]:
        """Gibt alle Chunks zurück"""
        return self.metadata.copy()
    
    def save(self):
        """Speichert Index und Metadaten"""
        if self.index:
            faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def clear(self):
        """Löscht alle Daten"""
        self._create_new()
        self.save()
    
    def size(self) -> int:
        """Anzahl der Chunks"""
        return self.index.ntotal if self.index else 0