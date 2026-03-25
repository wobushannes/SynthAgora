#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulations-Kernmodul für SynthAgora
"""

import json
import os
import time
import threading
import queue
import random
import hashlib
import re
import requests
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable, Generator, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config
from .database import SynthAgoraDB
from .knowledge_graph import KnowledgeGraph
from .agent import Agent
from .agent_factory import AgentFactory
from .task_manager import TaskManager, AnalysisJob
from .plugin_manager import PluginManager
from .debate_formats import get_available_formats, DebateSession, DebateConfig
from .debate_controller import DebateController, SanctionType
from .document_loader import DocumentLoader
from .result_analyzer import ResultAnalyzer
from .visualization import Visualization
from .migrate import MigrationTool
from .project_manager import ProjectManager
from .embedding_client import EmbeddingClient


class RateLimiter:
    """Einfacher Rate-Limiter für API-Aufrufe"""
    
    def __init__(self, requests_per_second: float = 1.5):
        self.interval = 1.0 / requests_per_second
        self.last_call = 0
        self.lock = threading.Lock()
    
    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()


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
        # FIX: Document in Prompt einbauen
        doc_text = f"\nDokument: {document[:500]}..." if document else ""
        prompt = f"""Du bist {self.name}. Thema: {topic}.{goal_text}{doc_text}
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
    """LLM-Client für API-Aufrufe mit Retry und Throttling"""
    
    def __init__(self):
        self.provider = Config.LM_PROVIDER
        self.session = None
        self.stats = {"calls": 0, "errors": 0, "retries": 0}
        self.is_processing = False
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._futures = []
        self._rate_limiter = RateLimiter(requests_per_second=1.5)
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
                # FIX: callback auch bei Exception aufrufen
                if callback:
                    callback(f"[Fehler: {str(e)[:30]}]")
        
        future = self._executor.submit(_ask)
        self._futures.append(future)
    
    def ask(self, prompt: str, system: str = None, stop_event: threading.Event = None, 
            callback: Callable = None, max_tokens: int = None, 
            max_retries: int = 3, retry_delay: float = 2.0) -> str:
        
        self._rate_limiter.wait()
        
        for attempt in range(max_retries):
            if stop_event and stop_event.is_set():
                self.is_processing = False
                return "[ABGEBROCHEN]"
            
            self.stats["calls"] += 1
            self.is_processing = True
            
            try:
                if self.provider == "lmstudio":
                    result = self._ask_lmstudio(prompt, system, stop_event, callback, max_tokens)
                elif self.provider == "ollama":
                    result = self._ask_ollama(prompt, system, stop_event, callback, max_tokens)
                else:
                    result = self._ask_beta(prompt, system)
                
                self.is_processing = False
                
                if result and result.startswith("[Fehler"):
                    raise Exception(result)
                
                return result
                
            except Exception as e:
                self.stats["errors"] += 1
                self.stats["retries"] += 1
                
                if attempt < max_retries - 1:
                    print(f"⚠️ API-Fehler (Versuch {attempt+1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                    continue
                else:
                    self.is_processing = False
                    return f"[Fehler: {str(e)[:30]}]"
        
        self.is_processing = False
        return "[Fehler: Max Retries]"
    
    def _ask_lmstudio(self, prompt: str, system: str = None, stop_event=None, 
                      callback=None, max_tokens=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            r = self.session.post(Config.LM_STUDIO_URL, json={
                "messages": messages,
                "max_tokens": max_tokens or Config.MAX_TOKENS,
                "temperature": Config.TEMPERATURE,
                "stop": ["\n\n", "User:", "Assistant:"]
            }, timeout=Config.TIMEOUT)
            
            if stop_event and stop_event.is_set():
                return "[ABGEBROCHEN]"
            
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}: {r.text[:100]}")
            
            data = r.json()
            if "choices" not in data:
                raise Exception(f"Unerwartete Antwort: {list(data.keys())}")
            
            text = data["choices"][0]["message"]["content"]
            text = re.sub(r'(?i)(thinking|thought).*?(\n|$)', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text if text else "..."
            
        except requests.exceptions.Timeout:
            raise Exception("Timeout")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection Error - Ist LM Studio gestartet?")
        except Exception as e:
            raise Exception(str(e))
    
    def _ask_ollama(self, prompt: str, system: str = None, stop_event=None,
                    callback=None, max_tokens=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
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
            
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}")
            
            data = r.json()
            if "message" not in data:
                raise Exception(f"Unerwartete Antwort: {list(data.keys())}")
            
            text = data["message"]["content"]
            text = re.sub(r'\s+', ' ', text).strip()
            return text if text else "..."
            
        except requests.exceptions.Timeout:
            raise Exception("Timeout")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection Error - Ist Ollama gestartet?")
        except Exception as e:
            raise Exception(str(e))
    
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
        self.plugin_manager.set_lm(self.lm)
        
        self.document_loader = DocumentLoader()
        self.result_analyzer = ResultAnalyzer(self.lm)
        self.visualization = Visualization()
        self.embedding_client = EmbeddingClient()
        self.project_manager = ProjectManager()
        
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
        self.discussion_goal = ""  # FIX: goal speichern
        self.active_projects: List[str] = []
        self.debate_settings: Dict = {}
        
        self.debate_session: Optional[DebateSession] = None
        self.debate_controller: Optional[DebateController] = None
        self.current_debate_format = "classic"
        
        # FIX: Thread-Pool für lernen (statt unkontrollierte Thread-Flut)
        self._learn_executor = ThreadPoolExecutor(max_workers=5)
        self._learn_futures = []
        
        self.stats = {
            "total_contributions": 0,
            "start_time": None,
            "end_time": None,
            "current_round": 0,
            "max_rounds": 0,
            "citations_total": 0,
            "external_citations_total": 0,
            "api_retries": 0
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
    
    def load_agents_from_pool(self, agent_names: List[str]) -> bool:
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
                    agent.set_simulation(self)
                    agent.set_project_manager(self.project_manager)
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
        self.discussion_goal = goal or ""
        if self.moderator and goal:
            self.moderator.set_discussion_goal(goal)
    
    def set_active_projects(self, project_names: List[str], retrieval_k: int = 5):
        self.active_projects = project_names
        for agent in self.agents:
            agent.set_projects(project_names, retrieval_k)
        print(f"📁 Aktive Projekte: {project_names} (k={retrieval_k})")
    
    def start_discussion(self, topic: str, document: Optional[str], 
                         rounds: int = 2, use_moderator: bool = True,
                         team_mode: bool = False):
        """Legacy-Methode - wird durch start_debate ersetzt"""
        config = {
            "format": "classic",
            "rounds": rounds,
            "use_moderator": use_moderator,
            "pro_agents": [],
            "contra_agents": []
        }
        return self.start_debate(topic, document, config)
    
    def _run_debate_loop(self, topic: str, document: Optional[str], config: Dict,
                          use_moderator: bool, projects: List[str],
                          pro_agents: List[str], contra_agents: List[str]) -> Generator:
        """Haupt-Debatten-Loop (einheitlich für alle Formate)"""
        rounds = config.get("rounds", 3)
        
        # Team-Modus für Pro/Contra
        is_pro_contra = config.get("format") == "pro_contra"
        pro_names = set(pro_agents)
        contra_names = set(contra_agents)
        
        for round_num in range(rounds):
            if self.stop_event.is_set():
                break
            
            self.current_round = round_num + 1
            yield ("system", f"--- RUNDE {round_num+1}/{rounds} ---")
            yield ("round_update", f"Runde {round_num+1}/{rounds}")
            
            # Bestimme Reihenfolge: bei Pro/Contra abwechselnd, sonst zufällig
            if is_pro_contra:
                # Pro und Contra abwechselnd
                pro_list = [a for a in self.agents if a.name in pro_names]
                contra_list = [a for a in self.agents if a.name in contra_names]
                # Mischen für Abwechslung
                random.shuffle(pro_list)
                random.shuffle(contra_list)
                agents_in_order = []
                max_len = max(len(pro_list), len(contra_list))
                for i in range(max_len):
                    if i < len(pro_list):
                        agents_in_order.append(pro_list[i])
                    if i < len(contra_list):
                        agents_in_order.append(contra_list[i])
            else:
                agents_in_order = self.agents.copy()
                random.shuffle(agents_in_order)
            
            for agent in agents_in_order:
                if self.stop_event.is_set():
                    break
                
                if agent.ausgeschlossen:
                    continue
                
                # Team-Tag für Log und Prompt
                team_tag = ""
                team_name = None
                if is_pro_contra:
                    if agent.name in pro_names:
                        team_tag = "[PRO] "
                        team_name = "pro"
                    elif agent.name in contra_names:
                        team_tag = "[CONTRA] "
                        team_name = "contra"
                
                # Moderator-Frage
                if use_moderator and self.moderator and self.moderator.enabled:
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
                
                # Agent-Antwort
                answer = self._get_answer(agent, topic, document, round_num, team_name)
                
                if answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                    self.stats["total_contributions"] += 1
                    doc_citations_count = len(agent.citations_in_current_response)
                    ext_citations_count = len(agent.external_citations_in_current_response)
                    self.stats["citations_total"] += doc_citations_count
                    self.stats["external_citations_total"] += ext_citations_count
                    
                    self.db.add_contribution(
                        self.current_discussion_id, agent.agent_id, answer,
                        round_num, False, None, None,
                        {
                            "citations": doc_citations_count,
                            "external_citations": ext_citations_count,
                            "projects": projects
                        }
                    )
                    
                    # Log mit Team-Tag
                    log_entry = f"{team_tag}{agent.name}: {answer}"
                    self.discussion_log.append(log_entry)
                    self._limit_discussion_log()
                    
                    yield ("agent", agent.name, answer, agent.color, team_name)
                    yield ("agent_update", agent.name, answer)
                    yield ("contribution_added", 1)
                    
                    # FIX: Thread-Pool für lernen (statt unkontrollierte Thread-Flut)
                    self._schedule_learning(agent, answer, topic, round_num)
        
        # Zusammenfassung
        if not self.stop_event.is_set() and use_moderator and self.moderator and self.moderator.enabled:
            summary = self.moderator.summarize(
                "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
            )
            if summary and summary != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 📋 {summary}")
                self.db.end_discussion(self.current_discussion_id, summary)
    
    def _schedule_learning(self, agent: Agent, answer: str, topic: str, round_num: int):
        """Plant Lern-Jobs im Thread-Pool"""
        # Begrenze Anzahl der Lern-Jobs: nur 3 zufällige andere Agenten
        other_agents = [a for a in self.agents if a.name != agent.name and not a.ausgeschlossen]
        if not other_agents:
            return
        
        # Maximal 3 zufällige Agenten zum Lernen auswählen
        max_learners = min(3, len(other_agents))
        learners = random.sample(other_agents, max_learners)
        
        for other in learners:
            future = self._learn_executor.submit(
                self._learn_single, other, agent.name, answer, topic, agent.role
            )
            self._learn_futures.append(future)
        
        # Cleanup alte Futures
        self._learn_futures = [f for f in self._learn_futures if not f.done()]
    
    def _learn_single(self, agent: Agent, other_name: str, statement: str, topic: str, other_role: str):
        """Einzelner Lern-Job"""
        try:
            agent.learn_from(other_name, statement, topic, self.lm, other_role)
        except Exception as e:
            print(f"⚠️ Lern-Fehler bei {agent.name}: {e}")
    
    def start_debate(self, topic: str, document: Optional[str], config: Dict) -> Generator:
        """Startet eine Debatte mit dem gewählten Format"""
        self.stop_event.clear()
        self.is_running = True
        self.discussion_log = []
        self.current_topic = topic
        self.current_debate_format = config.get("format", "classic")
        self.debate_settings = config
        self.team_mode = config.get("format") == "pro_contra"
        
        projects = config.get("projects", [])
        retrieval_k = config.get("retrieval_k", 5)
        if projects:
            self.set_active_projects(projects, retrieval_k)
        
        print(f"🎭 Starte Debatte: Format={self.current_debate_format}, Thema={topic}")
        print(f"   Projekte: {projects}")
        print(f"   Moderator aktiv: {config.get('use_moderator', False)}")
        
        for agent in self.agents:
            agent.schon_gesagtes = []
            agent.wiederholungen = 0
            agent.ausgeschlossen = False
            agent.discussion_log = self.discussion_log
            agent.missing_citations_this_round = 0
        
        if self.moderator:
            self.moderator.enabled = config.get("use_moderator", True)
            self.moderator.evasions = {}
            self.moderator.abgebrochene_agenten = set()
        
        self.current_discussion_id = f"debate_{int(time.time())}"
        
        # Setze Diskussions-Ziel aus Prämisse
        premise = config.get("premise", "")
        prove_mode = config.get("prove_mode", True)
        if premise:
            self.set_discussion_purpose(f"Prämisse prüfen: {premise}", 
                                        f"Die These '{premise}' {'beweisen' if prove_mode else 'widerlegen'}")
        
        self.db.start_discussion(
            self.current_discussion_id, topic,
            f"Debatte ({self.current_debate_format})",
            self.discussion_goal or premise,
            self.moderator.name if self.moderator else None,
            {"projects": projects, "format": self.current_debate_format}
        )
        
        # Moderator-Einführung
        use_moderator = config.get("use_moderator", True) and self.moderator is not None
        if use_moderator and self.moderator:
            intro = self.moderator.introduce(topic, document, self.lm, self.stop_event)
            if intro and intro != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 {intro}")
                self.discussion_log.append(f"Moderator: {intro}")
        
        # Verwende DebateSession für komplexe Formate, sonst eigene Loop
        format_id = config.get("format", "classic")
        if format_id in ["fishbowl", "world_cafe", "delphi"]:
            # Nutze DebateSession für spezielle Formate
            debate_config = DebateConfig(
                format=format_id,
                rounds=config.get("rounds", 3),
                time_per_round=config.get("time_per_round", 0),
                thinking_time=config.get("thinking_time", 10),
                enable_moderator=use_moderator,
                enable_voting=config.get("enable_voting", False),
                enable_sanctions=config.get("enable_sanctions", False),
                inner_circle_size=config.get("inner_circle_size", 5),
                cafe_tables=config.get("cafe_tables", 3),
                rotation_rounds=config.get("rotation_rounds", 3),
                delphi_rounds=config.get("rounds", 3),
                anonymous_votes=config.get("anonymous_votes", True),
                show_statistics=config.get("show_statistics", True),
                premise=premise,
                prove_mode=prove_mode
            )
            
            # Team-Zuordnung für Pro/Contra bei premise_check
            if format_id == "premise_check":
                debate_config.pro_agents = config.get("pro_agents", [])
                debate_config.contra_agents = config.get("contra_agents", [])
            
            self.debate_session = DebateSession(topic, debate_config, self.agents, self.lm, self.db)
            for msg in self.debate_session.start():
                if msg[0] == "agent" and len(msg) > 4 and msg[4]:
                    # Team-Tag in Nachricht einbauen
                    team = msg[4]
                    team_tag = f"[{team.upper()}] "
                    msg_list = list(msg)
                    msg_list[2] = f"{team_tag}{msg[2]}"
                    msg = tuple(msg_list)
                yield msg
        else:
            # Eigene Loop für classic und pro_contra
            use_moderator = config.get("use_moderator", True) and self.moderator is not None
            projects = config.get("projects", [])
            pro_agents = config.get("pro_agents", [])
            contra_agents = config.get("contra_agents", [])
            
            for msg in self._run_debate_loop(topic, document, config, use_moderator, 
                                              projects, pro_agents, contra_agents):
                yield msg
        
        # Aufräumen
        if not self.stop_event.is_set() and use_moderator and self.moderator:
            summary = self.moderator.summarize(
                "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
            )
            if summary and summary != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 📋 {summary}")
                self.db.end_discussion(self.current_discussion_id, summary)
        else:
            self.db.end_discussion(self.current_discussion_id, "Diskussion beendet")
        
        self._cleanup_duplicate_memories()
        self.is_running = False
        self.stop_event.clear()
        
        # Thread-Pool aufräumen
        for future in self._learn_futures:
            future.cancel()
        self._learn_futures.clear()
    
    def _get_answer(self, agent, topic, document, round_num, team=None) -> str:
        """Holt Antwort von Agent mit Timeout"""
        max_retries = 3
        retry_delay = 2.0
        
        # Team-Information für Prompt
        topic_with_team = topic
        if team:
            topic_with_team = f"[TEAM {team.upper()}] {topic}"
        
        for attempt in range(max_retries):
            result_queue = queue.Queue()
            
            def _ask():
                try:
                    answer = agent.answer(topic_with_team, document, self.lm, self.stop_event, round_num)
                    result_queue.put(answer)
                except Exception as e:
                    result_queue.put(f"[Fehler: {str(e)[:30]}]")
            
            thread = threading.Thread(target=_ask)
            thread.daemon = True
            thread.start()
            thread.join(timeout=Config.TIMEOUT)
            
            if thread.is_alive():
                print(f"⚠️ Timeout bei {agent.name} (Versuch {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "[Timeout]"
            
            try:
                result = result_queue.get_nowait()
                if result.startswith("[Fehler") and attempt < max_retries - 1:
                    print(f"⚠️ Fehler bei {agent.name}: {result}, Retry {attempt+1}")
                    self.stats["api_retries"] += 1
                    time.sleep(retry_delay)
                    continue
                return result
            except queue.Empty:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "[Fehler]"
        
        return "[Fehler: Max Retries]"
    
    def _learn_async(self, agent, other_name, statement, topic, other_role):
        """Legacy - wird durch _schedule_learning ersetzt"""
        pass
    
    def _cleanup_duplicate_memories(self):
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            # Verbesserte Query mit Hashing für bessere Performance
            cursor.execute("""
                DELETE FROM memory_crystals 
                WHERE crystal_id NOT IN (
                    SELECT MIN(crystal_id) 
                    FROM memory_crystals 
                    GROUP BY substr(fact, 1, 500)
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
    
    def run_analysis(self, job: AnalysisJob, progress_callback: Callable = None) -> AnalysisJob:
        return self.task_manager.run_analysis(job, progress_callback)
    
    def analyze_results(self, contributions: List[Dict] = None) -> Dict:
        if contributions is None:
            contributions = []
            for line in self.discussion_log:
                # Entferne Team-Tags für Analyse
                clean_line = re.sub(r'^\[(PRO|CONTRA)\] ', '', line)
                if ": " in clean_line:
                    parts = clean_line.split(": ", 1)
                    if len(parts) == 2:
                        contributions.append({
                            "agent": parts[0],
                            "content": parts[1],
                            "round": self.current_round
                        })
        
        return self.result_analyzer.generate_full_report(
            contributions, self.agents, self.current_topic
        )
    
    def load_document(self, source: str, source_type: str = "auto") -> Dict:
        return self.document_loader.load_document(source, source_type)
    
    def load_multiple_documents(self, sources: List[Dict]) -> Dict:
        return self.document_loader.load_multiple(sources)
    
    def add_document_to_project(self, project_name: str, source: str, source_type: str = "auto") -> Dict:
        return self.project_manager.add_document_to_project(project_name, source, source_type)
    
    def add_folder_to_project(self, project_name: str, folder_path: str) -> List[Dict]:
        return self.project_manager.add_folder_to_project(project_name, folder_path)
    
    def create_project(self, name: str) -> Dict:
        project = self.project_manager.create_project(name)
        return project.metadata
    
    def get_project_context(self, query: str, projects: List[str] = None, k: int = 5) -> str:
        return self.project_manager.get_context(query, projects, k)
    
    def search_projects(self, query: str, projects: List[str] = None, k: int = 5) -> List[Dict]:
        return self.project_manager.search_projects(query, projects, k)
    
    def list_projects(self) -> List[Dict]:
        return self.project_manager.list_projects()
    
    def get_citation_stats(self, agent_id: str = None) -> Dict:
        return self.db.get_citation_stats(agent_id)
    
    def get_citation_leaderboard(self, limit: int = 10) -> List[Dict]:
        return self.db.get_citation_leaderboard(limit)
    
    def get_external_citation_leaderboard(self, limit: int = 10) -> List[Dict]:
        return self.db.get_external_citation_leaderboard(limit)
    
    def get_visualization(self):
        return self.visualization
    
    def get_network_data(self) -> Tuple[List[Dict], List[Dict]]:
        nodes = []
        edges = []
        
        for agent in self.agents:
            nodes.append({
                "id": agent.agent_id,
                "name": agent.name,
                "color": agent.color,
                "size": 500 + agent.experience_points / 100
            })
        
        for agent in self.agents:
            influences = self.db.get_influences(agent.agent_id)
            for inf in influences.get("given", []):
                edges.append({
                    "from": agent.agent_id,
                    "to": inf.get("to"),
                    "strength": inf.get("strength", 0.5)
                })
        
        return nodes, edges
    
    def search_pool(self, query: str, limit: int = 100) -> List[Dict]:
        return self.agent_factory.search_pool(query, limit)
    
    def get_random_from_pool(self, count: int, filters: Dict = None) -> List[Dict]:
        return self.agent_factory.get_random_from_pool(count, filters)
    
    def get_pool_stats(self) -> Dict:
        return self.db.get_pool_stats()
    
    def get_db_info(self) -> Dict:
        try:
            stats = self.db.get_stats()
            stats["active_projects"] = len(self.active_projects)
            stats["projects_list"] = self.active_projects
            stats["api_retries"] = self.stats.get("api_retries", 0)
            stats["citations_total"] = self.stats.get("citations_total", 0)
            stats["external_citations_total"] = self.stats.get("external_citations_total", 0)
            return stats
        except Exception as e:
            print(f"⚠️ get_db_info Fehler: {e}")
            return {
                "total_agents": 0, "active_agents": 0, "kg_nodes": 0, "kg_edges": 0,
                "topics": 0, "teams": 0, "prognoses": 0, "discussions": 0,
                "contributions": 0, "projects": 0, "project_documents": 0,
                "project_chunks": 0, "citations": 0, "external_citations": 0,
                "avg_fachwissen": 0, "avg_kommunikation": 0, "avg_analyse": 0,
                "ranks": {}, "error": str(e)
            }
    
    def backup_db(self) -> str:
        return self.db.backup()
    
    def reset_db(self) -> bool:
        self.db.backup()
        self.db = SynthAgoraDB()
        self.knowledge_graph = KnowledgeGraph()
        self.project_manager = ProjectManager()
        return True
    
    def stop(self):
        self.stop_event.set()
        self.is_running = False
        if self.debate_session:
            self.debate_session.stop()
        self.lm.cancel_all()
        # Thread-Pool aufräumen
        for future in self._learn_futures:
            future.cancel()
        self._learn_futures.clear()