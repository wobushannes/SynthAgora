#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║  🐟 SynthAgora - Konfigurationsdatei (REDUZIERT)                   ║
║  Nur funktionierende Komponenten: Wikipedia + arXiv                    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import json
import os
from datetime import datetime

class Config:
    # ===================== PROVIDER =====================
    LM_PROVIDER = "lmstudio"  # lmstudio, ollama, openai, grok, claude
    
    # ===================== LM STUDIO =====================
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    
    # ===================== OLLAMA =====================
    OLLAMA_URL = "http://localhost:11434/api/chat"
    OLLAMA_MODEL = "llama3"
    
    # ===================== OPENAI =====================
    OPENAI_URL = "https://api.openai.com/v1/chat/completions"
    OPENAI_MODEL = "gpt-3.5-turbo"
    OPENAI_API_KEY = ""
    
    # ===================== GROK =====================
    GROK_URL = "https://api.x.ai/v1/chat/completions"
    GROK_MODEL = "grok-1"
    GROK_API_KEY = ""
    
    # ===================== CLAUDE =====================
    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    CLAUDE_MODEL = "claude-3-opus-20240229"
    CLAUDE_API_KEY = ""
    CLAUDE_VERSION = "2023-06-01"
    
    # ===================== ALLGEMEINE EINSTELLUNGEN =====================
    TIMEOUT = 30
    TEMPERATURE = 0.7
    MAX_TOKENS = 300
    
    # ===================== SIMULATION =====================
    DEFAULT_ROUNDS = 3
    AUTO_SAVE_INTERVAL = 60
    
    # ===================== PERSÖNLICHKEIT =====================
    PERSONALITY_ENABLED = True
    PERSONALITY_CHANGE_RATE = 0.05
    LEARNING_RATE = 0.03
    
    # ===================== SCORING =====================
    SCORING_ENABLED = True
    POINTS_PER_CONTRIBUTION = 1
    POINTS_PER_INFLUENCE = 5
    POINTS_PER_CORRECT_PROGNOSIS = 10
    POINTS_PENALTY_EXCLUSION = -5
    
    # ===================== PROGNOSEN =====================
    PROGNOSIS_ENABLED = True
    PROGNOSIS_AUTO_COLLECT = False
    
    # ===================== TRAINING =====================
    TRAINING_ENABLED = True
    MAX_TRAINING_ROUNDS = 5
    SKILL_INCREASE_PER_ROUND = 0.1
    
    # ===================== GEDÄCHTNIS-PALAST =====================
    MEMORY_PALACE_ENABLED = True
    CRYSTAL_DECAY = 0.95
    MAX_MEMORIES_PER_AGENT = 500
    
    # ===================== TEAMS =====================
    TEAMS_ENABLED = True
    AUTO_ROTATE_SPOKESPERSON = True
    
    # ===================== EXTERNE QUELLEN =====================
    EXTERNAL_ENABLED = False  # Standardmäßig aus
    EXTERNAL_TIMEOUT = 10
    
    # ===================== ORDNER =====================
    AGENTS_FOLDER = "agents"
    MODERATORS_FOLDER = "moderators"
    EXAMPLES_FOLDER = "examples"
    EXPORTS_FOLDER = "exports"
    MEMORY_FOLDER = "memory"
    KNOWLEDGE_FOLDER = "knowledge_graph"
    PLUGINS_FOLDER = "includes/plugins"
    
    # ===================== KNOWLEDGE GRAPH =====================
    KG_AUTO_SAVE = True
    KG_SAVE_INTERVAL = 30
    KG_MAX_EDGES_PER_NODE = 1000
    
    # ===================== EXPORT =====================
    EXPORT_FORMAT = "txt"
    EXPORT_INCLUDE_METADATA = True
    EXPORT_INCLUDE_TIMESTAMP = True
    
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
    
    # ===================== VERSION =====================
    VERSION = "2.0.0"
    
    @classmethod
    def load_from_file(cls, filepath="config.json"):
        """Lädt die Konfiguration aus einer JSON-Datei"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # LM Studio
            lm = data.get("lm_studio", {})
            cls.LM_STUDIO_URL = lm.get("url", cls.LM_STUDIO_URL)
            cls.TIMEOUT = lm.get("timeout", cls.TIMEOUT)
            cls.TEMPERATURE = lm.get("temperature", cls.TEMPERATURE)
            cls.MAX_TOKENS = lm.get("max_tokens", cls.MAX_TOKENS)
            
            # Ollama
            ollama = data.get("ollama", {})
            cls.OLLAMA_URL = ollama.get("url", cls.OLLAMA_URL)
            cls.OLLAMA_MODEL = ollama.get("model", cls.OLLAMA_MODEL)
            
            # OpenAI
            openai = data.get("openai", {})
            cls.OPENAI_URL = openai.get("url", cls.OPENAI_URL)
            cls.OPENAI_MODEL = openai.get("model", cls.OPENAI_MODEL)
            cls.OPENAI_API_KEY = openai.get("api_key", cls.OPENAI_API_KEY)
            
            # Grok
            grok = data.get("grok", {})
            cls.GROK_URL = grok.get("url", cls.GROK_URL)
            cls.GROK_MODEL = grok.get("model", cls.GROK_MODEL)
            cls.GROK_API_KEY = grok.get("api_key", cls.GROK_API_KEY)
            
            # Claude
            claude = data.get("claude", {})
            cls.CLAUDE_URL = claude.get("url", cls.CLAUDE_URL)
            cls.CLAUDE_MODEL = claude.get("model", cls.CLAUDE_MODEL)
            cls.CLAUDE_API_KEY = claude.get("api_key", cls.CLAUDE_API_KEY)
            cls.CLAUDE_VERSION = claude.get("version", cls.CLAUDE_VERSION)
            
            # Provider
            provider = data.get("provider", {})
            cls.LM_PROVIDER = provider.get("active", cls.LM_PROVIDER)
            
            # UI
            ui = data.get("ui", {})
            cls.BG_MAIN = ui.get("colors", {}).get("bg_main", cls.BG_MAIN)
            cls.BG_PANEL = ui.get("colors", {}).get("bg_panel", cls.BG_PANEL)
            cls.BG_INPUT = ui.get("colors", {}).get("bg_input", cls.BG_INPUT)
            cls.BG_BUTTON = ui.get("colors", {}).get("bg_button", cls.BG_BUTTON)
            cls.BG_BUTTON_HOVER = ui.get("colors", {}).get("bg_button_hover", cls.BG_BUTTON_HOVER)
            cls.BG_STOP = ui.get("colors", {}).get("bg_stop", cls.BG_STOP)
            cls.BG_STOP_HOVER = ui.get("colors", {}).get("bg_stop_hover", cls.BG_STOP_HOVER)
            cls.FG = ui.get("colors", {}).get("fg", cls.FG)
            cls.FG_DIM = ui.get("colors", {}).get("fg_dim", cls.FG_DIM)
            cls.FG_BUTTON = ui.get("colors", {}).get("fg_button", cls.FG_BUTTON)
            cls.SUCCESS = ui.get("colors", {}).get("success", cls.SUCCESS)
            cls.ERROR = ui.get("colors", {}).get("error", cls.ERROR)
            cls.WARNING = ui.get("colors", {}).get("warning", cls.WARNING)
            cls.BETA = ui.get("colors", {}).get("beta", cls.BETA)
            
            # Simulation
            sim = data.get("simulation", {})
            cls.DEFAULT_ROUNDS = sim.get("default_rounds", cls.DEFAULT_ROUNDS)
            cls.AUTO_SAVE_INTERVAL = sim.get("auto_save_interval", cls.AUTO_SAVE_INTERVAL)
            
            # Persönlichkeits-Entwicklung
            pers = sim.get("personality_development", {})
            cls.PERSONALITY_ENABLED = pers.get("enabled", cls.PERSONALITY_ENABLED)
            cls.PERSONALITY_CHANGE_RATE = pers.get("change_rate", cls.PERSONALITY_CHANGE_RATE)
            cls.LEARNING_RATE = pers.get("learning_rate", cls.LEARNING_RATE)
            
            # Scoring
            score = sim.get("scoring", {})
            cls.SCORING_ENABLED = score.get("enabled", cls.SCORING_ENABLED)
            cls.POINTS_PER_CONTRIBUTION = score.get("points_per_contribution", cls.POINTS_PER_CONTRIBUTION)
            cls.POINTS_PER_INFLUENCE = score.get("points_per_influence", cls.POINTS_PER_INFLUENCE)
            cls.POINTS_PER_CORRECT_PROGNOSIS = score.get("points_per_correct_prognosis", cls.POINTS_PER_CORRECT_PROGNOSIS)
            cls.POINTS_PENALTY_EXCLUSION = score.get("points_penalty_exclusion", cls.POINTS_PENALTY_EXCLUSION)
            
            # Prognosen
            prog = sim.get("prognosis", {})
            cls.PROGNOSIS_ENABLED = prog.get("enabled", cls.PROGNOSIS_ENABLED)
            cls.PROGNOSIS_AUTO_COLLECT = prog.get("auto_collect", cls.PROGNOSIS_AUTO_COLLECT)
            
            # Training
            train = sim.get("training", {})
            cls.TRAINING_ENABLED = train.get("enabled", cls.TRAINING_ENABLED)
            cls.MAX_TRAINING_ROUNDS = train.get("max_training_rounds", cls.MAX_TRAINING_ROUNDS)
            cls.SKILL_INCREASE_PER_ROUND = train.get("skill_increase_per_round", cls.SKILL_INCREASE_PER_ROUND)
            
            # Gedächtnis-Palast
            mp = sim.get("memory_palace", {})
            cls.MEMORY_PALACE_ENABLED = mp.get("enabled", cls.MEMORY_PALACE_ENABLED)
            cls.CRYSTAL_DECAY = mp.get("crystal_decay", cls.CRYSTAL_DECAY)
            cls.MAX_MEMORIES_PER_AGENT = mp.get("max_memories_per_agent", cls.MAX_MEMORIES_PER_AGENT)
            
            # Teams
            team = sim.get("teams", {})
            cls.TEAMS_ENABLED = team.get("enabled", cls.TEAMS_ENABLED)
            cls.AUTO_ROTATE_SPOKESPERSON = team.get("auto_rotate_spokesperson", cls.AUTO_ROTATE_SPOKESPERSON)
            
            # Externe Quellen - NUR Wikipedia + arXiv bleiben relevant
            ext = data.get("external_sources", {})
            cls.EXTERNAL_ENABLED = ext.get("enabled", cls.EXTERNAL_ENABLED)
            cls.EXTERNAL_TIMEOUT = ext.get("timeout", cls.EXTERNAL_TIMEOUT)
            
            # Knowledge Graph
            kg = data.get("knowledge_graph", {})
            cls.KG_AUTO_SAVE = kg.get("auto_save", cls.KG_AUTO_SAVE)
            cls.KG_SAVE_INTERVAL = kg.get("save_interval", cls.KG_SAVE_INTERVAL)
            cls.KG_MAX_EDGES_PER_NODE = kg.get("max_edges_per_node", cls.KG_MAX_EDGES_PER_NODE)
            
            # Export
            exp = data.get("export", {})
            cls.EXPORT_FORMAT = exp.get("format", cls.EXPORT_FORMAT)
            cls.EXPORT_INCLUDE_METADATA = exp.get("include_metadata", cls.EXPORT_INCLUDE_METADATA)
            cls.EXPORT_INCLUDE_TIMESTAMP = exp.get("include_timestamp", cls.EXPORT_INCLUDE_TIMESTAMP)
            
            # Ordner
            folders = data.get("folders", {})
            cls.AGENTS_FOLDER = folders.get("agents", cls.AGENTS_FOLDER)
            cls.MODERATORS_FOLDER = folders.get("moderators", cls.MODERATORS_FOLDER)
            cls.EXAMPLES_FOLDER = folders.get("examples", cls.EXAMPLES_FOLDER)
            cls.EXPORTS_FOLDER = folders.get("exports", cls.EXPORTS_FOLDER)
            cls.MEMORY_FOLDER = folders.get("memory", cls.MEMORY_FOLDER)
            cls.KNOWLEDGE_FOLDER = folders.get("knowledge_graph", cls.KNOWLEDGE_FOLDER)
            cls.PLUGINS_FOLDER = folders.get("plugins", cls.PLUGINS_FOLDER)
            
            # Version
            cls.VERSION = data.get("version", cls.VERSION)
            
            return True
        except Exception as e:
            print(f"⚠️ Konfiguration konnte nicht geladen werden: {e}")
            return False
    
    @classmethod
    def save_to_file(cls, filepath="config.json"):
        """Speichert die aktuelle Konfiguration in einer JSON-Datei"""
        try:
            data = {
                "lm_studio": {
                    "url": cls.LM_STUDIO_URL,
                    "timeout": cls.TIMEOUT,
                    "temperature": cls.TEMPERATURE,
                    "max_tokens": cls.MAX_TOKENS
                },
                "ollama": {
                    "url": cls.OLLAMA_URL,
                    "model": cls.OLLAMA_MODEL,
                    "timeout": cls.TIMEOUT,
                    "temperature": cls.TEMPERATURE,
                    "max_tokens": cls.MAX_TOKENS
                },
                "openai": {
                    "url": cls.OPENAI_URL,
                    "model": cls.OPENAI_MODEL,
                    "api_key": cls.OPENAI_API_KEY,
                    "timeout": cls.TIMEOUT,
                    "temperature": cls.TEMPERATURE,
                    "max_tokens": cls.MAX_TOKENS
                },
                "grok": {
                    "url": cls.GROK_URL,
                    "model": cls.GROK_MODEL,
                    "api_key": cls.GROK_API_KEY,
                    "timeout": cls.TIMEOUT,
                    "temperature": cls.TEMPERATURE,
                    "max_tokens": cls.MAX_TOKENS
                },
                "claude": {
                    "url": cls.CLAUDE_URL,
                    "model": cls.CLAUDE_MODEL,
                    "api_key": cls.CLAUDE_API_KEY,
                    "version": cls.CLAUDE_VERSION,
                    "timeout": cls.TIMEOUT,
                    "temperature": cls.TEMPERATURE,
                    "max_tokens": cls.MAX_TOKENS
                },
                "provider": {
                    "active": cls.LM_PROVIDER
                },
                "ui": {
                    "theme": "dark",
                    "font_family": "Segoe UI",
                    "font_size": 10,
                    "colors": {
                        "bg_main": cls.BG_MAIN,
                        "bg_panel": cls.BG_PANEL,
                        "bg_input": cls.BG_INPUT,
                        "bg_button": cls.BG_BUTTON,
                        "bg_button_hover": cls.BG_BUTTON_HOVER,
                        "bg_stop": cls.BG_STOP,
                        "bg_stop_hover": cls.BG_STOP_HOVER,
                        "fg": cls.FG,
                        "fg_dim": cls.FG_DIM,
                        "fg_button": cls.FG_BUTTON,
                        "success": cls.SUCCESS,
                        "error": cls.ERROR,
                        "warning": cls.WARNING,
                        "beta": cls.BETA
                    }
                },
                "simulation": {
                    "default_rounds": cls.DEFAULT_ROUNDS,
                    "auto_save_interval": cls.AUTO_SAVE_INTERVAL,
                    "memory_palace": {
                        "enabled": cls.MEMORY_PALACE_ENABLED,
                        "crystal_decay": cls.CRYSTAL_DECAY,
                        "max_memories_per_agent": cls.MAX_MEMORIES_PER_AGENT
                    },
                    "teams": {
                        "enabled": cls.TEAMS_ENABLED,
                        "auto_rotate_spokesperson": cls.AUTO_ROTATE_SPOKESPERSON
                    },
                    "personality_development": {
                        "enabled": cls.PERSONALITY_ENABLED,
                        "change_rate": cls.PERSONALITY_CHANGE_RATE,
                        "learning_rate": cls.LEARNING_RATE
                    },
                    "scoring": {
                        "enabled": cls.SCORING_ENABLED,
                        "points_per_contribution": cls.POINTS_PER_CONTRIBUTION,
                        "points_per_influence": cls.POINTS_PER_INFLUENCE,
                        "points_per_correct_prognosis": cls.POINTS_PER_CORRECT_PROGNOSIS,
                        "points_penalty_exclusion": cls.POINTS_PENALTY_EXCLUSION
                    },
                    "prognosis": {
                        "enabled": cls.PROGNOSIS_ENABLED,
                        "auto_collect": cls.PROGNOSIS_AUTO_COLLECT
                    },
                    "training": {
                        "enabled": cls.TRAINING_ENABLED,
                        "max_training_rounds": cls.MAX_TRAINING_ROUNDS,
                        "skill_increase_per_round": cls.SKILL_INCREASE_PER_ROUND
                    }
                },
                "external_sources": {
                    "enabled": cls.EXTERNAL_ENABLED,
                    "timeout": cls.EXTERNAL_TIMEOUT,
                    "plugins": {
                        "wikipedia": {
                            "enabled": False,
                            "api_url": "https://de.wikipedia.org/w/api.php"
                        },
                        "arxiv": {
                            "enabled": False,
                            "api_url": "http://export.arxiv.org/api/query"
                        }
                        # ALLE ANDEREN PLUGINS ENTFERNT!
                    }
                },
                "knowledge_graph": {
                    "auto_save": cls.KG_AUTO_SAVE,
                    "save_interval": cls.KG_SAVE_INTERVAL,
                    "max_edges_per_node": cls.KG_MAX_EDGES_PER_NODE
                },
                "export": {
                    "format": cls.EXPORT_FORMAT,
                    "include_metadata": cls.EXPORT_INCLUDE_METADATA,
                    "include_timestamp": cls.EXPORT_INCLUDE_TIMESTAMP
                },
                "folders": {
                    "agents": cls.AGENTS_FOLDER,
                    "moderators": cls.MODERATORS_FOLDER,
                    "examples": cls.EXAMPLES_FOLDER,
                    "exports": cls.EXPORTS_FOLDER,
                    "memory": cls.MEMORY_FOLDER,
                    "knowledge_graph": cls.KNOWLEDGE_FOLDER,
                    "plugins": cls.PLUGINS_FOLDER
                },
                "version": cls.VERSION,
                "last_updated": datetime.now().strftime("%Y-%m-%d")
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Konfiguration konnte nicht gespeichert werden: {e}")
            return False

# ===================== AUTO-LOAD =====================
Config.load_from_file()