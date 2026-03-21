#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulations-Kernmodul für SynthAgora
- Agenten-Verwaltung
- Diskussions-Steuerung
- Debatten-Formate (Pro/Contra, Fishbowl, Delphi, etc.)
- Dokumenten-Loader
- Ergebnis-Analyse
- Visualisierung
"""

import json
import os
import time
import threading
import queue
import random
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable, Generator, Tuple
from concurrent.futures import ThreadPoolExecutor

from .config import Config
from .database import SynthAgoraDB
from .knowledge_graph import KnowledgeGraph
from .agent import Agent
from .agent_factory import AgentFactory
from .task_manager import TaskManager, AnalysisJob
from .plugins import PluginManager
from .debate_formats import DebateSession, DebateConfig, get_available_formats
from .debate_controller import DebateController, SanctionType
from .document_loader import DocumentLoader
from .result_analyzer import ResultAnalyzer
from .visualization import Visualization
from .migrate import MigrationTool


class Moderator:
    """Moderator für Diskussionen"""
    
    def __init__(self, data: dict):
        self.name = data["name"]
        self.role = data["role"]
        self.personality = data["personality"]
        self.color = data.get("color", "#c586c0")
        self.style = data.get("style", "professionell")
        self.enabled = True
        self.evasions = {}
        self.abgebrochene_agenten = set()
        self.discussion_goal = None
    
    def introduce(self, topic: str, document: Optional[str], lm, stop_event=None) -> str:
        if not self.enabled:
            return ""
        self.evasions = {}
        self.abgebrochene_agenten = set()
        prompt = f"""Du bist {self.name}, {self.role}. Stil: {self.style}
Thema: "{topic}". Stelle dich KURZ vor (max 2 Sätze)."""
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)
    
    def ask_question(self, agent_name: str, agent_role: str, agent_personality: str,
                     topic: str, document: Optional[str], context: str,
                     lm, stop_event=None) -> Optional[str]:
        if not self.enabled or agent_name in self.abgebrochene_agenten:
            return None
        goal_text = f" Ziel der Diskussion: {self.discussion_goal}" if self.discussion_goal else ""
        prompt = f"""Du bist {self.name}. Thema: {topic}.{goal_text}
Stelle {agent_name} eine präzise Frage zum Thema. Max 2 Sätze.
Verwende deinen Stil: {self.style}."""
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)
    
    def set_discussion_goal(self, goal: str):
        self.discussion_goal = goal
    
    def summarize(self, discussion: str, topic: str, lm, stop_event=None) -> str:
        if not self.enabled:
            return ""
        prompt = f"""Du bist {self.name}. Thema: {topic}.
Fasse die wichtigsten Positionen und Ergebnisse der Diskussion in 2-3 Sätzen zusammen.
Verwende deinen Stil: {self.style}."""
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)


class LLMClient:
    """LLM-Client für API-Aufrufe"""
    
    def __init__(self):
        self.provider = Config.LM_PROVIDER
        self.session = None
        self.stats = {"calls": 0, "errors": 0}
        self.is_processing = False
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._futures = []
        
        self._init_session()
    
    def _init_session(self):
        import requests
        self.session = requests.Session()
    
    def test(self) -> Tuple[bool, str]:
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
    
    def ask_async(self, prompt: str, system: str = None, callback: Callable = None, 
                  max_tokens: int = None, timeout: int = 60) -> None:
        def _ask():
            try:
                result = self.ask(prompt, system, None, None, max_tokens)
                if callback:
                    callback(result)
            except Exception as e:
                if callback:
                    callback(f"[Fehler: {str(e)[:30]}]")
        
        future = self._executor.submit(_ask)
        self._futures.append(future)
    
    def ask(self, prompt: str, system: str = None, stop_event: threading.Event = None, 
            callback: Callable = None, max_tokens: int = None) -> str:
        self.stats["calls"] += 1
        self.is_processing = True
        
        try:
            if stop_event and stop_event.is_set():
                self.is_processing = False
                return "[ABGEBROCHEN]"
            
            if self.provider == "lmstudio":
                result = self._ask_lmstudio(prompt, system, stop_event, callback, max_tokens)
            elif self.provider == "ollama":
                result = self._ask_ollama(prompt, system, stop_event, callback, max_tokens)
            else:
                result = self._ask_beta(prompt, system)
            
            self.is_processing = False
            return result
                
        except Exception as e:
            self.stats["errors"] += 1
            self.is_processing = False
            return f"[Fehler: {str(e)[:30]}]"
    
    def _ask_lmstudio(self, prompt: str, system: str = None, stop_event=None, 
                      callback=None, max_tokens=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        r = self.session.post(Config.LM_STUDIO_URL, json={
            "messages": messages,
            "max_tokens": max_tokens or Config.MAX_TOKENS,
            "temperature": Config.TEMPERATURE,
            "stop": ["\n\n", "User:", "Assistant:"]
        }, timeout=Config.TIMEOUT)
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        text = r.json()["choices"][0]["message"]["content"]
        text = re.sub(r'(?i)(thinking|thought).*?(\n|$)', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."
    
    def _ask_ollama(self, prompt: str, system: str = None, stop_event=None,
                    callback=None, max_tokens=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        r = self.session.post(Config.OLLAMA_URL, json={
            "model": Config.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": Config.TEMPERATURE,
                "num_predict": max_tokens or Config.MAX_TOKENS
            }
        }, timeout=Config.TIMEOUT)
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        text = r.json()["message"]["content"]
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."
    
    def _ask_beta(self, prompt: str, system: str = None) -> str:
        return f"[{self.provider} - Kein API-Key konfiguriert]\nPrompt: {prompt[:100]}..."
    
    def cancel_all(self):
        for future in self._futures:
            future.cancel()
        self._futures.clear()


class ProgressManager:
    """Fortschritts-Manager für lange Operationen"""
    
    def __init__(self, status_callback: Callable = None):
        self.status_callback = status_callback
        self.total = 0
        self.current = 0
        self.operation = ""
        self.start_time = None
        self.is_running = False
    
    def start(self, operation: str, total: int = 1):
        self.operation = operation
        self.total = total
        self.current = 0
        self.start_time = time.time()
        self.is_running = True
        self._update("start")
    
    def update(self, increment: int = 1, message: str = None):
        self.current += increment
        self._update("progress", message)
    
    def set_message(self, message: str):
        self._update("message", message)
    
    def finish(self, message: str = "✅ Fertig"):
        self.is_running = False
        self._update("done", message)
    
    def _update(self, status: str, message: str = None):
        if self.status_callback:
            elapsed = time.time() - self.start_time if self.start_time else 0
            progress = (self.current / self.total * 100) if self.total > 0 else 0
            
            status_text = message or self.operation
            if self.total > 1:
                status_text = f"{self.operation} ({self.current}/{self.total} • {progress:.0f}%)"
            
            if elapsed > 0 and self.current < self.total and self.current > 0:
                remaining = (elapsed / self.current) * (self.total - self.current)
                if remaining > 0:
                    status_text += f" • ⏱️ noch ca. {int(remaining)}s"
            
            self.status_callback(status, status_text)


class Simulation:
    """Haupt-Simulations-Klasse"""
    
    def __init__(self):
        self.lm = LLMClient()
        self.db = SynthAgoraDB()
        self.knowledge_graph = KnowledgeGraph()
        self.agent_factory = AgentFactory(self.lm)
        self.task_manager = TaskManager(max_workers=5)
        self.plugin_manager = PluginManager()
        
        # Neue Module
        self.document_loader = DocumentLoader()
        self.result_analyzer = ResultAnalyzer(self.lm)
        self.visualization = Visualization()
        
        # Agenten und Diskussion
        self.agents: List[Agent] = []
        self.moderator: Optional[Moderator] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.discussion_log = []
        self.current_topic = ""
        self.current_round = 0
        self.max_rounds = 0
        self.teams = {}
        self.team_mode = False
        self.current_discussion_id = None
        self.discussion_purpose = ""
        
        # Debatten
        self.debate_session: Optional[DebateSession] = None
        self.debate_controller: Optional[DebateController] = None
        self.current_debate_format = "classic"
        
        self.stats = {
            "total_contributions": 0,
            "start_time": None,
            "end_time": None,
            "current_round": 0,
            "max_rounds": 0
        }
        
        self._auto_migrate()
    
    def _auto_migrate(self):
        stats = self.db.get_pool_stats()
        if stats['total'] == 0:
            kg_file = os.path.join(Config.KNOWLEDGE_FOLDER, "knowledge_graph.json")
            if os.path.exists(kg_file):
                print("📦 Automatische Migration: Knowledge Graph...")
                migrator = MigrationTool(self.db)
                migrator._migrate_knowledge_graph(kg_file)
    
    def trigger_callback(self, event: str, data: Any = None):
        if hasattr(self, '_callback') and self._callback:
            self._callback(event, data)
    
    def set_callback(self, callback):
        self._callback = callback
    
    # ==================== AGENTEN-VERWALTUNG ====================
    
    def load_agents_from_pool(self, agent_names: List[str]) -> bool:
        """Lädt Agenten aus der Datenbank"""
        try:
            self.agents = []
            self.teams = {}
            
            loaded_count = 0
            total = len(agent_names)
            unique_names = set()
            
            for agent_name in agent_names:
                if agent_name in unique_names:
                    continue
                unique_names.add(agent_name)
                
                try:
                    pool_agent = self.db.get_agent_from_pool_by_name(agent_name)
                    if not pool_agent:
                        continue
                    
                    meta = {}
                    if pool_agent.get("metadata"):
                        meta = pool_agent["metadata"]
                        if isinstance(meta, str):
                            meta = json.loads(meta)
                    
                    # Persönlichkeit aus Metadaten oder JSON-File
                    personality = meta.get("personality", "")
                    if not personality and pool_agent.get("json_file"):
                        try:
                            with open(pool_agent["json_file"], 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                                for a in json_data.get("agents", []):
                                    if a.get("name") == agent_name:
                                        personality = a.get("personality", "Standard-Persönlichkeit")
                                        break
                        except:
                            pass
                    
                    if not personality:
                        personality = "Standard-Persönlichkeit"
                    
                    agent_data = {
                        "name": pool_agent["name"],
                        "role": pool_agent["role"],
                        "personality": personality,
                        "color": meta.get("color", "#cccccc"),
                        "goals": meta.get("goals", []),
                        "fears": meta.get("fears", []),
                        "education": meta.get("education", ""),
                        "background": meta.get("background", ""),
                        "team": meta.get("team", ""),
                        "charakter_typ": meta.get("charakter_typ", "Realist")
                    }
                    
                    agent_id = f"agent_{agent_name.lower().replace(' ', '_')}_{hashlib.md5(agent_name.encode()).hexdigest()[:8]}"
                    agent_data["agent_id"] = agent_id
                    
                    agent = Agent(agent_data, self.knowledge_graph, self.plugin_manager)
                    agent.set_db(self.db)
                    agent.set_external_source(self.plugin_manager)
                    self.agents.append(agent)
                    
                    self.db.add_agent(agent.agent_id, agent_data, pool_agent["agent_id"])
                    
                    if agent.team:
                        if agent.team not in self.teams:
                            self.teams[agent.team] = []
                        self.teams[agent.team].append(agent)
                    
                    loaded_count += 1
                    
                except Exception as e:
                    print(f"❌ Fehler bei {agent_name}: {e}")
                    continue
            
            for agent in self.agents:
                agent.discussion_log = self.discussion_log
            
            return len(self.agents) > 0
            
        except Exception as e:
            print(f"❌ Fehler: {e}")
            return False
    
    def load_moderator(self, filepath: str) -> bool:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.moderator = Moderator(data)
            return True
        except:
            return False
    
    def set_discussion_purpose(self, purpose: str, goal: str = None):
        self.discussion_purpose = purpose
        if self.moderator and goal:
            self.moderator.set_discussion_goal(goal)
    
    # ==================== DISKUSSION (KLASSISCH) ====================
    
    def start_discussion(self, topic: str, document: Optional[str], 
                         rounds: int = 2, use_moderator: bool = True,
                         team_mode: bool = False):
        """Startet eine klassische Diskussion"""
        self.stop_event.clear()
        self.is_running = True
        self.discussion_log = []
        self.current_topic = topic
        self.current_round = 0
        self.max_rounds = rounds
        self.team_mode = team_mode
        self.stats["start_time"] = datetime.now().isoformat()
        self.stats["total_contributions"] = 0
        
        for agent in self.agents:
            agent.schon_gesagtes = []
            agent.wiederholungen = 0
            agent.ausgeschlossen = False
            agent.discussion_log = self.discussion_log
        
        self.current_discussion_id = f"disc_{int(time.time())}"
        self.db.start_discussion(
            self.current_discussion_id, topic, 
            self.discussion_purpose or "Diskussion",
            self.moderator.discussion_goal if self.moderator else None,
            self.moderator.name if self.moderator else None
        )
        
        if self.moderator:
            self.moderator.enabled = use_moderator
            self.moderator.evasions = {}
            self.moderator.abgebrochene_agenten = set()
        
        try:
            yield from self._run_discussion(topic, document, rounds, use_moderator, team_mode)
        finally:
            self._cleanup_duplicate_memories()
        
        self.stats["end_time"] = datetime.now().isoformat()
        self.is_running = False
        self.stop_event.clear()
    
    def _run_discussion(self, topic: str, document: Optional[str],
                        rounds: int, use_moderator: bool, team_mode: bool):
        """Interne Diskussions-Logik"""
        for round_num in range(rounds):
            if self.stop_event.is_set():
                break
            
            self.current_round = round_num + 1
            yield ("system", f"--- RUNDE {round_num+1}/{rounds} ---")
            yield ("round_update", f"Runde {round_num+1}/{rounds}")
            
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
                        self._limit_discussion_log()
                        
                        answer = self._get_answer(agent, topic, document, round_num)
                        
                        if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                            self.stats["total_contributions"] += 1
                            self.db.add_contribution(
                                self.current_discussion_id, agent.agent_id, answer,
                                round_num, False, None, None
                            )
                            yield ("agent", agent.name, answer, agent.color)
                            self.discussion_log.append(f"{agent.name}: {answer}")
                            self._limit_discussion_log()
                            yield ("agent_update", agent.name, answer)
                            yield ("contribution_added", 1)
                            
                            for other in self.agents:
                                if other.name != agent.name and not other.ausgeschlossen and not self.stop_event.is_set():
                                    self._learn_async(other, agent.name, answer, topic, agent.role)
                
                else:
                    answer = self._get_answer(agent, topic, document, round_num)
                    
                    if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        self.stats["total_contributions"] += 1
                        self.db.add_contribution(
                            self.current_discussion_id, agent.agent_id, answer,
                            round_num, False, None, None
                        )
                        yield ("agent", agent.name, answer, agent.color)
                        self.discussion_log.append(f"{agent.name}: {answer}")
                        self._limit_discussion_log()
                        yield ("agent_update", agent.name, answer)
                        yield ("contribution_added", 1)
                        
                        for other in self.agents:
                            if other.name != agent.name and not other.ausgeschlossen and not self.stop_event.is_set():
                                self._learn_async(other, agent.name, answer, topic, agent.role)
        
        if not self.stop_event.is_set() and use_moderator and self.moderator:
            summary = self.moderator.summarize(
                "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
            )
            if summary and summary != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 📋 {summary}")
                self.db.end_discussion(self.current_discussion_id, summary)
    
    def _get_answer(self, agent, topic, document, round_num):
        result_queue = queue.Queue()
        
        def _ask():
            try:
                answer = agent.answer(topic, document, self.lm, self.stop_event, round_num)
                result_queue.put(answer)
            except Exception as e:
                result_queue.put(f"[Fehler: {str(e)[:30]}]")
        
        thread = threading.Thread(target=_ask)
        thread.daemon = True
        thread.start()
        thread.join(timeout=Config.TIMEOUT)
        
        if thread.is_alive():
            return "[Timeout]"
        
        try:
            return result_queue.get_nowait()
        except queue.Empty:
            return "[Fehler]"
    
    def _learn_async(self, agent, other_name, statement, topic, other_role):
        def _learn():
            try:
                agent.learn_from(other_name, statement, topic, self.lm, other_role)
            except:
                pass
        thread = threading.Thread(target=_learn)
        thread.daemon = True
        thread.start()
    
    def _cleanup_duplicate_memories(self):
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM memory_crystals 
                WHERE crystal_id NOT IN (
                    SELECT MIN(crystal_id) 
                    FROM memory_crystals 
                    GROUP BY fact
                )
            """)
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if deleted > 0:
                print(f"🧹 {deleted} Duplikate aus memory_crystals entfernt")
        except Exception as e:
            print(f"⚠️ Fehler beim Bereinigen der Duplikate: {e}")
    
    def _limit_discussion_log(self):
        if len(self.discussion_log) > Config.MAX_DISCUSSION_LOG:
            self.discussion_log = self.discussion_log[-Config.MAX_DISCUSSION_LOG:]
    
    # ==================== DEBATTEN-FORMATE ====================
    
    def start_debate(self, topic: str, document: Optional[str], config: Dict) -> Generator:
        """
        Startet eine Debatte mit erweiterten Formaten.
        FIX: Moderator wird im "classic" Format verwendet.
        """
        self.stop_event.clear()
        self.is_running = True
        self.discussion_log = []
        self.current_topic = topic
        self.current_debate_format = config.get("format", "classic")
        
        # Debug-Ausgabe
        print(f"🎭 Starte Debatte: Format={self.current_debate_format}, Thema={topic}")
        print(f"   Pro-Agenten aus config: {config.get('pro_agents', [])}")
        print(f"   Contra-Agenten aus config: {config.get('contra_agents', [])}")
        print(f"   Moderator aktiv: {config.get('use_moderator', False)}")
        print(f"   Moderator vorhanden: {self.moderator is not None}")
        
        # Agenten zurücksetzen
        for agent in self.agents:
            agent.schon_gesagtes = []
            agent.wiederholungen = 0
            agent.ausgeschlossen = False
            agent.discussion_log = self.discussion_log
        
        # Moderator zurücksetzen
        if self.moderator:
            self.moderator.enabled = config.get("use_moderator", True)
            self.moderator.evasions = {}
            self.moderator.abgebrochene_agenten = set()
        
        # Diskussion in DB starten
        self.current_discussion_id = f"debate_{int(time.time())}"
        self.db.start_discussion(
            self.current_discussion_id, topic,
            f"Debatte ({self.current_debate_format})",
            config.get("premise", None),
            self.moderator.name if self.moderator else None
        )
        
        # FÜR CLASSIC: Verwende die klassische Diskussionslogik mit Moderator
        if self.current_debate_format == "classic":
            rounds = config.get("rounds", 3)
            use_moderator = config.get("use_moderator", True) and self.moderator is not None
            
            # Moderator-Vorstellung
            if use_moderator and self.moderator:
                intro = self.moderator.introduce(topic, document, self.lm, self.stop_event)
                if intro and intro != "[ABGEBROCHEN]":
                    yield ("moderator", f"🎭 {intro}")
                    self.discussion_log.append(f"Moderator: {intro}")
            
            # Führe klassische Diskussion durch
            for round_num in range(rounds):
                if self.stop_event.is_set():
                    break
                
                self.current_round = round_num + 1
                yield ("system", f"--- RUNDE {round_num+1}/{rounds} ---")
                yield ("round_update", f"Runde {round_num+1}/{rounds}")
                
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
                            self._limit_discussion_log()
                            
                            answer = self._get_answer(agent, topic, document, round_num)
                            
                            if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                                self.stats["total_contributions"] += 1
                                self.db.add_contribution(
                                    self.current_discussion_id, agent.agent_id, answer,
                                    round_num, False, None, None
                                )
                                yield ("agent", agent.name, answer, agent.color)
                                self.discussion_log.append(f"{agent.name}: {answer}")
                                self._limit_discussion_log()
                                yield ("agent_update", agent.name, answer)
                                yield ("contribution_added", 1)
                                
                                for other in self.agents:
                                    if other.name != agent.name and not other.ausgeschlossen and not self.stop_event.is_set():
                                        self._learn_async(other, agent.name, answer, topic, agent.role)
                    
                    else:
                        answer = self._get_answer(agent, topic, document, round_num)
                        
                        if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                            self.stats["total_contributions"] += 1
                            self.db.add_contribution(
                                self.current_discussion_id, agent.agent_id, answer,
                                round_num, False, None, None
                            )
                            yield ("agent", agent.name, answer, agent.color)
                            self.discussion_log.append(f"{agent.name}: {answer}")
                            self._limit_discussion_log()
                            yield ("agent_update", agent.name, answer)
                            yield ("contribution_added", 1)
                            
                            for other in self.agents:
                                if other.name != agent.name and not other.ausgeschlossen and not self.stop_event.is_set():
                                    self._learn_async(other, agent.name, answer, topic, agent.role)
            
            # Abschluss-Zusammenfassung durch Moderator
            if not self.stop_event.is_set() and use_moderator and self.moderator:
                summary = self.moderator.summarize(
                    "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
                )
                if summary and summary != "[ABGEBROCHEN]":
                    yield ("moderator", f"🎭 📋 {summary}")
                    self.db.end_discussion(self.current_discussion_id, summary)
            else:
                self.db.end_discussion(self.current_discussion_id, "Diskussion beendet")
            
            self.is_running = False
            self.stop_event.clear()
            return
        
        # Für alle anderen Formate: Verwende DebateSession
        format_map = {
            "classic": "classic",
            "pro_contra": "pro_contra",
            "fishbowl": "fishbowl",
            "world_cafe": "world_cafe",
            "delphi": "delphi",
            "premise_check": "premise_check"
        }
        
        format_str = format_map.get(config.get("format", "classic"), "classic")
        
        # FIX: Stelle sicher, dass pro_agents und contra_agents korrekt übernommen werden
        pro_agents = config.get("pro_agents", [])
        contra_agents = config.get("contra_agents", [])
        
        # FIX: Entferne mögliche Duplikate und leere Einträge
        pro_agents = [a for a in pro_agents if a and a.strip()]
        contra_agents = [a for a in contra_agents if a and a.strip()]
        
        print(f"   Bereinigte Pro-Agenten: {pro_agents}")
        print(f"   Bereinigte Contra-Agenten: {contra_agents}")
        
        # FIX: Wenn keine Teams zugewiesen sind, aber Agenten vorhanden sind, verteile zufällig
        if not pro_agents and not contra_agents and self.agents:
            print("⚠️ Keine Team-Zuordnung in config, verteile zufällig...")
            shuffled = self.agents.copy()
            random.shuffle(shuffled)
            half = len(shuffled) // 2
            pro_agents = [a.name for a in shuffled[:half]]
            contra_agents = [a.name for a in shuffled[half:]]
            print(f"   Zufällige Pro-Agenten: {pro_agents}")
            print(f"   Zufällige Contra-Agenten: {contra_agents}")
        
        # Für Prämisse prüfen: Kombiniere Dokument + Prämisse
        premise = config.get("premise", topic)
        if format_str == "premise_check" and document:
            combined_premise = f"""Dokument:
{document[:2000]}

Prämisse/These:
{premise}

Aufgabe: {'Beweise' if config.get('prove_mode', True) else 'Widerlege'} die These basierend auf dem Dokument."""
            premise = combined_premise
        
        # FIX: Stelle sicher, dass topic korrekt gesetzt wird
        debate_topic = topic
        if format_str == "premise_check":
            debate_topic = premise
        
        # Debatten-Konfiguration
        debate_config = DebateConfig(
            format=format_str,
            rounds=config.get("rounds", 3),
            time_per_round=config.get("time_per_round", 0),
            thinking_time=config.get("thinking_time", 10),
            enable_moderator=config.get("enable_moderator", False),
            enable_voting=config.get("enable_voting", False),
            enable_sanctions=config.get("enable_sanctions", False),
            pro_agents=pro_agents,
            contra_agents=contra_agents,
            premise=premise,
            prove_mode=config.get("prove_mode", True),
            inner_circle_size=config.get("inner_circle_size", 5),
            cafe_tables=config.get("cafe_tables", 3),
            rotation_rounds=config.get("rotation_rounds", 3),
            anonymous_votes=config.get("anonymous_votes", True),
            show_statistics=config.get("show_statistics", True)
        )
        
        print(f"   DebateConfig Pro-Agenten: {debate_config.pro_agents}")
        print(f"   DebateConfig Contra-Agenten: {debate_config.contra_agents}")
        
        # Debatten-Session erstellen
        self.debate_session = DebateSession(
            debate_topic,
            debate_config, 
            self.agents, 
            self.lm,
            self.db
        )
        
        # Controller für Steuerung (Timer, Rednerliste, Sanktionen)
        self.debate_controller = DebateController(
            self.agents,
            config={
                "time_per_round": config.get("time_per_round", 0),
                "thinking_time": config.get("thinking_time", 10),
                "speaker_list": config.get("speaker_list", False),
                "interruptions": config.get("interruptions", False),
                "sanctions": config.get("enable_sanctions", False),
                "max_warnings": config.get("max_warnings", 3),
                "mute_rounds": config.get("mute_rounds", 2),
                "repetition_threshold": config.get("repetition_threshold", 2)
            }
        )
        
        # Für Lern-Aufrufe: letzte Beiträge speichern
        last_contributions = []
        
        # Debatte ausführen
        try:
            for msg in self.debate_session.start():
                # Nachrichten an GUI weiterleiten
                if msg[0] == "agent":
                    agent_name = msg[1]
                    content = msg[2]
                    color = msg[3]
                    team = msg[4] if len(msg) > 4 else None
                    
                    # In DB speichern
                    agent = next((a for a in self.agents if a.name == agent_name), None)
                    if agent:
                        self.db.add_contribution(
                            self.current_discussion_id, agent.agent_id, content,
                            self.debate_session.current_round, False, None, None
                        )
                        self.stats["total_contributions"] += 1
                    
                    # FÜR LERNEN: Andere Agenten lernen aus diesem Beitrag
                    last_contributions.append({"agent": agent_name, "content": content, "round": self.debate_session.current_round})
                    if len(last_contributions) > 10:
                        last_contributions.pop(0)
                    
                    # Alle anderen Agenten lernen von diesem Beitrag
                    for other_agent in self.agents:
                        if other_agent.name != agent_name and not other_agent.ausgeschlossen and not self.stop_event.is_set():
                            self._learn_async(other_agent, agent_name, content, topic, agent.role if agent else "")
                    
                    yield msg
                    
                elif msg[0] == "system":
                    self.discussion_log.append(msg[1])
                    yield msg
                    
                elif msg[0] == "round_start":
                    # Extrahiere Runden-Nummer aus Nachricht
                    if len(msg) > 1 and isinstance(msg[1], str):
                        match = re.search(r'(\d+)', msg[1])
                        if match:
                            self.current_round = int(match.group(1))
                    else:
                        self.current_round += 1
                    yield msg
                    
                elif msg[0] == "round_end":
                    yield msg
                    
                else:
                    yield msg
                    
        finally:
            self._cleanup_duplicate_memories()
            self.db.end_discussion(self.current_discussion_id, 
                                   self.debate_session._generate_summary() if self.debate_session else "")
        
        self.is_running = False
        self.stop_event.clear()
    
    # ==================== ANALYSE ====================
    
    def run_analysis(self, job: AnalysisJob, progress_callback: Callable = None) -> AnalysisJob:
        """Führt eine Analyse mit den Agenten durch"""
        return self.task_manager.run_analysis(job, progress_callback)
    
    def analyze_results(self, contributions: List[Dict] = None) -> Dict:
        """
        Analysiert die Ergebnisse einer Diskussion.
        
        Args:
            contributions: Liste der Beiträge (optional, verwendet sonst self.discussion_log)
        """
        if contributions is None:
            # Aus discussion_log extrahieren
            contributions = []
            for line in self.discussion_log:
                if ": " in line:
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        contributions.append({
                            "agent": parts[0],
                            "content": parts[1],
                            "round": self.current_round
                        })
        
        return self.result_analyzer.generate_full_report(
            contributions, self.agents, self.current_topic
        )
    
    # ==================== DOKUMENTEN-LOADER ====================
    
    def load_document(self, source: str, source_type: str = "auto") -> Dict:
        """Lädt ein Dokument für die Diskussion"""
        return self.document_loader.load_document(source, source_type)
    
    def load_multiple_documents(self, sources: List[Dict]) -> Dict:
        """Lädt mehrere Dokumente"""
        return self.document_loader.load_multiple(sources)
    
    # ==================== VISUALISIERUNG ====================
    
    def get_visualization(self):
        """Gibt das Visualisierungsobjekt zurück"""
        return self.visualization
    
    def get_network_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Holt Daten für Netzwerk-Graph"""
        nodes = []
        edges = []
        
        for agent in self.agents:
            nodes.append({
                "id": agent.agent_id,
                "name": agent.name,
                "color": agent.color,
                "size": 500 + agent.experience_points / 100
            })
        
        # Einflüsse aus DB holen
        for agent in self.agents:
            influences = self.db.get_influences(agent.agent_id)
            for inf in influences.get("given", []):
                edges.append({
                    "from": agent.agent_id,
                    "to": inf.get("to"),
                    "strength": inf.get("strength", 0.5)
                })
        
        return nodes, edges
    
    # ==================== DATENBANK ====================
    
    def search_pool(self, query: str, limit: int = 100) -> List[Dict]:
        return self.agent_factory.search_pool(query, limit)
    
    def get_random_from_pool(self, count: int, filters: Dict = None) -> List[Dict]:
        return self.agent_factory.get_random_from_pool(count, filters)
    
    def get_pool_stats(self) -> Dict:
        return self.db.get_pool_stats()
    
    def get_db_info(self) -> Dict:
        return self.db.get_stats()
    
    def backup_db(self) -> str:
        return self.db.backup()
    
    def reset_db(self) -> bool:
        self.db.backup()
        self.db = SynthAgoraDB()
        self.knowledge_graph = KnowledgeGraph()
        return True
    
    def stop(self):
        self.stop_event.set()
        self.is_running = False
        if self.debate_session:
            self.debate_session.stop()
        self.lm.cancel_all()