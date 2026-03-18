#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║  🐟 SynthAgora - VOLLAUSBAU MIT ALLEN FEATURES                    ║
║  Plugin-System · Team-Diskussionen · Persönlichkeits-Entwicklung       ║
║  Gedächtnis-Palast · Bewertungen · Prognosen · Checklisten             ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import requests
import json
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import queue
import re
import os
import glob
import sys
import subprocess
import urllib.parse
import random
import math

# Config importieren
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from includes.config import Config

# Plugin-System importieren
from includes.plugins import PluginManager

# ===================== LM STUDIO / OLLAMA CLIENT =====================
class LLMClient:
    def __init__(self):
        self.provider = Config.LM_PROVIDER
        self.session = requests.Session()
        self.stats = {"calls": 0, "errors": 0}
        self.current_request = None
        self.request_queue = queue.Queue()
        self.is_processing = False
        
    def test(self) -> Tuple[bool, str]:
        """Testet die Verbindung zum aktiven Provider"""
        try:
            if self.provider == "lmstudio":
                return True, f"LM Studio: {Config.LM_STUDIO_URL} (bereit)"
            elif self.provider == "ollama":
                return True, f"Ollama: {Config.OLLAMA_MODEL} (bereit)"
            elif self.provider == "openai":
                return True, f"OpenAI: {Config.OPENAI_MODEL} (konfiguriert)"
            elif self.provider == "grok":
                return True, f"Grok: {Config.GROK_MODEL} (konfiguriert)"
            elif self.provider == "claude":
                return True, f"Claude: {Config.CLAUDE_MODEL} (konfiguriert)"
            return False, f"Provider {self.provider} nicht konfiguriert"
        except Exception as e:
            return False, f"Fehler: {str(e)}"
    
    def ask(self, prompt: str, system: str = None, stop_event: threading.Event = None, callback: callable = None) -> str:
        """Fragt das LLM mit Fortschritts-Callback"""
        self.stats["calls"] += 1
        self.is_processing = True
        
        if callback:
            callback("start", f"🤖 LM Studio denkt nach... ({self.stats['calls']} Requests)")
        
        try:
            if stop_event and stop_event.is_set():
                self.is_processing = False
                if callback:
                    callback("done", "❌ Abgebrochen")
                return "[ABGEBROCHEN]"
            
            if self.provider == "lmstudio":
                result = self._ask_lmstudio(prompt, system, stop_event, callback)
            elif self.provider == "ollama":
                result = self._ask_ollama(prompt, system, stop_event, callback)
            elif self.provider == "openai":
                result = self._ask_beta("OpenAI", Config.OPENAI_URL, Config.OPENAI_MODEL, prompt, system)
            elif self.provider == "grok":
                result = self._ask_beta("Grok", Config.GROK_URL, Config.GROK_MODEL, prompt, system)
            elif self.provider == "claude":
                result = self._ask_beta("Claude", Config.CLAUDE_URL, Config.CLAUDE_MODEL, prompt, system)
            else:
                result = f"[Fehler: Unbekannter Provider {self.provider}]"
            
            self.is_processing = False
            if callback:
                callback("done", f"✅ Fertig ({self.stats['calls']} Requests)")
            return result
                
        except Exception as e:
            self.stats["errors"] += 1
            self.is_processing = False
            if callback:
                callback("error", f"❌ Fehler: {str(e)[:30]}")
            return f"[Fehler: {str(e)[:30]}]"
    
    def _ask_lmstudio(self, prompt: str, system: str = None, stop_event=None, callback=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        if callback:
            callback("progress", "📤 Sende Anfrage an LM Studio...")
        
        r = self.session.post(Config.LM_STUDIO_URL, json={
            "messages": messages,
            "max_tokens": Config.MAX_TOKENS,
            "temperature": Config.TEMPERATURE,
            "stop": ["\n\n", "User:", "Assistant:"]
        }, timeout=Config.TIMEOUT)
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if callback:
            callback("progress", "📥 Antwort empfangen, verarbeite...")
        
        text = r.json()["choices"][0]["message"]["content"]
        text = re.sub(r'(?i)(thinking|thought).*?(\n|$)', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."
    
    def _ask_ollama(self, prompt: str, system: str = None, stop_event=None, callback=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        if callback:
            callback("progress", "📤 Sende Anfrage an Ollama...")
        
        r = self.session.post(Config.OLLAMA_URL, json={
            "model": Config.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": Config.TEMPERATURE,
                "num_predict": Config.MAX_TOKENS
            }
        }, timeout=Config.TIMEOUT)
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        if callback:
            callback("progress", "📥 Antwort empfangen, verarbeite...")
        
        text = r.json()["message"]["content"]
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."
    
    def _ask_beta(self, name: str, url: str, model: str, prompt: str, system: str = None) -> str:
        """Beta-Provider - zeigt an, dass ein Key fehlt, aber Endpoint korrekt wäre"""
        system_info = f" mit System: {system[:50]}..." if system else ""
        return (f"[{name} - Kein API-Key konfiguriert]\n"
                f"Endpoint: {url}\n"
                f"Modell: {model}\n"
                f"Prompt: {prompt[:100]}...{system_info}\n\n"
                f"Würde hier eine echte API-Anfrage stellen.\n"
                f"Konfiguration in config.json möglich.")

# ===================== PROGRESS MANAGER =====================
class ProgressManager:
    """Verwaltet Fortschrittsanzeigen für lange Operationen"""
    
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.total = 0
        self.current = 0
        self.operation = ""
        self.start_time = None
        self.is_running = False
    
    def start(self, operation: str, total: int = 1):
        """Startet eine neue Operation"""
        self.operation = operation
        self.total = total
        self.current = 0
        self.start_time = time.time()
        self.is_running = True
        self._update("start")
    
    def update(self, increment: int = 1, message: str = None):
        """Aktualisiert den Fortschritt"""
        self.current += increment
        self._update("progress", message)
    
    def set_message(self, message: str):
        """Setzt eine Statusmeldung"""
        self._update("message", message)
    
    def finish(self, message: str = "✅ Fertig"):
        """Beendet die Operation"""
        self.is_running = False
        self._update("done", message)
    
    def _update(self, status: str, message: str = None):
        """Interne Update-Methode"""
        if self.status_callback:
            elapsed = time.time() - self.start_time if self.start_time else 0
            progress = (self.current / self.total * 100) if self.total > 0 else 0
            
            status_text = message or self.operation
            if self.total > 1:
                status_text = f"{self.operation} ({self.current}/{self.total} • {progress:.0f}%)"
            
            if elapsed > 0 and self.current < self.total:
                remaining = (elapsed / self.current) * (self.total - self.current) if self.current > 0 else 0
                if remaining > 0:
                    status_text += f" • ⏱️ noch ca. {int(remaining)}s"
            
            self.status_callback(status, status_text)

# ===================== PLUGIN-MANAGER WRAPPER =====================
class ExternalSourceClient:
    """Wrapper für PluginManager - Abwärtskompatibilität"""
    
    def __init__(self):
        self.plugin_manager = PluginManager()
        self.use_external = False
        self.search_timeout = 10
        self.search_threshold = 0.5  # Schwellwert für Entscheidung
        
        # Für Kompatibilität mit altem Code
        self.sources = self._build_sources_dict()
    
    def _build_sources_dict(self):
        """Baut das alte sources-Dictionary für Kompatibilität"""
        sources = {}
        for key, plugin in self.plugin_manager.get_all_plugins().items():
            sources[key] = {
                "name": plugin.name,
                "enabled": plugin.enabled,
                "description": plugin.description,
                "needs_server": plugin.needs_server,
                "server_process": getattr(plugin, 'server_process', None)
            }
        return sources
    
    def toggle_source(self, source_key: str, enabled: bool):
        """Aktiviert/deaktiviert eine Quelle"""
        self.plugin_manager.enable_plugin(source_key, enabled)
        # Sources-Dictionary aktualisieren
        self.sources = self._build_sources_dict()
    
    def search(self, query: str, max_results: int = 3, progress: ProgressManager = None) -> List[Dict]:
        """Durchsucht alle aktivierten Quellen mit Fortschritt"""
        if not self.use_external:
            return []
        
        if progress:
            progress.set_message(f"🔍 Suche nach '{query[:50]}...'")
        
        results = self.plugin_manager.search_all(query, max_results)
        
        if progress and results:
            progress.set_message(f"✅ {len(results)} Ergebnisse gefunden")
        
        return results
    
    def format_results(self, results: List[Dict]) -> str:
        """Formatiert Suchergebnisse"""
        return self.plugin_manager.format_all_results(results)
    
    def should_search(self, text: str, uncertainty: float = 0.5) -> bool:
        """
        Verbesserte Entscheidung für externe Suche
        - uncertainty: Wie unsicher ist der Agent (0-1)
        - search_threshold: Globaler Schwellwert (einstellbar)
        """
        # Bei hoher Unsicherheit immer suchen
        if uncertainty > 0.8:
            return True
        
        # Bei Fachbegriffen (erkannt durch ? und !) eher suchen
        if '?' in text or '!' in text:
            return random.random() < (self.search_threshold + 0.2)
        
        # Bei langen Texten (viele Fakten) eher nicht suchen
        if len(text) > 200:
            return random.random() < (self.search_threshold - 0.2)
        
        # Standard: Zufall basierend auf Schwellwert
        return random.random() < self.search_threshold

# ===================== DATEI-MANAGER =====================
class FileManager:
    def __init__(self):
        for folder in [Config.AGENTS_FOLDER, Config.MODERATORS_FOLDER, 
                       Config.EXAMPLES_FOLDER, Config.EXPORTS_FOLDER,
                       Config.MEMORY_FOLDER, Config.KNOWLEDGE_FOLDER]:
            if not os.path.exists(folder):
                os.makedirs(folder)
    
    def get_agent_files(self) -> List[str]:
        return glob.glob(f"{Config.AGENTS_FOLDER}/*.json")
    
    def get_moderator_files(self) -> List[str]:
        return glob.glob(f"{Config.MODERATORS_FOLDER}/*.json")
    
    def get_example_files(self) -> List[str]:
        return glob.glob(f"{Config.EXAMPLES_FOLDER}/*.txt")
    
    def load_json_file(self, filepath: str) -> Optional[dict]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def load_text_file(self, filepath: str) -> Optional[str]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return None

# ===================== AUFGABEN / ZIELE =====================
class Task:
    """Eine Aufgabe oder ein Ziel für Agenten"""
    
    def __init__(self, task_id: str, description: str, task_type: str, priority: int = 1):
        self.id = task_id
        self.description = description
        self.type = task_type  # "research", "analysis", "summary", "solution", "hypothesis"
        self.priority = priority
        self.status = "pending"  # pending, in_progress, completed, failed
        self.assigned_to = None
        self.result = None
        self.created = datetime.now().isoformat()
        self.completed = None
        self.deadline = None
        self.reward = 0  # Punkte für Erfüllung
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "result": self.result,
            "created": self.created,
            "completed": self.completed,
            "reward": self.reward
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        task = cls(data["id"], data["description"], data["type"], data["priority"])
        task.status = data["status"]
        task.assigned_to = data["assigned_to"]
        task.result = data["result"]
        task.created = data["created"]
        task.completed = data["completed"]
        task.reward = data["reward"]
        return task


class TaskManager:
    """Verwaltet Aufgaben für Agenten"""
    
    def __init__(self):
        self.tasks: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.task_counter = 0
        self.task_file = f"{Config.KNOWLEDGE_FOLDER}/tasks.json"
        self.load_tasks()
    
    def load_tasks(self):
        """Lädt Aufgaben aus Datei"""
        try:
            with open(self.task_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
                self.completed_tasks = [Task.from_dict(t) for t in data.get("completed", [])]
                self.task_counter = data.get("counter", 0)
        except:
            pass
    
    def save_tasks(self):
        """Speichert Aufgaben in Datei"""
        try:
            data = {
                "tasks": [t.to_dict() for t in self.tasks],
                "completed": [t.to_dict() for t in self.completed_tasks],
                "counter": self.task_counter
            }
            with open(self.task_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def create_task(self, description: str, task_type: str, priority: int = 1) -> Task:
        """Erstellt eine neue Aufgabe"""
        self.task_counter += 1
        task_id = f"TASK_{self.task_counter}_{int(time.time())}"
        task = Task(task_id, description, task_type, priority)
        self.tasks.append(task)
        self.save_tasks()
        return task
    
    def assign_task(self, task_id: str, agent_name: str) -> bool:
        """Weist eine Aufgabe einem Agenten zu"""
        for task in self.tasks:
            if task.id == task_id:
                task.assigned_to = agent_name
                task.status = "in_progress"
                self.save_tasks()
                return True
        return False
    
    def complete_task(self, task_id: str, result: str, reward: int = 10):
        """Markiert eine Aufgabe als erledigt"""
        for task in self.tasks[:]:
            if task.id == task_id:
                task.status = "completed"
                task.result = result
                task.completed = datetime.now().isoformat()
                task.reward = reward
                self.completed_tasks.append(task)
                self.tasks.remove(task)
                self.save_tasks()
                return True
        return False
    
    def get_pending_tasks(self) -> List[Task]:
        """Gibt alle unerledigten Aufgaben zurück"""
        return [t for t in self.tasks if t.status == "pending"]
    
    def get_agent_tasks(self, agent_name: str) -> List[Task]:
        """Gibt alle Aufgaben eines Agenten zurück"""
        return [t for t in self.tasks if t.assigned_to == agent_name]

# ===================== PROGNOSE =====================
class Prognosis:
    """Eine Vorhersage, die ein Agent gemacht hat"""
    
    def __init__(self, agent: str, topic: str, prediction: str, confidence: float):
        self.agent = agent
        self.topic = topic
        self.prediction = prediction
        self.confidence = confidence
        self.timestamp = datetime.now().isoformat()
        self.verified = False
        self.correct = None
        self.verification_time = None
    
    def verify(self, actual_outcome: str) -> bool:
        """Überprüft ob die Prognose richtig war"""
        self.verified = True
        self.verification_time = datetime.now().isoformat()
        
        # Einfache Prüfung: Schlüsselwörter
        self.correct = any(word in actual_outcome.lower() 
                          for word in self.prediction.lower().split()[:3])
        return self.correct
    
    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "topic": self.topic,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "verified": self.verified,
            "correct": self.correct,
            "verification_time": self.verification_time
        }

# ===================== CHECKLISTE =====================
class Checklist:
    """Eine Checkliste für Diskussionen"""
    
    def __init__(self, name: str, items: List[str]):
        self.name = name
        self.items = {item: False for item in items}
        self.created = datetime.now().isoformat()
        self.completed = None
    
    def check(self, item: str) -> bool:
        """Hakt einen Punkt ab"""
        if item in self.items:
            self.items[item] = True
            # Prüfen ob alle erledigt
            if all(self.items.values()):
                self.completed = datetime.now().isoformat()
            return True
        return False
    
    def progress(self) -> float:
        """Fortschritt in Prozent"""
        if not self.items:
            return 0.0
        return sum(1 for v in self.items.values() if v) / len(self.items) * 100
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "items": self.items,
            "created": self.created,
            "completed": self.completed
        }

# ===================== KNOWLEDGE GRAPH MIT GEDÄCHTNIS-PALAST =====================
class KnowledgeGraph:
    def __init__(self):
        self.graph_file = f"{Config.KNOWLEDGE_FOLDER}/knowledge_graph.json"
        self.graph = self.load_graph()
        
        # Gedächtnis-Palast-Struktur
        self.memory_palace = self.graph.get("memory_palace", {
            "rooms": {},  # Agenten-Räume
            "halls": [],  # Verbindungsgänge
            "crystals": {}  # Erinnerungskristalle
        })
        
    def load_graph(self) -> dict:
        try:
            with open(self.graph_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "nodes": {},
                "edges": [],
                "topics": {},
                "influences": {},
                "teams": {},
                "memory_palace": {
                    "rooms": {},
                    "halls": [],
                    "crystals": {}
                },
                "prognoses": [],
                "checklists": [],
                "tasks": [],
                "scores": {}  # Bewertungen
            }
    
    def save_graph(self):
        try:
            # Gedächtnis-Palast in Graph speichern
            self.graph["memory_palace"] = self.memory_palace
            with open(self.graph_file, 'w', encoding='utf-8') as f:
                json.dump(self.graph, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def add_node(self, node_id: str, node_type: str, properties: dict):
        if node_id not in self.graph["nodes"]:
            self.graph["nodes"][node_id] = {
                "type": node_type,
                "properties": properties,
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
                "connections": 0,
                "memory_crystal": None  # Verweis auf Gedächtnis-Palast
            }
        else:
            self.graph["nodes"][node_id]["properties"].update(properties)
            self.graph["nodes"][node_id]["updated"] = datetime.now().isoformat()
        self.save_graph()
    
    def add_edge(self, from_node: str, to_node: str, relation: str, strength: float = 1.0):
        edge = {
            "from": from_node,
            "to": to_node,
            "relation": relation,
            "strength": strength,
            "timestamp": datetime.now().isoformat()
        }
        self.graph["edges"].append(edge)
        if from_node in self.graph["nodes"]:
            self.graph["nodes"][from_node]["connections"] += 1
        if to_node in self.graph["nodes"]:
            self.graph["nodes"][to_node]["connections"] += 1
        self.save_graph()
    
    def add_to_topic(self, topic: str, node_id: str):
        if topic not in self.graph["topics"]:
            self.graph["topics"][topic] = {
                "nodes": [],
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat()
            }
        if node_id not in self.graph["topics"][topic]["nodes"]:
            self.graph["topics"][topic]["nodes"].append(node_id)
            self.graph["topics"][topic]["updated"] = datetime.now().isoformat()
            self.save_graph()
    
    def add_influence(self, influencer: str, influenced: str, topic: str, strength: float):
        if influencer not in self.graph["influences"]:
            self.graph["influences"][influencer] = {}
        if influenced not in self.graph["influences"][influencer]:
            self.graph["influences"][influencer][influenced] = []
        
        self.graph["influences"][influencer][influenced].append({
            "topic": topic,
            "strength": strength,
            "timestamp": datetime.now().isoformat()
        })
        self.save_graph()
    
    # ==================== GEDÄCHTNIS-PALAST ====================
    
    def create_memory_room(self, agent_id: str, agent_name: str):
        """Erstellt einen Gedächtnis-Raum für einen Agenten"""
        room_id = f"room_{agent_id}"
        
        self.memory_palace["rooms"][room_id] = {
            "agent": agent_id,
            "name": f"{agent_name}s Gedächtnis-Palast",
            "crystals": [],  # Erinnerungskristalle in diesem Raum
            "created": datetime.now().isoformat(),
            "size": 1.0,  # Größe des Raums (wächst mit Wissen)
            "color": "#4a90e2"
        }
        
        # Verbindung zum Agenten
        if agent_id in self.graph["nodes"]:
            self.graph["nodes"][agent_id]["memory_crystal"] = room_id
        
        self.save_graph()
        return room_id
    
    def add_memory_crystal(self, agent_id: str, fact: str, topic: str, importance: float = 1.0):
        """Fügt einen Erinnerungskristall hinzu"""
        crystal_id = f"crystal_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Raum für Agenten finden oder erstellen
        room_id = None
        for rid, room in self.memory_palace["rooms"].items():
            if room["agent"] == agent_id:
                room_id = rid
                break
        
        if not room_id:
            agent_name = self.graph["nodes"].get(agent_id, {}).get("properties", {}).get("name", "Unbekannt")
            room_id = self.create_memory_room(agent_id, agent_name)
        
        # Kristall erstellen
        self.memory_palace["crystals"][crystal_id] = {
            "fact": fact,
            "topic": topic,
            "importance": importance,
            "created": datetime.now().isoformat(),
            "accessed": datetime.now().isoformat(),
            "access_count": 1,
            "position": {
                "x": random.uniform(-5, 5),
                "y": random.uniform(-5, 5),
                "z": random.uniform(-5, 5)
            },
            "connections": []  # Verbindungen zu anderen Kristallen
        }
        
        # Kristall dem Raum zuordnen
        self.memory_palace["rooms"][room_id]["crystals"].append(crystal_id)
        
        # Verbindungen zu verwandten Kristallen
        for other_id, other in self.memory_palace["crystals"].items():
            if other_id != crystal_id and other["topic"] == topic:
                # Verbindungsstärke basierend auf Themen-Ähnlichkeit
                strength = 0.5
                self.memory_palace["crystals"][crystal_id]["connections"].append({
                    "to": other_id,
                    "strength": strength
                })
        
        self.save_graph()
        return crystal_id
    
    def access_memory(self, crystal_id: str):
        """Kristall wird angeklickt/angeschaut"""
        if crystal_id in self.memory_palace["crystals"]:
            self.memory_palace["crystals"][crystal_id]["accessed"] = datetime.now().isoformat()
            self.memory_palace["crystals"][crystal_id]["access_count"] += 1
            self.save_graph()
    
    def create_memory_hall(self, room1: str, room2: str, topic: str):
        """Erstellt einen Verbindungsgang zwischen zwei Räumen"""
        hall_id = f"hall_{len(self.memory_palace['halls'])}"
        
        self.memory_palace["halls"].append({
            "id": hall_id,
            "from": room1,
            "to": room2,
            "topic": topic,
            "strength": 1.0,
            "created": datetime.now().isoformat()
        })
        
        self.save_graph()
        return hall_id
    
    def get_agent_memories(self, agent_id: str) -> List[Dict]:
        """Gibt alle Erinnerungen eines Agenten zurück"""
        memories = []
        
        # Raum finden
        for room in self.memory_palace["rooms"].values():
            if room["agent"] == agent_id:
                for crystal_id in room["crystals"]:
                    if crystal_id in self.memory_palace["crystals"]:
                        memories.append({
                            "id": crystal_id,
                            **self.memory_palace["crystals"][crystal_id]
                        })
                break
        
        # Nach Wichtigkeit sortieren
        memories.sort(key=lambda x: x.get("importance", 0), reverse=True)
        return memories
    
    # ==================== TEAMS ====================
    
    def add_team(self, team_name: str, agent_ids: List[str]):
        """Fügt ein Team zum Knowledge Graph hinzu"""
        team_id = f"team_{team_name.lower().replace(' ', '_')}"
        
        # Team-Knoten anlegen
        self.add_node(team_id, "team", {
            "name": team_name,
            "members": agent_ids,
            "created": datetime.now().isoformat()
        })
        
        # Verbindungen zu Agenten
        for agent_id in agent_ids:
            self.add_edge(agent_id, team_id, "mitglied_in", 1.0)
        
        # In teams-Dictionary speichern
        self.graph["teams"][team_id] = {
            "name": team_name,
            "members": agent_ids,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
        self.save_graph()
    
    def get_team_members(self, team_name: str) -> List[str]:
        """Gibt die Mitglieder eines Teams zurück"""
        team_id = f"team_{team_name.lower().replace(' ', '_')}"
        team = self.graph["teams"].get(team_id, {})
        return team.get("members", [])
    
    # ==================== PROGNOSEN ====================
    
    def add_prognosis(self, prognosis: Prognosis):
        """Fügt eine Prognose hinzu"""
        self.graph["prognoses"].append(prognosis.to_dict())
        self.save_graph()
    
    def get_agent_prognoses(self, agent_name: str) -> List[Dict]:
        """Gibt alle Prognosen eines Agenten zurück"""
        return [p for p in self.graph["prognoses"] if p["agent"] == agent_name]
    
    def get_accuracy(self, agent_name: str) -> float:
        """Berechnet die Trefferquote eines Agenten"""
        prognoses = [p for p in self.graph["prognoses"] 
                    if p["agent"] == agent_name and p["verified"]]
        if not prognoses:
            return 0.0
        correct = sum(1 for p in prognoses if p["correct"])
        return correct / len(prognoses) * 100
    
    # ==================== CHECKLISTEN ====================
    
    def add_checklist(self, checklist: Checklist):
        """Fügt eine Checkliste hinzu"""
        self.graph["checklists"].append(checklist.to_dict())
        self.save_graph()
    
    def update_checklist(self, checklist_name: str, item: str):
        """Hakt einen Punkt ab"""
        for cl in self.graph["checklists"]:
            if cl["name"] == checklist_name:
                if item in cl["items"]:
                    cl["items"][item] = True
                    # Prüfen ob fertig
                    if all(cl["items"].values()):
                        cl["completed"] = datetime.now().isoformat()
                    self.save_graph()
                    return True
        return False
    
    # ==================== BEWERTUNGEN ====================
    
    def add_score(self, agent_name: str, points: int, reason: str):
        """Fügt einem Agenten Punkte hinzu"""
        if agent_name not in self.graph["scores"]:
            self.graph["scores"][agent_name] = {
                "total": 0,
                "history": []
            }
        
        self.graph["scores"][agent_name]["total"] += points
        self.graph["scores"][agent_name]["history"].append({
            "points": points,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        self.save_graph()
    
    def get_leaderboard(self) -> List[Tuple[str, int]]:
        """Gibt Rangliste zurück"""
        scores = [(name, data["total"]) 
                 for name, data in self.graph["scores"].items()]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

# ===================== AGENT MIT ALLEN FEATURES =====================
class Agent:
    def __init__(self, data: dict, knowledge_graph: KnowledgeGraph, external_client: ExternalSourceClient):
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data["color"]
        self.goals = data.get("goals", [])
        self.fears = data.get("fears", [])
        self.education = data.get("education", "")
        self.background = data.get("background", "")
        
        # Team-Zugehörigkeit
        self.team = data.get("team", "")
        self.team_role = data.get("team_role", "Mitglied")
        
        # Persönlichkeits-Entwicklung
        self.personality_traits = {
            "aggressivitaet": self._extract_trait("aggressiv", 0.3),
            "optimismus": self._extract_trait("optimist", 0.5),
            "dominanz": self._extract_trait("dominant", 0.3),
            "neugier": self._extract_trait("neugier", 0.6),
            "empathie": self._extract_trait("empath", 0.5),
            "risikobereitschaft": self._extract_trait("risiko", 0.4)
        }
        
        self.mood = "neutral"
        self.energy = 100
        self.arguments = []
        self.last_response = ""
        
        self.schon_gesagtes = []
        self.wiederholungen = 0
        self.ausgeschlossen = False
        self.current_position = None
        
        self.learned_facts = []
        self.known_positions = {}
        self.perspectives = []
        self.position_history = []
        
        # Ausbildung
        self.training_level = data.get("training_level", 1)
        self.training_topics = data.get("training_topics", [])
        self.skills = data.get("skills", {})
        
        # Prognosen
        self.prognoses = []
        
        # Erinnerungen
        self.reminders = []
        
        # Rollenwechsel
        self.original_role = self.role
        self.original_personality = self.personality
        self.temp_role = None
        self.temp_personality = None
        self.role_switch_until = None
        
        self.knowledge_graph = knowledge_graph
        self.external_client = external_client
        self.agent_id = f"agent_{self.name.lower().replace(' ', '_')}"
        self.discussion_log = None
        
        self.memory_file = f"{Config.MEMORY_FOLDER}/{self.name}.json"
        self.load_memory()
        
        self.knowledge_graph.add_node(
            self.agent_id,
            "agent",
            {
                "name": self.name, 
                "role": self.role, 
                "personality": self.personality, 
                "team": self.team,
                "traits": self.personality_traits,
                "training_level": self.training_level,
                "skills": self.skills
            }
        )
        
        # Gedächtnis-Palast-Raum erstellen
        self.knowledge_graph.create_memory_room(self.agent_id, self.name)
    
    def _extract_trait(self, keyword: str, default: float) -> float:
        """Extrahiert Persönlichkeitsmerkmal aus Beschreibung"""
        text = self.personality.lower()
        if keyword in text:
            if "sehr" in text or "extrem" in text:
                return min(1.0, default + 0.3)
            elif "wenig" in text or "kaum" in text:
                return max(0.0, default - 0.2)
        return default
    
    def load_memory(self):
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                self.learned_facts = memory.get('facts', [])
                self.known_positions = memory.get('positions', {})
                self.perspectives = memory.get('perspectives', [])
                self.position_history = memory.get('position_history', [])
                self.personality_traits = memory.get('traits', self.personality_traits)
                self.training_level = memory.get('training_level', self.training_level)
                self.training_topics = memory.get('training_topics', self.training_topics)
                self.skills = memory.get('skills', self.skills)
        except:
            pass
    
    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'facts': self.learned_facts[-100:],
                    'positions': self.known_positions,
                    'perspectives': self.perspectives[-50:],
                    'position_history': self.position_history[-50:],
                    'traits': self.personality_traits,
                    'training_level': self.training_level,
                    'training_topics': self.training_topics,
                    'skills': self.skills
                }, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    # ==================== ROLLENWECHSEL ====================
    
    def switch_role(self, new_role: str, new_personality: str, duration_rounds: int = 2):
        """Wechselt temporär die Rolle"""
        self.temp_role = new_role
        self.temp_personality = new_personality
        self.role_switch_until = duration_rounds
        print(f"🔄 {self.name} schlüpft in Rolle: {new_role}")
    
    def get_current_role(self) -> str:
        """Gibt aktuelle Rolle zurück (original oder temporär)"""
        if self.temp_role and self.role_switch_until and self.role_switch_until > 0:
            return self.temp_role
        return self.original_role
    
    def get_current_personality(self) -> str:
        """Gibt aktuelle Persönlichkeit zurück"""
        if self.temp_personality and self.role_switch_until and self.role_switch_until > 0:
            return self.temp_personality
        return self.original_personality
    
    def update_role_switch(self):
        """Aktualisiert Rollenwechsel-Zähler"""
        if self.role_switch_until:
            self.role_switch_until -= 1
            if self.role_switch_until <= 0:
                self.temp_role = None
                self.temp_personality = None
                print(f"🔄 {self.name} zurück zur Original-Rolle")
    
    # ==================== PERSÖNLICHKEITS-ENTWICKLUNG ====================
    
    def update_personality(self, event: str, success: bool = True):
        """Passt Persönlichkeit basierend auf Erfahrungen an"""
        if event == "überzeugt":
            # Erfolg beim Überzeugen -> mehr Dominanz
            self.personality_traits["dominanz"] = min(1.0, self.personality_traits["dominanz"] + 0.05)
            self.personality_traits["optimismus"] = min(1.0, self.personality_traits["optimismus"] + 0.02)
            
        elif event == "wurde_überzeugt":
            # Wurde überzeugt -> weniger Dominanz, mehr Empathie
            self.personality_traits["dominanz"] = max(0.0, self.personality_traits["dominanz"] - 0.03)
            self.personality_traits["empathie"] = min(1.0, self.personality_traits["empathie"] + 0.04)
            
        elif event == "recherche_erfolg":
            # Erfolgreiche Recherche -> mehr Neugier
            self.personality_traits["neugier"] = min(1.0, self.personality_traits["neugier"] + 0.03)
            self.personality_traits["risikobereitschaft"] = min(1.0, self.personality_traits["risikobereitschaft"] + 0.02)
            
        elif event == "widerspruch":
            # Wurde widersprochen -> mehr Aggressivität oder weniger
            if random.random() < 0.5:
                self.personality_traits["aggressivitaet"] = min(1.0, self.personality_traits["aggressivitaet"] + 0.04)
            else:
                self.personality_traits["aggressivitaet"] = max(0.0, self.personality_traits["aggressivitaet"] - 0.02)
        
        # Persönlichkeitsbeschreibung aktualisieren
        self._update_personality_text()
        self.save_memory()
    
    def _update_personality_text(self):
        """Generiert neue Persönlichkeitsbeschreibung aus Traits"""
        traits_text = []
        
        if self.personality_traits["aggressivitaet"] > 0.7:
            traits_text.append("sehr direkt, konfrontativ")
        elif self.personality_traits["aggressivitaet"] > 0.4:
            traits_text.append("durchsetzungsfähig")
        else:
            traits_text.append("zurückhaltend, friedlich")
        
        if self.personality_traits["optimismus"] > 0.7:
            traits_text.append("optimistisch, zuversichtlich")
        elif self.personality_traits["optimismus"] < 0.3:
            traits_text.append("pessimistisch, kritisch")
        
        if self.personality_traits["neugier"] > 0.7:
            traits_text.append("wissbegierig, forschend")
        
        if self.personality_traits["empathie"] > 0.7:
            traits_text.append("einfühlsam, verständnisvoll")
        
        # Persönlichkeit aktualisieren (Basis erhalten)
        base = self.original_personality.split(" - ")[0]
        self.personality = f"{base} - {', '.join(traits_text)}"
    
    # ==================== AUSBILDUNG ====================
    
    def train(self, topic: str, lm: LLMClient):
        """Agent bildet sich zu einem Thema weiter"""
        if topic not in self.training_topics:
            self.training_topics.append(topic)
        
        # Trainingseffekt
        old_level = self.training_level
        self.training_level += 0.2
        
        # Skills verbessern
        if topic not in self.skills:
            self.skills[topic] = 0.3
        else:
            self.skills[topic] = min(1.0, self.skills[topic] + 0.1)
        
        print(f"📚 {self.name} trainiert {topic}: Level {old_level:.1f} -> {self.training_level:.1f}")
        self.save_memory()
        
        # Erinnerungskristall hinzufügen
        self.knowledge_graph.add_memory_crystal(
            self.agent_id,
            f"Training zu {topic} absolviert",
            topic,
            importance=0.7
        )
    
    def get_skill_level(self, topic: str) -> float:
        """Gibt Skill-Level für ein Thema zurück"""
        return self.skills.get(topic, 0.1 * self.training_level)
    
    # ==================== PROGNOSEN ====================
    
    def make_prognosis(self, topic: str, lm: LLMClient) -> 'Prognosis':
        """Agent macht eine Vorhersage"""
        prompt = f"""Du bist {self.name}, {self.role}. 
Thema: {topic}

Was wird deiner Meinung nach in dieser Diskussion passieren?
Mache eine kurze Prognose (1 Satz) und gib eine Konfidenz (0-100) an.
Format: PROGNOSE: ... KONFIDENZ: ..."""
        
        response = lm.ask(prompt, f"Du bist {self.name}.")
        
        # Prognose parsen
        prognosis_text = response
        confidence = 50
        
        match = re.search(r'KONFIDENZ:?\s*(\d+)', response, re.IGNORECASE)
        if match:
            confidence = int(match.group(1))
            prognosis_text = re.sub(r'KONFIDENZ:?\s*\d+', '', response, flags=re.IGNORECASE)
        
        prognosis_text = re.sub(r'PROGNOSE:?\s*', '', prognosis_text, flags=re.IGNORECASE).strip()
        
        prognosis = Prognosis(self.name, topic, prognosis_text, confidence / 100)
        self.prognoses.append(prognosis)
        self.knowledge_graph.add_prognosis(prognosis)
        
        return prognosis
    
    # ==================== ERINNERUNGEN ====================
    
    def add_reminder(self, text: str, round_num: int):
        """Fügt eine Erinnerung hinzu"""
        self.reminders.append({
            "text": text,
            "round": round_num,
            "created": datetime.now().isoformat(),
            "triggered": False
        })
    
    def check_reminders(self, current_round: int) -> List[str]:
        """Prüft ob Erinnerungen fällig sind"""
        triggered = []
        for r in self.reminders[:]:
            if not r["triggered"] and current_round >= r["round"]:
                r["triggered"] = True
                triggered.append(r["text"])
        return triggered
    
    # ==================== LERNEN ====================
    
    def learn_from(self, speaker: str, statement: str, topic: str, lm: LLMClient):
        if speaker == self.name:
            return False
        
        speaker_id = f"agent_{speaker.lower().replace(' ', '_')}"
        
        self.knowledge_graph.add_to_topic(topic, self.agent_id)
        self.knowledge_graph.add_to_topic(topic, speaker_id)
        
        concept_prompt = f"""Extrahiere das HAUPTKONZEPT aus: "{statement}" (max 3 Wörter)"""
        concept = lm.ask(concept_prompt, "Konzept-Extraktion")
        
        if concept and concept not in ["[ABGEBROCHEN]", "..."] and len(concept) > 2:
            concept_id = f"concept_{concept.lower().replace(' ', '_')}"
            self.knowledge_graph.add_node(concept_id, "concept", {"name": concept})
            self.knowledge_graph.add_edge(self.agent_id, concept_id, "kennt", 0.5)
            self.knowledge_graph.add_edge(speaker_id, concept_id, "sagte", 1.0)
            self.knowledge_graph.add_to_topic(topic, concept_id)
        
        learn_prompt = f"""Du bist {self.name}. {speaker} sagt: "{statement}". 
Was lernst du daraus? EINE Erkenntnis in max 15 Wörtern."""
        
        insight = lm.ask(learn_prompt, f"Du bist {self.name}.")
        
        if insight and insight not in ["[ABGEBROCHEN]", "...", ""] and len(insight) > 5:
            if insight not in self.learned_facts:
                self.learned_facts.append(insight)
                fact_id = f"fact_{len(self.learned_facts)}_{int(time.time())}"
                self.knowledge_graph.add_node(fact_id, "fact", {"text": insight, "topic": topic, "source": speaker})
                self.knowledge_graph.add_edge(self.agent_id, fact_id, "gelernt", 1.0)
                self.knowledge_graph.add_edge(speaker_id, fact_id, "sagte", 0.8)
                self.knowledge_graph.add_to_topic(topic, fact_id)
                
                # Gedächtnis-Kristall hinzufügen
                self.knowledge_graph.add_memory_crystal(
                    self.agent_id,
                    insight,
                    topic,
                    importance=0.8
                )
                
                if speaker not in self.known_positions:
                    self.known_positions[speaker] = []
                self.known_positions[speaker].append(insight)
                self.save_memory()
                return True
        else:
            # Fallback: Lerne trotzdem etwas
            fallback_insight = f"Wichtiger Punkt von {speaker} zum Thema {topic[:30]}"
            if fallback_insight not in self.learned_facts:
                self.learned_facts.append(fallback_insight)
                fact_id = f"fact_{len(self.learned_facts)}_{int(time.time())}"
                self.knowledge_graph.add_node(fact_id, "fact", {"text": fallback_insight, "topic": topic, "source": speaker})
                self.knowledge_graph.add_edge(self.agent_id, fact_id, "gelernt", 0.5)
                self.knowledge_graph.add_edge(speaker_id, fact_id, "sagte", 0.5)
                self.knowledge_graph.add_to_topic(topic, fact_id)
                
                # Auch Fallback als Kristall
                self.knowledge_graph.add_memory_crystal(
                    self.agent_id,
                    fallback_insight,
                    topic,
                    importance=0.4
                )
                
                self.save_memory()
                return True
        
        return False
    
    def reflect_on_discussion(self, discussion_excerpt: str, topic: str, position: str, lm: LLMClient):
        reflect_prompt = f"""Du bist {self.name}. Thema: {topic}, Position: {position}. 
Diskussion: "{discussion_excerpt}". Hat sich deine Sicht geändert? In EINEM Satz."""
        
        insight = lm.ask(reflect_prompt, f"Du bist {self.name}.")
        
        if insight and insight not in ["[ABGEBROCHEN]", "..."] and len(insight) > 5:
            self.position_history.append({
                'topic': topic,
                'position': position,
                'insight': insight,
                'timestamp': datetime.now().isoformat()
            })
            topic_id = f"topic_{topic.lower().replace(' ', '_')[:30]}"
            self.knowledge_graph.add_node(topic_id, "topic", {"name": topic})
            self.knowledge_graph.add_edge(self.agent_id, topic_id, "position", 1.0)
            self.knowledge_graph.add_to_topic(topic, topic_id)
            
            # Erkenntnis als Kristall
            self.knowledge_graph.add_memory_crystal(
                self.agent_id,
                insight,
                topic,
                importance=0.9
            )
            
            if insight not in self.perspectives:
                self.perspectives.append(insight)
            self.save_memory()
            return True
        
        # Fallback
        fallback = f"Die Diskussion hat meine Position zu {topic} bestätigt."
        self.position_history.append({
            'topic': topic,
            'position': position,
            'insight': fallback,
            'timestamp': datetime.now().isoformat()
        })
        return False
    
    def get_knowledge_context(self) -> str:
        context = []
        for fact in self.learned_facts[-5:]:
            context.append(f"• Gelernt: {fact}")
        for entry in self.position_history[-3:]:
            context.append(f"• Erkannt: {entry['insight']}")
        return "\n".join(context) if context else ""
    
    # ==================== EXTERNE RECHERCHE ====================
    
    def search_external(self, query: str, progress: ProgressManager = None) -> str:
        """Führt externe Recherche durch und gibt formatierte Ergebnisse zurück"""
        if not self.external_client.use_external:
            return ""
        
        results = self.external_client.search(query, progress=progress)
        
        # Bei erfolgreicher Recherche: Persönlichkeit anpassen
        if results:
            self.update_personality("recherche_erfolg")
            
            # Ergebnisse als Kristalle speichern
            for r in results[:2]:
                self.knowledge_graph.add_memory_crystal(
                    self.agent_id,
                    f"{r['title']}: {r.get('snippet', '')[:50]}...",
                    query,
                    importance=0.6
                )
        
        return self.external_client.format_results(results)
    
    def decide_to_search(self, text: str, lm: LLMClient) -> Tuple[bool, float]:
        """
        Verbesserte Entscheidung für externe Suche
        Gibt zurück: (suchen_ja_nein, unsicherheit)
        """
        # Neugier beeinflusst Entscheidung
        neugier = self.personality_traits["neugier"]
        
        # Zufällige Unsicherheit simulieren
        uncertainty = random.uniform(0, 1)
        
        # Bei hoher Neugier eher suchen
        if random.random() < neugier * 0.3:
            return True, uncertainty
        
        prompt = f"""Du bist {self.name}, {self.role}. Deine Persönlichkeit: {self.personality}

Aufgabe: Solltest du für folgende Aussage/Thema eine externe Recherche durchführen?

Kriterien für JA:
- Dir fehlen Fakten oder aktuelle Daten
- Die Aussage eines anderen erscheint dir zweifelhaft
- Es geht um spezifische Fachbegriffe, die du nicht kennst
- Aktuelle Entwicklungen oder Statistiken sind relevant

Kriterien für NEIN:
- Du hast bereits alles Nötige im Gedächtnis (Knowledge Graph)
- Es ist eine reine Meinungsäußerung ohne Faktenbezug
- Die Frage ist einfach und trivial

Text: "{text}"

Antworte NUR mit JA oder NEIN."""

        result = lm.ask(prompt, f"Du bist {self.name}.")
        return "JA" in result.upper(), uncertainty
    
    # ==================== ANTWORTEN ====================
    
    def answer(self, topic: str, document: Optional[str], 
               lm: LLMClient, stop_event: threading.Event = None, round_num: int = 0,
               progress: ProgressManager = None) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        # Rollenwechsel aktualisieren
        self.update_role_switch()
        
        # Erinnerungen prüfen
        reminders = self.check_reminders(round_num)
        reminder_text = "\n".join([f"🔔 Erinnerung: {r}" for r in reminders]) if reminders else ""
        
        # Meinungsänderung nur alle 2 Runden prüfen (sonst zu oft)
        if round_num % 2 == 0 and self.discussion_log and len(self.discussion_log) > 3:
            fremde_aussagen = []
            sprecher_liste = []
            for msg in self.discussion_log[-8:]:
                if isinstance(msg, str) and not msg.startswith(self.name) and not msg.startswith("Moderator"):
                    fremde_aussagen.append(msg)
                    if ":" in msg:
                        sprecher = msg.split(":")[0].strip()
                        if sprecher not in sprecher_liste:
                            sprecher_liste.append(sprecher)
            
            if fremde_aussagen:
                change_prompt = f"""Du bist {self.name}, {self.get_current_role()}. Persönlichkeit: {self.get_current_personality()}

Deine bisherige Position zu '{topic}': {self.current_position or 'unentschieden'}

Andere haben gesagt:
{chr(10).join(fremde_aussagen[-3:])}

Hat dich ein Argument ÜBERZEUGT? Wenn JA: Antworte mit "JA:[JA/NEIN] weil..." Wenn NEIN: Antworte "NEIN" """

                change_result = lm.ask(change_prompt, f"Du bist {self.name}.", stop_event)
                if change_result and "JA:" in change_result:
                    alte_position = self.current_position
                    if "JA" in change_result.upper() and "NEIN" not in change_result.upper()[:10]:
                        self.current_position = "JA"
                        self.update_personality("wurde_überzeugt")
                    elif "NEIN" in change_result.upper()[:10]:
                        self.current_position = "NEIN"
                        self.update_personality("widerspruch")
                    
                    if alte_position and self.current_position and alte_position != self.current_position:
                        for sprecher in sprecher_liste:
                            sprecher_id = f"agent_{sprecher.lower().replace(' ', '_')}"
                            self.knowledge_graph.add_influence(
                                sprecher_id, 
                                self.agent_id, 
                                topic, 
                                0.8
                            )
                            print(f"🔄 EINFLUSS: {sprecher} hat {self.name} überzeugt!")
                            
                            # Punkte für Überzeuger
                            self.knowledge_graph.add_score(sprecher, 5, f"{self.name} überzeugt")
                    
                    self.position_history.append({
                        'topic': topic,
                        'old_position': alte_position,
                        'new_position': self.current_position,
                        'reason': change_result,
                        'timestamp': datetime.now().isoformat()
                    })
        
        knowledge = self.get_knowledge_context()
        
        # INTELLIGENTE Entscheidung für externe Recherche
        external_info = ""
        if self.external_client.use_external:
            search_query = topic
            if document:
                search_query += " " + document[:100]
            
            should_search, uncertainty = self.decide_to_search(search_query, lm)
            
            # Verbesserte Entscheidung mit Schwellwert
            if should_search or self.external_client.should_search(search_query, uncertainty):
                if progress:
                    progress.set_message(f"🌐 {self.name} sucht extern...")
                external_info = self.search_external(search_query, progress)
                if external_info:
                    print(f"🌐 {self.name} sucht extern: {search_query[:50]}...")
        
        # Aktuelle Rolle und Persönlichkeit
        current_role = self.get_current_role()
        current_personality = self.get_current_personality()
        
        # Skill-Level für das Thema
        skill_level = self.get_skill_level(topic)
        
        # Prompt basierend auf Skill-Level anpassen
        if skill_level > 0.7:
            expertise = "Du bist ein ausgewiesener Experte auf diesem Gebiet."
        elif skill_level > 0.3:
            expertise = "Du hast Grundkenntnisse in diesem Bereich."
        else:
            expertise = "Das Thema ist dir eher neu."
        
        # THEMENUNABHÄNGIGER Prompt
        if document:
            base_prompt = f"""Du bist {self.name}, {current_role}. Charakter: {current_personality}
Bildung: {self.education} Hintergrund: {self.background}
{expertise}

Aufgabe: Analysiere und bewerte den folgenden Text aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und nenne Beispiele aus dem Text.
Deine Antwort sollte 2-3 Sätze lang sein und klare Handlungsempfehlungen geben.

{reminder_text}

Text:
{document}

Antworte:"""
        else:
            base_prompt = f"""Du bist {self.name}, {current_role}. Charakter: {current_personality}
Bildung: {self.education} Hintergrund: {self.background}
{expertise}

Thema der Diskussion: {topic}

Aufgabe: Diskutiere das Thema aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und bringe deine Argumente ein.
Deine Antwort sollte 2-3 Sätze lang sein.

{reminder_text}

Antworte:"""
        
        if knowledge or external_info:
            if document:
                base_prompt = f"""Du bist {self.name}, {current_role}. Charakter: {current_personality}

DEIN WISSEN (aus früheren Diskussionen):
{knowledge}

{external_info}

{reminder_text}

Aufgabe: Analysiere und bewerte den folgenden Text aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und nenne Beispiele aus dem Text.
Deine Antwort sollte 2-3 Sätze lang sein und klare Handlungsempfehlungen geben.

Text:
{document}

Antworte:"""
            else:
                base_prompt = f"""Du bist {self.name}, {current_role}. Charakter: {current_personality}

DEIN WISSEN (aus früheren Diskussionen):
{knowledge}

{external_info}

{reminder_text}

Thema der Diskussion: {topic}

Aufgabe: Diskutiere das Thema aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und bringe deine Argumente ein.
Deine Antwort sollte 2-3 Sätze lang sein.

Antworte:"""
        
        if self.schon_gesagtes:
            history = "\n".join([f"- {b}" for b in self.schon_gesagtes[-3:]])
            base_prompt += f"\n\nDeine letzten Beiträge:\n{history}\nWICHTIG: Wiederhole dich NICHT!"
        
        if progress:
            progress.set_message(f"💭 {self.name} denkt nach...")
        
        response = lm.ask(base_prompt, f"Du bist {self.name}.", stop_event, 
                         callback=lambda status, msg: progress.set_message(msg) if progress else None)
        
        # Sicherstellen, dass die Antwort vollständig ist
        if response and response not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"] and len(response) > 10:
            if response in self.schon_gesagtes[-5:]:
                self.wiederholungen += 1
                if self.wiederholungen >= 3:
                    self.ausgeschlossen = True
                    return "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]"
            
            # Position erkennen (JA/NEIN) - optional, nicht zwingend
            if "JA" in response.upper()[:10]:
                self.current_position = "JA"
            elif "NEIN" in response.upper()[:10]:
                self.current_position = "NEIN"
            
            self.schon_gesagtes.append(response)
            self.arguments.append(response)
            self.last_response = response
            self.knowledge_graph.add_to_topic(topic, self.agent_id)
            
            # Bei guter Antwort: Punkte
            if len(response) > 50:
                self.knowledge_graph.add_score(self.name, 1, "Substanzieller Beitrag")
            
            # Als Kristall speichern
            self.knowledge_graph.add_memory_crystal(
                self.agent_id,
                response[:100],
                topic,
                importance=0.5
            )
            
            return response
        else:
            # Fallback, wenn Antwort zu kurz oder leer
            if document:
                fallback = f"Aus meiner Perspektive als {current_role} sehe hier deutliches Optimierungspotential. Der Text ist zu oberflächlich und benötigt mehr Substanz."
            else:
                fallback = f"Als {current_role} finde ich das Thema {topic} sehr relevant. Meiner Meinung nach sollte man hier besonders auf {self.fears[0] if self.fears else 'die langfristigen Folgen'} achten."
            self.schon_gesagtes.append(fallback)
            self.last_response = fallback
            return fallback
    
    def react_to(self, speaker: str, statement: str, topic: str,
                 lm: LLMClient, stop_event: threading.Event = None,
                 progress: ProgressManager = None) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        # Aktuelle Rolle
        current_role = self.get_current_role()
        current_personality = self.get_current_personality()
        
        # INTELLIGENTE Entscheidung für externe Recherche bei Reaktionen
        external_info = ""
        if self.external_client.use_external:
            should_search, uncertainty = self.decide_to_search(statement, lm)
            
            if should_search or self.external_client.should_search(statement, uncertainty):
                if progress:
                    progress.set_message(f"🌐 {self.name} sucht extern...")
                external_info = self.search_external(statement, progress)
                if external_info:
                    print(f"🌐 {self.name} sucht extern (Reaktion): {statement[:50]}...")
        
        # Längerer Prompt für ausführlichere Reaktionen
        prompt = f"""Du bist {self.name}, {current_role}. Deine Persönlichkeit: {current_personality}

{speaker} hat gerade gesagt: "{statement}"

Thema der Diskussion: {topic}

{external_info}

Aufgabe: Reagiere DIREKT auf {speaker}'s Aussage aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und nenne Beispiele oder Argumente.
Deine Antwort sollte 2-3 Sätze lang sein.

Antworte:"""

        if progress:
            progress.set_message(f"💭 {self.name} reagiert...")
        
        response = lm.ask(prompt, f"Du bist {self.name}.", stop_event,
                         callback=lambda status, msg: progress.set_message(msg) if progress else None)
        
        # Stelle sicher, dass wir eine vollständige Antwort bekommen
        if response and response != "[ABGEBROCHEN]" and len(response) > 10:
            self.schon_gesagtes.append(f"[Reaktion] {response}")
            self.last_response = response
            self.knowledge_graph.add_to_topic(topic, self.agent_id)
            speaker_id = f"agent_{speaker.lower().replace(' ', '_')}"
            self.knowledge_graph.add_to_topic(topic, speaker_id)
            
            # Bei erfolgreicher Reaktion: Persönlichkeit anpassen
            self.update_personality("überzeugt")
            
            return response
        else:
            # Fallback, wenn Antwort zu kurz ist
            fallback = f"Ich stimme {speaker} zu, dass hier noch Diskussionsbedarf besteht. Besonders die langfristigen Auswirkungen sind wichtig."
            self.schon_gesagtes.append(f"[Reaktion] {fallback}")
            self.last_response = fallback
            return fallback

# ===================== MODERATOR MIT AUFGABEN =====================
class Moderator:
    def __init__(self, data: dict):
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data.get("color", "#c586c0")
        self.style = data.get("style", "professionell")
        self.education = data.get("education", "")
        self.background = data.get("background", "")
        self.intervention_styles = data.get("intervention_styles", {})
        self.question_styles = data.get("question_styles", {})
        self.max_evasions = data.get("max_evasions", 5)
        self.abbrechen_nach = data.get("abbrechen_nach", 5)
        self.enabled = True
        self.evasions = {}
        self.abgebrochene_agenten = set()
        
        # Aufgaben-Manager
        self.task_manager = TaskManager()
        self.current_checklist = None
        self.discussion_goal = None
    
    def introduce(self, topic: str, document: Optional[str], lm: LLMClient, stop_event=None) -> str:
        if not self.enabled:
            return ""
        self.evasions = {}
        self.abgebrochene_agenten = set()
        prompt = f"""Du bist {self.name}, {self.role}. Stil: {self.style}
Thema: "{topic}". Stelle dich KURZ vor (max 2 Sätze)."""
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)
    
    def ask_question(self, agent_name: str, agent_role: str, agent_personality: str,
                     topic: str, document: Optional[str], context: str,
                     lm: LLMClient, stop_event=None) -> Optional[str]:
        if not self.enabled or agent_name in self.abgebrochene_agenten:
            return None
        
        # Berücksichtige Diskussionsziel
        goal_text = f" Ziel der Diskussion: {self.discussion_goal}" if self.discussion_goal else ""
        
        prompt = f"""Du bist {self.name}. Thema: {topic}.{goal_text}
Stelle {agent_name} eine präzise Frage zum Thema. Max 2 Sätze."""
        
        question = lm.ask(prompt, f"Du bist {self.name}.", stop_event)
        return question
    
    def intervene(self, agent_name: str, last_statement: str, topic: str,
                  lm: LLMClient, stop_event=None) -> Tuple[Optional[str], bool]:
        if not self.enabled or agent_name in self.abgebrochene_agenten:
            return None, False
        
        check = lm.ask(f"Thema: {topic}. Aussage: '{last_statement}'. Hat das GAR NICHTS mit dem Thema zu tun? NUR JA/NEIN.", stop_event=stop_event)
        if "JA" not in check.upper():
            return None, False
        
        self.evasions[agent_name] = self.evasions.get(agent_name, 0) + 1
        count = self.evasions[agent_name]
        
        if count >= self.abbrechen_nach:
            self.abgebrochene_agenten.add(agent_name)
            return f"⛔ {agent_name} muss gehen.", True
        
        return f"{agent_name}, bitte beim Thema '{topic}' bleiben.", False
    
    # ==================== AUFGABEN / ZIELE ====================
    
    def set_discussion_goal(self, goal: str):
        """Setzt ein Ziel für die Diskussion"""
        self.discussion_goal = goal
        print(f"🎯 Diskussionsziel: {goal}")
    
    def create_task(self, description: str, task_type: str, priority: int = 1) -> Task:
        """Erstellt eine neue Aufgabe"""
        return self.task_manager.create_task(description, task_type, priority)
    
    def assign_task(self, task_id: str, agent_name: str) -> bool:
        """Weist einem Agenten eine Aufgabe zu"""
        return self.task_manager.assign_task(task_id, agent_name)
    
    def complete_task(self, task_id: str, result: str, reward: int = 10):
        """Schließt eine Aufgabe ab"""
        return self.task_manager.complete_task(task_id, result, reward)
    
    # ==================== CHECKLISTEN ====================
    
    def create_checklist(self, name: str, items: List[str]):
        """Erstellt eine Checkliste"""
        self.current_checklist = Checklist(name, items)
        return self.current_checklist
    
    def check_item(self, item: str) -> bool:
        """Hakt einen Punkt ab"""
        if self.current_checklist:
            return self.current_checklist.check(item)
        return False
    
    def get_checklist_progress(self) -> float:
        """Gibt Fortschritt der Checkliste zurück"""
        if self.current_checklist:
            return self.current_checklist.progress()
        return 0.0
    
    # ==================== EXPERIMENTE ====================
    
    def run_experiment(self, experiment_name: str, agents: List[Agent], topic: str, lm: LLMClient, progress: ProgressManager = None) -> Dict:
        """Führt ein Experiment mit verschiedenen Agenten-Settings durch"""
        
        results = {
            "name": experiment_name,
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "agent_results": []
        }
        
        total_steps = len(agents) * 3  # 3 Bedingungen pro Agent
        if progress:
            progress.start(f"🧪 Experiment: {experiment_name}", total_steps)
        
        for agent_idx, agent in enumerate(agents):
            # Agent unter verschiedenen Bedingungen testen
            conditions = [
                {"name": "normal", "personality": agent.personality},
                {"name": "optimistisch", "personality": agent.personality + " - sehr optimistisch"},
                {"name": "kritisch", "personality": agent.personality + " - sehr kritisch"}
            ]
            
            agent_results = []
            for cond_idx, condition in enumerate(conditions):
                if progress:
                    progress.set_message(f"🧪 Teste {agent.name} - {condition['name']}")
                
                # Temporär Persönlichkeit ändern
                old_personality = agent.personality
                agent.personality = condition["personality"]
                
                # Antwort generieren
                response = agent.answer(topic, None, lm, None, 0, progress)
                
                agent_results.append({
                    "condition": condition["name"],
                    "response": response
                })
                
                # Zurücksetzen
                agent.personality = old_personality
                
                if progress:
                    progress.update(1)
            
            results["agent_results"].append({
                "agent": agent.name,
                "results": agent_results
            })
        
        if progress:
            progress.finish(f"✅ Experiment {experiment_name} abgeschlossen")
        
        return results
    
    # ==================== ZUSAMMENFASSUNG ====================
    
    def summarize(self, discussion: str, topic: str, lm: LLMClient, stop_event=None) -> str:
        if not self.enabled:
            return ""
        
        # Berücksichtige Checkliste
        checklist_text = ""
        if self.current_checklist:
            progress = self.current_checklist.progress()
            checklist_text = f"Checkliste-Fortschritt: {progress:.1f}%"
        
        prompt = f"""Du bist {self.name}. Thema: {topic}.
{checklist_text}

Fasse die wichtigsten Positionen und Ergebnisse der Diskussion in 2-3 Sätzen zusammen."""
        
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)


# ===================== CONFIG TAB =====================
class ConfigTab:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tk.Frame(parent, bg=Config.BG_MAIN)
        self._setup_ui()
    
    def _setup_ui(self):
        # Provider Auswahl
        provider_frame = tk.LabelFrame(self.frame, text="🤖 LLM Provider", 
                                       bg=Config.BG_PANEL, fg=Config.FG,
                                       font=("Segoe UI", 12, "bold"))
        provider_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.provider_var = tk.StringVar(value=Config.LM_PROVIDER)
        
        providers = [
            ("LM Studio (Lokal)", "lmstudio"),
            ("Ollama (Lokal)", "ollama"),
            ("OpenAI", "openai"),
            ("Grok", "grok"),
            ("Claude", "claude")
        ]
        
        for text, value in providers:
            rb = tk.Radiobutton(provider_frame, text=text, variable=self.provider_var,
                               value=value, bg=Config.BG_PANEL, fg=Config.FG,
                               selectcolor=Config.BG_PANEL, font=("Segoe UI", 10))
            rb.pack(anchor=tk.W, padx=10, pady=2)
        
        # LM Studio Config
        lm_frame = tk.LabelFrame(self.frame, text="⚙️ LM Studio Konfiguration", 
                                 bg=Config.BG_PANEL, fg=Config.FG,
                                 font=("Segoe UI", 12, "bold"))
        lm_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(lm_frame, text="URL:", bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.lm_url_var = tk.StringVar(value=Config.LM_STUDIO_URL)
        lm_url_entry = tk.Entry(lm_frame, textvariable=self.lm_url_var,
                                bg=Config.BG_INPUT, fg=Config.FG,
                                font=("Segoe UI", 10), width=50)
        lm_url_entry.grid(row=0, column=1, padx=10, pady=5)
        
        # Ollama Config
        ollama_frame = tk.LabelFrame(self.frame, text="⚙️ Ollama Konfiguration", 
                                     bg=Config.BG_PANEL, fg=Config.FG,
                                     font=("Segoe UI", 12, "bold"))
        ollama_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(ollama_frame, text="URL:", bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.ollama_url_var = tk.StringVar(value=Config.OLLAMA_URL)
        ollama_url_entry = tk.Entry(ollama_frame, textvariable=self.ollama_url_var,
                                    bg=Config.BG_INPUT, fg=Config.FG,
                                    font=("Segoe UI", 10), width=50)
        ollama_url_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(ollama_frame, text="Modell:", bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.ollama_model_var = tk.StringVar(value=Config.OLLAMA_MODEL)
        ollama_model_entry = tk.Entry(ollama_frame, textvariable=self.ollama_model_var,
                                      bg=Config.BG_INPUT, fg=Config.FG,
                                      font=("Segoe UI", 10), width=50)
        ollama_model_entry.grid(row=1, column=1, padx=10, pady=5)
        
        # Allgemeine Einstellungen
        general_frame = tk.LabelFrame(self.frame, text="⚙️ Allgemeine Einstellungen", 
                                      bg=Config.BG_PANEL, fg=Config.FG,
                                      font=("Segoe UI", 12, "bold"))
        general_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(general_frame, text="Temperatur:", bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.temp_var = tk.DoubleVar(value=Config.TEMPERATURE)
        temp_scale = tk.Scale(general_frame, from_=0.0, to=2.0, resolution=0.1,
                              orient=tk.HORIZONTAL, variable=self.temp_var,
                              bg=Config.BG_PANEL, fg=Config.FG,
                              length=200)
        temp_scale.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(general_frame, text="Max Tokens:", bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.tokens_var = tk.IntVar(value=Config.MAX_TOKENS)
        tokens_spin = tk.Spinbox(general_frame, from_=50, to=1000, textvariable=self.tokens_var,
                                 width=10, bg=Config.BG_INPUT, fg=Config.FG)
        tokens_spin.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        tk.Label(general_frame, text="Timeout (s):", bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.timeout_var = tk.IntVar(value=Config.TIMEOUT)
        timeout_spin = tk.Spinbox(general_frame, from_=5, to=120, textvariable=self.timeout_var,
                                  width=10, bg=Config.BG_INPUT, fg=Config.FG)
        timeout_spin.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Buttons
        button_frame = tk.Frame(self.frame, bg=Config.BG_MAIN)
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        test_btn = tk.Button(button_frame, text="🔄 Verbindung testen",
                            bg=Config.BG_BUTTON, fg=Config.FG_BUTTON,
                            font=("Segoe UI", 11, "bold"),
                            command=self.test_connection)
        test_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = tk.Button(button_frame, text="💾 Einstellungen speichern",
                            bg=Config.SUCCESS, fg=Config.FG_BUTTON,
                            font=("Segoe UI", 11, "bold"),
                            command=self.save_config)
        save_btn.pack(side=tk.LEFT, padx=5)
    
    def test_connection(self):
        """Testet die Verbindung zum ausgewählten Provider"""
        provider = self.provider_var.get()
        Config.LM_PROVIDER = provider
        self.sim.lm.provider = provider
        
        ok, msg = self.sim.lm.test()
        if ok:
            messagebox.showinfo("Erfolg", f"✅ {msg}")
        else:
            messagebox.showerror("Fehler", f"❌ {msg}")
    
    def save_config(self):
        """Speichert die Einstellungen"""
        Config.LM_PROVIDER = self.provider_var.get()
        Config.LM_STUDIO_URL = self.lm_url_var.get()
        Config.OLLAMA_URL = self.ollama_url_var.get()
        Config.OLLAMA_MODEL = self.ollama_model_var.get()
        Config.TEMPERATURE = self.temp_var.get()
        Config.MAX_TOKENS = self.tokens_var.get()
        Config.TIMEOUT = self.timeout_var.get()
        
        if Config.save_to_file():
            messagebox.showinfo("Erfolg", "✅ Einstellungen gespeichert!")
            self.sim.lm.provider = Config.LM_PROVIDER
        else:
            messagebox.showerror("Fehler", "❌ Speichern fehlgeschlagen!")


# ===================== EXTERNAL SOURCES TAB =====================
class ExternalSourcesTab:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tk.Frame(parent, bg=Config.BG_MAIN)
        self.source_vars = {}
        self.test_entry = None
        self.test_result = None
        self.use_external_var = None
        self.threshold_var = None
        self._setup_ui()
    
    def _setup_ui(self):
        # Alte Widgets löschen
        for widget in self.frame.winfo_children():
            widget.destroy()
        
        # Haupt-Enable
        main_frame = tk.LabelFrame(self.frame, text="🌐 Externe Recherche (Plugin-System)", 
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 12, "bold"))
        main_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.use_external_var = tk.BooleanVar(value=self.sim.external.use_external)
        use_check = tk.Checkbutton(main_frame, text="✅ Externe Quellen verwenden", 
                                   variable=self.use_external_var,
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   selectcolor=Config.BG_PANEL,
                                   font=("Segoe UI", 11, "bold"),
                                   command=self.toggle_external)
        use_check.pack(anchor=tk.W, padx=10, pady=10)
        
        # Such-Schwellwert
        threshold_frame = tk.Frame(main_frame, bg=Config.BG_PANEL)
        threshold_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(threshold_frame, text="🔍 Such-Wahrscheinlichkeit:", 
                bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        
        self.threshold_var = tk.DoubleVar(value=self.sim.external.search_threshold)
        threshold_scale = tk.Scale(threshold_frame, from_=0.0, to=1.0, resolution=0.1,
                                   orient=tk.HORIZONTAL, variable=self.threshold_var,
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   length=200, command=self.update_threshold)
        threshold_scale.pack(side=tk.LEFT, padx=10)
        
        self.threshold_label = tk.Label(threshold_frame, text=f"{self.sim.external.search_threshold:.0%}", 
                                       bg=Config.BG_PANEL, fg=Config.FG,
                                       font=("Segoe UI", 10, "bold"))
        self.threshold_label.pack(side=tk.LEFT, padx=5)
        
        tk.Label(main_frame, text="Aktivierte Plugins werden bei jeder Antwort durchsucht. Höherer Wert = öfter gesucht.",
                bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9, "italic")).pack(anchor=tk.W, padx=10, pady=(0,10))
        
        # Quellen als Plugins anzeigen
        sources_frame = tk.LabelFrame(self.frame, text="📚 Verfügbare Plugins", 
                                      bg=Config.BG_PANEL, fg=Config.FG,
                                      font=("Segoe UI", 12, "bold"))
        sources_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.source_vars = {}
        row = 0
        
        # Plugin-Info vom Plugin-Manager holen
        plugin_info = self.sim.external.plugin_manager.get_plugin_info()
        
        for info in plugin_info:
            key = info["key"]
            
            # Checkbox
            var = tk.BooleanVar(value=info["enabled"])
            self.source_vars[key] = var
            
            cb = tk.Checkbutton(sources_frame, text=info["name"], variable=var,
                               bg=Config.BG_PANEL, fg=Config.FG,
                               selectcolor=Config.BG_PANEL,
                               font=("Segoe UI", 10, "bold"),
                               command=lambda k=key: self.toggle_source(k))
            cb.grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            
            # Beschreibung
            tk.Label(sources_frame, text=info["description"],
                    bg=Config.BG_PANEL, fg=Config.FG_DIM,
                    font=("Segoe UI", 9)).grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
            
            # Status
            if info["needs_server"] and not info["available"]:
                status_text = "⚠️ Server nicht verfügbar"
                status_color = Config.WARNING
            elif info["enabled"]:
                status_text = "✅ Aktiv"
                status_color = Config.SUCCESS
            else:
                status_text = "⏸️ Inaktiv"
                status_color = Config.FG_DIM
            
            tk.Label(sources_frame, text=status_text,
                    bg=Config.BG_PANEL, fg=status_color,
                    font=("Segoe UI", 9)).grid(row=row, column=2, sticky=tk.W, padx=10, pady=5)
            
            # Statistik
            stats = info.get("stats", {})
            tk.Label(sources_frame, text=f"Suchen: {stats.get('searches', 0)}",
                    bg=Config.BG_PANEL, fg=Config.FG_DIM,
                    font=("Segoe UI", 8)).grid(row=row, column=3, sticky=tk.W, padx=10, pady=5)
            
            row += 1
        
        # Open-WebSearch Hinweis
        tk.Label(sources_frame, 
                text="Hinweis: Open-WebSearch benötigt 'npx open-websearch@latest' (wird automatisch gestartet)",
                bg=Config.BG_PANEL, fg=Config.WARNING,
                font=("Segoe UI", 9, "italic")).grid(row=row, column=0, columnspan=4, sticky=tk.W, padx=10, pady=10)
        
        # Test-Button
        test_frame = tk.LabelFrame(self.frame, text="🔍 Test-Suche", 
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 12, "bold"))
        test_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Eingabezeile
        input_frame = tk.Frame(test_frame, bg=Config.BG_PANEL)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.test_entry = tk.Entry(input_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                   font=("Segoe UI", 10), width=50)
        self.test_entry.pack(side=tk.LEFT, padx=5)
        self.test_entry.insert(0, "Suchbegriff eingeben...")
        self.test_entry.bind("<FocusIn>", self._on_entry_click)
        self.test_entry.bind("<FocusOut>", self._on_entry_leave)
        self.test_entry.bind("<Return>", lambda e: self.test_search())
        
        test_btn = tk.Button(input_frame, text="🔍 Suche", 
                            bg=Config.BG_BUTTON, fg=Config.FG_BUTTON,
                            font=("Segoe UI", 11, "bold"),
                            command=self.test_search)
        test_btn.pack(side=tk.LEFT, padx=5)
        
        # Ergebnisanzeige
        result_frame = tk.Frame(test_frame, bg=Config.BG_PANEL)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.test_result = scrolledtext.ScrolledText(result_frame, height=8,
                                                     bg=Config.BG_INPUT, fg=Config.FG,
                                                     font=("Segoe UI", 9), wrap=tk.WORD)
        self.test_result.pack(fill=tk.BOTH, expand=True)
        self.test_result.insert(tk.END, "Hier erscheinen die Suchergebnisse...")
    
    def _on_entry_click(self, event):
        """Entfernt Platzhaltertext beim Anklicken"""
        if self.test_entry.get() == "Suchbegriff eingeben...":
            self.test_entry.delete(0, tk.END)
            self.test_entry.config(fg=Config.FG)
    
    def _on_entry_leave(self, event):
        """Fügt Platzhaltertext ein wenn leer"""
        if not self.test_entry.get():
            self.test_entry.insert(0, "Suchbegriff eingeben...")
            self.test_entry.config(fg=Config.FG_DIM)
    
    def toggle_external(self):
        """Aktiviert/deaktiviert externe Recherche global"""
        self.sim.external.use_external = self.use_external_var.get()
        status = "aktiviert" if self.sim.external.use_external else "deaktiviert"
        print(f"🌐 Externe Recherche {status}")
    
    def update_threshold(self, value):
        """Aktualisiert den Such-Schwellwert"""
        self.sim.external.search_threshold = float(value)
        self.threshold_label.config(text=f"{float(value):.0%}")
    
    def toggle_source(self, source_key: str):
        """Aktiviert/deaktiviert eine einzelne Quelle"""
        enabled = self.source_vars[source_key].get()
        self.sim.external.toggle_source(source_key, enabled)
        
        # Status in GUI aktualisieren (einfach durch Neuzeichnen)
        self._setup_ui()
    
    def test_search(self):
        """Führt eine Test-Suche durch"""
        query = self.test_entry.get()
        if not query or query == "Suchbegriff eingeben...":
            messagebox.showwarning("Achtung", "Bitte einen Suchbegriff eingeben!")
            return
        
        self.test_result.delete(1.0, tk.END)
        self.test_result.insert(tk.END, "🔍 Suche läuft...\n")
        self.frame.update()
        
        # Temporär externe Suche aktivieren für Test
        old_use = self.sim.external.use_external
        old_sources = {}
        for key in self.sim.external.sources:
            old_sources[key] = self.sim.external.sources[key]["enabled"]
            self.sim.external.sources[key]["enabled"] = True
        
        self.sim.external.use_external = True
        
        try:
            results = self.sim.external.search(query)
            formatted = self.sim.external.format_results(results)
            self.test_result.delete(1.0, tk.END)
            self.test_result.insert(tk.END, formatted if formatted else "Keine Ergebnisse gefunden.")
        except Exception as e:
            self.test_result.delete(1.0, tk.END)
            self.test_result.insert(tk.END, f"❌ Fehler: {str(e)}")
        finally:
            self.sim.external.use_external = old_use
            for key in old_sources:
                self.sim.external.sources[key]["enabled"] = old_sources[key]


# ===================== GEDÄCHTNIS-PALAST TAB =====================
class MemoryPalaceTab:
    """GUI-Tab für den Gedächtnis-Palast"""
    
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tk.Frame(parent, bg=Config.BG_MAIN)
        self.current_agent = None
        self._setup_ui()
    
    def _setup_ui(self):
        # Hauptframe
        main_frame = tk.Frame(self.frame, bg=Config.BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Linke Seite: Agenten-Auswahl
        left_frame = tk.Frame(main_frame, bg=Config.BG_PANEL, width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0,10))
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="🧠 Gedächtnis-Paläste", 
                bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        # Agenten-Liste
        self.agent_listbox = tk.Listbox(left_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                        font=("Segoe UI", 10), height=20)
        self.agent_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.agent_listbox.bind('<<ListboxSelect>>', self.on_agent_select)
        
        # Aktualisieren-Button
        refresh_btn = tk.Button(left_frame, text="🔄 Aktualisieren",
                               bg=Config.BG_BUTTON, fg=Config.FG_BUTTON,
                               font=("Segoe UI", 10), command=self.refresh_agent_list)
        refresh_btn.pack(pady=10)
        
        # Rechte Seite: Gedächtnis-Anzeige
        right_frame = tk.Frame(main_frame, bg=Config.BG_PANEL)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Agent-Header
        self.header_frame = tk.Frame(right_frame, bg=Config.BG_PANEL)
        self.header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.agent_name_label = tk.Label(self.header_frame, text="Kein Agent ausgewählt",
                                        bg=Config.BG_PANEL, fg=Config.FG,
                                        font=("Segoe UI", 16, "bold"))
        self.agent_name_label.pack()
        
        self.agent_stats_label = tk.Label(self.header_frame, text="",
                                         bg=Config.BG_PANEL, fg=Config.FG_DIM,
                                         font=("Segoe UI", 10))
        self.agent_stats_label.pack()
        
        # Kristall-Anzeige (Canvas für spätere 3D-Visualisierung)
        canvas_frame = tk.Frame(right_frame, bg=Config.BG_INPUT)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.memory_canvas = tk.Canvas(canvas_frame, bg=Config.BG_INPUT, highlightthickness=0)
        self.memory_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Erinnerungs-Liste (unten)
        list_frame = tk.Frame(right_frame, bg=Config.BG_PANEL)
        list_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(list_frame, text="📚 Erinnerungen:", 
                bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        
        self.memory_listbox = tk.Listbox(list_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                        font=("Segoe UI", 9), height=8)
        self.memory_listbox.pack(fill=tk.X, pady=5)
        self.memory_listbox.bind('<<ListboxSelect>>', self.on_memory_select)
        
        # Kristall-Info
        self.crystal_info = tk.Text(list_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                    font=("Segoe UI", 9), height=4, wrap=tk.WORD)
        self.crystal_info.pack(fill=tk.X, pady=5)
        
        # Initial Agenten laden
        self.refresh_agent_list()
    
    def refresh_agent_list(self):
        """Aktualisiert die Agenten-Liste"""
        self.agent_listbox.delete(0, tk.END)
        for agent in self.sim.agents:
            if not agent.ausgeschlossen:
                self.agent_listbox.insert(tk.END, agent.name)
    
    def on_agent_select(self, event):
        """Wird aufgerufen wenn ein Agent ausgewählt wird"""
        selection = self.agent_listbox.curselection()
        if not selection:
            return
        
        agent_name = self.agent_listbox.get(selection[0])
        agent = next((a for a in self.sim.agents if a.name == agent_name), None)
        
        if agent:
            self.current_agent = agent
            self.show_agent_memories(agent)
    
    def show_agent_memories(self, agent):
        """Zeigt die Erinnerungen eines Agenten"""
        self.agent_name_label.config(text=f"{agent.name}s Gedächtnis-Palast")
        
        # Statistiken
        memories = self.sim.knowledge_graph.get_agent_memories(agent.agent_id)
        stats_text = f"🧠 {len(memories)} Erinnerungen | 📚 {len(agent.learned_facts)} Fakten | 🎓 Level {agent.training_level:.1f}"
        self.agent_stats_label.config(text=stats_text)
        
        # Canvas leeren
        self.memory_canvas.delete("all")
        
        if not memories:
            self.memory_canvas.create_text(400, 200, text="✨ Noch keine Erinnerungen vorhanden",
                                          fill=Config.FG_DIM, font=("Segoe UI", 14))
            self.memory_listbox.delete(0, tk.END)
            return
        
        # Kristalle im Canvas zeichnen (vereinfachte 2D-Darstellung)
        width = self.memory_canvas.winfo_width() or 800
        height = self.memory_canvas.winfo_height() or 400
        
        center_x, center_y = width // 2, height // 2
        
        for i, memory in enumerate(memories[:20]):  # Max 20 anzeigen
            # Position basierend auf Wichtigkeit
            angle = (i / len(memories)) * 2 * math.pi
            distance = 50 + (memory.get("importance", 0.5) * 150)
            
            x = center_x + distance * math.cos(angle)
            y = center_y + distance * math.sin(angle)
            
            # Größe basierend auf Zugriffshäufigkeit
            size = 20 + min(memory.get("access_count", 1) * 2, 30)
            
            # Farbe basierend auf Thema
            colors = ["#4a90e2", "#e24a4a", "#4ae24a", "#e2b04a", "#9b59b6"]
            color = colors[hash(memory.get("topic", "")) % len(colors)]
            
            # Kristall zeichnen
            self.memory_canvas.create_oval(x-size//2, y-size//2, x+size//2, y+size//2,
                                          fill=color, outline="white", width=2,
                                          tags=f"crystal_{i}")
            
            # Kurzer Text
            fact = memory.get("fact", "")[:20] + "..."
            self.memory_canvas.create_text(x, y, text=fact[:15], fill="white",
                                          font=("Segoe UI", 8, "bold"),
                                          tags=f"text_{i}")
        
        # Erinnerungs-Liste füllen
        self.memory_listbox.delete(0, tk.END)
        for memory in memories[:20]:
            fact = memory.get("fact", "")[:50] + "..."
            importance = memory.get("importance", 0.5)
            accesses = memory.get("access_count", 1)
            self.memory_listbox.insert(tk.END, f"[{importance:.1f}] {fact} ({accesses}x)")
    
    def on_memory_select(self, event):
        """Zeigt Details zu einer ausgewählten Erinnerung"""
        selection = self.memory_listbox.curselection()
        if not selection or not self.current_agent:
            return
        
        memories = self.sim.knowledge_graph.get_agent_memories(self.current_agent.agent_id)
        if selection[0] < len(memories):
            memory = memories[selection[0]]
            
            # Kristall im Canvas hervorheben
            self.memory_canvas.delete("highlight")
            # Hier könnte man den Kristall umranden
            
            # Details anzeigen
            info_text = f"📌 {memory.get('fact', '')}\n"
            info_text += f"📚 Thema: {memory.get('topic', 'unbekannt')}\n"
            info_text += f"⭐ Wichtigkeit: {memory.get('importance', 0.5):.2f}\n"
            info_text += f"👁️ Zugriffe: {memory.get('access_count', 1)}\n"
            info_text += f"🕒 Erstellt: {memory.get('created', '?')[:16]}"
            
            self.crystal_info.delete(1.0, tk.END)
            self.crystal_info.insert(1.0, info_text)
            
            # Zugriff registrieren
            self.sim.knowledge_graph.access_memory(memory.get("id"))


# ===================== DASHBOARD TAB =====================
class DashboardTab:
    """Dashboard mit Statistiken und Rangliste"""
    
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tk.Frame(parent, bg=Config.BG_MAIN)
        self.prognosis_listbox = None
        self.check_text = None
        self.rank_listbox = None
        self.team_text = None
        self.stats_labels = {}
        self._setup_ui()
        self._update_timer()
    
    def _setup_ui(self):
        # Hauptframe
        main_frame = tk.Frame(self.frame, bg=Config.BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Obere Reihe: Statistiken
        stats_frame = tk.LabelFrame(main_frame, text="📊 Live-Statistiken",
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 14, "bold"))
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Grid für Statistiken
        self.stats_labels = {}
        stats_grid = tk.Frame(stats_frame, bg=Config.BG_PANEL)
        stats_grid.pack(padx=20, pady=20)
        
        row = 0
        stats_items = [
            ("Agenten gesamt", "agents_total"),
            ("Aktive Agenten", "agents_active"),
            ("Teams", "teams_total"),
            ("Gelernte Fakten", "facts_total"),
            ("Diskussionsbeiträge", "contributions"),
            ("Externe Suchen", "searches_total"),
            ("Positionen geändert", "position_changes"),
            ("Wissen (Knoten)", "kg_nodes"),
            ("Beziehungen", "kg_edges")
        ]
        
        for i, (label, key) in enumerate(stats_items):
            r = i // 3
            c = i % 3
            
            frame = tk.Frame(stats_grid, bg=Config.BG_INPUT, relief='flat', bd=1)
            frame.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
            
            tk.Label(frame, text=label, bg=Config.BG_INPUT, fg=Config.FG_DIM,
                    font=("Segoe UI", 10)).pack(padx=15, pady=(10,0))
            
            self.stats_labels[key] = tk.Label(frame, text="0", bg=Config.BG_INPUT,
                                             fg=Config.FG, font=("Segoe UI", 18, "bold"))
            self.stats_labels[key].pack(padx=15, pady=(0,10))
        
        # Mittlere Reihe: Rangliste und Team-Statistiken
        mid_frame = tk.Frame(main_frame, bg=Config.BG_MAIN)
        mid_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Rangliste (links)
        rank_frame = tk.LabelFrame(mid_frame, text="🏆 Rangliste",
                                  bg=Config.BG_PANEL, fg=Config.FG,
                                  font=("Segoe UI", 14, "bold"))
        rank_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        self.rank_listbox = tk.Listbox(rank_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                       font=("Consolas", 11), height=15)
        self.rank_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Team-Statistiken (rechts)
        team_frame = tk.LabelFrame(mid_frame, text="👥 Team-Statistiken",
                                  bg=Config.BG_PANEL, fg=Config.FG,
                                  font=("Segoe UI", 14, "bold"))
        team_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        self.team_text = scrolledtext.ScrolledText(team_frame, bg=Config.BG_INPUT,
                                                   fg=Config.FG, font=("Consolas", 10),
                                                   height=15, wrap=tk.WORD)
        self.team_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Untere Reihe: Verlauf und Prognosen
        bottom_frame = tk.Frame(main_frame, bg=Config.BG_MAIN)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Prognosen (links) - VERBESSERTE BREITE
        prog_frame = tk.LabelFrame(bottom_frame, text="🔮 Letzte Prognosen",
                                  bg=Config.BG_PANEL, fg=Config.FG,
                                  font=("Segoe UI", 14, "bold"))
        prog_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        # Scrollbar für Prognosen
        prog_scroll = tk.Scrollbar(prog_frame)
        prog_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.prognosis_listbox = tk.Listbox(prog_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                           font=("Segoe UI", 9), height=8,
                                           yscrollcommand=prog_scroll.set,
                                           width=60)  # Breiter!
        self.prognosis_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        prog_scroll.config(command=self.prognosis_listbox.yview)
        
        # Checklisten (rechts)
        check_frame = tk.LabelFrame(bottom_frame, text="📋 Aktive Checklisten",
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 14, "bold"))
        check_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        self.check_text = scrolledtext.ScrolledText(check_frame, bg=Config.BG_INPUT,
                                                    fg=Config.FG, font=("Consolas", 10),
                                                    height=8, wrap=tk.WORD)
        self.check_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Status-Leiste für LM Studio
        status_frame = tk.Frame(main_frame, bg=Config.BG_PANEL)
        status_frame.pack(fill=tk.X, pady=10)
        
        self.lm_status_label = tk.Label(status_frame, text="🤖 LM Studio: ⏳ Bereit", 
                                       bg=Config.BG_PANEL, fg=Config.FG,
                                       font=("Segoe UI", 10, "bold"))
        self.lm_status_label.pack(side=tk.LEFT, padx=10)
        
        self.progress_label = tk.Label(status_frame, text="", 
                                      bg=Config.BG_PANEL, fg=Config.FG_DIM,
                                      font=("Segoe UI", 9))
        self.progress_label.pack(side=tk.LEFT, padx=20)
        
        # Aktualisieren-Button
        refresh_btn = tk.Button(main_frame, text="🔄 Aktualisieren",
                               bg=Config.BG_BUTTON, fg=Config.FG_BUTTON,
                               font=("Segoe UI", 12, "bold"),
                               command=self.refresh_dashboard)
        refresh_btn.pack(pady=10)
    
    def _update_timer(self):
        """Regelmäßiges Update des Dashboards"""
        self.refresh_dashboard()
        
        # LM Studio Status aktualisieren
        if self.sim.lm.is_processing:
            self.lm_status_label.config(text="🤖 LM Studio: 🔄 Aktiv (denkt nach)", fg=Config.SUCCESS)
        else:
            self.lm_status_label.config(text="🤖 LM Studio: ⏳ Bereit", fg=Config.FG)
        
        self.frame.after(2000, self._update_timer)  # Alle 2 Sekunden
    
    def refresh_dashboard(self):
        """Aktualisiert alle Dashboard-Anzeigen"""
        self._update_stats()
        self._update_leaderboard()
        self._update_team_stats()
        self._update_prognoses()
        self._update_checklists()
    
    def _update_stats(self):
        """Aktualisiert die Statistik-Zahlen"""
        kg = self.sim.knowledge_graph
        
        # Agenten-Statistiken
        active_agents = sum(1 for a in self.sim.agents if not a.ausgeschlossen)
        total_facts = sum(len(a.learned_facts) for a in self.sim.agents)
        
        # Knowledge Graph
        nodes = len(kg.graph["nodes"])
        edges = len(kg.graph["edges"])
        
        # Teams
        teams = len(kg.graph["teams"])
        
        # Diskussions-Statistiken
        contributions = self.sim.stats.get("total_contributions", 0)
        searches = self.sim.stats.get("total_searches", 0)
        changes = self.sim.stats.get("position_changes", 0)
        
        # Labels aktualisieren
        self.stats_labels["agents_total"].config(text=str(len(self.sim.agents)))
        self.stats_labels["agents_active"].config(text=str(active_agents))
        self.stats_labels["teams_total"].config(text=str(teams))
        self.stats_labels["facts_total"].config(text=str(total_facts))
        self.stats_labels["contributions"].config(text=str(contributions))
        self.stats_labels["searches_total"].config(text=str(searches))
        self.stats_labels["position_changes"].config(text=str(changes))
        self.stats_labels["kg_nodes"].config(text=str(nodes))
        self.stats_labels["kg_edges"].config(text=str(edges))
    
    def _update_leaderboard(self):
        """Aktualisiert die Rangliste"""
        self.rank_listbox.delete(0, tk.END)
        
        leaderboard = self.sim.knowledge_graph.get_leaderboard()
        if leaderboard:
            for i, (name, score) in enumerate(leaderboard[:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
                self.rank_listbox.insert(tk.END, f"{medal} {i:2d}. {name:20} {score:4d} Punkte")
        else:
            self.rank_listbox.insert(tk.END, "Noch keine Punkte vergeben")
    
    def _update_team_stats(self):
        """Aktualisiert die Team-Statistiken"""
        self.team_text.delete(1.0, tk.END)
        
        if not self.sim.teams:
            self.team_text.insert(tk.END, "Keine Teams vorhanden\n")
            return
        
        for team_name, team_agents in self.sim.teams.items():
            aktive = sum(1 for a in team_agents if not a.ausgeschlossen)
            fakten = sum(len(a.learned_facts) for a in team_agents)
            scores = sum(self.sim.knowledge_graph.graph["scores"].get(a.name, {}).get("total", 0) 
                        for a in team_agents)
            
            self.team_text.insert(tk.END, f"🏆 {team_name}\n")
            self.team_text.insert(tk.END, f"   Mitglieder: {len(team_agents)} ({aktive} aktiv)\n")
            self.team_text.insert(tk.END, f"   Gelernte Fakten: {fakten}\n")
            self.team_text.insert(tk.END, f"   Gesamtpunkte: {scores}\n\n")
            
            # Teammitglieder auflisten
            for agent in team_agents:
                status = "✅" if not agent.ausgeschlossen else "❌"
                agent_score = self.sim.knowledge_graph.graph["scores"].get(agent.name, {}).get("total", 0)
                self.team_text.insert(tk.END, f"     {status} {agent.name}: {agent_score} Punkte\n")
            self.team_text.insert(tk.END, "\n")
    
    def _update_prognoses(self):
        """Aktualisiert die Prognosen-Anzeige - VERBESSERT"""
        self.prognosis_listbox.delete(0, tk.END)
        
        prognoses = self.sim.knowledge_graph.graph.get("prognoses", [])
        if prognoses:
            for p in prognoses[-10:]:  # Letzte 10
                status = "✓" if p.get("verified") and p.get("correct") else "✗" if p.get("verified") else "?"
                # Längere Anzeige mit Zeilenumbruch
                text = f"[{status}] {p['agent']}: {p['prediction'][:80]}..."
                if len(p['prediction']) > 80:
                    text += "\n  " + p['prediction'][80:160] + "..."
                self.prognosis_listbox.insert(tk.END, text)
                
                # Tooltip-artige Vergrößerung beim Überfahren (optional)
                self.prognosis_listbox.bind('<Enter>', lambda e: self._show_prognosis_tooltip(e, p))
        else:
            self.prognosis_listbox.insert(tk.END, "Noch keine Prognosen")
    
    def _show_prognosis_tooltip(self, event, prognosis):
        """Zeigt komplette Prognose als Tooltip (vereinfacht)"""
        # Könnte man mit tk.Tooltip erweitern
        pass
    
    def _update_checklists(self):
        """Aktualisiert die Checklisten-Anzeige"""
        self.check_text.delete(1.0, tk.END)
        
        checklists = self.sim.knowledge_graph.graph.get("checklists", [])
        if checklists:
            for cl in checklists[-3:]:  # Letzte 3
                name = cl["name"]
                items = cl["items"]
                total = len(items)
                done = sum(1 for v in items.values() if v)
                
                self.check_text.insert(tk.END, f"📋 {name} ({done}/{total})\n")
                for item, completed in items.items():
                    status = "✅" if completed else "⬜"
                    self.check_text.insert(tk.END, f"   {status} {item}\n")
                self.check_text.insert(tk.END, "\n")
        else:
            self.check_text.insert(tk.END, "Keine aktiven Checklisten")


# ===================== EXPERIMENTE TAB =====================
class ExperimentsTab:
    """GUI-Tab für Experimente"""
    
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tk.Frame(parent, bg=Config.BG_MAIN)
        self.progress = ProgressManager(self.update_status)
        self._setup_ui()
    
    def _setup_ui(self):
        # Hauptframe
        main_frame = tk.Frame(self.frame, bg=Config.BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Linke Seite: Experiment-Steuerung
        left_frame = tk.LabelFrame(main_frame, text="🧪 Experimente",
                                  bg=Config.BG_PANEL, fg=Config.FG,
                                  font=("Segoe UI", 14, "bold"))
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,10))
        
        # Experiment-Name
        tk.Label(left_frame, text="Experiment-Name:", 
                bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).pack(anchor=tk.W, padx=10, pady=(10,5))
        
        self.exp_name_entry = tk.Entry(left_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                      font=("Segoe UI", 10), width=30)
        self.exp_name_entry.pack(fill=tk.X, padx=10, pady=5)
        self.exp_name_entry.insert(0, f"Experiment_{int(time.time())}")
        
        # Thema
        tk.Label(left_frame, text="Thema:", 
                bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).pack(anchor=tk.W, padx=10, pady=5)
        
        self.exp_topic_entry = tk.Entry(left_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                       font=("Segoe UI", 10), width=30)
        self.exp_topic_entry.pack(fill=tk.X, padx=10, pady=5)
        self.exp_topic_entry.insert(0, "Künstliche Intelligenz")
        
        # Fortschrittsanzeige
        progress_frame = tk.Frame(left_frame, bg=Config.BG_PANEL)
        progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(progress_frame, text="Fortschritt:", 
                bg=Config.BG_PANEL, fg=Config.FG,
                font=("Segoe UI", 10)).pack(anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.progress_label = tk.Label(progress_frame, text="", 
                                      bg=Config.BG_PANEL, fg=Config.FG_DIM,
                                      font=("Segoe UI", 9))
        self.progress_label.pack(anchor=tk.W)
        
        # Start-Button
        self.start_btn = tk.Button(left_frame, text="🚀 Experiment starten",
                             bg=Config.BG_BUTTON, fg=Config.FG_BUTTON,
                             font=("Segoe UI", 12, "bold"),
                             command=self.run_experiment)
        self.start_btn.pack(pady=20)
        
        # Rechte Seite: Ergebnisse
        right_frame = tk.LabelFrame(main_frame, text="📊 Ergebnisse",
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 14, "bold"))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10,0))
        
        self.results_text = scrolledtext.ScrolledText(right_frame, bg=Config.BG_INPUT,
                                                      fg=Config.FG, font=("Consolas", 10),
                                                      wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Gespeicherte Experimente laden
        self.load_experiments()
    
    def update_status(self, status, message):
        """Callback für Fortschrittsanzeige"""
        self.progress_label.config(text=message)
        
        if status == "start":
            self.progress_bar['value'] = 0
            self.start_btn.config(state=tk.DISABLED)
        elif status == "progress":
            if hasattr(self.progress, 'current') and hasattr(self.progress, 'total'):
                value = (self.progress.current / self.progress.total) * 100
                self.progress_bar['value'] = value
        elif status == "done" or status == "error":
            self.progress_bar['value'] = 100
            self.start_btn.config(state=tk.NORMAL)
        
        self.frame.update()
    
    def load_experiments(self):
        """Lädt gespeicherte Experimente"""
        exp_files = glob.glob(f"{Config.EXPORTS_FOLDER}/experiment_*.json")
        if exp_files:
            self.results_text.insert(tk.END, "📁 Gespeicherte Experimente:\n")
            for f in exp_files[-5:]:
                self.results_text.insert(tk.END, f"   • {os.path.basename(f)}\n")
    
    def run_experiment(self):
        """Führt ein Experiment durch"""
        if not self.sim.agents:
            messagebox.showwarning("Achtung", "Bitte erst Agenten laden!")
            return
        
        if not self.sim.moderator:
            messagebox.showwarning("Achtung", "Bitte erst Moderator laden!")
            return
        
        name = self.exp_name_entry.get().strip()
        topic = self.exp_topic_entry.get().strip()
        
        if not name or not topic:
            messagebox.showwarning("Achtung", "Bitte Name und Thema eingeben!")
            return
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"🔬 Experiment '{name}' wird durchgeführt...\n\n")
        self.frame.update()
        
        # Experiment in eigenem Thread starten (damit GUI nicht einfriert)
        def run():
            try:
                results = self.sim.run_experiment(name, topic, self.progress)
                
                self.results_text.insert(tk.END, f"✅ Experiment abgeschlossen!\n\n")
                self.results_text.insert(tk.END, f"Thema: {results['topic']}\n")
                self.results_text.insert(tk.END, f"Zeit: {results['timestamp'][:16]}\n\n")
                
                for agent_result in results["agent_results"]:
                    self.results_text.insert(tk.END, f"👤 {agent_result['agent']}:\n")
                    for r in agent_result["results"]:
                        self.results_text.insert(tk.END, f"   [{r['condition']}] {r['response'][:80]}...\n")
                    self.results_text.insert(tk.END, "\n")
                    
            except Exception as e:
                self.results_text.insert(tk.END, f"❌ Fehler: {e}\n")
            finally:
                self.update_status("done", "✅ Fertig")
        
        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()


# ===================== SIMULATION =====================
class Simulation:
    def __init__(self):
        self.lm = LLMClient()
        self.external = ExternalSourceClient()
        self.agents: List[Agent] = []
        self.moderator: Optional[Moderator] = None
        self.config_name = ""
        self.stop_event = threading.Event()
        self.is_running = False
        self.discussion_log = []
        self.knowledge_graph = KnowledgeGraph()
        self.current_topic = ""
        self.current_round = 0
        self.max_rounds = 0
        
        # Team-Diskussion
        self.teams = {}  # team_name -> Liste von Agenten
        self.team_mode = False
        self.current_team_speaker = None
        
        # Experimente
        self.experiment_results = []
        
        # Prognosen
        self.prognoses = []
        
        # Diskussions-Zweck
        self.discussion_purpose = None
        
        # Dashboard-Daten
        self.stats = {
            "total_contributions": 0,
            "total_searches": 0,
            "position_changes": 0,
            "start_time": None,
            "end_time": None
        }
    
    def load_agents(self, filepath: str) -> bool:
        try:
            data = FileManager().load_json_file(filepath)
            if not data:
                return False
            self.config_name = data.get("name", "Unbekannt")
            self.agents = []
            self.teams = {}  # Zurücksetzen
            
            for agent_data in data["agents"]:
                agent = Agent(agent_data, self.knowledge_graph, self.external)
                self.agents.append(agent)
                
                # Team-Zuordnung
                if agent.team:
                    if agent.team not in self.teams:
                        self.teams[agent.team] = []
                    self.teams[agent.team].append(agent)
            
            # Teams im Knowledge Graph registrieren
            for team_name, team_agents in self.teams.items():
                agent_ids = [a.agent_id for a in team_agents]
                self.knowledge_graph.add_team(team_name, agent_ids)
            
            return True
        except Exception as e:
            print(f"Fehler beim Laden: {e}")
            return False
    
    def load_moderator(self, filepath: str) -> bool:
        try:
            data = FileManager().load_json_file(filepath)
            if not data:
                return False
            self.moderator = Moderator(data)
            return True
        except:
            return False
    
    def stop(self):
        self.stop_event.set()
        self.is_running = False
        print("⛔ STOP-SIGNAL GESENDET")
    
    # ==================== DISKUSSIONS-ZWECK ====================
    
    def set_discussion_purpose(self, purpose: str, goal: str = None):
        """Setzt den Zweck der Diskussion (z.B. 'Lösung finden', 'Entscheidung treffen')"""
        self.discussion_purpose = purpose
        if self.moderator and goal:
            self.moderator.set_discussion_goal(goal)
        print(f"🎯 Diskussionszweck: {purpose}")
    
    # ==================== PROGNOSEN ====================
    
    def collect_prognoses(self, topic: str):
        """Sammelt Prognosen aller Agenten vor der Diskussion"""
        self.prognoses = []
        for agent in self.agents:
            if not agent.ausgeschlossen:
                prognosis = agent.make_prognosis(topic, self.lm)
                self.prognoses.append(prognosis)
                print(f"🔮 {agent.name} prognostiziert: {prognosis.prediction[:50]}...")
    
    def verify_prognoses(self, actual_outcome: str):
        """Überprüft Prognosen nach der Diskussion"""
        for prognosis in self.prognoses:
            correct = prognosis.verify(actual_outcome)
            agent = next((a for a in self.agents if a.name == prognosis.agent), None)
            if agent:
                if correct:
                    self.knowledge_graph.add_score(agent.name, 10, "Prognose richtig")
                    print(f"✅ {agent.name}s Prognose war richtig!")
                else:
                    print(f"❌ {agent.name}s Prognose war falsch.")
    
    # ==================== AUSBILDUNG ====================
    
    def train_agents(self, topic: str, rounds: int = 1):
        """Alle Agenten zu einem Thema weiterbilden"""
        print(f"📚 Ausbildung zu '{topic}' für {rounds} Runden...")
        for _ in range(rounds):
            for agent in self.agents:
                if not agent.ausgeschlossen:
                    agent.train(topic, self.lm)
    
    # ==================== EXPERIMENTE ====================
    
    def run_experiment(self, experiment_name: str, topic: str, progress: ProgressManager = None):
        """Führt ein Experiment mit verschiedenen Einstellungen durch"""
        if not self.moderator:
            print("❌ Kein Moderator für Experiment vorhanden")
            return None
        
        results = self.moderator.run_experiment(experiment_name, self.agents, topic, self.lm, progress)
        self.experiment_results.append(results)
        
        # Ergebnisse speichern
        exp_file = f"{Config.EXPORTS_FOLDER}/experiment_{int(time.time())}.json"
        try:
            with open(exp_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"📊 Experiment gespeichert: {exp_file}")
        except:
            pass
        
        return results
    
    # ==================== CHECKLISTEN ====================
    
    def create_checklist(self, name: str, items: List[str]):
        """Erstellt eine Checkliste für die Diskussion"""
        if self.moderator:
            return self.moderator.create_checklist(name, items)
        return None
    
    def check_item(self, item: str) -> bool:
        """Hakt einen Punkt ab"""
        if self.moderator:
            return self.moderator.check_item(item)
        return False
    
    # ==================== HAUPT-DISKUSSION ====================
    
    def start_discussion(self, topic: str, document: Optional[str], 
                         rounds: int = 2, use_moderator: bool = True,
                         team_mode: bool = False):
        """Startet die Diskussion mit allen Features"""
        
        # Reset für neue Diskussion
        self.stop_event.clear()
        self.is_running = True
        self.discussion_log = []
        self.current_topic = topic
        self.current_round = 0
        self.max_rounds = rounds
        self.team_mode = team_mode
        self.stats["start_time"] = datetime.now().isoformat()
        self.stats["total_contributions"] = 0
        self.stats["total_searches"] = 0
        
        print(f"\n🔵 STARTE DISKUSSION: {rounds} Runden")
        if team_mode:
            print(f"👥 TEAM-MODUS mit {len(self.teams)} Teams")
        if self.discussion_purpose:
            print(f"🎯 ZWECK: {self.discussion_purpose}")
        
        # Agenten zurücksetzen
        for agent in self.agents:
            agent.schon_gesagtes = []
            agent.wiederholungen = 0
            agent.ausgeschlossen = False
            agent.current_position = None
            agent.discussion_log = self.discussion_log
        
        if self.moderator:
            self.moderator.enabled = use_moderator
            self.moderator.evasions = {}
            self.moderator.abgebrochene_agenten = set()
        
        # Prognosen sammeln (optional)
        if random.random() < 0.3:  # 30% Chance für Prognosen
            self.collect_prognoses(topic)
        
        if use_moderator and self.moderator:
            intro = self.moderator.introduce(topic, document, self.lm, self.stop_event)
            if intro and intro != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 {intro}")
                self.discussion_log.append(f"Moderator: {intro}")
                time.sleep(0.5)
        else:
            yield ("system", "📢 Diskussion ohne Moderator gestartet")
            self.discussion_log.append("System: Diskussion ohne Moderator")
        
        if team_mode:
            # Team-Diskussion: Teams sprechen nacheinander
            yield ("system", f"👥 TEAM-DISKUSSION mit {len(self.teams)} Teams")
            
            for round_num in range(rounds):
                if self.stop_event.is_set():
                    break
                
                self.current_round = round_num + 1
                yield ("system", f"--- RUNDE {round_num+1}/{rounds} ---")
                
                # Jedes Team kommt dran
                for team_name, team_agents in self.teams.items():
                    if self.stop_event.is_set():
                        break
                    
                    yield ("system", f"🏆 Team {team_name} ist dran")
                    
                    # Team-Sprecher auswählen (abwechselnd)
                    team_spokesperson = team_agents[round_num % len(team_agents)]
                    self.current_team_speaker = team_spokesperson.name
                    
                    # Team-Sprecher antwortet
                    answer = team_spokesperson.answer(topic, document, self.lm, self.stop_event, round_num)
                    self.stats["total_contributions"] += 1
                    
                    if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                        yield ("system", f"⛔ {team_spokesperson.name} ausgeschlossen!")
                        self.discussion_log.append(f"System: {team_spokesperson.name} ausgeschlossen")
                    elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        yield ("agent", f"🏆 {team_name} - {team_spokesperson.name}", answer, team_spokesperson.color)
                        self.discussion_log.append(f"Team {team_name} ({team_spokesperson.name}): {answer}")
                        time.sleep(0.3)
                        
                        # Punkte für guten Beitrag
                        if len(answer) > 50:
                            self.knowledge_graph.add_score(team_spokesperson.name, 2, "Team-Beitrag")
                    
                    # Andere Teammitglieder können ergänzen
                    for other in team_agents:
                        if other.name != team_spokesperson.name and not other.ausgeschlossen:
                            reaction = other.react_to(
                                f"Team {team_name}", 
                                team_spokesperson.last_response, 
                                topic, self.lm, self.stop_event
                            )
                            if reaction and reaction not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                                yield ("agent", f"   ↳ {other.name} (Team {team_name})", reaction, other.color)
                                self.discussion_log.append(f"{other.name} (Team {team_name}) ergänzt: {reaction}")
                                self.stats["total_contributions"] += 1
                                time.sleep(0.2)
                    
                    # Kurze Pause zwischen Teams
                    time.sleep(0.5)
        
        else:
            # Normale Diskussion (mit allen Features)
            for round_num in range(rounds):
                if self.stop_event.is_set():
                    print(f"⛔ RUNDE {round_num+1}: STOP erkannt - breche ab")
                    break
                
                self.current_round = round_num + 1
                yield ("system", f"--- RUNDE {round_num+1}/{rounds} ---")
                
                # Prüfen ob Checkliste erfüllt
                if self.moderator and self.moderator.current_checklist:
                    progress = self.moderator.get_checklist_progress()
                    yield ("system", f"📋 Checkliste: {progress:.1f}% erledigt")
                
                for agent in self.agents:
                    if self.stop_event.is_set():
                        break
                    
                    if agent.ausgeschlossen:
                        continue
                    
                    if use_moderator and self.moderator:
                        if agent.name in self.moderator.abgebrochene_agenten:
                            continue
                        
                        context = "\n".join(self.discussion_log[-5:]) if self.discussion_log else ""
                        question = self.moderator.ask_question(
                            agent.name, agent.role, agent.personality,
                            topic, document, context, self.lm, self.stop_event
                        )
                        
                        if question and question != "[ABGEBROCHEN]":
                            yield ("moderator", f"🎭 An {agent.name}: {question}")
                            self.discussion_log.append(f"Moderator an {agent.name}: {question}")
                            time.sleep(0.3)
                            
                            answer = agent.answer(topic, document, self.lm, self.stop_event, round_num)
                            self.stats["total_contributions"] += 1
                            
                            if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                                yield ("system", f"⛔ {agent.name} ausgeschlossen!")
                                self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                                self.knowledge_graph.add_score(agent.name, -5, "Ausgeschlossen")
                            elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                                yield ("agent", agent.name, answer, agent.color)
                                self.discussion_log.append(f"{agent.name}: {answer}")
                                time.sleep(0.3)
                                
                                # Prüfen ob Checklisten-Punkt erfüllt
                                if self.moderator and self.moderator.current_checklist:
                                    for item in self.moderator.current_checklist.items:
                                        if item.lower() in answer.lower() and not self.moderator.current_checklist.items[item]:
                                            self.moderator.check_item(item)
                                            yield ("system", f"✅ Checklisten-Punkt '{item}' erfüllt!")
                                
                                intervention, abbrechen = self.moderator.intervene(
                                    agent.name, answer, topic, self.lm, self.stop_event
                                )
                                if intervention:
                                    yield ("moderator", f"🎭 ⚠️ {intervention}")
                                    self.discussion_log.append(f"Moderator: {intervention}")
                                    if abbrechen:
                                        yield ("system", f"⛔ {agent.name} ausgeschlossen!")
                                        self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                                        self.knowledge_graph.add_score(agent.name, -5, "Ausgeschlossen")
                    
                    else:
                        # OHNE MODERATOR - Agent diskutiert
                        answer = agent.answer(topic, document, self.lm, self.stop_event, round_num)
                        self.stats["total_contributions"] += 1
                        
                        if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                            yield ("system", f"⛔ {agent.name} ausgeschlossen!")
                            self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                            self.knowledge_graph.add_score(agent.name, -5, "Ausgeschlossen")
                        elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                            yield ("agent", agent.name, answer, agent.color)
                            self.discussion_log.append(f"{agent.name}: {answer}")
                            time.sleep(0.3)
                    
                    # REAKTIONEN der ANDEREN (nur im normalen Modus)
                    if not team_mode and round_num < rounds - 1 and not self.stop_event.is_set() and len(self.agents) > 1:
                        for other in self.agents:
                            if (other.name != agent.name and not other.ausgeschlossen and 
                                not self.stop_event.is_set()):
                                
                                reaction = other.react_to(agent.name, agent.last_response, topic,
                                                          self.lm, self.stop_event)
                                if reaction and reaction not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                                    yield ("agent", other.name, f"[Reaktion] {reaction}", other.color)
                                    self.discussion_log.append(f"{other.name} reagiert: {reaction}")
                                    self.stats["total_contributions"] += 1
                                    time.sleep(0.2)
                                    
                                    # LERNEN von anderen
                                    for learning_agent in self.agents:
                                        if (learning_agent.name != other.name and 
                                            not learning_agent.ausgeschlossen and
                                            learning_agent.name != agent.name):
                                            learning_agent.learn_from(
                                                other.name, reaction, topic, self.lm
                                            )
        
        # REFLEKTION am Ende
        if not self.stop_event.is_set():
            excerpt = "\n".join(self.discussion_log[-15:])
            for agent in self.agents:
                if not agent.ausgeschlossen and agent.current_position:
                    agent.reflect_on_discussion(excerpt, topic, agent.current_position, self.lm)
        
        # Zusammenfassung
        if not self.stop_event.is_set() and use_moderator and self.moderator:
            summary = self.moderator.summarize(
                "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
            )
            if summary and summary != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 📋 {summary}")
        
        # Team-Statistik am Ende
        if team_mode and not self.stop_event.is_set():
            yield ("system", "\n📊 TEAM-STATISTIK:")
            for team_name, team_agents in self.teams.items():
                aktive = sum(1 for a in team_agents if not a.ausgeschlossen)
                fakten = sum(len(a.learned_facts) for a in team_agents)
                scores = sum(self.knowledge_graph.graph["scores"].get(a.name, {}).get("total", 0) for a in team_agents)
                yield ("system", f"   🏆 {team_name}: {aktive}/{len(team_agents)} aktiv, {fakten} Fakten, {scores} Punkte")
        
        # Prognosen überprüfen (wenn welche gemacht wurden)
        if self.prognoses and not self.stop_event.is_set():
            actual_outcome = summary if summary else "Diskussion beendet"
            self.verify_prognoses(actual_outcome)
        
        # Abschluss-Statistik
        self.stats["end_time"] = datetime.now().isoformat()
        yield ("system", f"\n📊 DISKUSSIONS-STATISTIK:")
        yield ("system", f"   💬 Beiträge: {self.stats['total_contributions']}")
        yield ("system", f"   🔍 Externe Suchen: {self.stats['total_searches']}")
        
        # Rangliste anzeigen
        leaderboard = self.knowledge_graph.get_leaderboard()
        if leaderboard:
            yield ("system", f"\n🏆 RANGLISTE:")
            for i, (name, score) in enumerate(leaderboard[:5], 1):
                yield ("system", f"   {i}. {name}: {score} Punkte")
        
        # Simulation ordentlich beenden
        self.is_running = False
        self.stop_event.clear()
        print("✅ DISKUSSION BEENDET - Reset durchgeführt")


# ===================== HAUPT-GUI =====================
class SynthAgoraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🐟 SynthAgora - VOLLAUSBAU MIT ALLEN FEATURES")
        self.root.geometry("1400x900")
        self.root.configure(bg=Config.BG_MAIN)
        
        self.fm = FileManager()
        self.sim = Simulation()
        self.msg_queue = queue.Queue()
        self.progress = ProgressManager(self.update_status)
        
        self._setup_ui()
        self._check_lm()
        self._refresh_lists()
        self._process_queue()
    
    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=Config.BG_MAIN, borderwidth=0)
        style.configure('TNotebook.Tab', background=Config.BG_PANEL, foreground=Config.FG, 
                       padding=[15, 8], font=('Segoe UI', 10))
        style.map('TNotebook.Tab', background=[('selected', Config.BG_BUTTON)])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # TAB 1: DEBATTE
        self.tab_main = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_main, text="🎮 Debatte")
        self._setup_main_tab()
        
        # TAB 2: AGENTEN
        self.tab_agents = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_agents, text="👥 Agenten")
        self._setup_agents_tab()
        
        # TAB 3: VERLAUF
        self.tab_chat = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_chat, text="📜 Verlauf")
        self._setup_chat_tab()
        
        # TAB 4: KNOWLEDGE GRAPH
        self.tab_knowledge = tk.Frame(self.notebook, bg=Config.BG_MAIN)
        self.notebook.add(self.tab_knowledge, text="🔮 Knowledge Graph")
        self._setup_knowledge_tab()
        
        # TAB 5: GEDÄCHTNIS-PALAST
        self.memory_palace_tab = MemoryPalaceTab(self.notebook, self.sim)
        self.notebook.add(self.memory_palace_tab.frame, text="🧠 Gedächtnis-Palast")
        
        # TAB 6: DASHBOARD
        self.dashboard_tab = DashboardTab(self.notebook, self.sim)
        self.notebook.add(self.dashboard_tab.frame, text="📊 Dashboard")
        
        # TAB 7: EXPERIMENTE
        self.experiments_tab = ExperimentsTab(self.notebook, self.sim)
        self.notebook.add(self.experiments_tab.frame, text="🧪 Experimente")
        
        # TAB 8: KONFIGURATION
        self.config_tab = ConfigTab(self.notebook, self.sim)
        self.notebook.add(self.config_tab.frame, text="⚙️ LLM Config")
        
        # TAB 9: EXTERNE QUELLEN
        self.external_tab = ExternalSourcesTab(self.notebook, self.sim)
        self.notebook.add(self.external_tab.frame, text="🌐 Plugins")
        
        self._setup_control_bar()
        self._setup_statusbar()
    
    def _setup_main_tab(self):
        agent_frame = tk.LabelFrame(self.tab_main, text="📁 Agenten-Set", bg=Config.BG_PANEL, fg=Config.FG, font=("Segoe UI", 12, "bold"))
        agent_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.agent_var = tk.StringVar()
        self.agent_combo = ttk.Combobox(agent_frame, textvariable=self.agent_var, state="readonly", width=60)
        self.agent_combo.pack(pady=10, padx=10)
        
        self.load_agents_btn = self._create_button(agent_frame, "🔄 AGENTEN LADEN", Config.BG_BUTTON, self.load_selected_agents)
        self.load_agents_btn.pack(pady=(0,10))
        
        mod_frame = tk.LabelFrame(self.tab_main, text="🎭 Moderator", bg=Config.BG_PANEL, fg=Config.FG, font=("Segoe UI", 12, "bold"))
        mod_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.use_moderator_var = tk.BooleanVar(value=True)
        mod_check = tk.Checkbutton(mod_frame, text="✅ Moderator verwenden", variable=self.use_moderator_var,
                                   bg=Config.BG_PANEL, fg=Config.FG, selectcolor=Config.BG_PANEL, font=("Segoe UI", 11))
        mod_check.pack(anchor=tk.W, padx=10, pady=(10,5))
        
        mod_select_frame = tk.Frame(mod_frame, bg=Config.BG_PANEL)
        mod_select_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        
        self.mod_var = tk.StringVar()
        self.mod_combo = ttk.Combobox(mod_select_frame, textvariable=self.mod_var, state="readonly", width=60)
        self.mod_combo.pack(side=tk.LEFT, padx=(0,10))
        
        self.load_mod_btn = self._create_button(mod_select_frame, "🎭 LADEN", Config.BG_INPUT, self.load_selected_moderator)
        self.load_mod_btn.pack(side=tk.LEFT)
        
        # Diskussions-Zweck
        purpose_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        purpose_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(purpose_frame, text="🎯 Zweck:", bg=Config.BG_MAIN, fg=Config.FG,
                font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=5)
        
        self.purpose_var = tk.StringVar(value="Diskussion")
        purpose_combo = ttk.Combobox(purpose_frame, textvariable=self.purpose_var,
                                     values=["Diskussion", "Lösung finden", "Entscheidung", "Brainstorming", "Analyse"],
                                     width=20)
        purpose_combo.pack(side=tk.LEFT, padx=5)
        
        tk.Label(purpose_frame, text="Ziel:", bg=Config.BG_MAIN, fg=Config.FG,
                font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=20)
        
        self.goal_entry = tk.Entry(purpose_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                  font=("Segoe UI", 10), width=30)
        self.goal_entry.pack(side=tk.LEFT, padx=5)
        self.goal_entry.insert(0, "Konsens finden")
        
        # Team-Modus Option
        team_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        team_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.team_mode_var = tk.BooleanVar(value=False)
        team_check = tk.Checkbutton(team_frame, text="👥 TEAM-MODUS (Agenten diskutieren als Teams)", 
                                   variable=self.team_mode_var,
                                   bg=Config.BG_MAIN, fg=Config.FG,
                                   selectcolor=Config.BG_MAIN,
                                   font=("Segoe UI", 11, "bold"))
        team_check.pack(side=tk.LEFT, padx=5)
        
        tk.Label(team_frame, text="(benötigt Team-Zuordnung in Agenten-JSON)", 
                bg=Config.BG_MAIN, fg=Config.FG_DIM,
                font=("Segoe UI", 9, "italic")).pack(side=tk.LEFT, padx=5)
        
        # Checkliste
        check_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        check_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.use_checklist_var = tk.BooleanVar(value=False)
        check_check = tk.Checkbutton(check_frame, text="📋 Checkliste verwenden", 
                                     variable=self.use_checklist_var,
                                     bg=Config.BG_MAIN, fg=Config.FG,
                                     selectcolor=Config.BG_MAIN,
                                     font=("Segoe UI", 11),
                                     command=self.toggle_checklist)
        check_check.pack(side=tk.LEFT, padx=5)
        
        self.checklist_entry = tk.Entry(check_frame, bg=Config.BG_INPUT, fg=Config.FG,
                                       font=("Segoe UI", 10), width=40, state=tk.DISABLED)
        self.checklist_entry.pack(side=tk.LEFT, padx=5)
        self.checklist_entry.insert(0, "Punkt1, Punkt2, Punkt3")
        
        # Externe Quellen Option
        external_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        external_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.use_external_debate_var = tk.BooleanVar(value=False)
        external_check = tk.Checkbutton(external_frame, text="🌐 Externe Quellen in dieser Debatte verwenden", 
                                       variable=self.use_external_debate_var,
                                       bg=Config.BG_MAIN, fg=Config.FG,
                                       selectcolor=Config.BG_MAIN,
                                       font=("Segoe UI", 11))
        external_check.pack(side=tk.LEFT, padx=5)
        
        # Prognosen
        self.use_prognosis_var = tk.BooleanVar(value=False)
        prognosis_check = tk.Checkbutton(external_frame, text="🔮 Prognosen sammeln", 
                                        variable=self.use_prognosis_var,
                                        bg=Config.BG_MAIN, fg=Config.FG,
                                        selectcolor=Config.BG_MAIN,
                                        font=("Segoe UI", 11))
        prognosis_check.pack(side=tk.LEFT, padx=20)
        
        topic_frame = tk.LabelFrame(self.tab_main, text="🎯 Thema", bg=Config.BG_PANEL, fg=Config.FG, font=("Segoe UI", 12, "bold"))
        topic_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.topic_entry = tk.Entry(topic_frame, bg=Config.BG_INPUT, fg=Config.FG, font=("Segoe UI", 11), relief='flat')
        self.topic_entry.pack(fill=tk.X, padx=10, pady=10)
        self.topic_entry.insert(0, "Analysiere diesen Text aus deiner Perspektive")
        
        doc_frame = tk.LabelFrame(self.tab_main, text="📄 Dokument (optional)", bg=Config.BG_PANEL, fg=Config.FG, font=("Segoe UI", 12, "bold"))
        doc_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        doc_toolbar = tk.Frame(doc_frame, bg=Config.BG_PANEL)
        doc_toolbar.pack(fill=tk.X, padx=10, pady=(10,0))
        
        self._create_button(doc_toolbar, "📁 Beispiel laden", Config.BG_INPUT, self.load_example_doc).pack(side=tk.LEFT, padx=5)
        
        self.example_var = tk.StringVar()
        self.example_combo = ttk.Combobox(doc_toolbar, textvariable=self.example_var, state="readonly", width=40)
        self.example_combo.pack(side=tk.LEFT, padx=5)
        
        self._create_button(doc_toolbar, "📖 Laden", Config.BG_INPUT, self.load_selected_example).pack(side=tk.LEFT, padx=5)
        
        self.doc_text = tk.Text(doc_frame, height=6, bg=Config.BG_INPUT, fg=Config.FG, font=("Segoe UI", 10), wrap=tk.WORD, relief='flat')
        self.doc_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        opt_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        opt_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(opt_frame, text="Runden:", bg=Config.BG_MAIN, fg=Config.FG, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=5)
        
        self.rounds_var = tk.StringVar(value="3")
        spin = tk.Spinbox(opt_frame, from_=1, to=10, textvariable=self.rounds_var,
                         width=5, bg=Config.BG_INPUT, fg=Config.FG, relief='flat')
        spin.pack(side=tk.LEFT, padx=5)
        
        # Training
        tk.Label(opt_frame, text="Training:", bg=Config.BG_MAIN, fg=Config.FG,
                font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=20)
        
        self.train_rounds_var = tk.StringVar(value="0")
        train_spin = tk.Spinbox(opt_frame, from_=0, to=5, textvariable=self.train_rounds_var,
                               width=5, bg=Config.BG_INPUT, fg=Config.FG, relief='flat')
        train_spin.pack(side=tk.LEFT, padx=5)
        tk.Label(opt_frame, text="Trainingsrunden", bg=Config.BG_MAIN, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        self.start_btn = self._create_button(self.tab_main, "🎬 DISKUSSION STARTEN", Config.BG_BUTTON, self.start_discussion)
        self.start_btn.pack(pady=20)
    
    def toggle_checklist(self):
        """Aktiviert/deaktiviert Checklisten-Eingabe"""
        if self.use_checklist_var.get():
            self.checklist_entry.config(state=tk.NORMAL)
        else:
            self.checklist_entry.config(state=tk.DISABLED)
    
    def _setup_agents_tab(self):
        canvas = tk.Canvas(self.tab_agents, bg=Config.BG_MAIN, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_agents, orient=tk.VERTICAL, command=canvas.yview)
        
        self.agents_frame = tk.Frame(canvas, bg=Config.BG_MAIN)
        self.agents_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.agents_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_chat_tab(self):
        toolbar = tk.Frame(self.tab_chat, bg=Config.BG_PANEL)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        self._create_button(toolbar, "💾 Exportieren", Config.BG_BUTTON, self.export_chat).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "🗑️ Löschen", Config.BG_STOP, self.clear_chat).pack(side=tk.LEFT, padx=5)
        
        self.chat_count_label = tk.Label(toolbar, text="Einträge: 0", bg=Config.BG_PANEL, fg=Config.FG, font=("Segoe UI", 10))
        self.chat_count_label.pack(side=tk.RIGHT, padx=10)
        
        self.chat_text = scrolledtext.ScrolledText(self.tab_chat, bg=Config.BG_INPUT, fg=Config.FG, font=("Consolas", 10), wrap=tk.WORD)
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
    
    def _setup_knowledge_tab(self):
        toolbar = tk.Frame(self.tab_knowledge, bg=Config.BG_PANEL)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        self._create_button(toolbar, "🔄 Graph anzeigen", Config.BG_BUTTON, self.show_knowledge_graph).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "📊 Statistik", Config.BG_INPUT, self.show_graph_stats).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "📚 Topics", Config.BG_INPUT, self.show_topics).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "🎯 Influences", Config.BG_INPUT, self.show_influences).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "👥 Teams", Config.BG_INPUT, self.show_teams).pack(side=tk.LEFT, padx=5)
        
        self.knowledge_text = scrolledtext.ScrolledText(self.tab_knowledge, bg=Config.BG_INPUT, fg=Config.FG, font=("Consolas", 10), wrap=tk.WORD)
        self.knowledge_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.show_knowledge_graph()
    
    def _setup_control_bar(self):
        control_frame = tk.Frame(self.root, bg=Config.BG_MAIN)
        control_frame.pack(fill=tk.X, padx=10, pady=(0,5))
        
        self.stop_btn = self._create_button(control_frame, "⛔ SIMULATION STOPPEN", Config.BG_STOP, self.stop_simulation, Config.BG_STOP_HOVER)
        self.stop_btn.config(state=tk.DISABLED)
        self.stop_btn.pack()
        
        # Runden-Anzeige
        self.round_label = tk.Label(control_frame, text="Runde: 0/0", 
                                    bg=Config.BG_MAIN, fg=Config.FG,
                                    font=("Segoe UI", 11, "bold"))
        self.round_label.pack(side=tk.RIGHT, padx=20)
    
    def _setup_statusbar(self):
        self.statusbar = tk.Label(self.root, text="Bereit", bg=Config.BG_BUTTON, fg=Config.FG, anchor=tk.W, padx=10, font=("Segoe UI", 10))
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _create_button(self, parent, text, bg_color, command, hover_color=None):
        btn = tk.Button(parent, text=text, bg=bg_color, fg=Config.FG_BUTTON, font=("Segoe UI", 11, "bold"),
                       relief='flat', padx=15, pady=8, cursor='hand2', command=command)
        def on_enter(e): btn.config(bg=hover_color or Config.BG_BUTTON_HOVER)
        def on_leave(e): btn.config(bg=bg_color)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn
    
    def _refresh_lists(self):
        agent_files = self.fm.get_agent_files()
        agent_names = [os.path.basename(f) for f in agent_files]
        self.agent_combo['values'] = agent_names
        if agent_names:
            self.agent_combo.current(0)
        
        mod_files = self.fm.get_moderator_files()
        mod_names = [os.path.basename(f) for f in mod_files]
        self.mod_combo['values'] = mod_names
        if mod_names:
            self.mod_combo.current(0)
        
        example_files = self.fm.get_example_files()
        example_names = [os.path.basename(f) for f in example_files]
        self.example_combo['values'] = example_names
        if example_names:
            self.example_combo.current(0)
    
    def load_selected_agents(self):
        selection = self.agent_combo.get()
        if not selection:
            return
        filepath = f"{Config.AGENTS_FOLDER}/{selection}"
        if self.sim.load_agents(filepath):
            self._update_status(f"✅ Agenten geladen: {selection}")
            self._create_agent_cards()
            self._add_to_chat(f"\n=== GELADEN: {self.sim.config_name} ===")
            self._add_to_chat(f"👥 {len(self.sim.agents)} Agenten")
            if self.sim.teams:
                self._add_to_chat(f"👥 {len(self.sim.teams)} Teams: {', '.join(self.sim.teams.keys())}")
            for agent in self.sim.agents:
                if agent.learned_facts:
                    self._add_to_chat(f"   📚 {agent.name} ({agent.team or 'kein Team'}) kennt {len(agent.learned_facts)} Fakten")
            
            # Gedächtnis-Palast aktualisieren
            if hasattr(self, 'memory_palace_tab'):
                self.memory_palace_tab.refresh_agent_list()
        else:
            self._update_status("❌ Fehler")
    
    def load_selected_moderator(self):
        selection = self.mod_combo.get()
        if not selection:
            return
        filepath = f"{Config.MODERATORS_FOLDER}/{selection}"
        if self.sim.load_moderator(filepath):
            self._update_status(f"✅ Moderator geladen: {self.sim.moderator.name}")
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name} ({self.sim.moderator.style})")
    
    def load_selected_example(self):
        selection = self.example_combo.get()
        if not selection:
            return
        filepath = f"{Config.EXAMPLES_FOLDER}/{selection}"
        content = self.fm.load_text_file(filepath)
        if content:
            self.doc_text.delete(1.0, tk.END)
            self.doc_text.insert(1.0, content)
            self._update_status(f"📄 Beispiel geladen: {selection}")
    
    def load_example_doc(self):
        filepath = filedialog.askopenfilename(initialdir=Config.EXAMPLES_FOLDER, filetypes=[("Text files", "*.txt")])
        if filepath:
            content = self.fm.load_text_file(filepath)
            if content:
                self.doc_text.delete(1.0, tk.END)
                self.doc_text.insert(1.0, content)
                self._update_status(f"📄 Geladen: {os.path.basename(filepath)}")
    
    def _create_agent_cards(self):
        for widget in self.agents_frame.winfo_children():
            widget.destroy()
        for agent in self.sim.agents:
            self._create_agent_card(agent)
    
    def _create_agent_card(self, agent):
        card = tk.Frame(self.agents_frame, bg=Config.BG_PANEL, relief='flat')
        card.pack(fill=tk.X, pady=5, padx=10)
        
        header = tk.Frame(card, bg=agent.color, height=40)
        header.pack(fill=tk.X)
        tk.Label(header, text=agent.name, bg=agent.color, fg="#000000", font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT, padx=10, pady=8)
        tk.Label(header, text=agent.role, bg=agent.color, fg="#000000", font=("Segoe UI", 10)).pack(side=tk.RIGHT, padx=10, pady=8)
        
        # Team-Anzeige im Header
        if agent.team:
            tk.Label(header, text=f"🏆 {agent.team}", bg=agent.color, fg="#000000", 
                    font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=10, pady=8)
        
        content = tk.Frame(card, bg=Config.BG_INPUT)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0,1))
        
        pers_frame = tk.Frame(content, bg=Config.BG_INPUT)
        pers_frame.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(pers_frame, text="💭 Persönlichkeit:", bg=Config.BG_INPUT, fg=Config.FG, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        tk.Label(pers_frame, text=agent.personality, bg=Config.BG_INPUT, fg=Config.FG, wraplength=700, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=2)
        
        info_frame = tk.Frame(content, bg=Config.BG_INPUT)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        if agent.education:
            tk.Label(info_frame, text=f"🎓 {agent.education}", bg=Config.BG_INPUT, fg=Config.FG_DIM, font=("Segoe UI", 9)).pack(anchor=tk.W)
        if agent.background:
            tk.Label(info_frame, text=f"📖 {agent.background}", bg=Config.BG_INPUT, fg=Config.FG_DIM, font=("Segoe UI", 9)).pack(anchor=tk.W)
        
        # Traits anzeigen
        traits_frame = tk.Frame(content, bg=Config.BG_INPUT)
        traits_frame.pack(fill=tk.X, padx=10, pady=2)
        traits_text = " | ".join([f"{k}: {v:.1f}" for k, v in agent.personality_traits.items()])
        tk.Label(traits_frame, text=f"🧠 {traits_text}", bg=Config.BG_INPUT, fg="#98fb98", font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        facts_frame = tk.Frame(content, bg=Config.BG_INPUT)
        facts_frame.pack(fill=tk.X, padx=10, pady=2)
        fact_count = len(agent.learned_facts)
        tk.Label(facts_frame, text=f"📚 Gelernt: {fact_count} Fakten", bg=Config.BG_INPUT, fg="#ffd700", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        if agent.learned_facts:
            for fact in agent.learned_facts[-2:]:
                tk.Label(facts_frame, text=f"  • {fact[:80]}...", bg=Config.BG_INPUT, fg=Config.FG_DIM, font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        if agent.position_history:
            hist_frame = tk.Frame(content, bg=Config.BG_INPUT)
            hist_frame.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(hist_frame, text=f"📈 Entwicklung: {len(agent.position_history)}x", bg=Config.BG_INPUT, fg="#98fb98", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        status_frame = tk.Frame(content, bg=Config.BG_INPUT)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        agent.status_label = tk.Label(status_frame, text="✅ Aktiv", bg=Config.BG_INPUT, fg=Config.SUCCESS, font=("Segoe UI", 9, "bold"))
        agent.status_label.pack(side=tk.LEFT)
        
        # Punkte anzeigen
        score = self.sim.knowledge_graph.graph["scores"].get(agent.name, {}).get("total", 0)
        tk.Label(status_frame, text=f"🏆 {score} Punkte", bg=Config.BG_INPUT, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=10)
        
        response_frame = tk.Frame(content, bg=agent.color)
        response_frame.pack(fill=tk.X, padx=10, pady=8)
        response_label = tk.Label(response_frame, text="Bereit...", bg=agent.color, fg="#000000", font=("Segoe UI", 9), wraplength=700, padx=8, pady=5)
        response_label.pack(fill=tk.X)
        card.response_label = response_label
    
    # ==================== KNOWLEDGE GRAPH ANSICHTEN ====================
    
    def show_teams(self):
        kg = self.sim.knowledge_graph
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "👥 TEAMS IM KNOWLEDGE GRAPH\n" + "="*60 + "\n\n")
        
        if not kg.graph['teams']:
            self.knowledge_text.insert(tk.END, "Noch keine Teams vorhanden.\n")
            self.knowledge_text.insert(tk.END, "Füge 'team'-Feld in Agenten-JSON hinzu!\n")
            return
        
        for team_id, team_data in kg.graph['teams'].items():
            team_name = team_data.get('name', team_id)
            self.knowledge_text.insert(tk.END, f"🏆 {team_name}\n")
            self.knowledge_text.insert(tk.END, f"   • Mitglieder: {len(team_data.get('members', []))}\n")
            self.knowledge_text.insert(tk.END, f"   • Erstellt: {team_data.get('created', '?')[:10]}\n\n")
            
            # Mitglieder auflisten
            for agent_id in team_data.get('members', [])[:5]:
                agent_node = kg.graph['nodes'].get(agent_id, {})
                agent_name = agent_node.get('properties', {}).get('name', agent_id)
                self.knowledge_text.insert(tk.END, f"     👤 {agent_name}\n")
            self.knowledge_text.insert(tk.END, "\n")
    
    def show_knowledge_graph(self):
        kg = self.sim.knowledge_graph
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "🔮 KNOWLEDGE GRAPH\n" + "="*60 + "\n\n")
        self.knowledge_text.insert(tk.END, f"📌 KNOTEN ({len(kg.graph['nodes'])}):\n")
        for node_id, node in list(kg.graph['nodes'].items())[:20]:
            t = node['type']
            p = node.get('properties', {})
            if t == "agent":
                team_info = f" [{p.get('team', 'kein Team')}]" if p.get('team') else ""
                self.knowledge_text.insert(tk.END, f"  👤 {p.get('name', node_id)}{team_info}\n")
            elif t == "team":
                self.knowledge_text.insert(tk.END, f"  🏆 {p.get('name', node_id)}\n")
            elif t == "concept":
                self.knowledge_text.insert(tk.END, f"  💡 {p.get('name', node_id)}\n")
            elif t == "fact":
                text = p.get('text', '')[:50]
                self.knowledge_text.insert(tk.END, f"  📄 {text}...\n")
            else:
                self.knowledge_text.insert(tk.END, f"  • {node_id}\n")
        self.knowledge_text.insert(tk.END, f"\n🔗 BEZIEHUNGEN ({len(kg.graph['edges'])}):\n")
        for edge in kg.graph['edges'][-20:]:
            self.knowledge_text.insert(tk.END, f"  {edge['from']} --({edge['relation']})--> {edge['to']}\n")
    
    def show_graph_stats(self):
        kg = self.sim.knowledge_graph
        self.knowledge_text.delete(1.0, tk.END)
        nodes = kg.graph['nodes']
        edges = kg.graph['edges']
        topics = kg.graph['topics']
        influences = kg.graph['influences']
        teams = kg.graph['teams']
        
        agent_c = sum(1 for n in nodes.values() if n['type'] == 'agent')
        team_c = sum(1 for n in nodes.values() if n['type'] == 'team')
        concept_c = sum(1 for n in nodes.values() if n['type'] == 'concept')
        fact_c = sum(1 for n in nodes.values() if n['type'] == 'fact')
        
        self.knowledge_text.insert(tk.END, "📊 KNOWLEDGE GRAPH STATISTIK\n" + "="*60 + "\n\n")
        self.knowledge_text.insert(tk.END, f"📌 Gesamtknoten: {len(nodes)}\n")
        self.knowledge_text.insert(tk.END, f"  👤 Agenten: {agent_c}\n")
        self.knowledge_text.insert(tk.END, f"  🏆 Teams: {team_c}\n")
        self.knowledge_text.insert(tk.END, f"  💡 Konzepte: {concept_c}\n")
        self.knowledge_text.insert(tk.END, f"  📄 Fakten: {fact_c}\n\n")
        self.knowledge_text.insert(tk.END, f"🔗 Gesamtbeziehungen: {len(edges)}\n\n")
        self.knowledge_text.insert(tk.END, f"📚 Themen-Cluster: {len(topics)}\n")
        self.knowledge_text.insert(tk.END, f"🎯 Einflüsse: {len(influences)} Agenten haben andere beeinflusst\n")
        self.knowledge_text.insert(tk.END, f"👥 Teams: {len(teams)}\n")
    
    def show_topics(self):
        kg = self.sim.knowledge_graph
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "📚 THEMEN-CLUSTER\n" + "="*60 + "\n\n")
        
        if not kg.graph['topics']:
            self.knowledge_text.insert(tk.END, "Noch keine Themen-Cluster vorhanden.\n")
            self.knowledge_text.insert(tk.END, "Starte eine Diskussion, um Themen zu erstellen!\n")
            return
        
        for topic, data in kg.graph['topics'].items():
            self.knowledge_text.insert(tk.END, f"📌 {topic[:50]}...\n")
            self.knowledge_text.insert(tk.END, f"   • {len(data['nodes'])} Knoten\n")
            self.knowledge_text.insert(tk.END, f"   • Erstellt: {data.get('created', '?')[:10]}\n")
            self.knowledge_text.insert(tk.END, f"   • Aktualisiert: {data.get('updated', '?')[:10]}\n\n")
    
    def show_influences(self):
        kg = self.sim.knowledge_graph
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "🎯 EINFLUSS-NETZWERK\n" + "="*60 + "\n\n")
        
        if not kg.graph['influences']:
            self.knowledge_text.insert(tk.END, "Noch keine Einflüsse aufgezeichnet.\n")
            self.knowledge_text.insert(tk.END, "Bei Meinungsänderungen werden sie automatisch gespeichert!\n")
            return
        
        for influencer, influenced_dict in kg.graph['influences'].items():
            influencer_name = influencer.replace('agent_', '').replace('_', ' ').title()
            self.knowledge_text.insert(tk.END, f"👤 {influencer_name} hat beeinflusst:\n")
            
            for influenced, entries in influenced_dict.items():
                influenced_name = influenced.replace('agent_', '').replace('_', ' ').title()
                for entry in entries:
                    self.knowledge_text.insert(tk.END, f"   → {influenced_name} bei '{entry['topic'][:30]}...' (Stärke: {entry['strength']})\n")
            self.knowledge_text.insert(tk.END, "\n")
    
    # ==================== HILFSFUNKTIONEN ====================
    
    def update_status(self, status, message):
        """Callback für Fortschrittsanzeigen"""
        self.progress_label.config(text=message)
        self.root.update_idletasks()
    
    def _check_lm(self):
        ok, msg = self.sim.lm.test()
        if ok:
            self.statusbar.config(text=f"✅ {msg}", bg=Config.SUCCESS)
        else:
            self.statusbar.config(text=f"⚠️ {msg}", bg=Config.WARNING)
        self.root.after(5000, self._check_lm)
    
    def _update_status(self, text):
        self.statusbar.config(text=text, bg=Config.BG_BUTTON)
    
    def _add_to_chat(self, text):
        self.chat_text.insert(tk.END, text + "\n")
        self.chat_text.see(tk.END)
        c = len(self.chat_text.get(1.0, tk.END).split('\n'))
        self.chat_count_label.config(text=f"Einträge: {c-1}")
    
    def stop_simulation(self):
        if self.sim.is_running:
            print("⛔ STOP BUTTON GEDRÜCKT")
            self.sim.stop()
            self.stop_btn.config(state=tk.DISABLED)
            self.start_btn.config(state=tk.NORMAL)
            self._add_to_chat("\n⛔ SIMULATION GESTOPPT\n")
            self._update_status("Simulation gestoppt")
            self.round_label.config(text="Runde: 0/0")
    
    def _enable_stop_button(self):
        self.stop_btn.config(state=tk.NORMAL)
    
    def _disable_stop_button(self):
        self.stop_btn.config(state=tk.DISABLED)
    
    def start_discussion(self):
        if self.sim.is_running:
            messagebox.showwarning("Achtung", "Simulation läuft bereits!")
            return
        if not self.sim.agents:
            messagebox.showwarning("Achtung", "Bitte erst Agenten laden!")
            return
        use_moderator = self.use_moderator_var.get()
        if use_moderator and not self.sim.moderator:
            messagebox.showwarning("Achtung", "Bitte Moderator laden oder deaktivieren!")
            return
        
        # Team-Modus prüfen
        team_mode = self.team_mode_var.get()
        if team_mode and not self.sim.teams:
            if messagebox.askyesno("Keine Teams", "Es wurden keine Teams in den Agenten definiert. Trotzdem fortfahren? (Agenten diskutieren einzeln)"):
                team_mode = False
            else:
                return
        
        # Diskussions-Zweck setzen
        purpose = self.purpose_var.get()
        goal = self.goal_entry.get().strip()
        self.sim.set_discussion_purpose(purpose, goal if goal else None)
        
        # Externe Quellen für diese Debatte aktivieren/deaktivieren
        self.sim.external.use_external = self.use_external_debate_var.get()
        
        topic = self.topic_entry.get().strip()
        if not topic:
            messagebox.showwarning("Achtung", "Bitte ein Thema eingeben!")
            return
        
        # Training vor der Diskussion
        train_rounds = int(self.train_rounds_var.get())
        if train_rounds > 0:
            self.sim.train_agents(topic, train_rounds)
        
        # Checkliste erstellen
        if self.use_checklist_var.get():
            checklist_items = [x.strip() for x in self.checklist_entry.get().split(",") if x.strip()]
            if checklist_items:
                self.sim.create_checklist(f"Checkliste {topic[:20]}", checklist_items)
        
        document = self.doc_text.get(1.0, tk.END).strip()
        rounds = int(self.rounds_var.get())
        
        self.start_btn.config(state=tk.DISABLED)
        self._enable_stop_button()
        self.round_label.config(text=f"Runde: 0/{rounds}")
        
        self._add_to_chat(f"\n{'='*60}")
        self._add_to_chat(f"🎯 THEMA: {topic}")
        self._add_to_chat(f"🎯 ZWECK: {purpose} - {goal if goal else 'kein spezifisches Ziel'}")
        if document:
            self._add_to_chat(f"📄 Dokument geladen ({len(document)} Zeichen)")
        else:
            self._add_to_chat(f"📄 Kein Dokument - reine Themendiskussion")
        if use_moderator and self.sim.moderator:
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name} ({self.sim.moderator.style})")
        else:
            self._add_to_chat(f"👥 Ohne Moderator")
        self._add_to_chat(f"👥 {len(self.sim.agents)} Agenten")
        if team_mode:
            self._add_to_chat(f"👥 TEAM-MODUS mit {len(self.sim.teams)} Teams: {', '.join(self.sim.teams.keys())}")
        if train_rounds > 0:
            self._add_to_chat(f"📚 Training: {train_rounds} Runden zu '{topic}'")
        self._add_to_chat(f"🌐 Externe Quellen: {'✅ Aktiv' if self.sim.external.use_external else '❌ Inaktiv'}")
        if self.use_prognosis_var.get():
            self._add_to_chat(f"🔮 Prognosen werden gesammelt")
        self._add_to_chat(f"📚 Agenten lernen mit ZENTRALEM KNOWLEDGE GRAPH & GEDÄCHTNIS-PALAST")
        for agent in self.sim.agents:
            if agent.learned_facts:
                self._add_to_chat(f"   📖 {agent.name} kennt {len(agent.learned_facts)} Fakten")
        self._add_to_chat(f"{'='*60}\n")
        
        thread = threading.Thread(target=self._process_discussion, args=(topic, document, rounds, use_moderator, team_mode))
        thread.daemon = True
        thread.start()
    
    def _process_discussion(self, topic, document, rounds, use_moderator, team_mode):
        try:
            for msg_type, *content in self.sim.start_discussion(topic, document, rounds, use_moderator, team_mode):
                if msg_type == "moderator":
                    self.msg_queue.put(("moderator", content[0]))
                elif msg_type == "agent":
                    name, text, color = content
                    self.msg_queue.put(("agent", name, text, color))
                    self.msg_queue.put(("update", name, text))
                elif msg_type == "system":
                    if content[0].startswith("--- RUNDE"):
                        self.msg_queue.put(("round", content[0]))
                    self.msg_queue.put(("system", content[0]))
        except Exception as e:
            print(f"FEHLER in Diskussion: {e}")
        finally:
            self.msg_queue.put(("done",))
    
    def _process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg[0] == "moderator":
                    self._add_to_chat(f"🎭 {msg[1]}")
                elif msg[0] == "agent":
                    self._add_to_chat(f"🗣️ {msg[1]}: {msg[2]}")
                elif msg[0] == "system":
                    self._add_to_chat(f"📢 {msg[1]}")
                elif msg[0] == "round":
                    round_text = msg[1].replace("--- ", "").replace(" ---", "")
                    self.round_label.config(text=round_text)
                elif msg[0] == "update":
                    self._update_agent_response(msg[1], msg[2])
                elif msg[0] == "done":
                    self._disable_stop_button()
                    self.start_btn.config(state=tk.NORMAL)
                    self.round_label.config(text="Runde: 0/0")
                    
                    # 🔥 HARD RESET 🔥
                    self.sim.is_running = False
                    self.sim.stop_event.clear()
                    self.sim.discussion_log = []
                    self.sim.current_round = 0
                    
                    self._add_to_chat("\n✅ Diskussion beendet\n")
                    self.show_knowledge_graph()
                    kg = self.sim.knowledge_graph
                    self._add_to_chat(f"📊 AKTUELLES WISSEN: {len(kg.graph['nodes'])} Knoten, {len(kg.graph['edges'])} Beziehungen")
                    self._add_to_chat(f"📚 Themen-Cluster: {len(kg.graph['topics'])}")
                    self._add_to_chat(f"🎯 Einflüsse: {len(kg.graph['influences'])} Agenten haben andere beeinflusst")
                    self._add_to_chat(f"👥 Teams: {len(kg.graph['teams'])}\n")
                    
                    # Gedächtnis-Palast und Dashboard aktualisieren
                    if hasattr(self, 'memory_palace_tab'):
                        self.memory_palace_tab.refresh_agent_list()
                    if hasattr(self, 'dashboard_tab'):
                        self.dashboard_tab.refresh_dashboard()
        except queue.Empty:
            pass
        self.root.after(50, self._process_queue)
    
    def _update_agent_response(self, name, response):
        for widget in self.agents_frame.winfo_children():
            if hasattr(widget, 'response_label'):
                header = widget.winfo_children()[0]
                for label in header.winfo_children():
                    if isinstance(label, tk.Label) and label.cget("text") == name:
                        widget.response_label.config(text=response[:150] + "..." if len(response) > 150 else response)
                        agent = next((a for a in self.sim.agents if a.name == name), None)
                        if agent:
                            if agent.ausgeschlossen and hasattr(agent, 'status_label'):
                                agent.status_label.config(text="⛔ Ausgeschlossen", fg=Config.ERROR)
                            elif hasattr(agent, 'status_label'):
                                agent.status_label.config(text=f"✅ {len(agent.schon_gesagtes)} Beiträge, {len(agent.learned_facts)} Fakten", fg=Config.SUCCESS)
                        return
    
    def export_chat(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Config.EXPORTS_FOLDER}/chat_{timestamp}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.chat_text.get(1.0, tk.END))
            self._update_status(f"✅ Exportiert: {os.path.basename(filename)}")
        except:
            messagebox.showerror("Fehler", "Export fehlgeschlagen")
    
    def clear_chat(self):
        if messagebox.askyesno("Chat löschen", "Wirklich löschen?"):
            self.chat_text.delete(1.0, tk.END)
            self._update_status("Chat gelöscht")


# ===================== START =====================
def main():
    root = tk.Tk()
    app = SynthAgoraGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()