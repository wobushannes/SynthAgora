#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════╗
║  🐟 SynthAgora - Mit GEDÄCHTNIS & KNOWLEDGE GRAPH                  ║
║  Agenten lernen voneinander - THEMENUNABHÄNGIG!                        ║
║  NEU: Externe Quellen mit INTELLIGENTER ENTSCHEIDUNG!                  ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import requests
import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import queue
import re
import os
import glob
import sys
import subprocess
import urllib.parse

# Config importieren
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from includes.config import Config

# ===================== EXTERNE QUELLEN CLIENT =====================
class ExternalSourceClient:
    """Verwaltet externe, kostenfreie Quellen für die Recherche"""
    
    def __init__(self):
        self.sources = {
            "openwebsearch": {
                "name": "Open-WebSearch",
                "enabled": False,
                "description": "Mehrere Suchmaschinen (Bing, DuckDuckGo, Baidu, Exa, Brave)",
                "command": "npx open-websearch@latest",
                "port": 3000,
                "url": "http://localhost:3000/search",
                "needs_server": True,
                "server_process": None
            },
            "wikipedia": {
                "name": "Wikipedia",
                "enabled": False,
                "description": "Enzyklopädisches Wissen, Definitionen, Fakten",
                "api_url": "https://de.wikipedia.org/w/api.php",
                "needs_server": False
            },
            "arxiv": {
                "name": "arXiv",
                "enabled": False,
                "description": "Wissenschaftliche Paper (Physik, Mathematik, Informatik)",
                "api_url": "http://export.arxiv.org/api/query",
                "needs_server": False
            },
            "duckduckgo": {
                "name": "DuckDuckGo (Light)",
                "enabled": False,
                "description": "Einfache HTML-Suche ohne API-Key",
                "url": "https://html.duckduckgo.com/html/",
                "needs_server": False
            }
        }
        self.use_external = False
        self.search_timeout = 10
    
    def toggle_source(self, source_key: str, enabled: bool):
        """Aktiviert/deaktiviert eine Quelle"""
        if source_key in self.sources:
            self.sources[source_key]["enabled"] = enabled
            
            # Open-WebSearch Server steuern
            if source_key == "openwebsearch":
                if enabled and not self.sources[source_key]["server_process"]:
                    self._start_openwebsearch()
                elif not enabled and self.sources[source_key]["server_process"]:
                    self._stop_openwebsearch()
    
    def _start_openwebsearch(self):
        """Startet den Open-WebSearch Server"""
        try:
            cmd = self.sources["openwebsearch"]["command"].split()
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.sources["openwebsearch"]["server_process"] = process
            print("✅ Open-WebSearch Server gestartet")
            time.sleep(2)  # Kurz warten, bis Server hochgefahren
        except Exception as e:
            print(f"❌ Fehler beim Starten von Open-WebSearch: {e}")
    
    def _stop_openwebsearch(self):
        """Stoppt den Open-WebSearch Server"""
        process = self.sources["openwebsearch"]["server_process"]
        if process:
            process.terminate()
            process.wait()
            self.sources["openwebsearch"]["server_process"] = None
            print("✅ Open-WebSearch Server gestoppt")
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Durchsucht alle aktivierten Quellen und gibt kombinierte Ergebnisse zurück"""
        if not self.use_external:
            return []
        
        results = []
        
        # Open-WebSearch
        if self.sources["openwebsearch"]["enabled"]:
            try:
                response = requests.get(
                    self.sources["openwebsearch"]["url"],
                    params={"q": query, "num": max_results},
                    timeout=self.search_timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("results", [])[:max_results]:
                        results.append({
                            "source": "Open-WebSearch",
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("snippet", ""),
                            "relevance": 1.0
                        })
            except Exception as e:
                print(f"⚠️ Open-WebSearch Fehler: {e}")
        
        # Wikipedia
        if self.sources["wikipedia"]["enabled"]:
            try:
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": max_results
                }
                response = requests.get(
                    self.sources["wikipedia"]["api_url"],
                    params=params,
                    timeout=self.search_timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("query", {}).get("search", [])[:max_results]:
                        results.append({
                            "source": "Wikipedia",
                            "title": item.get("title", ""),
                            "url": f"https://de.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', ''))}",
                            "snippet": item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
                            "relevance": 0.9
                        })
            except Exception as e:
                print(f"⚠️ Wikipedia Fehler: {e}")
        
        # arXiv
        if self.sources["arxiv"]["enabled"]:
            try:
                params = {
                    "search_query": f"all:{query}",
                    "max_results": max_results
                }
                response = requests.get(
                    self.sources["arxiv"]["api_url"],
                    params=params,
                    timeout=self.search_timeout
                )
                if response.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(response.text)
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    for entry in root.findall("atom:entry", ns)[:max_results]:
                        title = entry.find("atom:title", ns).text if entry.find("atom:title", ns) is not None else ""
                        summary = entry.find("atom:summary", ns).text if entry.find("atom:summary", ns) is not None else ""
                        url = entry.find("atom:id", ns).text if entry.find("atom:id", ns) is not None else ""
                        results.append({
                            "source": "arXiv",
                            "title": title,
                            "url": url,
                            "snippet": summary[:200] + "..." if len(summary) > 200 else summary,
                            "relevance": 0.8
                        })
            except Exception as e:
                print(f"⚠️ arXiv Fehler: {e}")
        
        # DuckDuckGo Light (HTML-Suche)
        if self.sources["duckduckgo"]["enabled"]:
            try:
                response = requests.post(
                    self.sources["duckduckgo"]["url"],
                    data={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=self.search_timeout
                )
                if response.status_code == 200:
                    # Einfaches Parsen der HTML-Ergebnisse
                    import re
                    results_html = response.text
                    # Sehr einfaches Parsen - in Produktion besser BeautifulSoup nutzen
                    for i, match in enumerate(re.finditer(r'<a rel="nofollow" href="([^"]+)"[^>]*>([^<]+)</a>', results_html)):
                        if i >= max_results:
                            break
                        url = match.group(1)
                        title = match.group(2)
                        results.append({
                            "source": "DuckDuckGo",
                            "title": title,
                            "url": url,
                            "snippet": "",
                            "relevance": 0.7
                        })
            except Exception as e:
                print(f"⚠️ DuckDuckGo Fehler: {e}")
        
        # Nach Relevanz sortieren
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results
    
    def format_results(self, results: List[Dict]) -> str:
        """Formatiert Suchergebnisse für die Anzeige"""
        if not results:
            return ""
        
        formatted = "\n📚 EXTERNE RECHERCHE:\n"
        for i, r in enumerate(results[:3], 1):
            formatted += f"\n{i}. [{r['source']}] {r['title']}\n"
            formatted += f"   {r['url']}\n"
            if r['snippet']:
                formatted += f"   {r['snippet'][:150]}...\n"
        return formatted

# ===================== LM STUDIO / OLLAMA CLIENT =====================
class LLMClient:
    def __init__(self):
        self.provider = Config.LM_PROVIDER
        self.session = requests.Session()
        self.stats = {"calls": 0, "errors": 0}
        
    def test(self) -> Tuple[bool, str]:
        """Testet die Verbindung zum aktiven Provider"""
        try:
            if self.provider == "lmstudio":
                return True, f"LM Studio: {Config.LM_STUDIO_URL} (bereit)"
            elif self.provider == "ollama":
                return True, f"Ollama: {Config.OLLAMA_MODEL} (bereit)"
            elif self.provider == "openai":
                return True, f"OpenAI (BETA): {Config.OPENAI_MODEL} (Endpoint konfiguriert)"
            elif self.provider == "grok":
                return True, f"Grok (BETA): {Config.GROK_MODEL} (Endpoint konfiguriert)"
            elif self.provider == "claude":
                return True, f"Claude (BETA): {Config.CLAUDE_MODEL} (Endpoint konfiguriert)"
            return False, f"Provider {self.provider} nicht konfiguriert"
        except Exception as e:
            return False, f"Fehler: {str(e)}"
    
    def ask(self, prompt: str, system: str = None, stop_event: threading.Event = None) -> str:
        self.stats["calls"] += 1
        
        try:
            if stop_event and stop_event.is_set():
                return "[ABGEBROCHEN]"
            
            if self.provider == "lmstudio":
                return self._ask_lmstudio(prompt, system, stop_event)
            elif self.provider == "ollama":
                return self._ask_ollama(prompt, system, stop_event)
            elif self.provider == "openai":
                return self._ask_beta("OpenAI", Config.OPENAI_URL, Config.OPENAI_MODEL, prompt, system)
            elif self.provider == "grok":
                return self._ask_beta("Grok", Config.GROK_URL, Config.GROK_MODEL, prompt, system)
            elif self.provider == "claude":
                return self._ask_beta("Claude", Config.CLAUDE_URL, Config.CLAUDE_MODEL, prompt, system)
            else:
                return f"[Fehler: Unbekannter Provider {self.provider}]"
                
        except Exception as e:
            self.stats["errors"] += 1
            return f"[Fehler: {str(e)[:30]}]"
    
    def _ask_lmstudio(self, prompt: str, system: str = None, stop_event=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        r = self.session.post(Config.LM_STUDIO_URL, json={
            "messages": messages,
            "max_tokens": Config.MAX_TOKENS,
            "temperature": Config.TEMPERATURE,
            "stop": ["\n\n", "User:", "Assistant:"]
        }, timeout=Config.TIMEOUT)
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        text = r.json()["choices"][0]["message"]["content"]
        text = re.sub(r'(?i)(thinking|thought).*?(\n|$)', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."
    
    def _ask_ollama(self, prompt: str, system: str = None, stop_event=None) -> str:
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
                "num_predict": Config.MAX_TOKENS
            }
        }, timeout=Config.TIMEOUT)
        
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        
        text = r.json()["message"]["content"]
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."
    
    def _ask_beta(self, name: str, url: str, model: str, prompt: str, system: str = None) -> str:
        """Beta-Provider - zeigt an, dass ein Key fehlt, aber Endpoint korrekt wäre"""
        system_info = f" mit System: {system[:50]}..." if system else ""
        return (f"[{name} BETA - Kein API-Key konfiguriert]\n"
                f"Endpoint: {url}\n"
                f"Modell: {model}\n"
                f"Prompt: {prompt[:100]}...{system_info}\n\n"
                f"Würde hier eine echte API-Anfrage stellen.\n"
                f"Konfiguration in config.json möglich.")

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

# ===================== KNOWLEDGE GRAPH =====================
class KnowledgeGraph:
    def __init__(self):
        self.graph_file = f"{Config.KNOWLEDGE_FOLDER}/knowledge_graph.json"
        self.graph = self.load_graph()
        
    def load_graph(self) -> dict:
        try:
            with open(self.graph_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "nodes": {},
                "edges": [],
                "topics": {},
                "influences": {}
            }
    
    def save_graph(self):
        try:
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
                "connections": 0
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

# ===================== AGENT =====================
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
        
        self.knowledge_graph = knowledge_graph
        self.external_client = external_client
        self.agent_id = f"agent_{self.name.lower().replace(' ', '_')}"
        self.discussion_log = None
        
        self.memory_file = f"{Config.MEMORY_FOLDER}/{self.name}.json"
        self.load_memory()
        
        self.knowledge_graph.add_node(
            self.agent_id,
            "agent",
            {"name": self.name, "role": self.role, "personality": self.personality}
        )
        
    def load_memory(self):
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                self.learned_facts = memory.get('facts', [])
                self.known_positions = memory.get('positions', {})
                self.perspectives = memory.get('perspectives', [])
                self.position_history = memory.get('position_history', [])
        except:
            self.learned_facts = []
            self.known_positions = {}
            self.perspectives = []
            self.position_history = []
    
    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'facts': self.learned_facts[-100:],
                    'positions': self.known_positions,
                    'perspectives': self.perspectives[-50:],
                    'position_history': self.position_history[-50:],
                }, f, indent=2, ensure_ascii=False)
        except:
            pass
    
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
        
        # FIX: Prüfe ob insight gültig ist
        if insight and insight not in ["[ABGEBROCHEN]", "...", ""] and len(insight) > 5:
            if insight not in self.learned_facts:
                self.learned_facts.append(insight)
                fact_id = f"fact_{len(self.learned_facts)}_{int(time.time())}"
                self.knowledge_graph.add_node(fact_id, "fact", {"text": insight, "topic": topic, "source": speaker})
                self.knowledge_graph.add_edge(self.agent_id, fact_id, "gelernt", 1.0)
                self.knowledge_graph.add_edge(speaker_id, fact_id, "sagte", 0.8)
                self.knowledge_graph.add_to_topic(topic, fact_id)
                
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
    
    def search_external(self, query: str) -> str:
        """Führt externe Recherche durch und gibt formatierte Ergebnisse zurück"""
        if not self.external_client.use_external:
            return ""
        
        results = self.external_client.search(query)
        return self.external_client.format_results(results)
    
    def decide_to_search(self, text: str, lm: LLMClient) -> bool:
        """Entscheidet intelligent, ob eine externe Suche sinnvoll ist"""
        
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
        return "JA" in result.upper()
    
    def answer(self, topic: str, document: Optional[str], 
               lm: LLMClient, stop_event: threading.Event = None, round_num: int = 0) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
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
                change_prompt = f"""Du bist {self.name}, {self.role}. Persönlichkeit: {self.personality}

Deine bisherige Position zu '{topic}': {self.current_position or 'unentschieden'}

Andere haben gesagt:
{chr(10).join(fremde_aussagen[-3:])}

Hat dich ein Argument ÜBERZEUGT? Wenn JA: Antworte mit "JA:[JA/NEIN] weil..." Wenn NEIN: Antworte "NEIN" """

                change_result = lm.ask(change_prompt, f"Du bist {self.name}.", stop_event)
                if change_result and "JA:" in change_result:
                    alte_position = self.current_position
                    if "JA" in change_result.upper() and "NEIN" not in change_result.upper()[:10]:
                        self.current_position = "JA"
                    elif "NEIN" in change_result.upper()[:10]:
                        self.current_position = "NEIN"
                    
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
            if self.decide_to_search(search_query, lm):
                external_info = self.search_external(search_query)
                if external_info:
                    print(f"🌐 {self.name} sucht extern: {search_query[:50]}...")
        
        # THEMENUNABHÄNGIGER Prompt - KEINE Texterwähnung wenn kein Dokument!
        if document:
            base_prompt = f"""Du bist {self.name}, {self.role}. Charakter: {self.personality}
Bildung: {self.education} Hintergrund: {self.background}

Aufgabe: Analysiere und bewerte den folgenden Text aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und nenne Beispiele aus dem Text.
Deine Antwort sollte 2-3 Sätze lang sein und klare Handlungsempfehlungen geben.

Text:
{document}

Antworte:"""
        else:
            base_prompt = f"""Du bist {self.name}, {self.role}. Charakter: {self.personality}
Bildung: {self.education} Hintergrund: {self.background}

Thema der Diskussion: {topic}

Aufgabe: Diskutiere das Thema aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und bringe deine Argumente ein.
Deine Antwort sollte 2-3 Sätze lang sein.

Antworte:"""
        
        if knowledge or external_info:
            if document:
                base_prompt = f"""Du bist {self.name}, {self.role}. Charakter: {self.personality}

DEIN WISSEN (aus früheren Diskussionen):
{knowledge}

{external_info}

Aufgabe: Analysiere und bewerte den folgenden Text aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und nenne Beispiele aus dem Text.
Deine Antwort sollte 2-3 Sätze lang sein und klare Handlungsempfehlungen geben.

Text:
{document}

Antworte:"""
            else:
                base_prompt = f"""Du bist {self.name}, {self.role}. Charakter: {self.personality}

DEIN WISSEN (aus früheren Diskussionen):
{knowledge}

{external_info}

Thema der Diskussion: {topic}

Aufgabe: Diskutiere das Thema aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und bringe deine Argumente ein.
Deine Antwort sollte 2-3 Sätze lang sein.

Antworte:"""
        
        if self.schon_gesagtes:
            history = "\n".join([f"- {b}" for b in self.schon_gesagtes[-3:]])
            base_prompt += f"\n\nDeine letzten Beiträge:\n{history}\nWICHTIG: Wiederhole dich NICHT!"
        
        response = lm.ask(base_prompt, f"Du bist {self.name}.", stop_event)
        
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
            return response
        else:
            # Fallback, wenn Antwort zu kurz oder leer
            if document:
                fallback = f"Aus meiner Perspektive als {self.role} sehe hier deutliches Optimierungspotential. Der Text ist zu oberflächlich und benötigt mehr Substanz."
            else:
                fallback = f"Als {self.role} finde ich das Thema {topic} sehr relevant. Meiner Meinung nach sollte man hier besonders auf {self.fears[0] if self.fears else 'die langfristigen Folgen'} achten."
            self.schon_gesagtes.append(fallback)
            self.last_response = fallback
            return fallback
    
    def react_to(self, speaker: str, statement: str, topic: str,
                 lm: LLMClient, stop_event: threading.Event = None) -> str:
        if stop_event and stop_event.is_set():
            return "[ABGEBROCHEN]"
        if self.ausgeschlossen:
            return "[AUSGESCHLOSSEN]"
        
        # INTELLIGENTE Entscheidung für externe Recherche bei Reaktionen
        external_info = ""
        if self.external_client.use_external:
            if self.decide_to_search(statement, lm):
                external_info = self.search_external(statement)
                if external_info:
                    print(f"🌐 {self.name} sucht extern (Reaktion): {statement[:50]}...")
        
        # Längerer Prompt für ausführlichere Reaktionen
        prompt = f"""Du bist {self.name}, {self.role}. Deine Persönlichkeit: {self.personality}

{speaker} hat gerade gesagt: "{statement}"

Thema der Diskussion: {topic}

{external_info}

Aufgabe: Reagiere DIREKT auf {speaker}'s Aussage aus deiner fachlichen Perspektive. 
Sei spezifisch, konkret und nenne Beispiele oder Argumente.
Deine Antwort sollte 2-3 Sätze lang sein.

Antworte:"""

        response = lm.ask(prompt, f"Du bist {self.name}.", stop_event)
        
        # Stelle sicher, dass wir eine vollständige Antwort bekommen
        if response and response != "[ABGEBROCHEN]" and len(response) > 10:
            self.schon_gesagtes.append(f"[Reaktion] {response}")
            self.last_response = response
            self.knowledge_graph.add_to_topic(topic, self.agent_id)
            speaker_id = f"agent_{speaker.lower().replace(' ', '_')}"
            self.knowledge_graph.add_to_topic(topic, speaker_id)
            return response
        else:
            # Fallback, wenn Antwort zu kurz ist
            fallback = f"Ich stimme {speaker} zu, dass hier noch Diskussionsbedarf besteht. Besonders die langfristigen Auswirkungen sind wichtig."
            self.schon_gesagtes.append(f"[Reaktion] {fallback}")
            self.last_response = fallback
            return fallback

# ===================== MODERATOR =====================
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
        prompt = f"""Du bist {self.name}. Thema: {topic}. Stelle {agent_name} eine präzise Frage zum Thema. Max 2 Sätze."""
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
    
    def summarize(self, discussion: str, topic: str, lm: LLMClient, stop_event=None) -> str:
        if not self.enabled:
            return ""
        prompt = f"""Du bist {self.name}. Thema: {topic}. Fasse Positionen in 2-3 Sätzen zusammen."""
        return lm.ask(prompt, f"Du bist {self.name}.", stop_event)

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
    
    def load_agents(self, filepath: str) -> bool:
        try:
            data = FileManager().load_json_file(filepath)
            if not data:
                return False
            self.config_name = data.get("name", "Unbekannt")
            self.agents = []
            for agent_data in data["agents"]:
                agent = Agent(agent_data, self.knowledge_graph, self.external)
                self.agents.append(agent)
            return True
        except:
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
    
    def start_discussion(self, topic: str, document: Optional[str], 
                         rounds: int = 2, use_moderator: bool = True):
        # Reset für neue Diskussion
        self.stop_event.clear()
        self.is_running = True
        self.discussion_log = []
        self.current_topic = topic
        self.current_round = 0
        self.max_rounds = rounds
        
        print(f"\n🔵 STARTE DISKUSSION: {rounds} Runden")
        
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
        
        if use_moderator and self.moderator:
            intro = self.moderator.introduce(topic, document, self.lm, self.stop_event)
            if intro and intro != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 {intro}")
                self.discussion_log.append(f"Moderator: {intro}")
                time.sleep(0.5)
        else:
            yield ("system", "📢 Diskussion ohne Moderator gestartet")
            self.discussion_log.append("System: Diskussion ohne Moderator")
        
        for round_num in range(rounds):
            if self.stop_event.is_set():
                print(f"⛔ RUNDE {round_num+1}: STOP erkannt - breche ab")
                break
            
            self.current_round = round_num + 1
            yield ("system", f"--- RUNDE {round_num+1}/{rounds} ---")
            
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
                        
                        if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                            yield ("system", f"⛔ {agent.name} ausgeschlossen!")
                            self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                        elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                            yield ("agent", agent.name, answer, agent.color)
                            self.discussion_log.append(f"{agent.name}: {answer}")
                            time.sleep(0.3)
                            
                            intervention, abbrechen = self.moderator.intervene(
                                agent.name, answer, topic, self.lm, self.stop_event
                            )
                            if intervention:
                                yield ("moderator", f"🎭 ⚠️ {intervention}")
                                self.discussion_log.append(f"Moderator: {intervention}")
                                if abbrechen:
                                    yield ("system", f"⛔ {agent.name} ausgeschlossen!")
                                    self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                
                else:
                    # OHNE MODERATOR - Agent diskutiert
                    answer = agent.answer(topic, document, self.lm, self.stop_event, round_num)
                    if answer == "[WEGEN WIEDERHOLUNG AUSGESCHLOSSEN]":
                        yield ("system", f"⛔ {agent.name} ausgeschlossen!")
                        self.discussion_log.append(f"System: {agent.name} ausgeschlossen")
                    elif answer and answer not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                        yield ("agent", agent.name, answer, agent.color)
                        self.discussion_log.append(f"{agent.name}: {answer}")
                        time.sleep(0.3)
                
                # REAKTIONEN der ANDEREN
                if round_num < rounds - 1 and not self.stop_event.is_set() and len(self.agents) > 1:
                    for other in self.agents:
                        if (other.name != agent.name and not other.ausgeschlossen and 
                            not self.stop_event.is_set()):
                            
                            reaction = other.react_to(agent.name, agent.last_response, topic,
                                                      self.lm, self.stop_event)
                            if reaction and reaction not in ["[ABGEBROCHEN]", "[AUSGESCHLOSSEN]"]:
                                yield ("agent", other.name, f"[Reaktion] {reaction}", other.color)
                                self.discussion_log.append(f"{other.name} reagiert: {reaction}")
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
        
        if not self.stop_event.is_set() and use_moderator and self.moderator:
            summary = self.moderator.summarize(
                "\n".join(self.discussion_log[-10:]), topic, self.lm, self.stop_event
            )
            if summary and summary != "[ABGEBROCHEN]":
                yield ("moderator", f"🎭 📋 {summary}")
        
        # Simulation ordentlich beenden
        self.is_running = False
        self.stop_event.clear()
        print("✅ DISKUSSION BEENDET - Reset durchgeführt")

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
            ("OpenAI (BETA)", "openai"),
            ("Grok (BETA)", "grok"),
            ("Claude (BETA)", "claude")
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
        
        # Beta Provider Info
        beta_frame = tk.LabelFrame(self.frame, text="🤖 Beta Provider (ohne API-Key)", 
                                   bg=Config.BG_PANEL, fg=Config.FG,
                                   font=("Segoe UI", 12, "bold"))
        beta_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # OpenAI
        tk.Label(beta_frame, text="OpenAI:", bg=Config.BG_PANEL, fg=Config.BETA,
                font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        tk.Label(beta_frame, text=Config.OPENAI_URL, bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        tk.Label(beta_frame, text=f"Modell: {Config.OPENAI_MODEL}", bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).grid(row=0, column=2, sticky=tk.W, padx=10, pady=5)
        
        # Grok
        tk.Label(beta_frame, text="Grok:", bg=Config.BG_PANEL, fg=Config.BETA,
                font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        tk.Label(beta_frame, text=Config.GROK_URL, bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        tk.Label(beta_frame, text=f"Modell: {Config.GROK_MODEL}", bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).grid(row=1, column=2, sticky=tk.W, padx=10, pady=5)
        
        # Claude
        tk.Label(beta_frame, text="Claude:", bg=Config.BG_PANEL, fg=Config.BETA,
                font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        tk.Label(beta_frame, text=Config.CLAUDE_URL, bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        tk.Label(beta_frame, text=f"Modell: {Config.CLAUDE_MODEL}", bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9)).grid(row=2, column=2, sticky=tk.W, padx=10, pady=5)
        
        tk.Label(beta_frame, text="Hinweis: Diese Provider benötigen API-Keys in der config.json", 
                bg=Config.BG_PANEL, fg=Config.WARNING,
                font=("Segoe UI", 9, "italic")).grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=10, pady=10)
        
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
        self._setup_ui()
    
    def _setup_ui(self):
        # Alte Widgets löschen
        for widget in self.frame.winfo_children():
            widget.destroy()
        
        # Haupt-Enable
        main_frame = tk.LabelFrame(self.frame, text="🌐 Externe Recherche (kostenfrei)", 
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
        
        tk.Label(main_frame, text="Aktivierte Quellen werden bei jeder Antwort durchsucht.",
                bg=Config.BG_PANEL, fg=Config.FG_DIM,
                font=("Segoe UI", 9, "italic")).pack(anchor=tk.W, padx=10, pady=(0,10))
        
        # Quellen
        sources_frame = tk.LabelFrame(self.frame, text="📚 Verfügbare Quellen", 
                                      bg=Config.BG_PANEL, fg=Config.FG,
                                      font=("Segoe UI", 12, "bold"))
        sources_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.source_vars = {}
        row = 0
        for key, source in self.sim.external.sources.items():
            # Checkbox
            var = tk.BooleanVar(value=source["enabled"])
            self.source_vars[key] = var
            
            cb = tk.Checkbutton(sources_frame, text=source["name"], variable=var,
                               bg=Config.BG_PANEL, fg=Config.FG,
                               selectcolor=Config.BG_PANEL,
                               font=("Segoe UI", 10, "bold"),
                               command=lambda k=key: self.toggle_source(k))
            cb.grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            
            # Beschreibung
            tk.Label(sources_frame, text=source["description"],
                    bg=Config.BG_PANEL, fg=Config.FG_DIM,
                    font=("Segoe UI", 9)).grid(row=row, column=1, sticky=tk.W, padx=10, pady=5)
            
            # Status
            status_text = "✅ Aktiv" if source["enabled"] else "⏸️ Inaktiv"
            status_color = Config.SUCCESS if source["enabled"] else Config.FG_DIM
            tk.Label(sources_frame, text=status_text,
                    bg=Config.BG_PANEL, fg=status_color,
                    font=("Segoe UI", 9)).grid(row=row, column=2, sticky=tk.W, padx=10, pady=5)
            
            row += 1
        
        # Open-WebSearch Hinweis
        tk.Label(sources_frame, 
                text="Hinweis: Open-WebSearch benötigt 'npx open-websearch@latest' (wird automatisch gestartet)",
                bg=Config.BG_PANEL, fg=Config.WARNING,
                font=("Segoe UI", 9, "italic")).grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=10, pady=10)
        
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

# ===================== GUI =====================
class SynthAgoraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🐟 SynthAgora - Mit Knowledge Graph & Externen Quellen")
        self.root.geometry("1400x900")
        self.root.configure(bg=Config.BG_MAIN)
        
        self.fm = FileManager()
        self.sim = Simulation()
        self.msg_queue = queue.Queue()
        
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
        
        # TAB 5: KONFIGURATION (LLM Provider)
        self.config_tab = ConfigTab(self.notebook, self.sim)
        self.notebook.add(self.config_tab.frame, text="⚙️ LLM Config")
        
        # TAB 6: EXTERNE QUELLEN
        self.external_tab = ExternalSourcesTab(self.notebook, self.sim)
        self.notebook.add(self.external_tab.frame, text="🌐 Externe Quellen")
        
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
        
        # Externe Quellen Option in der Debatte
        external_frame = tk.Frame(self.tab_main, bg=Config.BG_MAIN)
        external_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.use_external_debate_var = tk.BooleanVar(value=False)
        external_check = tk.Checkbutton(external_frame, text="🌐 Externe Quellen in dieser Debatte verwenden", 
                                       variable=self.use_external_debate_var,
                                       bg=Config.BG_MAIN, fg=Config.FG,
                                       selectcolor=Config.BG_MAIN,
                                       font=("Segoe UI", 11))
        external_check.pack(side=tk.LEFT, padx=5)
        
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
        
        self.start_btn = self._create_button(self.tab_main, "🎬 DISKUSSION STARTEN", Config.BG_BUTTON, self.start_discussion)
        self.start_btn.pack(pady=20)
    
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
        self._create_button(toolbar, "📚 Topics anzeigen", Config.BG_INPUT, self.show_topics).pack(side=tk.LEFT, padx=5)
        self._create_button(toolbar, "🎯 Influences", Config.BG_INPUT, self.show_influences).pack(side=tk.LEFT, padx=5)
        
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
            for agent in self.sim.agents:
                if agent.learned_facts:
                    self._add_to_chat(f"   📚 {agent.name} kennt {len(agent.learned_facts)} Fakten")
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
        
        response_frame = tk.Frame(content, bg=agent.color)
        response_frame.pack(fill=tk.X, padx=10, pady=8)
        response_label = tk.Label(response_frame, text="Bereit...", bg=agent.color, fg="#000000", font=("Segoe UI", 9), wraplength=700, padx=8, pady=5)
        response_label.pack(fill=tk.X)
        card.response_label = response_label
    
    def show_knowledge_graph(self):
        kg = self.sim.knowledge_graph
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "🔮 KNOWLEDGE GRAPH\n" + "="*60 + "\n\n")
        self.knowledge_text.insert(tk.END, f"📌 KNOTEN ({len(kg.graph['nodes'])}):\n")
        for node_id, node in list(kg.graph['nodes'].items())[:20]:
            t = node['type']
            p = node.get('properties', {})
            if t == "agent":
                self.knowledge_text.insert(tk.END, f"  👤 {p.get('name', node_id)} ({t})\n")
            elif t == "concept":
                self.knowledge_text.insert(tk.END, f"  💡 {p.get('name', node_id)} ({t})\n")
            elif t == "fact":
                text = p.get('text', '')[:50]
                self.knowledge_text.insert(tk.END, f"  📄 {text}... ({t})\n")
            else:
                self.knowledge_text.insert(tk.END, f"  • {node_id} ({t})\n")
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
        
        agent_c = sum(1 for n in nodes.values() if n['type'] == 'agent')
        concept_c = sum(1 for n in nodes.values() if n['type'] == 'concept')
        fact_c = sum(1 for n in nodes.values() if n['type'] == 'fact')
        
        self.knowledge_text.insert(tk.END, "📊 KNOWLEDGE GRAPH STATISTIK\n" + "="*60 + "\n\n")
        self.knowledge_text.insert(tk.END, f"📌 Gesamtknoten: {len(nodes)}\n")
        self.knowledge_text.insert(tk.END, f"  👤 Agenten: {agent_c}\n")
        self.knowledge_text.insert(tk.END, f"  💡 Konzepte: {concept_c}\n")
        self.knowledge_text.insert(tk.END, f"  📄 Fakten: {fact_c}\n\n")
        self.knowledge_text.insert(tk.END, f"🔗 Gesamtbeziehungen: {len(edges)}\n\n")
        self.knowledge_text.insert(tk.END, f"📚 Themen-Cluster: {len(topics)}\n")
        self.knowledge_text.insert(tk.END, f"🎯 Einflüsse: {len(influences)} Agenten haben andere beeinflusst\n")
    
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
        
        # Externe Quellen für diese Debatte aktivieren/deaktivieren
        self.sim.external.use_external = self.use_external_debate_var.get()
        
        topic = self.topic_entry.get().strip()
        if not topic:
            messagebox.showwarning("Achtung", "Bitte ein Thema eingeben!")
            return
            
        document = self.doc_text.get(1.0, tk.END).strip()
        # Dokument ist OPTIONAL! Keine Warnung wenn leer.
        
        rounds = int(self.rounds_var.get())
        
        self.start_btn.config(state=tk.DISABLED)
        self._enable_stop_button()
        self.round_label.config(text=f"Runde: 0/{rounds}")
        
        self._add_to_chat(f"\n{'='*60}")
        self._add_to_chat(f"🎯 THEMA: {topic}")
        if document:
            self._add_to_chat(f"📄 Dokument geladen ({len(document)} Zeichen)")
        else:
            self._add_to_chat(f"📄 Kein Dokument - reine Themendiskussion")
        if use_moderator and self.sim.moderator:
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name} ({self.sim.moderator.style})")
        else:
            self._add_to_chat(f"👥 Ohne Moderator")
        self._add_to_chat(f"👥 {len(self.sim.agents)} Agenten")
        self._add_to_chat(f"🌐 Externe Quellen: {'✅ Aktiv' if self.sim.external.use_external else '❌ Inaktiv'}")
        self._add_to_chat(f"📚 Agenten lernen mit ZENTRALEM KNOWLEDGE GRAPH")
        for agent in self.sim.agents:
            if agent.learned_facts:
                self._add_to_chat(f"   📖 {agent.name} kennt {len(agent.learned_facts)} Fakten")
        self._add_to_chat(f"{'='*60}\n")
        
        thread = threading.Thread(target=self._process_discussion, args=(topic, document, rounds, use_moderator))
        thread.daemon = True
        thread.start()
    
    def _process_discussion(self, topic, document, rounds, use_moderator):
        try:
            for msg_type, *content in self.sim.start_discussion(topic, document, rounds, use_moderator):
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
                    self._add_to_chat("\n✅ Diskussion beendet\n")
                    self.show_knowledge_graph()
                    kg = self.sim.knowledge_graph
                    self._add_to_chat(f"📊 AKTUELLES WISSEN: {len(kg.graph['nodes'])} Knoten, {len(kg.graph['edges'])} Beziehungen")
                    self._add_to_chat(f"📚 Themen-Cluster: {len(kg.graph['topics'])}")
                    self._add_to_chat(f"🎯 Einflüsse: {len(kg.graph['influences'])} Agenten haben andere beeinflusst\n")
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