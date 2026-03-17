#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║  🐟 SynthAgora - Konfigurationsdatei                               ║
║  Ausgelagert für bessere Übersichtlichkeit                             ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import json
import os
from datetime import datetime

class Config:
    # ===================== PROVIDER =====================
    # Standard: LM Studio
    LM_PROVIDER = "lmstudio"  # lmstudio, ollama, openai(beta), grok(beta), claude(beta)
    
    # ===================== LM STUDIO =====================
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    
    # ===================== OLLAMA =====================
    OLLAMA_URL = "http://localhost:11434/api/chat"
    OLLAMA_MODEL = "llama3"
    
    # ===================== OPENAI (BETA) =====================
    OPENAI_URL = "https://api.openai.com/v1/chat/completions"
    OPENAI_MODEL = "gpt-3.5-turbo"
    OPENAI_API_KEY = ""  # Hier API-Key eintragen für echte Anfragen
    
    # ===================== GROK (BETA) =====================
    GROK_URL = "https://api.x.ai/v1/chat/completions"
    GROK_MODEL = "grok-1"
    GROK_API_KEY = ""  # Hier API-Key eintragen für echte Anfragen
    
    # ===================== CLAUDE (BETA) =====================
    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    CLAUDE_MODEL = "claude-3-opus-20240229"
    CLAUDE_API_KEY = ""  # Hier API-Key eintragen für echte Anfragen
    CLAUDE_VERSION = "2023-06-01"
    
    # ===================== ALLGEMEINE EINSTELLUNGEN =====================
    TIMEOUT = 30
    TEMPERATURE = 0.7
    MAX_TOKENS = 300
    
    # ===================== ORDNER =====================
    AGENTS_FOLDER = "agents"
    MODERATORS_FOLDER = "moderators"
    EXAMPLES_FOLDER = "examples"
    EXPORTS_FOLDER = "exports"
    MEMORY_FOLDER = "memory"
    KNOWLEDGE_FOLDER = "knowledge_graph"
    
    # ===================== UI FARBEN =====================
    BG_MAIN = "#1a1a1a"
    BG_PANEL = "#2d2d2d"
    BG_INPUT = "#3c3c3c"
    BG_BUTTON = "#0e639c"
    BG_BUTTON_HOVER = "#1177bb"
    BG_STOP = "#b52b2b"
    BG_STOP_HOVER = "#c43a3a"
    
    FG = "#ffffff"
    FG_DIM = "#cccccc"
    FG_BUTTON = "#ffffff"
    
    SUCCESS = "#2e7d32"
    ERROR = "#b52b2b"
    WARNING = "#ff9900"
    BETA = "#9b59b6"
    
    @classmethod
    def load_from_file(cls, filepath="config.json"):
        """Lädt die Konfiguration aus einer JSON-Datei"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # LM Studio
            lm = data.get("lm_studio", {})
            cls.LM_STUDIO_URL = lm.get("url", cls.LM_STUDIO_URL)
            
            # Ollama
            ollama = data.get("ollama", {})
            cls.OLLAMA_URL = ollama.get("url", cls.OLLAMA_URL)
            cls.OLLAMA_MODEL = ollama.get("model", cls.OLLAMA_MODEL)
            
            # Beta-Provider
            beta = data.get("beta", {})
            
            # OpenAI
            openai = beta.get("openai", {})
            cls.OPENAI_URL = openai.get("url", cls.OPENAI_URL)
            cls.OPENAI_MODEL = openai.get("model", cls.OPENAI_MODEL)
            cls.OPENAI_API_KEY = openai.get("api_key", cls.OPENAI_API_KEY)
            
            # Grok
            grok = beta.get("grok", {})
            cls.GROK_URL = grok.get("url", cls.GROK_URL)
            cls.GROK_MODEL = grok.get("model", cls.GROK_MODEL)
            cls.GROK_API_KEY = grok.get("api_key", cls.GROK_API_KEY)
            
            # Claude
            claude = beta.get("claude", {})
            cls.CLAUDE_URL = claude.get("url", cls.CLAUDE_URL)
            cls.CLAUDE_MODEL = claude.get("model", cls.CLAUDE_MODEL)
            cls.CLAUDE_API_KEY = claude.get("api_key", cls.CLAUDE_API_KEY)
            cls.CLAUDE_VERSION = claude.get("version", cls.CLAUDE_VERSION)
            
            # Allgemeine Einstellungen
            cls.TIMEOUT = data.get("timeout", cls.TIMEOUT)
            cls.TEMPERATURE = data.get("temperature", cls.TEMPERATURE)
            cls.MAX_TOKENS = data.get("max_tokens", cls.MAX_TOKENS)
            
            # Ordner
            folders = data.get("folders", {})
            cls.AGENTS_FOLDER = folders.get("agents", cls.AGENTS_FOLDER)
            cls.MODERATORS_FOLDER = folders.get("moderators", cls.MODERATORS_FOLDER)
            cls.EXAMPLES_FOLDER = folders.get("examples", cls.EXAMPLES_FOLDER)
            cls.EXPORTS_FOLDER = folders.get("exports", cls.EXPORTS_FOLDER)
            cls.MEMORY_FOLDER = folders.get("memory", cls.MEMORY_FOLDER)
            cls.KNOWLEDGE_FOLDER = folders.get("knowledge_graph", cls.KNOWLEDGE_FOLDER)
            
            # Provider
            provider = data.get("provider", {})
            cls.LM_PROVIDER = provider.get("active", cls.LM_PROVIDER)
            
            return True
        except:
            return False
    
    @classmethod
    def save_to_file(cls, filepath="config.json"):
        """Speichert die aktuelle Konfiguration in einer JSON-Datei"""
        try:
            data = {
                "lm_studio": {
                    "url": cls.LM_STUDIO_URL
                },
                "ollama": {
                    "url": cls.OLLAMA_URL,
                    "model": cls.OLLAMA_MODEL
                },
                "beta": {
                    "openai": {
                        "url": cls.OPENAI_URL,
                        "model": cls.OPENAI_MODEL,
                        "api_key": cls.OPENAI_API_KEY
                    },
                    "grok": {
                        "url": cls.GROK_URL,
                        "model": cls.GROK_MODEL,
                        "api_key": cls.GROK_API_KEY
                    },
                    "claude": {
                        "url": cls.CLAUDE_URL,
                        "model": cls.CLAUDE_MODEL,
                        "api_key": cls.CLAUDE_API_KEY,
                        "version": cls.CLAUDE_VERSION
                    }
                },
                "timeout": cls.TIMEOUT,
                "temperature": cls.TEMPERATURE,
                "max_tokens": cls.MAX_TOKENS,
                "provider": {
                    "active": cls.LM_PROVIDER
                },
                "folders": {
                    "agents": cls.AGENTS_FOLDER,
                    "moderators": cls.MODERATORS_FOLDER,
                    "examples": cls.EXAMPLES_FOLDER,
                    "exports": cls.EXPORTS_FOLDER,
                    "memory": cls.MEMORY_FOLDER,
                    "knowledge_graph": cls.KNOWLEDGE_FOLDER
                }
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False

# ===================== AUTO-LOAD =====================
# Beim Import automatisch laden
Config.load_from_file()