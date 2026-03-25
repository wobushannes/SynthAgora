#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config-Modul für SynthAgora
ERWEITERT: Embedding, Projekte, Zitier-Pflicht, Plugin-Kategorien
"""

import os
import json
from pathlib import Path


class Config:
    """Zentrale Konfiguration für SynthAgora"""
    
    # ==================== LLM PROVIDER ====================
    LM_PROVIDER = "lmstudio"  # lmstudio, ollama, openai, grok, claude
    
    # LM Studio
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    
    # Ollama
    OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
    OLLAMA_MODEL = "llama3.2:3b"
    
    # OpenAI
    OPENAI_API_KEY = ""
    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_BASE_URL = "https://api.openai.com/v1"
    
    # Grok (xAI)
    GROK_API_KEY = ""
    GROK_MODEL = "grok-beta"
    GROK_BASE_URL = "https://api.x.ai/v1"
    
    # Claude (Anthropic)
    CLAUDE_API_KEY = ""
    CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
    CLAUDE_BASE_URL = "https://api.anthropic.com/v1"
    
    # ==================== LLM PARAMETER ====================
    TEMPERATURE = 0.7
    MAX_TOKENS = 300
    TIMEOUT = 60
    
    # ==================== EMBEDDING (NEU - SENTENCE TRANSFORMER) ====================
    EMBEDDING_PROVIDER = "sentence_transformer"  # sentence_transformer, lmstudio, ollama, openai
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # all-MiniLM-L6-v2, paraphrase-multilingual-MiniLM-L12-v2, etc.
    EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2 hat 384 Dimensionen
    EMBEDDING_BATCH_SIZE = 32
    EMBEDDING_DEVICE = "cuda"  # cuda, cpu
    
    # ==================== ORDNERSTRUKTUR ====================
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    AGENTS_FOLDER = os.path.join(BASE_DIR, "agents")
    MODERATORS_FOLDER = os.path.join(BASE_DIR, "moderators")
    EXAMPLES_FOLDER = os.path.join(BASE_DIR, "examples")
    EXPORTS_FOLDER = os.path.join(BASE_DIR, "exports")
    MEMORY_FOLDER = os.path.join(BASE_DIR, "memory")
    KNOWLEDGE_FOLDER = os.path.join(BASE_DIR, "knowledge")
    PLUGINS_FOLDER = os.path.join(BASE_DIR, "plugins")
    
    # ==================== PROJEKTE (NEU) ====================
    PROJECTS_FOLDER = os.path.join(BASE_DIR, "projects")
    
    # ==================== CHUNKING (NEU) ====================
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP = 200
    
    # ==================== PLUGIN-SYSTEM (NEU) ====================
    PLUGIN_CATEGORIES = ["tasks", "synthesis", "export"]
    
    # ==================== ZITIER-PFLICHT (NEU) ====================
    CITATION_REQUIRED_FOR_RANKS = ["Junior"]  # Pflicht für diese Ränge
    CITATION_BONUS_FOR_RANKS = ["Senior", "Experte", "Master"]  # Bonus für diese Ränge
    CITATION_PENALTY = 1  # Punkteabzug pro fehlendem Zitat
    
    # ==================== SIMULATION ====================
    MAX_AGENTS = 500
    DEFAULT_ROUNDS = 3
    DEFAULT_PURPOSE = "Diskussion"
    
    # ==================== SKILLS & EVOLUTION ====================
    SKILL_GAIN_FACTOR = 0.05
    XP_PER_CONTRIBUTION = 5
    XP_PER_REACTION = 3
    XP_PER_LEARNED_FACT = 10
    XP_PER_ANALYSIS = 10
    XP_PER_PROGNOSIS = 8
    
    RANK_THRESHOLDS = {
        "Junior": 0,
        "Senior": 1000,
        "Experte": 5000,
        "Master": 20000
    }
    
    # ==================== DUPLIKAT-ERKENNUNG ====================
    DUPLICATE_SIMILARITY_THRESHOLD = 0.85
    LOCAL_DUPLICATE_THRESHOLD = 0.7
    TIME_WINDOW_DUPLICATE = 5  # Sekunden
    
    # ==================== MAXIMALE GRÖSSEN ====================
    MAX_LEARNED_FACTS_PER_AGENT = 500
    MAX_DISCUSSION_LOG = 100
    MAX_MEMORY_RESULTS = 1000
    
    @classmethod
    def load_from_file(cls, path: str = None):
        """Lädt Konfiguration aus JSON-Datei"""
        if path is None:
            path = os.path.join(cls.BASE_DIR, "config.json")
        
        if not os.path.exists(path):
            cls.save_to_file(path)
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key, value in data.items():
                if hasattr(cls, key):
                    setattr(cls, key, value)
            
            print(f"✅ Konfiguration geladen von {path}")
        except Exception as e:
            print(f"⚠️ Konfiguration konnte nicht geladen werden: {e}")
    
    @classmethod
    def save_to_file(cls, path: str = None):
        """Speichert Konfiguration in JSON-Datei"""
        if path is None:
            path = os.path.join(cls.BASE_DIR, "config.json")
        
        # Alle relevanten Attribute sammeln
        config_data = {}
        for key in dir(cls):
            if key.isupper() and not key.startswith('_'):
                value = getattr(cls, key)
                # Überspringe Methoden und Callables
                if not callable(value):
                    config_data[key] = value
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Konfiguration gespeichert in {path}")
            return True
        except Exception as e:
            print(f"❌ Konfiguration konnte nicht gespeichert werden: {e}")
            return False
    
    @classmethod
    def ensure_folders(cls):
        """Stellt sicher, dass alle benötigten Ordner existieren"""
        folders = [
            cls.AGENTS_FOLDER,
            cls.MODERATORS_FOLDER,
            cls.EXAMPLES_FOLDER,
            cls.EXPORTS_FOLDER,
            cls.MEMORY_FOLDER,
            cls.KNOWLEDGE_FOLDER,
            cls.PLUGINS_FOLDER,
            cls.PROJECTS_FOLDER  # NEU
        ]
        
        # Plugin-Unterordner (NEU)
        for cat in cls.PLUGIN_CATEGORIES:
            folders.append(os.path.join(cls.PLUGINS_FOLDER, cat))
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)


# Beim Import automatisch laden
Config.load_from_file()
Config.ensure_folders()