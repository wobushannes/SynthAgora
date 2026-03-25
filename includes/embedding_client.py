#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding-Client für Vektordatenbank
- Unterstützt SentenceTransformer (lokal), LM Studio, Ollama, OpenAI
"""

import requests
import numpy as np
from typing import List, Union
import time
import json
import torch

from .config import Config


class EmbeddingClient:
    """Client für Embedding-APIs"""
    
    def __init__(self):
        self.provider = Config.EMBEDDING_PROVIDER
        self.model_name = Config.EMBEDDING_MODEL
        self.dimension = Config.EMBEDDING_DIMENSION
        self.batch_size = Config.EMBEDDING_BATCH_SIZE
        self.device = Config.EMBEDDING_DEVICE if torch.cuda.is_available() else "cpu"
        self._session = requests.Session()
        self._model = None  # Für SentenceTransformer
        self._load_model()
    
    def _load_model(self):
        """Lädt das SentenceTransformer Modell (falls verwendet)"""
        if self.provider == "sentence_transformer":
            try:
                from sentence_transformers import SentenceTransformer
                print(f"📦 Lade SentenceTransformer Modell: {self.model_name} (device={self.device})")
                self._model = SentenceTransformer(self.model_name, device=self.device)
                # Test-Embedding um Dimension zu bestimmen
                test_embedding = self._model.encode(["test"], convert_to_numpy=True)
                self.dimension = test_embedding.shape[1]
                print(f"✅ Modell geladen. Dimension: {self.dimension}")
            except ImportError:
                print("⚠️ sentence_transformers nicht installiert. Bitte ausführen: pip install sentence-transformers")
                self.provider = "random"
            except Exception as e:
                print(f"⚠️ Fehler beim Laden des Modells: {e}")
                self.provider = "random"
    
    def embed(self, text: str) -> List[float]:
        """Erzeugt Embedding für einzelnen Text"""
        result = self.embed_batch([text])
        return result[0] if result else [0.0] * self.dimension
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Erzeugt Embeddings für mehrere Texte"""
        if not texts:
            return []
        
        if self.provider == "sentence_transformer":
            return self._embed_sentence_transformer(texts)
        elif self.provider == "lmstudio":
            return self._embed_lmstudio(texts)
        elif self.provider == "ollama":
            return self._embed_ollama(texts)
        elif self.provider == "openai":
            return self._embed_openai(texts)
        else:
            # Fallback: random embeddings
            return [self._random_embedding() for _ in texts]
    
    def _embed_sentence_transformer(self, texts: List[str]) -> List[List[float]]:
        """SentenceTransformer (lokal) - wie in index.py"""
        if self._model is None:
            return [self._random_embedding() for _ in texts]
        
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                embeddings = self._model.encode(
                    batch,
                    convert_to_numpy=True,
                    batch_size=len(batch),
                    show_progress_bar=False
                )
                for emb in embeddings:
                    results.append(emb.tolist())
            except Exception as e:
                print(f"⚠️ SentenceTransformer Embedding fehlgeschlagen: {e}")
                for _ in batch:
                    results.append(self._random_embedding())
        
        return results
    
    def _embed_lmstudio(self, texts: List[str]) -> List[List[float]]:
        """LM Studio Embeddings"""
        results = []
        
        for text in texts:
            try:
                url = Config.LM_STUDIO_URL.replace("/chat/completions", "/embeddings")
                
                payload = {
                    "input": text,
                    "model": "embedding"
                }
                
                resp = self._session.post(url, json=payload, timeout=Config.TIMEOUT)
                
                if resp.status_code != 200:
                    print(f"⚠️ LM Studio Embedding HTTP {resp.status_code}")
                    results.append(self._random_embedding())
                    continue
                
                data = resp.json()
                
                if "data" in data and len(data["data"]) > 0:
                    if "embedding" in data["data"][0]:
                        results.append(data["data"][0]["embedding"])
                    else:
                        results.append(data["data"][0])
                elif "embedding" in data:
                    results.append(data["embedding"])
                else:
                    print(f"⚠️ LM Studio Embedding: Unerwartetes Format. Keys: {list(data.keys())}")
                    results.append(self._random_embedding())
                    
            except Exception as e:
                print(f"⚠️ LM Studio Embedding fehlgeschlagen: {e}")
                results.append(self._random_embedding())
        
        return results
    
    def _embed_ollama(self, texts: List[str]) -> List[List[float]]:
        """Ollama Embeddings"""
        url = Config.OLLAMA_URL.replace("/v1/chat/completions", "/api/embeddings")
        results = []
        
        for text in texts:
            try:
                resp = self._session.post(url, json={
                    "model": Config.EMBEDDING_MODEL,
                    "prompt": text
                }, timeout=Config.TIMEOUT)
                
                if resp.status_code != 200:
                    print(f"⚠️ Ollama Embedding HTTP {resp.status_code}")
                    results.append(self._random_embedding())
                    continue
                
                data = resp.json()
                if "embedding" in data:
                    results.append(data["embedding"])
                else:
                    print(f"⚠️ Ollama Embedding: Unerwartetes Format. Keys: {list(data.keys())}")
                    results.append(self._random_embedding())
                    
            except Exception as e:
                print(f"⚠️ Ollama Embedding fehlgeschlagen: {e}")
                results.append(self._random_embedding())
        
        return results
    
    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """OpenAI Embeddings"""
        if not Config.OPENAI_API_KEY:
            print("⚠️ OpenAI API Key nicht konfiguriert")
            return [self._random_embedding() for _ in texts]
        
        url = "https://api.openai.com/v1/embeddings"
        headers = {"Authorization": f"Bearer {Config.OPENAI_API_KEY}"}
        
        try:
            resp = self._session.post(url, json={
                "model": "text-embedding-ada-002",
                "input": texts
            }, headers=headers, timeout=Config.TIMEOUT)
            
            if resp.status_code != 200:
                print(f"⚠️ OpenAI Embedding HTTP {resp.status_code}")
                return [self._random_embedding() for _ in texts]
            
            data = resp.json()
            results = []
            for item in data.get("data", []):
                results.append(item.get("embedding", self._random_embedding()))
            
            while len(results) < len(texts):
                results.append(self._random_embedding())
            
            return results
            
        except Exception as e:
            print(f"⚠️ OpenAI Embedding fehlgeschlagen: {e}")
            return [self._random_embedding() for _ in texts]
    
    def _random_embedding(self) -> List[float]:
        """Fallback: Zufälliges Embedding"""
        return np.random.randn(self.dimension).tolist()
    
    def test(self) -> tuple:
        """Testet die Embedding-API"""
        try:
            test_text = "Test"
            embedding = self.embed(test_text)
            
            if len(embedding) == self.dimension:
                return True, f"✅ {self.provider}: {self.model_name} (Dimension {self.dimension})"
            return False, f"❌ Dimension falsch: {len(embedding)} != {self.dimension}"
            
        except Exception as e:
            return False, f"❌ Fehler: {e}"