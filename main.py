#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SynthAgora - Haupt-GUI
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import os
import sys
import threading
import queue
import time
import random
import math
import hashlib
import shutil
import re
import csv
import webbrowser
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import Counter

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from includes.config import Config
from includes.simulation import Simulation, ProgressManager, Moderator
from includes.task_manager import AnalysisJob
from includes.migrate import MigrationWindow
from includes.agent import Agent
from includes.debate_formats import get_available_formats
from includes.result_analyzer import ResultAnalyzer
from includes.visualization import Visualization
from includes.synthesis_tab import SynthesisTab
from includes.legal_analysis_tab import LegalAnalysisTab

class FileManager:
    def __init__(self):
        for folder in [Config.AGENTS_FOLDER, Config.MODERATORS_FOLDER, 
                       Config.EXAMPLES_FOLDER, Config.EXPORTS_FOLDER,
                       Config.MEMORY_FOLDER, Config.KNOWLEDGE_FOLDER,
                       Config.PROJECTS_FOLDER]:
            if not os.path.exists(folder):
                os.makedirs(folder)
    
    def get_moderator_files(self) -> List[str]:
        import glob
        return glob.glob(f"{Config.MODERATORS_FOLDER}/*.json")
    
    def get_example_files(self) -> List[str]:
        import glob
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


class MemoryPalaceTab:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tb.Frame(parent)
        self.current_agent_id = None
        self.crystal_objects = {}
        self._setup_ui()
        self._load_agents()
    
    def _setup_ui(self):
        main_panel = tb.Panedwindow(self.frame, orient=HORIZONTAL)
        main_panel.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tb.Frame(main_panel, width=300)
        main_panel.add(left_frame, weight=1)
        
        header_frame = tb.Frame(left_frame)
        header_frame.pack(fill=X, pady=(0,10))
        tb.Label(header_frame, text="🧠 Gedächtnis-Paläste", font=("Segoe UI", 16, "bold")).pack(side=LEFT)
        refresh_btn = tb.Button(header_frame, text="🔄", width=3, command=self.refresh_agent_list, bootstyle="info")
        refresh_btn.pack(side=RIGHT)
        
        filter_frame = tb.Frame(left_frame)
        filter_frame.pack(fill=X, pady=5)
        self.show_active_only = tk.BooleanVar(value=True)
        tb.Checkbutton(filter_frame, text="✅ NUR AKTIVE AGENTEN (in Diskussion)", 
                      variable=self.show_active_only, command=self.filter_agents, bootstyle="info").pack(anchor=W, padx=5)
        
        search_frame = tb.Frame(left_frame)
        search_frame.pack(fill=X, pady=(0,10))
        self.search_var = tk.StringVar()
        self.search_entry = tb.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.search_entry.insert(0, "Agent suchen...")
        self.search_entry.bind('<KeyRelease>', self.filter_agents)
        
        list_frame = tb.Frame(left_frame)
        list_frame.pack(fill=BOTH, expand=True)
        self.agent_listbox = tk.Listbox(list_frame, font=("Consolas", 10), selectmode=tk.SINGLE, height=25)
        self.agent_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar = tb.Scrollbar(list_frame, orient=VERTICAL)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.agent_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.agent_listbox.yview)
        self.agent_listbox.bind('<<ListboxSelect>>', self.on_agent_select)
        
        stats_frame = tb.Frame(left_frame)
        stats_frame.pack(fill=X, pady=10)
        self.stats_label = tb.Label(stats_frame, text="👥 0 Agenten", bootstyle="secondary")
        self.stats_label.pack()
        
        right_frame = tb.Frame(main_panel)
        main_panel.add(right_frame, weight=3)
        
        self.agent_header = tb.Label(right_frame, text="Kein Agent ausgewählt", font=("Segoe UI", 18, "bold"))
        self.agent_header.pack(pady=(0,10))
        
        profile_btn = tb.Button(right_frame, text="📋 AGENTEN-STECKBRIEF", 
                                command=self.show_agent_profile, bootstyle="info")
        profile_btn.pack(pady=5)
        
        canvas_frame = tb.Frame(right_frame, bootstyle="dark")
        canvas_frame.pack(fill=BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)
        
        detail_frame = tb.Frame(right_frame)
        detail_frame.pack(fill=X, pady=10)
        self.crystal_count_label = tb.Label(detail_frame, text="💎 0 Kristalle", bootstyle="info")
        self.crystal_count_label.pack(side=LEFT, padx=5)
        self.importance_label = tb.Label(detail_frame, text="⭐ Durchschnitt: 0.0", bootstyle="secondary")
        self.importance_label.pack(side=LEFT, padx=5)
        self.info_text = tk.Text(detail_frame, height=3, wrap=tk.WORD, font=("Segoe UI", 9))
        self.info_text.pack(side=RIGHT, fill=X, expand=True, padx=5)
    
    def _load_agents(self):
        self.agents = []
        try:
            self.agents = self.sim.db.get_all_agents(active_only=True)
            self.filter_agents()
        except Exception as e:
            print(f"❌ Fehler beim Laden der Agenten: {e}")
    
    def filter_agents(self, event=None):
        search = self.search_var.get().lower()
        if search == "agent suchen...":
            search = ""
        
        if self.show_active_only.get():
            active_names = [a.name for a in self.sim.agents]
            filtered = [a for a in self.agents if a.get('name', '') in active_names]
        else:
            filtered = self.agents.copy()
        
        if search:
            filtered = [a for a in filtered if search in a.get('name', '').lower()]
        
        self.display_agents = filtered
        self._update_agent_list()
    
    def _update_agent_list(self):
        self.agent_listbox.delete(0, tk.END)
        for agent in self.display_agents:
            name = agent.get('name', 'Unbekannt')
            role = agent.get('role', '')
            evolution = agent.get('evolution', {})
            rank = evolution.get('rank', '?')
            
            try:
                memories = self.sim.db.get_agent_memories(agent['agent_id'])
                count = len(memories)
            except:
                count = 0
            
            is_active = any(a.name == name for a in self.sim.agents)
            active_mark = "🟢 " if is_active else "⚪ "
            
            display = f"{active_mark}{name[:18]:18} | {rank[:3]:3} | {count:3} 💎 | {role[:25]}"
            self.agent_listbox.insert(tk.END, display)
        
        self.stats_label.config(text=f"👥 {len(self.display_agents)} Agenten")
    
    def refresh_agent_list(self):
        self._load_agents()
        if self.current_agent_id:
            for agent in self.display_agents:
                if agent['agent_id'] == self.current_agent_id:
                    self.load_memories(self.current_agent_id)
                    return
            self.clear_palace()
    
    def show_agent_profile(self):
        if not self.current_agent_id:
            messagebox.showinfo("Info", "Kein Agent ausgewählt")
            return
        agent = next((a for a in self.sim.agents if a.agent_id == self.current_agent_id), None)
        if not agent:
            messagebox.showinfo("Info", "Agent nicht in aktiver Diskussion")
            return
        AgentProfileWindow(self.frame, self.sim, agent)
    
    def on_agent_select(self, event):
        selection = self.agent_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self.display_agents):
            return
        agent = self.display_agents[idx]
        self.current_agent_id = agent['agent_id']
        self.agent_header.config(text=f"{agent.get('name', 'Unbekannt')}s Gedächtnis-Palast")
        self.load_memories(agent['agent_id'])
    
    def load_memories(self, agent_id: str):
        """Lädt Erinnerungen eines Agenten und aktualisiert Anzeige"""
        try:
            memories = self.sim.db.get_agent_memories(agent_id)
            count = len(memories)
            self.crystal_count_label.config(text=f"💎 {count} Kristalle")
            
            if count > 0:
                avg_importance = sum(m.get('importance', 0.5) for m in memories) / count
                self.importance_label.config(text=f"⭐ Durchschnitt: {avg_importance:.2f}")
                self._draw_palace(memories)
            else:
                self.importance_label.config(text="⭐ Durchschnitt: 0.0")
                self._draw_empty_palace()
        except Exception as e:
            print(f"❌ Fehler beim Laden der Erinnerungen: {e}")
            self._draw_empty_palace()
    
    def _draw_palace(self, memories: List[Dict]):
        self.canvas.delete("all")
        self.crystal_objects = {}
        width = self.canvas.winfo_width() or 800
        height = self.canvas.winfo_height() or 400
        center_x, center_y = width // 2, height // 2
        
        self.canvas.create_oval(center_x-200, center_y-200, center_x+200, center_y+200,
                                outline='#4a4a6a', width=2, dash=(5, 5))
        
        for i, memory in enumerate(memories[:30]):
            angle = (i / len(memories[:30])) * 2 * math.pi
            distance = 50 + (memory.get('importance', 0.5) * 150)
            x = center_x + distance * math.cos(angle)
            y = center_y + distance * math.sin(angle)
            size = 20 + min(memory.get('access_count', 1) * 2, 30)
            colors = ["#4a90e2", "#e24a4a", "#4ae24a", "#e2b04a", "#9b59b6", "#ff6b6b"]
            color = colors[hash(memory.get('topic', '')) % len(colors)]
            self.canvas.create_oval(x-size//2, y-size//2, x+size//2, y+size//2,
                                    fill=color, outline="white", width=2, tags=("crystal", f"crystal_{i}"))
            self.canvas.create_text(x, y, text=memory.get('fact', '')[:15], 
                                   fill="white", font=("Segoe UI", 8, "bold"))
    
    def _draw_empty_palace(self):
        self.canvas.delete("all")
        width = self.canvas.winfo_width() or 800
        height = self.canvas.winfo_height() or 400
        center_x, center_y = width // 2, height // 2
        self.canvas.create_oval(center_x-200, center_y-200, center_x+200, center_y+200,
                                outline='#4a4a6a', width=2, dash=(5, 5))
        self.canvas.create_text(center_x, center_y, text="✨ Noch keine Erinnerungen",
                                fill="#4a4a6a", font=("Segoe UI", 16, "bold"))
    
    def clear_palace(self):
        self.agent_header.config(text="Kein Agent ausgewählt")
        self.crystal_count_label.config(text="💎 0 Kristalle")
        self.importance_label.config(text="⭐ Durchschnitt: 0.0")
        self.info_text.delete(1.0, tk.END)
        self._draw_empty_palace()
        self.current_agent_id = None


class AgentProfileWindow:
    def __init__(self, parent, sim, agent):
        self.parent = parent
        self.sim = sim
        self.agent = agent
        self.window = tb.Toplevel(parent)
        self.window.title(f"📋 Agenten-Steckbrief: {agent.name}")
        self.window.geometry("1000x800")
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        notebook = tb.Notebook(self.window)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        profile_frame = tb.Frame(notebook)
        notebook.add(profile_frame, text="📄 Profil")
        self.profile_text = scrolledtext.ScrolledText(profile_frame, font=("Consolas", 10))
        self.profile_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        skills_frame = tb.Frame(notebook)
        notebook.add(skills_frame, text="⭐ Skills & Rang")
        self.skills_text = scrolledtext.ScrolledText(skills_frame, font=("Consolas", 10))
        self.skills_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        expertise_frame = tb.Frame(notebook)
        notebook.add(expertise_frame, text="📚 Expertise")
        self.expertise_text = scrolledtext.ScrolledText(expertise_frame, font=("Consolas", 10))
        self.expertise_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        memories_frame = tb.Frame(notebook)
        notebook.add(memories_frame, text="💎 Gelernte Fakten")
        self.memories_text = scrolledtext.ScrolledText(memories_frame, font=("Consolas", 10))
        self.memories_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        kg_frame = tb.Frame(notebook)
        notebook.add(kg_frame, text="🔮 Knowledge Graph")
        self.kg_text = scrolledtext.ScrolledText(kg_frame, font=("Consolas", 10))
        self.kg_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        stats_frame = tb.Frame(notebook)
        notebook.add(stats_frame, text="🔄 Einflüsse & Punkte")
        self.stats_text = scrolledtext.ScrolledText(stats_frame, font=("Consolas", 10))
        self.stats_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        citations_frame = tb.Frame(notebook)
        notebook.add(citations_frame, text="📚 Zitate")
        self.citations_text = scrolledtext.ScrolledText(citations_frame, font=("Consolas", 10))
        self.citations_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        external_citations_frame = tb.Frame(notebook)
        notebook.add(external_citations_frame, text="📖 Externe Zitate")
        self.external_citations_text = scrolledtext.ScrolledText(external_citations_frame, font=("Consolas", 10))
        self.external_citations_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        tb.Button(self.window, text="Schließen", command=self.window.destroy, bootstyle="secondary").pack(pady=10)
    
    def _load_data(self):
        agent_id = self.agent.agent_id
        
        skills = self.sim.db.get_agent_skills(agent_id)
        evolution = self.sim.db.get_agent_evolution(agent_id)
        expertise = self.sim.db.get_agent_expertise(agent_id)
        citations = self.sim.db.get_agent_citations(agent_id, 50)
        external_citations = self.sim.db.get_agent_external_citations(agent_id, 50)
        citation_stats = self.sim.db.get_citation_stats(agent_id)
        
        doc_citations = citation_stats.get('document_citations', 0)
        ext_citations = citation_stats.get('external_citations', 0)
        
        self.profile_text.insert(1.0, f"""
📋 AGENTEN-PROFIL

Name: {self.agent.name}
Rolle: {self.agent.role}
Team: {self.agent.team if self.agent.team else 'Kein Team'}
Charakter-Typ: {self.agent.charakter_typ}

PERSÖNLICHKEIT:
{self.agent.personality}

BILDUNG:
{self.agent.education}

HINTERGRUND:
{self.agent.background}

ZIELE:
{chr(10).join(f'  • {z}' for z in self.agent.goals) if self.agent.goals else 'Keine'}

ÄNGSTE:
{chr(10).join(f'  • {a}' for a in self.agent.fears) if self.agent.fears else 'Keine'}

STATUS:
  • Beiträge: {len(self.agent.schon_gesagtes)}
  • Gelernte Fakten: {len(self.agent.learned_facts)}
  • Dokumenten-Zitate insgesamt: {doc_citations}
  • Externe Zitate insgesamt: {ext_citations}
  • Zitat-Punkte: {self.agent.total_citation_points}
""")
        self.profile_text.config(state=DISABLED)
        
        rank = evolution.get("rank", "Junior")
        xp = evolution.get("experience_points", 0)
        
        rank_icons = {"Junior": "⚪", "Senior": "🟢", "Experte": "🔵", "Master": "🏆"}
        rank_icon = rank_icons.get(rank, "⚪")
        
        skills_text = f"""
⭐ SKILLS & RANG

{rank_icon} RANG: {rank}
📊 ERFAHRUNGSPUNKTE: {xp}

📈 SKILLS:
  • Fachwissen:     {skills.get('fachwissen', 0.5)*100:.0f}%  {'█' * int(skills.get('fachwissen', 0.5)*10)}
  • Kommunikation:  {skills.get('kommunikation', 0.5)*100:.0f}%  {'█' * int(skills.get('kommunikation', 0.5)*10)}
  • Analyse:        {skills.get('analyse', 0.5)*100:.0f}%  {'█' * int(skills.get('analyse', 0.5)*10)}
  • Kreativität:    {skills.get('kreativitaet', 0.5)*100:.0f}%  {'█' * int(skills.get('kreativitaet', 0.5)*10)}
  • Diplomatie:     {skills.get('diplomatie', 0.5)*100:.0f}%  {'█' * int(skills.get('diplomatie', 0.5)*10)}

📊 EVOLUTIONS-STATISTIK:
  • Diskussionen:   {evolution.get('total_discussions', 0)}
  • Beiträge:       {evolution.get('total_contributions', 0)}
  • Gelernte Fakten: {evolution.get('total_learned_facts', 0)}
  • Analysen:       {evolution.get('total_analyses', 0)}
  • Einflüsse gegeben: {evolution.get('total_influences_given', 0)}
  • Einflüsse erhalten: {evolution.get('total_influences_received', 0)}
  • Punkte:         {evolution.get('total_score_points', 0)}
"""
        self.skills_text.insert(1.0, skills_text)
        self.skills_text.config(state=DISABLED)
        
        if expertise:
            expert_text = "📚 EXPERTISE-BEREICHE\n\n"
            for exp in expertise[:20]:
                level = exp['expertise_level']
                expert_text += f"  • {exp['topic']}: {level*100:.0f}%  ({exp['contributions']} Beiträge)\n"
        else:
            expert_text = "📚 Noch keine Expertise-Bereiche entwickelt."
        
        self.expertise_text.insert(1.0, expert_text)
        self.expertise_text.config(state=DISABLED)
        
        memories = self.sim.db.get_agent_memories(agent_id)
        if memories:
            mem_text = f"💎 GELERNTE FAKTEN ({len(memories)})\n\n"
            for i, mem in enumerate(memories[:30], 1):
                mem_text += f"{i}. 📌 {mem.get('fact', '')[:200]}\n"
                mem_text += f"   📚 Thema: {mem.get('topic', 'unbekannt')}\n"
                mem_text += f"   ⭐ Wichtigkeit: {mem.get('importance', 0.5):.2f}\n"
                if mem.get('source_project'):
                    mem_text += f"   📁 Quelle: {mem.get('source_project')}/{mem.get('source_document', '')}\n"
                mem_text += f"   📅 Gelernt: {mem.get('created_at', 'unbekannt')[:19]}\n\n"
        else:
            mem_text = "💎 Noch keine gelernten Fakten."
        self.memories_text.insert(1.0, mem_text)
        self.memories_text.config(state=DISABLED)
        
        kg_node = self.sim.db.get_node(agent_id)
        if kg_node:
            kg_text = f"🔮 KNOWLEDGE GRAPH\n\nNode ID: {kg_node['node_id']}\nTyp: {kg_node['node_type']}\nWichtigkeit: {kg_node.get('importance', 0.5):.2f}\nZugriffe: {kg_node.get('access_count', 0)}\n"
            connections = self.sim.db.get_node_connections(agent_id)
            if connections['outgoing']:
                kg_text += f"\n📤 BEEINFLUSST ANDERE ({len(connections['outgoing'])}):\n"
                for edge in connections['outgoing'][:10]:
                    kg_text += f"  → {edge.get('to_node', '?')} (Stärke: {edge.get('strength', 0.5):.2f})\n"
            if connections['incoming']:
                kg_text += f"\n📥 WURDE BEEINFLUSST VON ({len(connections['incoming'])}):\n"
                for edge in connections['incoming'][:10]:
                    kg_text += f"  ← {edge.get('from_node', '?')} (Stärke: {edge.get('strength', 0.5):.2f})\n"
        else:
            kg_text = "🔮 Kein Knowledge Graph Knoten gefunden."
        self.kg_text.insert(1.0, kg_text)
        self.kg_text.config(state=DISABLED)
        
        scores = self.sim.db.get_agent_score_history(agent_id, 20)
        total_points = sum(s.get('points', 0) for s in scores)
        influences = self.sim.db.get_influences(agent_id)
        
        stats_text = f"⭐ PUNKTE & EINFLÜSSE\n\n"
        stats_text += f"📊 PUNKTE\n"
        stats_text += f"  • Gesamt: {total_points}\n"
        stats_text += f"  • Anzahl Einträge: {len(scores)}\n\n"
        if scores[:5]:
            stats_text += f"  LETZTE PUNKTE:\n"
            for score in scores[:5]:
                stats_text += f"    +{score.get('points', 0)}: {score.get('reason', '')[:60]}\n"
        
        stats_text += f"\n🔄 EINFLÜSSE\n"
        stats_text += f"  • Gegeben: {influences.get('given_count', 0)}\n"
        stats_text += f"  • Erhalten: {influences.get('received_count', 0)}\n"
        
        self.stats_text.insert(1.0, stats_text)
        self.stats_text.config(state=DISABLED)
        
        citations_text = f"📚 DOKUMENTEN-ZITATE ({len(citations)})\n\n"
        if citations:
            for cit in citations[:20]:
                citations_text += f"  • {cit.get('quoted_text', '')[:100]}\n"
                citations_text += f"    📁 {cit.get('project', '?')}/{cit.get('document', '?')}\n"
                citations_text += f"    ⭐ Genauigkeit: {cit.get('accuracy', 0)*100:.0f}% | Punkte: {cit.get('points_awarded', 0)}\n\n"
        else:
            citations_text += "  Keine Dokumenten-Zitate vorhanden.\n"
        
        self.citations_text.insert(1.0, citations_text)
        self.citations_text.config(state=DISABLED)
        
        ext_citations_text = f"📖 EXTERNE ZITATE ({len(external_citations)})\n\n"
        if external_citations:
            for cit in external_citations[:20]:
                ext_citations_text += f"  • {cit.get('source', '?')}\n"
                if cit.get('quoted_text'):
                    ext_citations_text += f"    💬 {cit.get('quoted_text', '')[:100]}\n"
                if cit.get('reference'):
                    ext_citations_text += f"    📖 {cit.get('reference', '')[:100]}\n"
                ext_citations_text += f"    📅 {cit.get('created_at', 'unbekannt')[:19]}\n\n"
        else:
            ext_citations_text += "  Keine externen Zitate vorhanden.\n"
        
        self.external_citations_text.insert(1.0, ext_citations_text)
        self.external_citations_text.config(state=DISABLED)


class ProjectsTab:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tb.Frame(parent)
        self.current_project = None
        self._setup_ui()
        self._refresh_project_list()
    
    def _setup_ui(self):
        main_panel = tb.Panedwindow(self.frame, orient=HORIZONTAL)
        main_panel.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tb.Frame(main_panel, width=350)
        main_panel.add(left_frame, weight=1)
        
        header_frame = tb.Frame(left_frame)
        header_frame.pack(fill=X, pady=(0,10))
        tb.Label(header_frame, text="📁 PROJEKTE", font=("Segoe UI", 16, "bold")).pack(side=LEFT)
        refresh_btn = tb.Button(header_frame, text="🔄", width=3, command=self._refresh_project_list, bootstyle="info")
        refresh_btn.pack(side=RIGHT)
        
        create_frame = tb.Frame(left_frame)
        create_frame.pack(fill=X, pady=5)
        self.new_project_name = tb.Entry(create_frame, font=("Segoe UI", 10))
        self.new_project_name.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.new_project_name.insert(0, "Neues Projekt...")
        tb.Button(create_frame, text="➕", command=self._create_project, bootstyle="success", width=3).pack(side=RIGHT)
        
        list_frame = tb.LabelFrame(left_frame, text="📋 Projektliste")
        list_frame.pack(fill=BOTH, expand=True, pady=5)
        
        self.project_listbox = tk.Listbox(list_frame, font=("Consolas", 10), selectmode=tk.SINGLE, height=12)
        self.project_listbox.pack(side=LEFT, fill=BOTH, expand=True, padx=5, pady=5)
        scrollbar = tb.Scrollbar(list_frame, orient=VERTICAL)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.project_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.project_listbox.yview)
        self.project_listbox.bind('<<ListboxSelect>>', self._on_project_select)
        
        right_frame = tb.Frame(main_panel)
        main_panel.add(right_frame, weight=3)
        
        self.project_header = tb.Label(right_frame, text="Kein Projekt ausgewählt", font=("Segoe UI", 14, "bold"))
        self.project_header.pack(anchor=W, pady=(0,10))
        
        notebook = tb.Notebook(right_frame)
        notebook.pack(fill=BOTH, expand=True)
        
        docs_frame = tb.Frame(notebook)
        notebook.add(docs_frame, text="📄 Dokumente")
        self._setup_docs_tab(docs_frame)
        
        search_frame = tb.Frame(notebook)
        notebook.add(search_frame, text="🔍 Suche")
        self._setup_search_tab(search_frame)
        
        stats_frame = tb.Frame(notebook)
        notebook.add(stats_frame, text="📊 Statistik")
        self._setup_stats_tab(stats_frame)
        
        btn_frame = tb.Frame(right_frame)
        btn_frame.pack(fill=X, pady=10)
        tb.Button(btn_frame, text="📥 Dokument hinzufügen", command=self._add_document, bootstyle="primary", width=20).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="📁 Ordner hinzufügen", command=self._add_folder, bootstyle="primary", width=20).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="🗑️ Projekt löschen", command=self._delete_project, bootstyle="danger", width=20).pack(side=RIGHT, padx=5)
    
    def _setup_docs_tab(self, parent):
        self.docs_listbox = tk.Listbox(parent, font=("Consolas", 9), selectmode=tk.SINGLE, height=15)
        self.docs_listbox.pack(side=LEFT, fill=BOTH, expand=True, padx=5, pady=5)
        docs_scroll = tb.Scrollbar(parent, orient=VERTICAL, command=self.docs_listbox.yview)
        docs_scroll.pack(side=RIGHT, fill=Y)
        self.docs_listbox.config(yscrollcommand=docs_scroll.set)
        self.docs_listbox.bind('<<ListboxSelect>>', self._on_doc_select)
        
        doc_preview_frame = tb.LabelFrame(parent, text="Vorschau")
        doc_preview_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.doc_preview = scrolledtext.ScrolledText(doc_preview_frame, height=8, font=("Consolas", 9))
        self.doc_preview.pack(fill=BOTH, expand=True, padx=5, pady=5)
    
    def _setup_search_tab(self, parent):
        search_frame = tb.Frame(parent)
        search_frame.pack(fill=X, padx=10, pady=10)
        
        tb.Label(search_frame, text="Suchanfrage:").pack(anchor=W)
        self.search_query = tb.Entry(search_frame, font=("Segoe UI", 11))
        self.search_query.pack(fill=X, pady=5)
        self.search_query.insert(0, "Suchbegriff...")
        
        k_frame = tb.Frame(search_frame)
        k_frame.pack(fill=X, pady=5)
        tb.Label(k_frame, text="Anzahl Ergebnisse (k):").pack(side=LEFT)
        self.search_k = tk.StringVar(value="5")
        tb.Spinbox(k_frame, from_=1, to=20, textvariable=self.search_k, width=5).pack(side=LEFT, padx=5)
        
        tb.Button(search_frame, text="🔍 Suchen", command=self._search_project, bootstyle="primary", width=20).pack(pady=10)
        
        self.search_results = scrolledtext.ScrolledText(parent, font=("Consolas", 9), height=15)
        self.search_results.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    def _setup_stats_tab(self, parent):
        self.project_stats = scrolledtext.ScrolledText(parent, font=("Consolas", 10))
        self.project_stats.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    def _refresh_project_list(self):
        self.project_listbox.delete(0, tk.END)
        projects = self.sim.list_projects()
        for proj in projects:
            name = proj.get('name', '?')
            docs = proj.get('document_count', 0)
            chunks = proj.get('chunk_count', 0)
            self.project_listbox.insert(tk.END, f"📁 {name} | {docs} Docs | {chunks} Chunks")
    
    def _create_project(self):
        name = self.new_project_name.get().strip()
        if not name or name == "Neues Projekt...":
            messagebox.showwarning("Achtung", "Bitte Projektnamen eingeben!")
            return
        try:
            self.sim.create_project(name)
            self._refresh_project_list()
            self.new_project_name.delete(0, tk.END)
            self.new_project_name.insert(0, "Neues Projekt...")
            messagebox.showinfo("Erfolg", f"Projekt '{name}' erstellt!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def _on_project_select(self, event):
        selection = self.project_listbox.curselection()
        if not selection:
            return
        line = self.project_listbox.get(selection[0])
        name = line.split(" | ")[0].replace("📁 ", "")
        self.current_project = name
        self.project_header.config(text=f"📁 {name}")
        self._load_project_docs()
        self._update_project_stats()
    
    def _load_project_docs(self):
        self.docs_listbox.delete(0, tk.END)
        if not self.current_project:
            return
        
        project = self.sim.project_manager.get_project(self.current_project)
        if project:
            for doc in project.documents:
                title = doc.get('title', doc.get('source', '?'))
                chunks = doc.get('chunk_count', 0)
                self.docs_listbox.insert(tk.END, f"📄 {title[:40]} | {chunks} Chunks")
    
    def _on_doc_select(self, event):
        selection = self.docs_listbox.curselection()
        if not selection or not self.current_project:
            return
        
        project = self.sim.project_manager.get_project(self.current_project)
        if project and selection[0] < len(project.documents):
            doc = project.documents[selection[0]]
            self.doc_preview.delete(1.0, tk.END)
            try:
                with open(doc.get('parsed_path', ''), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    content = data.get('content', '')[:2000]
                    self.doc_preview.insert(1.0, content)
                    if len(data.get('content', '')) > 2000:
                        self.doc_preview.insert(tk.END, "\n\n... (gekürzt)")
            except:
                self.doc_preview.insert(1.0, "Vorschau nicht verfügbar")
    
    def _add_document(self):
        if not self.current_project:
            messagebox.showwarning("Achtung", "Bitte zuerst ein Projekt auswählen!")
            return
        
        filepath = filedialog.askopenfilename(
            title="Dokument auswählen",
            filetypes=[
                ("Alle unterstützten", "*.txt *.pdf *.md *.html *.htm *.json *.csv"),
                ("Textdateien", "*.txt"),
                ("PDF", "*.pdf"),
                ("Markdown", "*.md"),
                ("HTML", "*.html *.htm"),
                ("JSON", "*.json"),
                ("CSV", "*.csv")
            ]
        )
        if filepath:
            try:
                result = self.sim.add_document_to_project(self.current_project, filepath, "file")
                self._load_project_docs()
                self._update_project_stats()
                messagebox.showinfo("Erfolg", f"Dokument hinzugefügt: {result.get('title', filepath)}")
            except Exception as e:
                messagebox.showerror("Fehler", str(e))
    
    def _add_folder(self):
        if not self.current_project:
            messagebox.showwarning("Achtung", "Bitte zuerst ein Projekt auswählen!")
            return
        
        folder = filedialog.askdirectory(title="Ordner mit Dokumenten auswählen")
        if folder:
            try:
                results = self.sim.add_folder_to_project(self.current_project, folder)
                self._load_project_docs()
                self._update_project_stats()
                messagebox.showinfo("Erfolg", f"{len(results)} Dokumente hinzugefügt!")
            except Exception as e:
                messagebox.showerror("Fehler", str(e))
    
    def _search_project(self):
        if not self.current_project:
            messagebox.showwarning("Achtung", "Bitte zuerst ein Projekt auswählen!")
            return
        
        query = self.search_query.get().strip()
        if not query or query == "Suchbegriff...":
            messagebox.showwarning("Achtung", "Bitte Suchbegriff eingeben!")
            return
        
        try:
            k = int(self.search_k.get())
        except:
            k = 5
        
        self.search_results.delete(1.0, tk.END)
        self.search_results.insert(1.0, f"🔍 Suche nach '{query}' (k={k})...\n\n")
        self.search_results.update()
        
        def search_thread():
            try:
                results = self.sim.search_projects(query, [self.current_project], k)
                self.frame.after(0, lambda: self._display_search_results(results))
            except Exception as e:
                self.frame.after(0, lambda: self.search_results.insert(tk.END, f"❌ Fehler: {e}"))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def _display_search_results(self, results):
        self.search_results.delete(1.0, tk.END)
        if not results:
            self.search_results.insert(1.0, "Keine Ergebnisse gefunden.")
            return
        
        text = f"📊 {len(results)} Ergebnisse:\n\n"
        for i, r in enumerate(results, 1):
            text += f"{i}. 📄 {r.get('document', '?')}\n"
            text += f"   📁 {r.get('source', '?')}\n"
            text += f"   ⭐ Ähnlichkeit: {r.get('similarity', 0):.2f}\n"
            text += f"   📝 {r.get('text', '')[:300]}...\n\n"
        
        self.search_results.insert(1.0, text)
    
    def _update_project_stats(self):
        if not self.current_project:
            return
        
        project = self.sim.project_manager.get_project(self.current_project)
        if project:
            text = f"📊 PROJEKT-STATISTIK\n\n"
            text += f"Name: {project.metadata.get('name', '?')}\n"
            text += f"Erstellt: {project.metadata.get('created', '?')}\n"
            text += f"Dokumente: {project.metadata.get('document_count', 0)}\n"
            text += f"Chunks: {project.metadata.get('chunk_count', 0)}\n"
            text += f"Chunk-Größe: {project.metadata.get('chunk_size', 1000)}\n"
            text += f"Chunk-Overlap: {project.metadata.get('chunk_overlap', 200)}\n"
            text += f"Embedding-Modell: {project.metadata.get('embedding_model', '?')}\n"
            
            if project.documents:
                text += f"\n📄 DOKUMENTE:\n"
                for doc in project.documents[:10]:
                    text += f"  • {doc.get('title', doc.get('source', '?'))[:40]} ({doc.get('chunk_count', 0)} Chunks)\n"
            
            self.project_stats.delete(1.0, tk.END)
            self.project_stats.insert(1.0, text)
    
    def _delete_project(self):
        if not self.current_project:
            return
        
        if messagebox.askyesno("Projekt löschen", f"Projekt '{self.current_project}' unwiderruflich löschen?"):
            try:
                self.sim.project_manager.delete_project(self.current_project)
                self.current_project = None
                self.project_header.config(text="Kein Projekt ausgewählt")
                self.docs_listbox.delete(0, tk.END)
                self.doc_preview.delete(1.0, tk.END)
                self.search_results.delete(1.0, tk.END)
                self.project_stats.delete(1.0, tk.END)
                self._refresh_project_list()
                messagebox.showinfo("Erfolg", "Projekt gelöscht!")
            except Exception as e:
                messagebox.showerror("Fehler", str(e))


class CitationLeaderboardTab:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tb.Frame(parent)
        self._setup_ui()
        self._refresh()
    
    def _setup_ui(self):
        header = tb.Label(self.frame, text="📚 ZITIER-LEADERBOARD", font=("Segoe UI", 16, "bold"))
        header.pack(pady=10)
        
        stats_frame = tb.Frame(self.frame)
        stats_frame.pack(fill=X, padx=20, pady=10)
        
        self.total_citations_label = tb.Label(stats_frame, text="Dokumenten-Zitate: 0", font=("Segoe UI", 12))
        self.total_citations_label.pack(side=LEFT, padx=10)
        
        self.total_external_label = tb.Label(stats_frame, text="Externe Zitate: 0", font=("Segoe UI", 12))
        self.total_external_label.pack(side=LEFT, padx=10)
        
        self.avg_accuracy_label = tb.Label(stats_frame, text="Durchschn. Genauigkeit: 0%", font=("Segoe UI", 12))
        self.avg_accuracy_label.pack(side=LEFT, padx=10)
        
        self.agents_with_citations_label = tb.Label(stats_frame, text="Agenten mit Zitaten: 0", font=("Segoe UI", 12))
        self.agents_with_citations_label.pack(side=LEFT, padx=10)
        
        tb.Button(stats_frame, text="🔄 Aktualisieren", command=self._refresh, bootstyle="primary").pack(side=RIGHT)
        
        notebook = tb.Notebook(self.frame)
        notebook.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        doc_frame = tb.Frame(notebook)
        notebook.add(doc_frame, text="📄 Dokumenten-Zitate (gewertet)")
        
        doc_columns = ("Rang", "Agent", "Rolle", "Zitate", "Genauigkeit", "Projekte")
        self.doc_leaderboard_tree = ttk.Treeview(doc_frame, columns=doc_columns, show="headings", height=15)
        
        self.doc_leaderboard_tree.heading("Rang", text="Rang")
        self.doc_leaderboard_tree.heading("Agent", text="Agent")
        self.doc_leaderboard_tree.heading("Rolle", text="Rolle")
        self.doc_leaderboard_tree.heading("Zitate", text="Zitate")
        self.doc_leaderboard_tree.heading("Genauigkeit", text="Genauigkeit")
        self.doc_leaderboard_tree.heading("Projekte", text="Projekte")
        
        self.doc_leaderboard_tree.column("Rang", width=50)
        self.doc_leaderboard_tree.column("Agent", width=200)
        self.doc_leaderboard_tree.column("Rolle", width=150)
        self.doc_leaderboard_tree.column("Zitate", width=80)
        self.doc_leaderboard_tree.column("Genauigkeit", width=100)
        self.doc_leaderboard_tree.column("Projekte", width=80)
        
        self.doc_leaderboard_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        doc_scroll = tb.Scrollbar(doc_frame, orient=VERTICAL, command=self.doc_leaderboard_tree.yview)
        doc_scroll.pack(side=RIGHT, fill=Y)
        self.doc_leaderboard_tree.configure(yscrollcommand=doc_scroll.set)
        
        ext_frame = tb.Frame(notebook)
        notebook.add(ext_frame, text="📖 Externe Zitate (ungwertet)")
        
        ext_columns = ("Rang", "Agent", "Rolle", "Zitate", "Quellen")
        self.ext_leaderboard_tree = ttk.Treeview(ext_frame, columns=ext_columns, show="headings", height=15)
        
        self.ext_leaderboard_tree.heading("Rang", text="Rang")
        self.ext_leaderboard_tree.heading("Agent", text="Agent")
        self.ext_leaderboard_tree.heading("Rolle", text="Rolle")
        self.ext_leaderboard_tree.heading("Zitate", text="Zitate")
        self.ext_leaderboard_tree.heading("Quellen", text="Quellen")
        
        self.ext_leaderboard_tree.column("Rang", width=50)
        self.ext_leaderboard_tree.column("Agent", width=200)
        self.ext_leaderboard_tree.column("Rolle", width=150)
        self.ext_leaderboard_tree.column("Zitate", width=80)
        self.ext_leaderboard_tree.column("Quellen", width=150)
        
        self.ext_leaderboard_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        ext_scroll = tb.Scrollbar(ext_frame, orient=VERTICAL, command=self.ext_leaderboard_tree.yview)
        ext_scroll.pack(side=RIGHT, fill=Y)
        self.ext_leaderboard_tree.configure(yscrollcommand=ext_scroll.set)
        
        history_frame = tb.Frame(notebook)
        notebook.add(history_frame, text="📜 Zitat-Historie")
        
        history_columns = ("Zeit", "Agent", "Typ", "Quelle", "Text")
        self.history_tree = ttk.Treeview(history_frame, columns=history_columns, show="headings", height=15)
        
        self.history_tree.heading("Zeit", text="Zeit")
        self.history_tree.heading("Agent", text="Agent")
        self.history_tree.heading("Typ", text="Typ")
        self.history_tree.heading("Quelle", text="Quelle")
        self.history_tree.heading("Text", text="Text")
        
        self.history_tree.column("Zeit", width=120)
        self.history_tree.column("Agent", width=150)
        self.history_tree.column("Typ", width=80)
        self.history_tree.column("Quelle", width=200)
        self.history_tree.column("Text", width=300)
        
        self.history_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        history_scroll = tb.Scrollbar(history_frame, orient=VERTICAL, command=self.history_tree.yview)
        history_scroll.pack(side=RIGHT, fill=Y)
        self.history_tree.configure(yscrollcommand=history_scroll.set)
    
    def _refresh(self):
        try:
            stats = self.sim.get_citation_stats()
            self.total_citations_label.config(text=f"Dokumenten-Zitate: {stats.get('document_citations', 0)}")
            self.total_external_label.config(text=f"Externe Zitate: {stats.get('external_citations', 0)}")
            self.avg_accuracy_label.config(text=f"Durchschn. Genauigkeit: {stats.get('avg_accuracy', 0)*100:.1f}%")
            self.agents_with_citations_label.config(text=f"Agenten mit Zitaten: {stats.get('agents_with_citations', 0)}")
            
            doc_leaderboard = self.sim.get_citation_leaderboard(10)
            for item in self.doc_leaderboard_tree.get_children():
                self.doc_leaderboard_tree.delete(item)
            
            for i, entry in enumerate(doc_leaderboard, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)
                self.doc_leaderboard_tree.insert("", tk.END, values=(
                    medal,
                    entry.get('name', '?')[:25],
                    entry.get('role', '?')[:20],
                    entry.get('citation_count', 0),
                    f"{entry.get('avg_accuracy', 0)*100:.1f}%",
                    entry.get('projects_used', 0)
                ))
            
            ext_leaderboard = self.sim.get_external_citation_leaderboard(10)
            for item in self.ext_leaderboard_tree.get_children():
                self.ext_leaderboard_tree.delete(item)
            
            for i, entry in enumerate(ext_leaderboard, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)
                self.ext_leaderboard_tree.insert("", tk.END, values=(
                    medal,
                    entry.get('name', '?')[:25],
                    entry.get('role', '?')[:20],
                    entry.get('citation_count', 0),
                    entry.get('sources_used', 0)
                ))
            
        except Exception as e:
            print(f"❌ Fehler beim Laden des Zitier-Leaderboards: {e}")
    
    def add_citation_to_history(self, agent_name: str, citation_type: str, source: str, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.history_tree.insert("", 0, values=(now, agent_name, citation_type, source, text[:100]))


class AnalysisResultWindow:
    def __init__(self, parent, sim, job):
        self.parent = parent
        self.sim = sim
        self.job = job
        self.window = tb.Toplevel(parent)
        self.window.title(f"📊 Ergebnisse: {job.name}")
        self.window.geometry("1000x700")
        self._setup_ui()
        self._display_results()
    
    def _setup_ui(self):
        header_frame = tb.Frame(self.window)
        header_frame.pack(fill=X, padx=10, pady=10)
        tb.Label(header_frame, text=f"📊 {self.job.name}", font=("Segoe UI", 16, "bold")).pack(side=LEFT)
        
        self.notebook = tb.Notebook(self.window)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        self.overview_frame = tb.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="📋 Übersicht")
        self.role_frame = tb.Frame(self.notebook)
        self.notebook.add(self.role_frame, text="👥 Nach Rolle")
        self.all_frame = tb.Frame(self.notebook)
        self.notebook.add(self.all_frame, text="📄 Alle Ergebnisse")
        self.export_frame = tb.Frame(self.notebook)
        self.notebook.add(self.export_frame, text="💾 Export")
        
        btn_frame = tb.Frame(self.window)
        btn_frame.pack(fill=X, padx=10, pady=10)
        tb.Button(btn_frame, text="💾 Exportieren", command=self.export_results, bootstyle="success", width=15).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="📋 In Zwischenablage", command=self.copy_to_clipboard, bootstyle="primary", width=20).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="Schließen", command=self.window.destroy, bootstyle="secondary", width=15).pack(side=RIGHT, padx=5)
    
    def export_results(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Config.EXPORTS_FOLDER}/{self.job.name}_{timestamp}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.job.to_dict(), f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Export", f"Exportiert nach:\n{filename}")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def _display_results(self):
        progress = self.job.get_progress()
        overview_text = scrolledtext.ScrolledText(self.overview_frame, font=("Consolas", 10))
        overview_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        agents_by_name = {a.name: a for a in self.sim.agents}
        role_results = self.job.get_results_by_role(agents_by_name)
        
        text = f"{'='*60}\n📊 ANALYSE: {self.job.name}\n{'='*60}\n\n📝 AUFGABE: {self.job.task_type}\n📅 ERSTELLT: {self.job.created_at}\n⏱️ DAUER: {self.job.duration:.1f}s\n👥 AGENTEN: {progress['total']} ({progress['completed']} fertig)\n\n{'='*60}\n📋 ERGEBNISSE NACH ROLLE:\n{'='*60}\n"
        for role, data in role_results.items():
            text += f"\n👤 {role.upper()}\n   Agenten: {len(data['agenten'])}\n"
            if data['durchschnitt']:
                text += f"   ⭐ Durchschnitt: {data['durchschnitt']:.1f}/10\n"
        overview_text.insert(1.0, text)
        overview_text.config(state=DISABLED)
        
        all_text = scrolledtext.ScrolledText(self.all_frame, font=("Consolas", 10))
        all_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        all_content = f"ALLE {len(self.job.tasks)} ERGEBNISSE:\n\n"
        for task in self.job.tasks:
            if task.status == "completed" and task.result:
                all_content += f"{'='*60}\n👤 {task.agent_name}\n📝 Aufgabe: {task.type}\n⏱️ Dauer: {task.duration:.1f}s\n\n{task.result.get('analysis', str(task.result))}\n\n"
        all_text.insert(1.0, all_content)
        all_text.config(state=DISABLED)
        
        export_label = tb.Label(self.export_frame, text="Wähle Export-Format:", font=("Segoe UI", 12))
        export_label.pack(pady=20)
        btn_frame = tb.Frame(self.export_frame)
        btn_frame.pack(pady=10)
        tb.Button(btn_frame, text="📄 JSON", command=lambda: self.export_format("json"), bootstyle="primary", width=15).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="📝 TXT", command=lambda: self.export_format("txt"), bootstyle="primary", width=15).pack(side=LEFT, padx=5)
    
    def export_format(self, format_type):
        result = self.sim.task_manager.export_job(self.job.id, format_type)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Config.EXPORTS_FOLDER}/{self.job.name}_{timestamp}.{format_type}"
        if format_type == "json":
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        elif format_type == "txt":
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(result.get("text", ""))
        messagebox.showinfo("Export", f"Exportiert nach:\n{filename}")
    
    def copy_to_clipboard(self):
        text = f"Analyse: {self.job.name}\nAgenten: {len(self.job.tasks)}\nFertig: {self.job.get_progress()['completed']}"
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        messagebox.showinfo("Kopiert", "In Zwischenablage kopiert!")


class AnalysisTab:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tb.Frame(parent)
        self.current_job = None
        self._setup_ui()
    
    def _setup_ui(self):
        paned = tb.Panedwindow(self.frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tb.Frame(paned)
        paned.add(left_frame, weight=1)
        
        tb.Label(left_frame, text="📋 Analyse-Name:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0,5))
        self.job_name_entry = tb.Entry(left_frame, font=("Segoe UI", 10))
        self.job_name_entry.pack(fill=X, pady=(0,10))
        self.job_name_entry.insert(0, f"Analyse_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        tb.Label(left_frame, text="🎯 Aufgaben-Typ:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0,5))
        self.task_type_var = tk.StringVar(value="analyse")
        task_frame = tb.Frame(left_frame)
        task_frame.pack(fill=X, pady=(0,10))
        types = [("🔍 Analysieren", "analyse"), ("📊 Bewerten", "evaluate"), ("💡 Empfehlen", "recommend"), ("📝 Zusammenfassen", "summarize"), ("🔎 Extrahieren", "extract")]
        for i, (text, value) in enumerate(types):
            rb = tb.Radiobutton(task_frame, text=text, variable=self.task_type_var, value=value, bootstyle="info")
            rb.grid(row=i//2, column=i%2, sticky=W, padx=5, pady=2)
        
        tb.Label(left_frame, text="📄 Text für Analyse:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0,5))
        text_frame = tb.Frame(left_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0,10))
        self.analysis_text = scrolledtext.ScrolledText(text_frame, height=15, font=("Segoe UI", 10), wrap=tk.WORD)
        self.analysis_text.pack(fill=BOTH, expand=True)
        self.analysis_text.insert(1.0, "Füge hier den zu analysierenden Text ein...")
        tb.Button(left_frame, text="📁 Beispiel laden", command=self.load_example, bootstyle="primary-outline").pack(pady=5)
        
        right_frame = tb.Frame(paned)
        paned.add(right_frame, weight=1)
        
        tb.Label(right_frame, text="👥 Agenten auswählen:", font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0,10))
        
        filter_frame = tb.LabelFrame(right_frame, text="🔍 Filter")
        filter_frame.pack(fill=X, pady=(0,10))
        filter_content = tb.Frame(filter_frame)
        filter_content.pack(fill=X, padx=10, pady=10)
        
        search_frame = tb.Frame(filter_content)
        search_frame.pack(fill=X, pady=5)
        tb.Label(search_frame, text="Suche:").pack(side=LEFT, padx=(0,5))
        self.filter_entry = tb.Entry(search_frame)
        self.filter_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        tb.Button(search_frame, text="🔍", width=3, command=self.filter_agents, bootstyle="info").pack(side=RIGHT)
        
        char_frame = tb.Frame(filter_content)
        char_frame.pack(fill=X, pady=5)
        tb.Label(char_frame, text="Charakter:").pack(side=LEFT, padx=(0,5))
        self.char_filter = ttk.Combobox(char_frame, values=["Alle", "Optimist", "Pessimist", "Realist", "Idealist", "Pragmatiker", "Träumer", "Macher", "Denker", "Chaot", "Pedant", "Nerd", "Hipster", "Zyniker", "Idiot"], state="readonly")
        self.char_filter.set("Alle")
        self.char_filter.pack(side=LEFT, fill=X, expand=True)
        
        role_frame = tb.Frame(filter_content)
        role_frame.pack(fill=X, pady=5)
        tb.Label(role_frame, text="Rolle:").pack(side=LEFT, padx=(0,5))
        self.role_filter = ttk.Combobox(role_frame, values=["Alle", "Anwalt", "Richter", "Arzt", "Pfleger", "Investor", "Forscher", "Journalist", "Politiker", "Experte", "Berater"], state="readonly")
        self.role_filter.set("Alle")
        self.role_filter.pack(side=LEFT, fill=X, expand=True)
        
        list_frame = tb.LabelFrame(right_frame, text="📋 Verfügbare Agenten")
        list_frame.pack(fill=BOTH, expand=True)
        list_content = tb.Frame(list_frame)
        list_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        list_container = tb.Frame(list_content)
        list_container.pack(fill=BOTH, expand=True)
        self.agent_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED, font=("Consolas", 9), height=15)
        self.agent_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar = tb.Scrollbar(list_container, orient=VERTICAL)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.agent_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.agent_listbox.yview)
        
        btn_frame = tb.Frame(right_frame)
        btn_frame.pack(fill=X, pady=10)
        tb.Button(btn_frame, text="✅ Alle auswählen", command=self.select_all, bootstyle="info-outline", width=15).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="❌ Alle abwählen", command=self.deselect_all, bootstyle="secondary-outline", width=15).pack(side=LEFT, padx=5)
        self.selection_label = tb.Label(btn_frame, text="0 ausgewählt")
        self.selection_label.pack(side=RIGHT)
        
        start_frame = tb.Frame(self.frame)
        start_frame.pack(fill=X, padx=10, pady=10)
        self.start_btn = tb.Button(start_frame, text="🚀 ANALYSE STARTEN", command=self.start_analysis, bootstyle="success", width=30)
        self.start_btn.pack()
        self.progress_bar = tb.Progressbar(self.frame, mode='determinate', bootstyle="striped")
        self.progress_bar.pack(fill=X, padx=10, pady=5)
        self.status_label = tb.Label(self.frame, text="Bereit", font=("Segoe UI", 9))
        self.status_label.pack()
        
        self.refresh_agent_list()
        self.agent_listbox.bind('<<ListboxSelect>>', self.update_selection_label)
    
    def refresh_agent_list(self):
        self.agent_listbox.delete(0, tk.END)
        for agent in self.sim.agents:
            rank_icon = "⚪" if agent.rank == "Junior" else "🟢" if agent.rank == "Senior" else "🔵" if agent.rank == "Experte" else "🏆"
            self.agent_listbox.insert(tk.END, f"{rank_icon} {agent.name} | {agent.rank} | {agent.role[:30]}")
        self.update_selection_label()
    
    def update_selection_label(self, event=None):
        self.selection_label.config(text=f"{len(self.agent_listbox.curselection())} ausgewählt")
    
    def filter_agents(self):
        query = self.filter_entry.get().lower()
        self.agent_listbox.delete(0, tk.END)
        for agent in self.sim.agents:
            if query in agent.name.lower() or query in agent.role.lower():
                rank_icon = "⚪" if agent.rank == "Junior" else "🟢" if agent.rank == "Senior" else "🔵" if agent.rank == "Experte" else "🏆"
                self.agent_listbox.insert(tk.END, f"{rank_icon} {agent.name} | {agent.rank} | {agent.role[:30]}")
        self.update_selection_label()
    
    def select_all(self):
        self.agent_listbox.selection_set(0, tk.END)
        self.update_selection_label()
    
    def deselect_all(self):
        self.agent_listbox.selection_clear(0, tk.END)
        self.update_selection_label()
    
    def load_example(self):
        example = "Das Krankenhaus St. Marien steht vor großen Herausforderungen:\n- Personalmangel in der Pflege\n- Lange Wartezeiten in der Notaufnahme\n- Veraltete IT-Systeme\n- Hohe Kosten bei gleichzeitigem Sparzwang\n- Unzufriedene Patienten\n\nDie Geschäftsführung sucht nach Lösungen zur Optimierung."
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(1.0, example)
    
    def start_analysis(self):
        if not self.sim.agents:
            messagebox.showwarning("Achtung", "Keine Agenten geladen!")
            return
        text = self.analysis_text.get(1.0, tk.END).strip()
        if not text or text == "Füge hier den zu analysierenden Text ein...":
            messagebox.showwarning("Achtung", "Bitte Text eingeben!")
            return
        selected = self.agent_listbox.curselection()
        if not selected:
            messagebox.showwarning("Achtung", "Bitte Agenten auswählen!")
            return
        agent_names = [self.agent_listbox.get(idx).split(" | ")[0].split(" ", 1)[-1] for idx in selected]
        
        job = self.sim.task_manager.create_job(name=self.job_name_entry.get().strip(), input_text=text, task_type=self.task_type_var.get(), agent_names=agent_names)
        self.current_job = job
        self.start_btn.config(state=DISABLED)
        self.progress_bar['value'] = 0
        self.status_label.config(text=f"⏳ Starte Analyse mit {len(agent_names)} Agenten...")
        threading.Thread(target=self._run_analysis_thread, args=(job,), daemon=True).start()
    
    def _run_analysis_thread(self, job):
        def progress_callback(status, job, progress=None, task=None):
            if status == "progress" and progress:
                self.frame.after(0, lambda: self._update_progress(progress))
        try:
            completed_job = self.sim.run_analysis(job, progress_callback)
            self.frame.after(0, lambda: self._analysis_complete(completed_job))
        except Exception as e:
            error_msg = str(e)
            self.frame.after(0, lambda: messagebox.showerror("Fehler", error_msg))
            self.frame.after(0, lambda: self.start_btn.config(state=NORMAL))
    
    def _update_progress(self, progress):
        self.progress_bar['value'] = progress['progress']
        self.status_label.config(text=f"⏳ {progress['completed']}/{progress['total']} Agenten fertig")
    
    def _analysis_complete(self, job):
        self.start_btn.config(state=NORMAL)
        self.progress_bar['value'] = 100
        AnalysisResultWindow(self.frame, self.sim, job)


class DBManagementWindow:
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.window = tb.Toplevel(parent)
        self.window.title("🗄️ Datenbank-Verwaltung")
        self.window.geometry("800x700")
        self._setup_ui()
        self._refresh_info()
    
    def _setup_ui(self):
        header = tb.Label(self.window, text="🗄️ KOMPLETTE DB-VERWALTUNG",
                         font=("Segoe UI", 16, "bold"), bootstyle="primary")
        header.pack(pady=10)
        
        notebook = tb.Notebook(self.window)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        info_frame = tb.Frame(notebook)
        notebook.add(info_frame, text="📊 Info")
        self.info_text = scrolledtext.ScrolledText(info_frame, height=20, font=("Consolas", 9))
        self.info_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        backup_frame = tb.Frame(notebook)
        notebook.add(backup_frame, text="💾 Backup")
        btn_frame = tb.Frame(backup_frame)
        btn_frame.pack(pady=20)
        tb.Button(btn_frame, text="📥 Backup erstellen", command=self.create_backup, bootstyle="success", width=25).pack(pady=5)
        tb.Button(btn_frame, text="📤 Backup wiederherstellen", command=self.restore_backup, bootstyle="primary", width=25).pack(pady=5)
        tb.Button(btn_frame, text="📦 Als JSON exportieren", command=self.export_json, bootstyle="info", width=25).pack(pady=5)
        
        mig_frame = tb.Frame(notebook)
        notebook.add(mig_frame, text="🔄 Migration")
        mig_btn_frame = tb.Frame(mig_frame)
        mig_btn_frame.pack(pady=20)
        tb.Button(mig_btn_frame, text="📁 Agenten migrieren", command=self.migrate_agents, bootstyle="primary", width=25).pack(pady=5)
        tb.Button(mig_btn_frame, text="🔮 Knowledge Graph migrieren", command=self.migrate_kg, bootstyle="primary", width=25).pack(pady=5)
        tb.Button(mig_btn_frame, text="⚡ ALLES migrieren", command=self.migrate_all, bootstyle="success", width=25).pack(pady=5)
        
        reset_frame = tb.Frame(notebook)
        notebook.add(reset_frame, text="⚠️ Gefahr")
        tb.Label(reset_frame, text="ALLE DATEN WERDEN GELÖSCHT!", font=("Segoe UI", 12, "bold"), bootstyle="danger").pack(pady=20)
        tb.Button(reset_frame, text="🗑️ DB ZURÜCKSETZEN", command=self.reset_db, bootstyle="danger", width=30).pack(pady=10)
        
        self.progress_bar = tb.Progressbar(self.window, mode='indeterminate', bootstyle="striped")
        self.progress_bar.pack(fill=X, padx=20, pady=5)
        self.status_label = tb.Label(self.window, text="Bereit", font=("Segoe UI", 9))
        self.status_label.pack()
        tb.Button(self.window, text="Schließen", command=self.window.destroy, bootstyle="secondary").pack(pady=10)
    
    def _refresh_info(self):
        try:
            stats = self.sim.get_db_info()
            self.info_text.delete(1.0, tk.END)
            text = f"📁 Datenbank: {self.sim.db.db_path}\n\n📊 GESAMTSTATISTIK:\n"
            text += f"  • Agenten im Pool: {stats['pool_size']}\n"
            text += f"  • Aktive Agenten: {stats['active_agents']}\n"
            text += f"  • Knowledge Graph Nodes: {stats['kg_nodes']}\n"
            text += f"  • Knowledge Graph Edges: {stats['kg_edges']}\n"
            text += f"  • Themen: {stats['topics']}\n"
            text += f"  • Teams: {stats['teams']}\n"
            text += f"  • Prognosen: {stats['prognoses']}\n"
            text += f"  • Diskussionen: {stats['discussions']}\n"
            text += f"  • Beiträge: {stats['contributions']}\n"
            text += f"  • Projekte: {stats.get('projects', 0)}\n"
            text += f"  • Projektdokumente: {stats.get('project_documents', 0)}\n"
            text += f"  • Chunks: {stats.get('project_chunks', 0)}\n"
            text += f"  • Dokumenten-Zitate: {stats.get('citations', 0)}\n"
            text += f"  • Externe Zitate: {stats.get('external_citations', 0)}\n"
            text += f"  • Durchschn. Fachwissen: {stats.get('avg_fachwissen', 0):.2f}\n"
            text += f"  • Durchschn. Kommunikation: {stats.get('avg_kommunikation', 0):.2f}\n"
            text += f"  • Durchschn. Analyse: {stats.get('avg_analyse', 0):.2f}\n"
            text += f"  • Rang-Verteilung: {stats.get('ranks', {})}\n"
            self.info_text.insert(tk.END, text)
        except Exception as e:
            self.info_text.insert(tk.END, f"❌ Fehler: {str(e)}")
    
    def update_status(self, message: str):
        self.status_label.config(text=message)
        self.window.update_idletasks()
    
    def create_backup(self):
        try:
            path = self.sim.backup_db()
            messagebox.showinfo("Erfolg", f"Backup erstellt:\n{path}")
            self._refresh_info()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def restore_backup(self):
        filepath = filedialog.askopenfilename(initialdir=Config.KNOWLEDGE_FOLDER, filetypes=[("DB files", "*.db")])
        if filepath and messagebox.askyesno("Wiederherstellen", "Fortfahren?"):
            try:
                shutil.copy2(filepath, self.sim.db.db_path)
                from includes.database import SynthAgoraDB
                from includes.knowledge_graph import KnowledgeGraph
                from includes.project_manager import ProjectManager
                self.sim.db = SynthAgoraDB()
                self.sim.knowledge_graph = KnowledgeGraph()
                self.sim.project_manager = ProjectManager()
                messagebox.showinfo("Erfolg", "Datenbank wiederhergestellt!")
                self._refresh_info()
            except Exception as e:
                messagebox.showerror("Fehler", str(e))
    
    def export_json(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(Config.EXPORTS_FOLDER, f"db_export_{timestamp}.json")
            data = {"tables": {}}
            conn = self.sim.db._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                for table in cursor.fetchall():
                    cursor.execute(f"SELECT * FROM {table[0]}")
                    rows = cursor.fetchall()
                    if rows:
                        data["tables"][table[0]] = [dict(row) for row in rows]
            finally:
                conn.close()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            messagebox.showinfo("Erfolg", f"Exportiert nach:\n{path}")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def migrate_agents(self):
        def run():
            self.progress_bar.start()
            self.update_status("⏳ Migriere Agenten...")
            from includes.migrate import MigrationTool
            migrator = MigrationTool(self.sim.db)
            migrator._migrate_agents_folder(Config.AGENTS_FOLDER)
            self.window.after(0, self.progress_bar.stop)
            self.window.after(0, lambda: self.update_status("✅ Fertig!"))
            self.window.after(0, self._refresh_info)
        threading.Thread(target=run, daemon=True).start()
    
    def migrate_kg(self):
        def run():
            self.progress_bar.start()
            self.update_status("⏳ Migriere Knowledge Graph...")
            from includes.migrate import MigrationTool
            migrator = MigrationTool(self.sim.db)
            kg_file = os.path.join(Config.KNOWLEDGE_FOLDER, "knowledge_graph.json")
            if os.path.exists(kg_file):
                migrator._migrate_knowledge_graph(kg_file)
            self.window.after(0, self.progress_bar.stop)
            self.window.after(0, lambda: self.update_status("✅ Fertig!"))
            self.window.after(0, self._refresh_info)
        threading.Thread(target=run, daemon=True).start()
    
    def migrate_all(self):
        def run():
            self.progress_bar.start()
            self.update_status("⏳ Migriere ALLES...")
            from includes.migrate import MigrationTool
            migrator = MigrationTool(self.sim.db)
            migrator.migrate_all()
            self.window.after(0, self.progress_bar.stop)
            self.window.after(0, lambda: self.update_status("✅ Fertig!"))
            self.window.after(0, self._refresh_info)
        threading.Thread(target=run, daemon=True).start()
    
    def reset_db(self):
        if messagebox.askyesno("WIRKLICH?", "ALLE DATEN werden gelöscht!", icon='warning'):
            try:
                self.sim.backup_db()
                from includes.database import SynthAgoraDB
                from includes.knowledge_graph import KnowledgeGraph
                from includes.project_manager import ProjectManager
                self.sim.db = SynthAgoraDB()
                self.sim.knowledge_graph = KnowledgeGraph()
                self.sim.project_manager = ProjectManager()
                self._refresh_info()
                messagebox.showinfo("Erfolg", "Datenbank zurückgesetzt!")
            except Exception as e:
                messagebox.showerror("Fehler", str(e))


class SynthAgoraGUI:
    def __init__(self):
        self.root = tb.Window(themename="cosmo")
        self.root.title("SynthAgora - Mit SQLite & Agenten-Pool & Projekten & Zitier-Pflicht & Synthese")
        self.root.geometry("1400x900")
        
        self.fm = FileManager()
        self.sim = Simulation()
        self.msg_queue = queue.Queue()
        self.progress = ProgressManager(self.update_status)
        
        self.current_pool_results = []
        
        self._setup_ui()
        self._check_lm()
        self._refresh_lists()
        self._process_queue()
        
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _setup_ui(self):
        top_frame = tb.Frame(self.root)
        top_frame.pack(fill=X, padx=10, pady=5)
        
        tb.Label(top_frame, text="SynthAgora", font=("Segoe UI", 18, "bold")).pack(side=LEFT)
        
        control_frame = tb.Frame(top_frame)
        control_frame.pack(side=RIGHT)
        
        self.start_btn = tb.Button(control_frame, text="🎬 DEBATTE STARTEN", 
                                   command=self.start_debate, bootstyle="success")
        self.start_btn.pack(side=LEFT, padx=2)
        
        self.stop_btn = tb.Button(control_frame, text="⛔ STOP", 
                                  command=self.stop_simulation, bootstyle="danger", state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=2)
        
        self.db_btn = tb.Button(control_frame, text="🗄️ DB", 
                                command=self.open_db_management, bootstyle="info")
        self.db_btn.pack(side=LEFT, padx=2)
        
        self.migrate_btn = tb.Button(control_frame, text="🔄 Migration", 
                                     command=self.open_migration, bootstyle="primary")
        self.migrate_btn.pack(side=LEFT, padx=2)
        
        self.notebook = tb.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        self.tab_main = tb.Frame(self.notebook)
        self.notebook.add(self.tab_main, text="🎭 Debatte")
        self._setup_debate_tab()
        
        self.tab_generate = tb.Frame(self.notebook)
        self.notebook.add(self.tab_generate, text="🤖 Generieren")
        
        self.tab_pool = tb.Frame(self.notebook)
        self.notebook.add(self.tab_pool, text="📚 Agenten-Pool")
        
        self.tab_projects = ProjectsTab(self.notebook, self.sim)
        self.notebook.add(self.tab_projects.frame, text="📁 Projekte")
        
        self.tab_analysis = AnalysisTab(self.notebook, self.sim)
        self.notebook.add(self.tab_analysis.frame, text="🔍 Analyse")
        
        self.tab_chat = tb.Frame(self.notebook)
        self.notebook.add(self.tab_chat, text="📜 Verlauf")
        
        self.tab_knowledge = tb.Frame(self.notebook)
        self.notebook.add(self.tab_knowledge, text="🔮 Knowledge Graph")
        
        self.tab_memory = MemoryPalaceTab(self.notebook, self.sim)
        self.notebook.add(self.tab_memory.frame, text="🧠 Gedächtnis-Palast")
        
        self.tab_citations = CitationLeaderboardTab(self.notebook, self.sim)
        self.notebook.add(self.tab_citations.frame, text="📚 Zitier-Ranking")
        
        self.tab_synthesis = SynthesisTab(self.notebook, self.sim)
        self.notebook.add(self.tab_synthesis.frame, text="🎨 Synthese")

        self.tab_legal = LegalAnalysisTab(self.notebook, self.sim)
        self.notebook.add(self.tab_legal.frame, text="⚖️ Legal Analysis")
        
        self.tab_dashboard = tb.Frame(self.notebook)
        self.notebook.add(self.tab_dashboard, text="📊 Dashboard")
        
        self.tab_config = tb.Frame(self.notebook)
        self.notebook.add(self.tab_config, text="⚙️ Config")
        
        self.tab_plugins = tb.Frame(self.notebook)
        self.notebook.add(self.tab_plugins, text="🌐 Plugins")
        
        self.tab_documents = tb.Frame(self.notebook)
        self.notebook.add(self.tab_documents, text="📄 Dokumente")
        
        self.tab_visualization = tb.Frame(self.notebook)
        self.notebook.add(self.tab_visualization, text="📊 Visualisierung")
        
        self.tab_results = tb.Frame(self.notebook)
        self.notebook.add(self.tab_results, text="📋 Ergebnis-Analyse")
        
        status_frame = tb.Frame(self.root)
        status_frame.pack(fill=X, padx=10, pady=5)
        
        self.statusbar = tb.Label(status_frame, text="Bereit", bootstyle="inverse-primary")
        self.statusbar.pack(side=LEFT, fill=X, expand=True)
        
        self.lm_status = tb.Label(status_frame, text="🤖 LM: ⏳", bootstyle="secondary")
        self.lm_status.pack(side=RIGHT, padx=5)
        
        self.round_status = tb.Label(status_frame, text="", bootstyle="secondary")
        self.round_status.pack(side=RIGHT, padx=5)
        
        self.agent_status = tb.Label(status_frame, text="👥 0 Agenten", bootstyle="secondary")
        self.agent_status.pack(side=RIGHT, padx=5)
        
        self._setup_generate_tab()
        self._setup_pool_tab()
        self._setup_chat_tab()
        self._setup_knowledge_tab()
        self._setup_dashboard_tab()
        self._setup_config_tab()
        self._setup_plugins_tab()
        self._setup_documents_tab()
        self._setup_visualization_tab()
        self._setup_results_tab()
        
        self._update_statusbar()
    
    def _setup_debate_tab(self):
        main_frame = tb.Frame(self.tab_main)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        sub_notebook = tb.Notebook(main_frame)
        sub_notebook.pack(fill=BOTH, expand=True, pady=5)
        
        basis_frame = tb.Frame(sub_notebook)
        sub_notebook.add(basis_frame, text="📋 BASIS")
        
        topic_frame = tb.LabelFrame(basis_frame, text="🎯 Thema")
        topic_frame.pack(fill=X, padx=10, pady=5)
        self.topic_entry = tb.Entry(topic_frame, font=("Segoe UI", 12))
        self.topic_entry.pack(fill=X, padx=10, pady=10)
        self.topic_entry.insert(0, "Thema der Diskussion...")
        
        doc_frame = tb.LabelFrame(basis_frame, text="📄 Dokument (optional)")
        doc_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        example_frame = tb.Frame(doc_frame)
        example_frame.pack(fill=X, padx=10, pady=5)
        self.example_combo = ttk.Combobox(example_frame, state="readonly", width=40)
        self.example_combo.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        tb.Button(example_frame, text="📖 Beispiel laden", command=self.load_selected_example, bootstyle="primary").pack(side=RIGHT)
        
        self.doc_text = scrolledtext.ScrolledText(doc_frame, height=6, font=("Segoe UI", 10))
        self.doc_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        param_frame = tb.LabelFrame(basis_frame, text="⚙️ Parameter")
        param_frame.pack(fill=X, padx=10, pady=5)
        param_content = tb.Frame(param_frame)
        param_content.pack(fill=X, padx=10, pady=10)
        
        rounds_frame = tb.Frame(param_content)
        rounds_frame.pack(side=LEFT, padx=10)
        tb.Label(rounds_frame, text="Runden:").pack(side=LEFT)
        self.rounds_var = tk.StringVar(value="3")
        tb.Spinbox(rounds_frame, from_=1, to=10, textvariable=self.rounds_var, width=5).pack(side=LEFT, padx=5)
        
        time_frame = tb.Frame(param_content)
        time_frame.pack(side=LEFT, padx=10)
        tb.Label(time_frame, text="Zeit/Runde (s):").pack(side=LEFT)
        self.time_per_round = tk.StringVar(value="0")
        tb.Spinbox(time_frame, from_=0, to=300, textvariable=self.time_per_round, width=5).pack(side=LEFT, padx=5)
        
        think_frame = tb.Frame(param_content)
        think_frame.pack(side=LEFT, padx=10)
        tb.Label(think_frame, text="Denkzeit (s):").pack(side=LEFT)
        self.thinking_time = tk.StringVar(value="10")
        tb.Spinbox(think_frame, from_=0, to=60, textvariable=self.thinking_time, width=5).pack(side=LEFT, padx=5)
        
        moderator_frame = tb.Frame(sub_notebook)
        sub_notebook.add(moderator_frame, text="🎭 MODERATOR")
        
        mod_control_frame = tb.Frame(moderator_frame)
        mod_control_frame.pack(fill=X, padx=10, pady=10)
        
        self.use_moderator_var = tk.BooleanVar(value=True)
        tb.Checkbutton(mod_control_frame, text="✅ Moderator verwenden", 
                       variable=self.use_moderator_var, bootstyle="success").pack(anchor=W)
        
        mod_select_frame = tb.Frame(moderator_frame)
        mod_select_frame.pack(fill=X, padx=10, pady=5)
        
        tb.Label(mod_select_frame, text="Moderator-Datei:").pack(anchor=W)
        self.mod_combo = ttk.Combobox(mod_select_frame, state="readonly", width=50)
        self.mod_combo.pack(fill=X, pady=5)
        self.load_mod_btn = tb.Button(mod_select_frame, text="🎭 LADEN", 
                                      command=self.load_selected_moderator, bootstyle="primary")
        self.load_mod_btn.pack(pady=5)
        
        self.mod_info_label = tb.Label(moderator_frame, text="Kein Moderator geladen", 
                                        bootstyle="secondary", wraplength=500)
        self.mod_info_label.pack(padx=10, pady=10)
        
        format_frame = tb.Frame(sub_notebook)
        sub_notebook.add(format_frame, text="🎭 FORMAT")
        
        formats = get_available_formats()
        self.debate_format_var = tk.StringVar(value="classic")
        
        format_grid = tb.LabelFrame(format_frame, text="Debatten-Format wählen")
        format_grid.pack(fill=X, padx=10, pady=10)
        grid_content = tb.Frame(format_grid)
        grid_content.pack(fill=X, padx=10, pady=10)
        
        for i, f in enumerate(formats):
            rb = tb.Radiobutton(grid_content, text=f"{f['name']} - {f['description']}",
                               variable=self.debate_format_var, value=f['id'], bootstyle="info")
            rb.grid(row=i//2, column=i%2, sticky=W, padx=10, pady=2)
        
        projects_frame = tb.Frame(sub_notebook)
        sub_notebook.add(projects_frame, text="📁 PROJEKTE")
        
        tb.Label(projects_frame, text="Projekte für Dokumenten-Retrieval", font=("Segoe UI", 12, "bold")).pack(anchor=W, padx=10, pady=5)
        tb.Label(projects_frame, text="Wähle Projekte aus, die Agenten während der Debatte nutzen können", bootstyle="secondary").pack(anchor=W, padx=10)
        
        self.projects_listbox = tk.Listbox(projects_frame, selectmode=tk.EXTENDED, font=("Consolas", 9), height=8)
        self.projects_listbox.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        proj_btn_frame = tb.Frame(projects_frame)
        proj_btn_frame.pack(fill=X, padx=10, pady=5)
        tb.Button(proj_btn_frame, text="✅ Alle auswählen", command=self.select_all_projects, bootstyle="info-outline", width=15).pack(side=LEFT, padx=2)
        tb.Button(proj_btn_frame, text="❌ Alle abwählen", command=self.deselect_all_projects, bootstyle="secondary-outline", width=15).pack(side=LEFT, padx=2)
        
        k_frame = tb.Frame(projects_frame)
        k_frame.pack(fill=X, padx=10, pady=10)
        tb.Label(k_frame, text="Anzahl relevanter Chunks pro Agent (k):").pack(side=LEFT)
        self.projects_k = tk.StringVar(value="5")
        tb.Spinbox(k_frame, from_=1, to=20, textvariable=self.projects_k, width=5).pack(side=LEFT, padx=5)
        
        self._refresh_projects_list()
        
        teams_frame = tb.Frame(sub_notebook)
        sub_notebook.add(teams_frame, text="⚖️ TEAMS")
        self._setup_teams_tab(teams_frame)
        
        premise_frame = tb.Frame(sub_notebook)
        sub_notebook.add(premise_frame, text="⚖️ PRÄMISSE")
        
        premise_info = tb.Label(premise_frame, text="💡 Bei 'Prämisse prüfen' wird diese These bewiesen oder widerlegt", bootstyle="info")
        premise_info.pack(anchor=W, padx=10, pady=5)
        
        self.premise_text = scrolledtext.ScrolledText(premise_frame, height=6, font=("Segoe UI", 11), wrap=tk.WORD)
        self.premise_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.premise_text.insert(1.0, "z.B. Klimawandel ist die größte Bedrohung unserer Zeit")
        
        mode_frame = tb.Frame(premise_frame)
        mode_frame.pack(fill=X, pady=5, padx=10)
        self.prove_mode = tk.BooleanVar(value=True)
        tb.Radiobutton(mode_frame, text="✅ These beweisen", variable=self.prove_mode, value=True, bootstyle="success").pack(side=LEFT, padx=10)
        tb.Radiobutton(mode_frame, text="❌ These widerlegen", variable=self.prove_mode, value=False, bootstyle="danger").pack(side=LEFT, padx=10)
        
        advanced_frame = tb.Frame(sub_notebook)
        sub_notebook.add(advanced_frame, text="⚙️ ERWEITERT")
        
        fb_frame = tb.LabelFrame(advanced_frame, text="🐟 Fishbowl")
        fb_frame.pack(fill=X, padx=10, pady=5)
        fb_content = tb.Frame(fb_frame)
        fb_content.pack(fill=X, padx=10, pady=5)
        tb.Label(fb_content, text="Innerer Kreis Größe:").pack(side=LEFT)
        self.inner_circle_size = tk.StringVar(value="5")
        tb.Spinbox(fb_content, from_=2, to=20, textvariable=self.inner_circle_size, width=5).pack(side=LEFT, padx=5)
        
        wc_frame = tb.LabelFrame(advanced_frame, text="☕ World Café")
        wc_frame.pack(fill=X, padx=10, pady=5)
        wc_content = tb.Frame(wc_frame)
        wc_content.pack(fill=X, padx=10, pady=5)
        tb.Label(wc_content, text="Tische:").pack(side=LEFT)
        self.cafe_tables = tk.StringVar(value="3")
        tb.Spinbox(wc_content, from_=2, to=10, textvariable=self.cafe_tables, width=5).pack(side=LEFT, padx=5)
        tb.Label(wc_content, text="Rotationsrunden:").pack(side=LEFT, padx=(10,0))
        self.rotation_rounds = tk.StringVar(value="3")
        tb.Spinbox(wc_content, from_=1, to=5, textvariable=self.rotation_rounds, width=5).pack(side=LEFT, padx=5)
        
        delphi_frame = tb.LabelFrame(advanced_frame, text="🔮 Delphi")
        delphi_frame.pack(fill=X, padx=10, pady=5)
        delphi_content = tb.Frame(delphi_frame)
        delphi_content.pack(fill=X, padx=10, pady=5)
        self.anonymous_votes = tk.BooleanVar(value=True)
        tb.Checkbutton(delphi_content, text="Anonyme Abstimmung", variable=self.anonymous_votes, bootstyle="info").pack(anchor=W)
        self.show_stats = tk.BooleanVar(value=True)
        tb.Checkbutton(delphi_content, text="Statistiken anzeigen", variable=self.show_stats, bootstyle="info").pack(anchor=W)
        
        sanction_frame = tb.LabelFrame(advanced_frame, text="⚖️ Sanktionen")
        sanction_frame.pack(fill=X, padx=10, pady=5)
        sanction_content = tb.Frame(sanction_frame)
        sanction_content.pack(fill=X, padx=10, pady=5)
        
        self.sanctions_var = tk.BooleanVar(value=False)
        tb.Checkbutton(sanction_content, text="Sanktionen aktivieren", variable=self.sanctions_var, bootstyle="info").pack(anchor=W)
        
        sanction_row = tb.Frame(sanction_content)
        sanction_row.pack(fill=X, pady=5)
        tb.Label(sanction_row, text="Max. Verwarnungen:").pack(side=LEFT)
        self.max_warnings = tk.StringVar(value="3")
        tb.Spinbox(sanction_row, from_=1, to=10, textvariable=self.max_warnings, width=3).pack(side=LEFT, padx=5)
        tb.Label(sanction_row, text="Mute-Runden:").pack(side=LEFT, padx=(10,0))
        self.mute_rounds = tk.StringVar(value="2")
        tb.Spinbox(sanction_row, from_=1, to=5, textvariable=self.mute_rounds, width=3).pack(side=LEFT, padx=5)
        
        speaker_frame = tb.LabelFrame(advanced_frame, text="🎤 Steuerung")
        speaker_frame.pack(fill=X, padx=10, pady=5)
        speaker_content = tb.Frame(speaker_frame)
        speaker_content.pack(fill=X, padx=10, pady=5)
        
        self.speaker_list_var = tk.BooleanVar(value=False)
        tb.Checkbutton(speaker_content, text="Rednerliste aktivieren", variable=self.speaker_list_var, bootstyle="info").pack(anchor=W)
        self.interruptions_var = tk.BooleanVar(value=False)
        tb.Checkbutton(speaker_content, text="Unterbrechungen erlauben", variable=self.interruptions_var, bootstyle="info").pack(anchor=W)
        self.voting_var = tk.BooleanVar(value=False)
        tb.Checkbutton(speaker_content, text="Abstimmungen aktivieren", variable=self.voting_var, bootstyle="info").pack(anchor=W)
        
        rep_frame = tb.LabelFrame(advanced_frame, text="🔄 Wiederholungsschutz")
        rep_frame.pack(fill=X, padx=10, pady=5)
        rep_content = tb.Frame(rep_frame)
        rep_content.pack(fill=X, padx=10, pady=5)
        tb.Label(rep_content, text="Schwellwert:").pack(side=LEFT)
        self.repetition_threshold = tk.StringVar(value="2")
        tb.Spinbox(rep_content, from_=1, to=5, textvariable=self.repetition_threshold, width=3).pack(side=LEFT, padx=5)
        
        agent_list_frame = tb.LabelFrame(main_frame, text="📋 Geladene Agenten")
        agent_list_frame.pack(fill=BOTH, expand=True, pady=5)
        
        self.debate_agent_listbox = tk.Listbox(agent_list_frame, font=("Consolas", 9), height=8, bg='#2a2a2a', fg='white')
        self.debate_agent_listbox.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=5)
        agent_scroll = tb.Scrollbar(agent_list_frame, orient=VERTICAL, command=self.debate_agent_listbox.yview)
        agent_scroll.pack(side=RIGHT, fill=Y)
        self.debate_agent_listbox.config(yscrollcommand=agent_scroll.set)
        
        btn_frame = tb.Frame(main_frame)
        btn_frame.pack(fill=X, pady=10)
        
        self.save_debate_btn = tb.Button(btn_frame, text="💾 EINSTELLUNGEN SPEICHERN", 
                                         command=self.save_debate_settings, bootstyle="success", width=25)
        self.save_debate_btn.pack(side=LEFT, padx=5)
        
        self.debate_agent_status = tb.Label(btn_frame, text="👥 0 Agenten geladen", bootstyle="secondary")
        self.debate_agent_status.pack(side=LEFT, padx=10)
        
        tb.Button(btn_frame, text="🎬 DEBATTE STARTEN", 
                  command=self.start_debate, bootstyle="primary", width=25).pack(side=RIGHT, padx=5)
    
    def _refresh_projects_list(self):
        self.projects_listbox.delete(0, tk.END)
        projects = self.sim.list_projects()
        for proj in projects:
            name = proj.get('name', '?')
            docs = proj.get('document_count', 0)
            self.projects_listbox.insert(tk.END, f"📁 {name} | {docs} Dokumente")
    
    def select_all_projects(self):
        self.projects_listbox.selection_set(0, tk.END)
    
    def deselect_all_projects(self):
        self.projects_listbox.selection_clear(0, tk.END)
    
    def _setup_teams_tab(self, parent):
        filter_frame = tb.Frame(parent)
        filter_frame.pack(fill=X, padx=10, pady=5)
        
        tb.Label(filter_frame, text="Suche:").pack(side=LEFT, padx=(0,5))
        self.agent_search_var = tk.StringVar()
        agent_search_entry = tb.Entry(filter_frame, textvariable=self.agent_search_var)
        agent_search_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        agent_search_entry.bind('<KeyRelease>', self.filter_team_agents)
        
        tb.Label(filter_frame, text="Team-Filter:").pack(side=LEFT, padx=(5,0))
        self.team_filter_var = tk.StringVar(value="Alle")
        team_filter_combo = ttk.Combobox(filter_frame, textvariable=self.team_filter_var, 
                                         values=["Alle", "Pro", "Contra", "Unassigned"], 
                                         state="readonly", width=12)
        team_filter_combo.pack(side=LEFT, padx=5)
        team_filter_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_team_agents())
        
        list_container = tb.Frame(parent)
        list_container.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        pro_frame = tb.LabelFrame(list_container, text="✅ Pro-Team")
        pro_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=5)
        
        self.pro_listbox = tk.Listbox(pro_frame, selectmode=tk.EXTENDED, font=("Consolas", 9), height=12, bg='#1a3a1a', fg='white')
        self.pro_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        pro_scroll = tb.Scrollbar(pro_frame, orient=VERTICAL, command=self.pro_listbox.yview)
        pro_scroll.pack(side=RIGHT, fill=Y)
        self.pro_listbox.config(yscrollcommand=pro_scroll.set)
        
        button_frame = tb.Frame(list_container)
        button_frame.pack(side=LEFT, padx=5)
        
        tb.Button(button_frame, text="→", command=self.move_to_pro, bootstyle="success", width=3).pack(pady=2)
        tb.Button(button_frame, text="←", command=self.move_from_pro, bootstyle="secondary", width=3).pack(pady=2)
        tb.Button(button_frame, text="→", command=self.move_to_contra, bootstyle="danger", width=3).pack(pady=2)
        tb.Button(button_frame, text="←", command=self.move_from_contra, bootstyle="secondary", width=3).pack(pady=2)
        tb.Button(button_frame, text="⚖️", command=self.random_teams, bootstyle="info", width=3).pack(pady=2)
        tb.Button(button_frame, text="🗑️", command=self.clear_teams, bootstyle="warning", width=3).pack(pady=2)
        
        contra_frame = tb.LabelFrame(list_container, text="❌ Contra-Team")
        contra_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=5)
        
        self.contra_listbox = tk.Listbox(contra_frame, selectmode=tk.EXTENDED, font=("Consolas", 9), height=12, bg='#3a1a1a', fg='white')
        self.contra_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        contra_scroll = tb.Scrollbar(contra_frame, orient=VERTICAL, command=self.contra_listbox.yview)
        contra_scroll.pack(side=RIGHT, fill=Y)
        self.contra_listbox.config(yscrollcommand=contra_scroll.set)
        
        available_frame = tb.LabelFrame(parent, text="📋 Verfügbare Agenten (Doppelklick zum Hinzufügen)")
        available_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        self.available_listbox_teams = tk.Listbox(available_frame, selectmode=tk.EXTENDED, font=("Consolas", 9), height=6, bg='#2a2a2a', fg='white')
        self.available_listbox_teams.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=5)
        available_scroll = tb.Scrollbar(available_frame, orient=VERTICAL, command=self.available_listbox_teams.yview)
        available_scroll.pack(side=RIGHT, fill=Y)
        self.available_listbox_teams.config(yscrollcommand=available_scroll.set)
        self.available_listbox_teams.bind('<Double-Button-1>', self.add_agent_to_team_from_teams)
        
        info_frame = tb.Frame(parent)
        info_frame.pack(fill=X, pady=5)
        self.team_info_label = tb.Label(info_frame, text="Pro: 0 | Contra: 0", font=("Segoe UI", 10, "bold"))
        self.team_info_label.pack()
        
        self.refresh_team_agent_list()
    
    def refresh_team_agent_list(self):
        if not hasattr(self, 'available_listbox_teams') or not self.available_listbox_teams:
            return
        
        self.available_listbox_teams.delete(0, tk.END)
        
        for agent in self.sim.agents:
            in_pro = any(agent.name == self.pro_listbox.get(i).split(" | ")[0] for i in range(self.pro_listbox.size()))
            in_contra = any(agent.name == self.contra_listbox.get(i).split(" | ")[0] for i in range(self.contra_listbox.size()))
            if not in_pro and not in_contra:
                rank_icon = "⚪" if agent.rank == "Junior" else "🟢" if agent.rank == "Senior" else "🔵" if agent.rank == "Experte" else "🏆"
                self.available_listbox_teams.insert(tk.END, f"{rank_icon} {agent.name} | {agent.role[:30]}")
        
        self.update_team_info()
        self.update_debate_agent_list()
    
    def update_debate_agent_list(self):
        if hasattr(self, 'debate_agent_listbox') and self.debate_agent_listbox:
            self.debate_agent_listbox.delete(0, tk.END)
            for agent in self.sim.agents:
                rank_icon = "⚪" if agent.rank == "Junior" else "🟢" if agent.rank == "Senior" else "🔵" if agent.rank == "Experte" else "🏆"
                self.debate_agent_listbox.insert(tk.END, f"{rank_icon} {agent.name} | {agent.rank} | {agent.role[:30]}")
            self.debate_agent_status.config(text=f"👥 {len(self.sim.agents)} Agenten geladen")
    
    def filter_team_agents(self, event=None):
        if not hasattr(self, 'available_listbox_teams') or not self.available_listbox_teams:
            return
        
        search = self.agent_search_var.get().lower()
        team_filter = self.team_filter_var.get()
        
        self.available_listbox_teams.delete(0, tk.END)
        for agent in self.sim.agents:
            in_pro = any(agent.name == self.pro_listbox.get(i).split(" | ")[0] for i in range(self.pro_listbox.size()))
            in_contra = any(agent.name == self.contra_listbox.get(i).split(" | ")[0] for i in range(self.contra_listbox.size()))
            
            if team_filter == "Pro" and not in_pro:
                continue
            if team_filter == "Contra" and not in_contra:
                continue
            if team_filter == "Unassigned" and (in_pro or in_contra):
                continue
            
            if search and search not in agent.name.lower() and search not in agent.role.lower():
                continue
            
            if not in_pro and not in_contra:
                rank_icon = "⚪" if agent.rank == "Junior" else "🟢" if agent.rank == "Senior" else "🔵" if agent.rank == "Experte" else "🏆"
                self.available_listbox_teams.insert(tk.END, f"{rank_icon} {agent.name} | {agent.role[:30]}")
    
    def add_agent_to_team_from_teams(self, event):
        if not self.available_listbox_teams:
            return
        selection = self.available_listbox_teams.curselection()
        if not selection:
            return
        
        result = messagebox.askyesno("Team zuweisen", "Pro-Team? (Ja = Pro, Nein = Contra)")
        
        for idx in selection:
            line = self.available_listbox_teams.get(idx)
            name = line.split(" | ")[0].split(" ", 1)[-1]
            agent = next((a for a in self.sim.agents if a.name == name), None)
            if agent:
                if result:
                    self.pro_listbox.insert(tk.END, f"{agent.name} | {agent.role[:30]}")
                else:
                    self.contra_listbox.insert(tk.END, f"{agent.name} | {agent.role[:30]}")
        
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def move_to_pro(self):
        if not self.available_listbox_teams:
            return
        selection = self.available_listbox_teams.curselection()
        for idx in reversed(selection):
            line = self.available_listbox_teams.get(idx)
            name = line.split(" | ")[0].split(" ", 1)[-1]
            agent = next((a for a in self.sim.agents if a.name == name), None)
            if agent:
                self.pro_listbox.insert(tk.END, f"{agent.name} | {agent.role[:30]}")
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def move_from_pro(self):
        selection = self.pro_listbox.curselection()
        for idx in reversed(selection):
            self.pro_listbox.delete(idx)
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def move_to_contra(self):
        if not self.available_listbox_teams:
            return
        selection = self.available_listbox_teams.curselection()
        for idx in reversed(selection):
            line = self.available_listbox_teams.get(idx)
            name = line.split(" | ")[0].split(" ", 1)[-1]
            agent = next((a for a in self.sim.agents if a.name == name), None)
            if agent:
                self.contra_listbox.insert(tk.END, f"{agent.name} | {agent.role[:30]}")
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def move_from_contra(self):
        selection = self.contra_listbox.curselection()
        for idx in reversed(selection):
            self.contra_listbox.delete(idx)
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def random_teams(self):
        self.pro_listbox.delete(0, tk.END)
        self.contra_listbox.delete(0, tk.END)
        
        agents = list(self.sim.agents)
        random.shuffle(agents)
        half = len(agents) // 2
        
        for agent in agents[:half]:
            self.pro_listbox.insert(tk.END, f"{agent.name} | {agent.role[:30]}")
        for agent in agents[half:]:
            self.contra_listbox.insert(tk.END, f"{agent.name} | {agent.role[:30]}")
        
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def clear_teams(self):
        self.pro_listbox.delete(0, tk.END)
        self.contra_listbox.delete(0, tk.END)
        self.refresh_team_agent_list()
        self.update_team_info()
    
    def update_team_info(self):
        pro_count = self.pro_listbox.size()
        contra_count = self.contra_listbox.size()
        self.team_info_label.config(text=f"Pro: {pro_count} | Contra: {contra_count}")
    
    def load_selected_moderator(self):
        selection = self.mod_combo.get()
        if not selection:
            return
        filepath = f"{Config.MODERATORS_FOLDER}/{selection}"
        if self.sim.load_moderator(filepath):
            self._update_status(f"✅ Moderator geladen: {self.sim.moderator.name}")
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name}")
            if hasattr(self, 'mod_info_label'):
                self.mod_info_label.config(text=f"✅ {self.sim.moderator.name} - {self.sim.moderator.role}", 
                                           bootstyle="success")
        else:
            messagebox.showerror("Fehler", "Moderator konnte nicht geladen werden")
    
    def save_debate_settings(self):
        premise = self.premise_text.get(1.0, tk.END).strip()
        
        pro_agents = []
        for i in range(self.pro_listbox.size()):
            line = self.pro_listbox.get(i)
            name = line.split(" | ")[0].strip()
            if name and name[0] in ["🟢", "⚪", "🔵", "🏆"]:
                name = name[1:].strip()
            pro_agents.append(name)
        
        contra_agents = []
        for i in range(self.contra_listbox.size()):
            line = self.contra_listbox.get(i)
            name = line.split(" | ")[0].strip()
            if name and name[0] in ["🟢", "⚪", "🔵", "🏆"]:
                name = name[1:].strip()
            contra_agents.append(name)
        
        try:
            rounds = int(self.rounds_var.get())
        except:
            rounds = 3
        
        selected_projects = []
        for idx in self.projects_listbox.curselection():
            line = self.projects_listbox.get(idx)
            name = line.split(" | ")[0].replace("📁 ", "")
            selected_projects.append(name)
        
        try:
            retrieval_k = int(self.projects_k.get())
        except:
            retrieval_k = 5
        
        self.debate_settings = {
            "format": self.debate_format_var.get(),
            "rounds": rounds,
            "time_per_round": int(self.time_per_round.get()),
            "thinking_time": int(self.thinking_time.get()),
            "speaker_list": self.speaker_list_var.get(),
            "interruptions": self.interruptions_var.get(),
            "enable_voting": self.voting_var.get(),
            "enable_sanctions": self.sanctions_var.get(),
            "max_warnings": int(self.max_warnings.get()),
            "mute_rounds": int(self.mute_rounds.get()),
            "repetition_threshold": int(self.repetition_threshold.get()),
            "pro_agents": pro_agents,
            "contra_agents": contra_agents,
            "inner_circle_size": int(self.inner_circle_size.get()),
            "cafe_tables": int(self.cafe_tables.get()),
            "rotation_rounds": int(self.rotation_rounds.get()),
            "anonymous_votes": self.anonymous_votes.get(),
            "show_statistics": self.show_stats.get(),
            "premise": premise,
            "prove_mode": self.prove_mode.get(),
            "use_moderator": self.use_moderator_var.get(),
            "projects": selected_projects,
            "retrieval_k": retrieval_k
        }
        
        self._update_status("✅ Debatten-Einstellungen gespeichert")
        messagebox.showinfo("Erfolg", "Debatten-Einstellungen gespeichert!")
    
    def start_debate(self):
        if self.sim.is_running:
            messagebox.showwarning("Achtung", "Simulation läuft bereits!")
            return
        if not self.sim.agents:
            messagebox.showwarning("Achtung", "Bitte erst Agenten laden (im Pool-Tab oder über Zufällig laden)!")
            return
        
        if not hasattr(self, 'debate_settings'):
            messagebox.showwarning("Achtung", "Bitte zuerst Einstellungen speichern!")
            return
        
        topic = self.topic_entry.get().strip()
        if not topic or topic == "Thema der Diskussion...":
            messagebox.showwarning("Achtung", "Bitte ein Thema eingeben!")
            return
        
        document = self.doc_text.get(1.0, tk.END).strip()
        
        try:
            rounds = int(self.rounds_var.get())
        except:
            rounds = 3
        self.debate_settings["rounds"] = rounds
        
        if self.sim.moderator:
            self.sim.moderator.enabled = self.debate_settings.get("use_moderator", True)
        
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        
        self._add_to_chat(f"\n{'='*60}")
        self._add_to_chat(f"🎭 DEBATTE: {self.debate_settings['format']}")
        self._add_to_chat(f"🎯 THEMA: {topic}")
        self._add_to_chat(f"👥 {len(self.sim.agents)} Agenten")
        
        projects = self.debate_settings.get('projects', [])
        if projects:
            self._add_to_chat(f"📁 PROJEKTE: {', '.join(projects)}")
        
        if self.debate_settings.get("use_moderator", False) and self.sim.moderator:
            self._add_to_chat(f"🎭 Moderator: {self.sim.moderator.name}")
        if self.debate_settings.get("pro_agents") or self.debate_settings.get("contra_agents"):
            self._add_to_chat(f"⚖️ Pro-Team ({len(self.debate_settings['pro_agents'])}): {', '.join(self.debate_settings['pro_agents'][:5])}{'...' if len(self.debate_settings['pro_agents']) > 5 else ''}")
            self._add_to_chat(f"⚖️ Contra-Team ({len(self.debate_settings['contra_agents'])}): {', '.join(self.debate_settings['contra_agents'][:5])}{'...' if len(self.debate_settings['contra_agents']) > 5 else ''}")
        if self.debate_settings.get("premise"):
            self._add_to_chat(f"⚖️ PRÄMISSE: {self.debate_settings['premise'][:100]}...")
        self._add_to_chat(f"{'='*60}\n")
        
        threading.Thread(target=self._process_debate, args=(topic, document), daemon=True).start()
    
    def _process_debate(self, topic, document):
        try:
            for msg in self.sim.start_debate(topic, document, self.debate_settings):
                self.msg_queue.put(msg)
        except Exception as e:
            print(f"FEHLER: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.msg_queue.put(("done",))
    
    def _setup_generate_tab(self):
        paned = tb.Panedwindow(self.tab_generate, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tb.Frame(paned)
        paned.add(left_frame, weight=1)
        
        tb.Label(left_frame, text="🤖 AGENTEN GENERIEREN", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0,10))
        
        self.gen_progress_bar = tb.Progressbar(left_frame, mode='determinate', bootstyle="striped")
        self.gen_progress_bar.pack(fill=X, pady=5)
        self.gen_status_label = tb.Label(left_frame, text="", bootstyle="secondary")
        self.gen_status_label.pack(fill=X)
        
        mode_frame = tb.LabelFrame(left_frame, text="📋 Generierungs-Modus")
        mode_frame.pack(fill=X, pady=5)
        mode_content = tb.Frame(mode_frame)
        mode_content.pack(fill=X, padx=10, pady=10)
        
        self.gen_mode = tk.StringVar(value="theme")
        
        modes = [
            ("🎯 Aus Thema (LLM)", "theme"),
            ("📄 Aus Text (LLM)", "text"),
            ("🤖 LLM nach Rolle (LLM)", "role_llm"),
            ("🎭 LLM nach Charakter (LLM)", "charakter_llm"),
            ("🎲 Zufällig (schnell)", "random"),
            ("👥 Nach Rolle (Template)", "role"),
            ("🎭 Nach Charakter (Template)", "charakter"),
            ("📊 Nach Verteilung (Template)", "distribution")
        ]
        
        for text, value in modes:
            tb.Radiobutton(mode_content, text=text, variable=self.gen_mode, 
                          value=value, bootstyle="info").pack(anchor=W, padx=10, pady=2)
        
        theme_frame = tb.LabelFrame(left_frame, text="🎯 Thema (für Theme-Modus)")
        theme_frame.pack(fill=X, pady=5)
        theme_content = tb.Frame(theme_frame)
        theme_content.pack(fill=X, padx=10, pady=10)
        self.theme_entry = tb.Entry(theme_content, font=("Segoe UI", 11))
        self.theme_entry.pack(fill=X)
        self.theme_entry.insert(0, "z.B. Krankenhaus, Schule, Justiz, Familie...")
        
        text_frame = tb.LabelFrame(left_frame, text="📄 Text (für Text-Modus)")
        text_frame.pack(fill=BOTH, expand=True, pady=5)
        text_content = tb.Frame(text_frame)
        text_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.gen_text = scrolledtext.ScrolledText(text_content, height=8, font=("Segoe UI", 10))
        self.gen_text.pack(fill=BOTH, expand=True)
        self.gen_text.insert(1.0, "Füge hier den Text ein...")
        
        param_frame = tb.LabelFrame(left_frame, text="⚙️ Parameter")
        param_frame.pack(fill=X, pady=5)
        param_content = tb.Frame(param_frame)
        param_content.pack(fill=X, padx=10, pady=10)
        
        count_frame = tb.Frame(param_content)
        count_frame.pack(fill=X, pady=5)
        tb.Label(count_frame, text="Anzahl Agenten:").pack(side=LEFT, padx=(0,10))
        self.gen_count = tk.StringVar(value="50")
        tb.Spinbox(count_frame, from_=10, to=500, textvariable=self.gen_count, width=8).pack(side=LEFT)
        
        role_frame = tb.Frame(param_content)
        role_frame.pack(fill=X, pady=5)
        tb.Label(role_frame, text="Rolle (für Rolle-Modus / LLM nach Rolle):").pack(anchor=W)
        self.gen_role_entry = tb.Entry(role_frame)
        self.gen_role_entry.pack(fill=X, pady=2)
        self.gen_role_entry.insert(0, "Arzt")
        
        char_frame = tb.Frame(param_content)
        char_frame.pack(fill=X, pady=5)
        tb.Label(char_frame, text="Charakter (für Charakter-Modus / LLM nach Charakter):").pack(anchor=W)
        self.gen_char_entry = tb.Entry(char_frame)
        self.gen_char_entry.pack(fill=X, pady=2)
        self.gen_char_entry.insert(0, "Nerd")
        
        dist_frame = tb.Frame(param_content)
        dist_frame.pack(fill=X, pady=5)
        tb.Label(dist_frame, text="Verteilung (für Distributions-Modus, z.B. medizin:20,justiz:10):").pack(anchor=W)
        self.distribution_entry = tb.Entry(dist_frame)
        self.distribution_entry.pack(fill=X, pady=2)
        self.distribution_entry.insert(0, "medizin:20,justiz:10,paedagogik:20,familie:30")
        
        self.generate_btn = tb.Button(left_frame, text="🚀 GENERIEREN", 
                                      command=self.start_generation, bootstyle="success", width=20)
        self.generate_btn.pack(pady=10)
        
        right_frame = tb.Frame(paned)
        paned.add(right_frame, weight=1)
        tb.Label(right_frame, text="📋 Vorschau", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0,10))
        self.preview_text = scrolledtext.ScrolledText(right_frame, font=("Consolas", 10))
        self.preview_text.pack(fill=BOTH, expand=True)
        self.preview_text.insert(1.0, "Hier erscheint die Vorschau...")
    
    def _setup_pool_tab(self):
        paned = tb.Panedwindow(self.tab_pool, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tb.Frame(paned)
        paned.add(left_frame, weight=2)
        
        stats_frame = tb.LabelFrame(left_frame, text="📊 POOL-STATISTIK")
        stats_frame.pack(fill=X, pady=5)
        
        stats_content = tb.Frame(stats_frame)
        stats_content.pack(fill=X, padx=10, pady=10)
        
        self.pool_total_label = tb.Label(stats_content, text="Gesamt: 0", font=("Segoe UI", 12, "bold"))
        self.pool_total_label.grid(row=0, column=0, padx=10, sticky=W)
        self.pool_sets_label = tb.Label(stats_content, text="Sets: 0", font=("Segoe UI", 10))
        self.pool_sets_label.grid(row=0, column=1, padx=10, sticky=W)
        
        rank_frame = tb.LabelFrame(stats_content, text="🏆 RANG-VERTEILUNG")
        rank_frame.grid(row=0, column=2, padx=10, pady=5, sticky="nsew")
        self.rank_stats_listbox = tk.Listbox(rank_frame, font=("Consolas", 9), height=4, width=15)
        self.rank_stats_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        role_frame = tb.LabelFrame(stats_content, text="🏆 TOP 10 ROLLEN")
        role_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.top_roles_listbox = tk.Listbox(role_frame, font=("Consolas", 9), height=8, width=25)
        self.top_roles_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.top_roles_listbox.bind('<Double-Button-1>', self.on_role_double_click)
        
        char_frame = tb.LabelFrame(stats_content, text="🎭 TOP 10 CHARAKTERE")
        char_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        self.top_charaktere_listbox = tk.Listbox(char_frame, font=("Consolas", 9), height=8, width=25)
        self.top_charaktere_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.top_charaktere_listbox.bind('<Double-Button-1>', self.on_charakter_double_click)
        
        team_frame = tb.LabelFrame(stats_content, text="👥 TOP 10 TEAMS")
        team_frame.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")
        self.top_teams_listbox = tk.Listbox(team_frame, font=("Consolas", 9), height=8, width=25)
        self.top_teams_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.top_teams_listbox.bind('<Double-Button-1>', self.on_team_double_click)
        
        stats_content.columnconfigure(0, weight=1)
        stats_content.columnconfigure(1, weight=1)
        stats_content.columnconfigure(2, weight=1)
        
        search_notebook = tb.Notebook(left_frame)
        search_notebook.pack(fill=X, pady=5)
        
        text_search = tb.Frame(search_notebook)
        search_notebook.add(text_search, text="🔤 Text")
        text_frame = tb.Frame(text_search)
        text_frame.pack(fill=X, padx=10, pady=10)
        self.pool_search_entry_pool = tb.Entry(text_frame)
        self.pool_search_entry_pool.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.pool_search_entry_pool.bind("<Return>", lambda e: self.search_pool())
        tb.Button(text_frame, text="🔍 Suchen", command=self.search_pool, bootstyle="primary").pack(side=RIGHT)
        
        tag_search = tb.Frame(search_notebook)
        search_notebook.add(tag_search, text="🏷️ Tags")
        tag_frame = tb.Frame(tag_search)
        tag_frame.pack(fill=X, padx=10, pady=10)
        tb.Label(tag_frame, text="Tags:").pack(anchor=W)
        self.pool_tags_entry = tb.Entry(tag_frame)
        self.pool_tags_entry.pack(fill=X, pady=5)
        self.pool_tags_entry.insert(0, "anwalt, richter, idiot")
        self.pool_match_all = tk.BooleanVar(value=False)
        tb.Checkbutton(tag_search, text="Alle Tags müssen passen", variable=self.pool_match_all, bootstyle="info").pack(anchor=W, padx=10)
        tb.Button(tag_search, text="🏷️ Tags suchen", command=self.search_by_tags, bootstyle="primary").pack(pady=5)
        
        quick_frame = tb.Frame(left_frame)
        quick_frame.pack(fill=X, pady=5)
        
        count_frame = tb.Frame(quick_frame)
        count_frame.pack(side=LEFT, padx=2)
        tb.Label(count_frame, text="Anzahl:").pack(side=LEFT)
        self.random_load_count = tk.StringVar(value="50")
        tb.Spinbox(count_frame, from_=1, to=500, textvariable=self.random_load_count, width=5).pack(side=LEFT, padx=2)
        
        tb.Button(quick_frame, text="🎲 ZUFÄLLIG LADEN", 
                  command=self.random_from_pool_and_load, bootstyle="info", width=18).pack(side=LEFT, padx=2)
        
        tb.Button(quick_frame, text="🔄 STATISTIK", 
                  command=self.refresh_pool_statistics, bootstyle="secondary", width=12).pack(side=RIGHT, padx=2)
        
        list_frame = tb.LabelFrame(left_frame, text="Ergebnisse")
        list_frame.pack(fill=BOTH, expand=True, pady=5)
        list_content = tb.Frame(list_frame)
        list_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        list_container = tb.Frame(list_content)
        list_container.pack(fill=BOTH, expand=True)
        self.pool_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED, font=("Consolas", 9), height=15)
        self.pool_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        self.pool_listbox.bind('<<ListboxSelect>>', self.on_pool_select)
        scrollbar = tb.Scrollbar(list_container, orient=VERTICAL)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.pool_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.pool_listbox.yview)
        
        export_btn_frame = tb.Frame(left_frame)
        export_btn_frame.pack(fill=X, pady=5)
        tb.Button(export_btn_frame, text="📄 Ergebnisse als JSON exportieren", 
                  command=self.export_pool_results_json, bootstyle="primary", width=25).pack(side=LEFT, padx=2)
        tb.Button(export_btn_frame, text="📝 Ergebnisse als CSV exportieren", 
                  command=self.export_pool_results_csv, bootstyle="info", width=25).pack(side=LEFT, padx=2)
        
        right_frame = tb.Frame(paned)
        paned.add(right_frame, weight=1)
        
        tb.Label(right_frame, text="📋 Agenten-DETAILS", font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0,5))
        detail_notebook = tb.Notebook(right_frame)
        detail_notebook.pack(fill=BOTH, expand=True)
        self.pool_detail_basic = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_basic, text="📄 Basis")
        self.pool_detail_skills = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_skills, text="⭐ Skills & Rang")
        self.pool_detail_memories = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_memories, text="💎 Erinnerungen")
        self.pool_detail_kg = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_kg, text="🔮 Knowledge Graph")
        self.pool_detail_influences = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_influences, text="🔄 Einflüsse")
        self.pool_detail_scores = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_scores, text="⭐ Punkte & Prognosen")
        self.pool_detail_citations = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_citations, text="📚 Dokumenten-Zitate")
        self.pool_detail_external = scrolledtext.ScrolledText(detail_notebook, font=("Consolas", 10))
        detail_notebook.add(self.pool_detail_external, text="📖 Externe Zitate")
        
        btn_frame = tb.Frame(right_frame)
        btn_frame.pack(fill=X, pady=5)
        self.pool_load_btn = tb.Button(btn_frame, text="📥 Ausgewählte laden", command=self.load_from_pool, bootstyle="success", width=20)
        self.pool_load_btn.pack(side=LEFT, padx=2)
        
        tb.Label(right_frame, text="💡 Tipp: Doppelklick auf Rolle/Charakter/Team lädt alle", bootstyle="secondary").pack()
        
        self.refresh_pool_statistics()
    
    def random_from_pool_and_load(self):
        try:
            count = int(self.random_load_count.get())
            count = max(1, min(500, count))
        except:
            count = 50
        
        def _show_error(msg):
            messagebox.showerror("Fehler", msg)
        
        def load_thread():
            try:
                results = self.sim.get_random_from_pool(count)
                agent_names = [r['name'] for r in results]
                if self.sim.load_agents_from_pool(agent_names):
                    self.root.after(0, lambda: self._agents_loaded(len(agent_names)))
                    self.root.after(0, lambda: self.refresh_team_agent_list())
                    self.root.after(0, lambda: self.update_debate_agent_list())
                    self.root.after(0, lambda: self.notebook.select(self.tab_main))
                else:
                    self.root.after(0, lambda: _show_error("Konnte Agenten nicht laden"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: _show_error(error_msg))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _agents_loaded(self, count):
        self._update_status(f"✅ {count} Agenten geladen")
        self._add_to_chat(f"\n=== GELADEN AUS POOL: {count} Agenten ===")
        self.refresh_dashboard()
        self.tab_memory.refresh_agent_list()
        self.update_debate_agent_list()
        self.tab_citations._refresh()
    
    def _setup_chat_tab(self):
        toolbar = tb.Frame(self.tab_chat)
        toolbar.pack(fill=X, padx=10, pady=5)
        tb.Button(toolbar, text="💾 Exportieren", command=self.export_chat, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(toolbar, text="🗑️ Löschen", command=self.clear_chat, bootstyle="danger").pack(side=LEFT, padx=2)
        self.chat_count_label = tb.Label(toolbar, text="Einträge: 0", bootstyle="secondary")
        self.chat_count_label.pack(side=RIGHT, padx=5)
        self.chat_text = scrolledtext.ScrolledText(self.tab_chat, font=("Consolas", 10))
        self.chat_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
    
    def _setup_knowledge_tab(self):
        toolbar = tb.Frame(self.tab_knowledge)
        toolbar.pack(fill=X, padx=10, pady=5)
        tb.Button(toolbar, text="🔄 Graph anzeigen", command=self.show_knowledge_graph, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(toolbar, text="📊 Statistik", command=self.show_graph_stats, bootstyle="info").pack(side=LEFT, padx=2)
        tb.Button(toolbar, text="📚 Themen", command=self.show_topics, bootstyle="info").pack(side=LEFT, padx=2)
        tb.Button(toolbar, text="👥 Teams", command=self.show_teams, bootstyle="info").pack(side=LEFT, padx=2)
        self.knowledge_text = scrolledtext.ScrolledText(self.tab_knowledge, font=("Consolas", 10))
        self.knowledge_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.show_knowledge_graph()
    
    def _setup_dashboard_tab(self):
        main_frame = tb.Frame(self.tab_dashboard)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        stats_frame = tb.Frame(main_frame)
        stats_frame.pack(fill=X, pady=5)
        self.stats_labels = {}
        stats_items = [("Agenten", "agents"), ("Aktiv", "active"), ("Teams", "teams"), 
                       ("Fakten", "facts"), ("Beiträge", "contributions"), ("Punkte", "points"),
                       ("Dok.-Zitate", "citations"), ("Ext.-Zitate", "external_citations")]
        for i, (label, key) in enumerate(stats_items):
            card = tb.Frame(stats_frame, bootstyle="primary", padding=10)
            card.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            tb.Label(card, text=label, font=("Segoe UI", 10)).pack()
            self.stats_labels[key] = tb.Label(card, text="0", font=("Segoe UI", 16, "bold"))
            self.stats_labels[key].pack()
        for i in range(len(stats_items)):
            stats_frame.columnconfigure(i, weight=1)
        
        rank_leaderboard_frame = tb.LabelFrame(main_frame, text="🏆 RANG-LEADERBOARD")
        rank_leaderboard_frame.pack(fill=X, pady=5)
        rank_content = tb.Frame(rank_leaderboard_frame)
        rank_content.pack(fill=X, padx=10, pady=10)
        self.rank_leaderboard_listbox = tk.Listbox(rank_content, font=("Consolas", 10), height=8)
        self.rank_leaderboard_listbox.pack(fill=X)
        
        hitlist_frame = tb.LabelFrame(main_frame, text="🏆 TOP 10 HITLISTE")
        hitlist_frame.pack(fill=BOTH, expand=True, pady=5)
        hitlist_notebook = tb.Notebook(hitlist_frame)
        hitlist_notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        points_frame = tb.Frame(hitlist_notebook)
        hitlist_notebook.add(points_frame, text="⭐ Punkte")
        self.top_points_listbox = tk.Listbox(points_frame, font=("Consolas", 10), height=12)
        self.top_points_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        contrib_frame = tb.Frame(hitlist_notebook)
        hitlist_notebook.add(contrib_frame, text="💬 Beiträge")
        self.top_contrib_listbox = tk.Listbox(contrib_frame, font=("Consolas", 10), height=12)
        self.top_contrib_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        facts_frame = tb.Frame(hitlist_notebook)
        hitlist_notebook.add(facts_frame, text="🧠 Gelernte Fakten")
        self.top_facts_listbox = tk.Listbox(facts_frame, font=("Consolas", 10), height=12)
        self.top_facts_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        influence_frame = tb.Frame(hitlist_notebook)
        hitlist_notebook.add(influence_frame, text="🔄 Einflüsse")
        self.top_influence_listbox = tk.Listbox(influence_frame, font=("Consolas", 10), height=12)
        self.top_influence_listbox.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        team_frame = tb.LabelFrame(main_frame, text="👥 Teams")
        team_frame.pack(fill=X, pady=5)
        team_content = tb.Frame(team_frame)
        team_content.pack(fill=X, padx=10, pady=10)
        self.team_text = scrolledtext.ScrolledText(team_content, font=("Consolas", 10), height=5)
        self.team_text.pack(fill=X)
        
        prog_frame = tb.LabelFrame(main_frame, text="🔮 Letzte Prognosen")
        prog_frame.pack(fill=X, pady=5)
        prog_content = tb.Frame(prog_frame)
        prog_content.pack(fill=X, padx=10, pady=10)
        self.prognosis_listbox = tk.Listbox(prog_content, font=("Consolas", 9), height=4)
        self.prognosis_listbox.pack(fill=X)
        
        tb.Button(main_frame, text="🔄 Aktualisieren", command=self.refresh_dashboard, bootstyle="primary").pack(pady=5)
        self._update_dashboard_timer()
    
    def _setup_config_tab(self):
        provider_frame = tb.LabelFrame(self.tab_config, text="🤖 LLM Provider")
        provider_frame.pack(fill=X, padx=10, pady=5)
        provider_content = tb.Frame(provider_frame)
        provider_content.pack(fill=X, padx=10, pady=10)
        self.provider_var = tk.StringVar(value=Config.LM_PROVIDER)
        providers = [("LM Studio", "lmstudio"), ("Ollama", "ollama"), ("OpenAI", "openai"), ("Grok", "grok"), ("Claude", "claude")]
        for text, value in providers:
            tb.Radiobutton(provider_content, text=text, variable=self.provider_var, value=value, bootstyle="info").pack(anchor=W, padx=10)
        
        embedding_frame = tb.LabelFrame(self.tab_config, text="🤖 Embedding Provider")
        embedding_frame.pack(fill=X, padx=10, pady=5)
        embedding_content = tb.Frame(embedding_frame)
        embedding_content.pack(fill=X, padx=10, pady=10)
        self.embedding_provider_var = tk.StringVar(value=Config.EMBEDDING_PROVIDER)
        emb_providers = [("Sentence Transformer (lokal)", "sentence_transformer"), ("LM Studio", "lmstudio"), ("Ollama", "ollama"), ("OpenAI", "openai")]
        for text, value in emb_providers:
            tb.Radiobutton(embedding_content, text=text, variable=self.embedding_provider_var, value=value, bootstyle="info").pack(anchor=W, padx=10)
        tb.Label(embedding_content, text="Modell:").pack(anchor=W, pady=(10,0))
        self.embedding_model_var = tk.StringVar(value=Config.EMBEDDING_MODEL)
        tb.Entry(embedding_content, textvariable=self.embedding_model_var, width=40).pack(anchor=W, pady=2)
        
        lm_frame = tb.LabelFrame(self.tab_config, text="⚙️ LM Studio")
        lm_frame.pack(fill=X, padx=10, pady=5)
        lm_content = tb.Frame(lm_frame)
        lm_content.pack(fill=X, padx=10, pady=10)
        tb.Label(lm_content, text="URL:").grid(row=0, column=0, sticky=W, padx=5, pady=2)
        self.lm_url_var = tk.StringVar(value=Config.LM_STUDIO_URL)
        tb.Entry(lm_content, textvariable=self.lm_url_var, width=50).grid(row=0, column=1, padx=5)
        
        ollama_frame = tb.LabelFrame(self.tab_config, text="⚙️ Ollama")
        ollama_frame.pack(fill=X, padx=10, pady=5)
        ollama_content = tb.Frame(ollama_frame)
        ollama_content.pack(fill=X, padx=10, pady=10)
        tb.Label(ollama_content, text="URL:").grid(row=0, column=0, sticky=W, padx=5, pady=2)
        self.ollama_url_var = tk.StringVar(value=Config.OLLAMA_URL)
        tb.Entry(ollama_content, textvariable=self.ollama_url_var, width=50).grid(row=0, column=1, padx=5)
        tb.Label(ollama_content, text="Modell:").grid(row=1, column=0, sticky=W, padx=5, pady=2)
        self.ollama_model_var = tk.StringVar(value=Config.OLLAMA_MODEL)
        tb.Entry(ollama_content, textvariable=self.ollama_model_var, width=50).grid(row=1, column=1, padx=5)
        
        general_frame = tb.LabelFrame(self.tab_config, text="⚙️ Allgemein")
        general_frame.pack(fill=X, padx=10, pady=5)
        general_content = tb.Frame(general_frame)
        general_content.pack(fill=X, padx=10, pady=10)
        tb.Label(general_content, text="Temperatur:").grid(row=0, column=0, sticky=W, padx=5, pady=2)
        self.temp_var = tk.DoubleVar(value=Config.TEMPERATURE)
        tb.Scale(general_content, from_=0.0, to=2.0, variable=self.temp_var, orient=HORIZONTAL, length=200).grid(row=0, column=1, padx=5)
        tb.Label(general_content, text="Max Tokens:").grid(row=1, column=0, sticky=W, padx=5, pady=2)
        self.tokens_var = tk.IntVar(value=Config.MAX_TOKENS)
        tb.Spinbox(general_content, from_=50, to=1000, textvariable=self.tokens_var, width=10).grid(row=1, column=1, sticky=W, padx=5)
        tb.Label(general_content, text="Timeout (s):").grid(row=2, column=0, sticky=W, padx=5, pady=2)
        self.timeout_var = tk.IntVar(value=Config.TIMEOUT)
        tb.Spinbox(general_content, from_=5, to=120, textvariable=self.timeout_var, width=10).grid(row=2, column=1, sticky=W, padx=5)
        
        btn_frame = tb.Frame(self.tab_config)
        btn_frame.pack(pady=10)
        tb.Button(btn_frame, text="🔄 Verbindung testen", command=self.test_connection, bootstyle="info", width=20).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="💾 Speichern", command=self.save_config, bootstyle="success", width=20).pack(side=LEFT, padx=5)
    
    def _setup_plugins_tab(self):
        main_frame = tb.Frame(self.tab_plugins)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        tb.Label(main_frame, text="🌐 Externe Recherche (Wikipedia + arXiv)", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0,10))
        self.use_external_var = tk.BooleanVar(value=self.sim.plugin_manager.use_external)
        tb.Checkbutton(main_frame, text="✅ Externe Quellen verwenden", variable=self.use_external_var, command=self.toggle_external, bootstyle="success").pack(anchor=W, pady=5)
        
        list_frame = tb.LabelFrame(main_frame, text="Verfügbare Plugins")
        list_frame.pack(fill=BOTH, expand=True, pady=10)
        list_content = tb.Frame(list_frame)
        list_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.plugin_vars = {}
        for key, plugin in self.sim.plugin_manager.get_all_plugins().items():
            plugin_frame = tb.Frame(list_content)
            plugin_frame.pack(fill=X, pady=2)
            var = tk.BooleanVar(value=plugin.enabled)
            self.plugin_vars[key] = var
            plugin_name = plugin.metadata.name if hasattr(plugin, 'metadata') else plugin.name
            plugin_desc = plugin.metadata.description if hasattr(plugin, 'metadata') else plugin.description
            tb.Checkbutton(plugin_frame, text=plugin_name, variable=var, command=lambda k=key: self.toggle_plugin(k), bootstyle="info").pack(side=LEFT)
            status = "✅ Aktiv" if plugin.enabled else "⏸️ Inaktiv"
            tb.Label(plugin_frame, text=status, bootstyle="success" if plugin.enabled else "secondary").pack(side=LEFT, padx=10)
            tb.Label(plugin_frame, text=plugin_desc[:50], bootstyle="secondary").pack(side=LEFT, padx=10)
        
        test_frame = tb.LabelFrame(main_frame, text="🔍 Test-Suche")
        test_frame.pack(fill=X, pady=10)
        test_content = tb.Frame(test_frame)
        test_content.pack(fill=X, padx=10, pady=10)
        input_frame = tb.Frame(test_content)
        input_frame.pack(fill=X)
        self.test_entry = tb.Entry(input_frame)
        self.test_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.test_entry.insert(0, "Suchbegriff...")
        self.test_entry.bind("<Return>", lambda e: self.test_search())
        tb.Button(input_frame, text="🔍 Suchen", command=self.test_search, bootstyle="primary").pack(side=RIGHT)
        self.test_result = scrolledtext.ScrolledText(test_content, height=8, font=("Consolas", 9))
        self.test_result.pack(fill=BOTH, expand=True, pady=5)
        self.test_result.insert(1.0, "Hier erscheinen die Suchergebnisse...")
    
    def _setup_documents_tab(self):
        main_frame = tb.Frame(self.tab_documents)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        tb.Label(main_frame, text="📄 Dokumente laden", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0,10))
        
        url_frame = tb.LabelFrame(main_frame, text="🌐 URL laden")
        url_frame.pack(fill=X, pady=5)
        url_content = tb.Frame(url_frame)
        url_content.pack(fill=X, padx=10, pady=10)
        
        self.url_entry = tb.Entry(url_content)
        self.url_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.url_entry.insert(0, "https://...")
        tb.Button(url_content, text="📥 Laden", command=self.load_url, bootstyle="primary").pack(side=RIGHT)
        
        file_frame = tb.LabelFrame(main_frame, text="📁 Datei laden")
        file_frame.pack(fill=X, pady=5)
        file_content = tb.Frame(file_frame)
        file_content.pack(fill=X, padx=10, pady=10)
        
        self.file_path_var = tk.StringVar()
        file_entry = tb.Entry(file_content, textvariable=self.file_path_var)
        file_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        tb.Button(file_content, text="📂 Durchsuchen", command=self.browse_file, bootstyle="secondary").pack(side=RIGHT)
        tb.Button(file_content, text="📥 Laden", command=self.load_file, bootstyle="primary").pack(side=RIGHT, padx=(5,0))
        
        multi_frame = tb.LabelFrame(main_frame, text="📚 Mehrere Dokumente")
        multi_frame.pack(fill=BOTH, expand=True, pady=5)
        multi_content = tb.Frame(multi_frame)
        multi_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.multi_text = scrolledtext.ScrolledText(multi_content, height=8, font=("Consolas", 9))
        self.multi_text.pack(fill=BOTH, expand=True)
        self.multi_text.insert(1.0, "JSON-Format:\n[\n  {\"source\": \"url oder pfad\", \"type\": \"auto\", \"weight\": 1.0},\n  ...\n]")
        
        btn_frame = tb.Frame(main_frame)
        btn_frame.pack(fill=X, pady=5)
        tb.Button(btn_frame, text="📥 Mehrere laden", command=self.load_multiple, bootstyle="primary").pack(side=LEFT, padx=2)
        
        preview_frame = tb.LabelFrame(main_frame, text="📄 Vorschau")
        preview_frame.pack(fill=BOTH, expand=True, pady=5)
        self.doc_preview = scrolledtext.ScrolledText(preview_frame, height=10, font=("Consolas", 9))
        self.doc_preview.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        tb.Button(main_frame, text="📋 Als Diskussionsgrundlage übernehmen", 
                 command=self.use_document_for_discussion, bootstyle="success", width=30).pack(pady=10)
    
    def _setup_visualization_tab(self):
        main_frame = tb.Frame(self.tab_visualization)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        btn_frame = tb.Frame(main_frame)
        btn_frame.pack(fill=X, pady=5)
        
        tb.Button(btn_frame, text="📊 Netzwerk-Graph", command=self.show_network_graph, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="🔥 Heatmap", command=self.show_heatmap, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="📈 Sentiment-Verlauf", command=self.show_sentiment_timeline, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="☁️ Wortwolke", command=self.show_wordcloud, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="🎯 Konsens-Tacho", command=self.show_consensus_gauge, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="🌳 Argument-Baum", command=self.show_argument_tree, bootstyle="primary").pack(side=LEFT, padx=2)
        
        tb.Button(btn_frame, text="📄 HTML-Export", command=self.export_html_report, bootstyle="success").pack(side=RIGHT, padx=2)
        tb.Button(btn_frame, text="📑 PDF-Export", command=self.export_pdf_report, bootstyle="success").pack(side=RIGHT, padx=2)
        
        self.viz_canvas_frame = tb.Frame(main_frame, bootstyle="dark")
        self.viz_canvas_frame.pack(fill=BOTH, expand=True, pady=5)
        
        self.viz_canvas = tk.Canvas(self.viz_canvas_frame, bg='#1a1a2e', highlightthickness=0)
        self.viz_canvas.pack(fill=BOTH, expand=True)
        
        self.viz_status = tb.Label(main_frame, text="Wähle eine Visualisierung", bootstyle="secondary")
        self.viz_status.pack()
    
    def _setup_results_tab(self):
        main_frame = tb.Frame(self.tab_results)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        btn_frame = tb.Frame(main_frame)
        btn_frame.pack(fill=X, pady=5)
        
        tb.Button(btn_frame, text="🔍 Analyse starten", command=self.analyze_current_discussion, bootstyle="primary").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="📋 Thesen extrahieren", command=self.show_theses, bootstyle="info").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="💬 Top-Zitate", command=self.show_top_quotes, bootstyle="info").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="📊 Konsens-Messung", command=self.show_consensus, bootstyle="info").pack(side=LEFT, padx=2)
        tb.Button(btn_frame, text="🎭 Themen-Cluster", command=self.show_clusters, bootstyle="info").pack(side=LEFT, padx=2)
        
        self.results_text = scrolledtext.ScrolledText(main_frame, font=("Consolas", 10), wrap=tk.WORD)
        self.results_text.pack(fill=BOTH, expand=True, pady=5)
        self.results_text.insert(1.0, "Hier erscheinen die Analyse-Ergebnisse...")
    
    def _refresh_lists(self):
        mod_files = self.fm.get_moderator_files()
        mod_names = [os.path.basename(f) for f in mod_files]
        if hasattr(self, 'mod_combo'):
            self.mod_combo['values'] = mod_names
            if mod_names:
                self.mod_combo.current(0)
        example_files = self.fm.get_example_files()
        example_names = [os.path.basename(f) for f in example_files]
        if hasattr(self, 'example_combo'):
            self.example_combo['values'] = example_names
            if example_names:
                self.example_combo.current(0)
        self._refresh_projects_list()
    
    def _check_lm(self):
        ok, msg = self.sim.lm.test()
        if ok:
            self.statusbar.config(text=f"✅ {msg}", bootstyle="success")
        else:
            self.statusbar.config(text=f"⚠️ {msg}", bootstyle="warning")
        self.root.after(5000, self._check_lm)
    
    def _update_statusbar(self):
        if self.sim.lm.is_processing:
            self.lm_status.config(text="🤖 LM: 🔄 aktiv", bootstyle="success")
        else:
            self.lm_status.config(text="🤖 LM: ⏳ bereit", bootstyle="secondary")
        agent_count = len(self.sim.agents)
        active_count = sum(1 for a in self.sim.agents if not a.ausgeschlossen)
        self.agent_status.config(text=f"👥 {active_count}/{agent_count} aktiv")
        if self.sim.is_running:
            self.round_status.config(text=f"🎯 Runde {self.sim.current_round}/{self.sim.max_rounds}")
        else:
            self.round_status.config(text="")
        self.root.after(500, self._update_statusbar)
    
    def _update_dashboard_timer(self):
        self.refresh_dashboard()
        self.root.after(5000, self._update_dashboard_timer)
    
    def update_status(self, status, message):
        self.statusbar.config(text=message)
        self.root.update_idletasks()
    
    def _process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg[0] == "moderator":
                    self._add_to_chat(f"🎭 {msg[1]}")
                elif msg[0] == "agent":
                    team_tag = f"[{msg[4].upper()}] " if len(msg) > 4 and msg[4] else ""
                    self._add_to_chat(f"🗣️ {team_tag}{msg[1]}: {msg[2]}")
                elif msg[0] == "system":
                    self._add_to_chat(f"📢 {msg[1]}")
                elif msg[0] == "round_update":
                    self.round_status.config(text=msg[1])
                elif msg[0] == "agent_update":
                    self.refresh_dashboard()
                elif msg[0] == "contribution_added":
                    self.refresh_dashboard()
                elif msg[0] == "memory_update":
                    self.tab_memory.refresh_agent_list()
                    self.refresh_dashboard()
                elif msg[0] == "done":
                    self.stop_btn.config(state=DISABLED)
                    self.start_btn.config(state=NORMAL)
                    self.round_status.config(text="")
                    self.sim.is_running = False
                    self._add_to_chat("\n✅ Diskussion beendet\n")
                    self.refresh_dashboard()
                    self.tab_memory.refresh_agent_list()
                    self.tab_citations._refresh()
        except queue.Empty:
            pass
        self.root.after(50, self._process_queue)
    
    def _add_to_chat(self, text):
        self.chat_text.insert(tk.END, text + "\n")
        self.chat_text.see(tk.END)
        lines = len(self.chat_text.get(1.0, tk.END).split('\n'))
        self.chat_count_label.config(text=f"Einträge: {lines-1}")
    
    def stop_simulation(self):
        if self.sim.is_running:
            self.sim.stop()
            self.stop_btn.config(state=DISABLED)
            self.start_btn.config(state=NORMAL)
            self._add_to_chat("\n⛔ SIMULATION GESTOPPT\n")
    
    def open_db_management(self):
        DBManagementWindow(self.root, self.sim)
    
    def open_migration(self):
        MigrationWindow(self.root)
    
    def _update_generation_progress(self, message, current=None, total=None):
        if current is not None and total is not None:
            progress = (current / total) * 100
            self.gen_progress_bar['value'] = progress
            self.gen_status_label.config(text=f"{message} ({current}/{total})")
        else:
            self.gen_status_label.config(text=message)
        self.root.update_idletasks()
    
    def start_generation(self):
        mode = self.gen_mode.get()
        try:
            count = int(self.gen_count.get())
            count = max(1, min(500, count))
        except:
            count = 50
        
        self.generate_btn.config(state=DISABLED)
        self.gen_progress_bar['value'] = 0
        self.gen_status_label.config(text="⏳ Generierung läuft...")
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, "⏳ Generiere Agenten...\n")
        
        self.sim.agent_factory.set_progress_callback(self._update_generation_progress)
        
        def _show_error(msg):
            messagebox.showerror("Fehler", msg)
            self.generate_btn.config(state=NORMAL)
            self.gen_status_label.config(text="❌ Fehler")
        
        def generate_thread():
            try:
                if mode == "theme":
                    theme = self.theme_entry.get().strip()
                    if not theme or theme == "z.B. Krankenhaus, Schule, Justiz, Familie...":
                        self.root.after(0, lambda: _show_error("Bitte Thema eingeben!"))
                        return
                    result = self.sim.agent_factory.generate_from_theme(theme, count)
                    
                elif mode == "text":
                    text = self.gen_text.get(1.0, tk.END).strip()
                    if not text or text == "Füge hier den Text ein...":
                        self.root.after(0, lambda: _show_error("Bitte Text eingeben!"))
                        return
                    result = self.sim.agent_factory.generate_from_text(text, count)
                    
                elif mode == "role_llm":
                    role = self.gen_role_entry.get().strip()
                    if not role:
                        role = "Arzt"
                    result = self.sim.agent_factory.generate_by_role_with_llm(role, count)
                    
                elif mode == "charakter_llm":
                    charakter = self.gen_char_entry.get().strip()
                    if not charakter:
                        charakter = "Nerd"
                    result = self.sim.agent_factory.generate_by_charakter_with_llm(charakter, count)
                    
                elif mode == "random":
                    result = self.sim.agent_factory.generate_random(count)
                    
                elif mode == "role":
                    role = self.gen_role_entry.get().strip()
                    if not role:
                        role = "Arzt"
                    result = self.sim.agent_factory.generate_by_role(role, count)
                    
                elif mode == "charakter":
                    charakter = self.gen_char_entry.get().strip()
                    if not charakter:
                        charakter = "Nerd"
                    result = self.sim.agent_factory.generate_by_charakter(charakter, count)
                    
                elif mode == "distribution":
                    dist_str = self.distribution_entry.get().strip()
                    distribution = {}
                    for part in dist_str.split(','):
                        if ':' in part:
                            key, val = part.split(':')
                            try:
                                distribution[key.strip()] = int(val.strip())
                            except:
                                pass
                    if not distribution:
                        distribution = {"medizin": 20, "justiz": 10, "paedagogik": 20}
                    result = self.sim.agent_factory.generate_by_role_distribution(distribution)
                else:
                    return
                
                self.root.after(0, lambda: self.show_generation_result(result))
                self.root.after(0, lambda: self.gen_status_label.config(text="✅ Fertig!"))
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: _show_error(error_msg))
            finally:
                self.root.after(0, lambda: self.generate_btn.config(state=NORMAL))
                self.root.after(0, lambda: self.gen_progress_bar.config(value=100))
        
        threading.Thread(target=generate_thread, daemon=True).start()
    
    def show_generation_result(self, result):
        self.preview_text.delete(1.0, tk.END)
        preview = f"✅ {len(result['agents'])} Agenten generiert!\n📁 Gespeichert in: agents/{result['name']}.json\n📅 {result['generation_date']}\n\n=== VORSCHAU (erste 5 Agenten) ===\n\n"
        for i, agent in enumerate(result['agents'][:5]):
            preview += f"\n--- Agent {i+1} ---\nName: {agent['name']}\nRolle: {agent['role']}\nRang: {agent.get('initial_rank', 'Junior')}\nPersönlichkeit: {agent['personality'][:100]}...\nZiele: {', '.join(agent['goals'])}\nÄngste: {', '.join(agent['fears'])}\n"
        self.preview_text.insert(1.0, preview)
        self._refresh_lists()
        self.refresh_pool_statistics()
        messagebox.showinfo("Erfolg", f"{len(result['agents'])} Agenten generiert!")
    
    def refresh_pool_statistics(self):
        try:
            stats = self.sim.agent_factory.get_pool_statistics()
            self.pool_total_label.config(text=f"Gesamt: {stats['total']}")
            self.pool_sets_label.config(text=f"Sets: {stats['sets']}")
            
            self.rank_stats_listbox.delete(0, tk.END)
            ranks = stats.get('ranks', {})
            rank_order = ["Master", "Experte", "Senior", "Junior"]
            for rank in rank_order:
                count = ranks.get(rank, 0)
                self.rank_stats_listbox.insert(tk.END, f"{rank:8} {count:4d}")
            
            self.top_roles_listbox.delete(0, tk.END)
            for role, count in stats['top_roles'][:10]:
                self.top_roles_listbox.insert(tk.END, f"{role[:25]:25} {count:4d}")
            
            self.top_charaktere_listbox.delete(0, tk.END)
            for char, count in stats['top_charaktere'][:10]:
                self.top_charaktere_listbox.insert(tk.END, f"{char[:25]:25} {count:4d}")
            
            self.top_teams_listbox.delete(0, tk.END)
            for team, count in stats['top_teams'][:10]:
                self.top_teams_listbox.insert(tk.END, f"{team[:25]:25} {count:4d}")
                
        except Exception as e:
            print(f"❌ Fehler bei Pool-Statistik: {e}")
    
    def on_role_double_click(self, event):
        selection = self.top_roles_listbox.curselection()
        if not selection:
            return
        line = self.top_roles_listbox.get(selection[0])
        role = line[:25].strip()
        if role:
            self._load_agents_by_criteria("role", role)
    
    def on_charakter_double_click(self, event):
        selection = self.top_charaktere_listbox.curselection()
        if not selection:
            return
        line = self.top_charaktere_listbox.get(selection[0])
        charakter = line[:25].strip()
        if charakter:
            self._load_agents_by_criteria("charakter", charakter)
    
    def on_team_double_click(self, event):
        selection = self.top_teams_listbox.curselection()
        if not selection:
            return
        line = self.top_teams_listbox.get(selection[0])
        team = line[:25].strip()
        if team:
            self._load_agents_by_criteria("team", team)
    
    def _load_agents_by_criteria(self, criteria: str, value: str):
        def _show_error(msg):
            messagebox.showerror("Fehler", msg)
        
        def load_thread():
            try:
                if criteria == "role":
                    results = self.sim.agent_factory.get_agents_by_role(value, 500)
                elif criteria == "charakter":
                    results = self.sim.agent_factory.get_agents_by_charakter(value, 500)
                elif criteria == "team":
                    results = self.sim.agent_factory.get_agents_by_team(value, 500)
                else:
                    return
                
                agent_names = [r['name'] for r in results]
                if self.sim.load_agents_from_pool(agent_names):
                    self.root.after(0, lambda: self._agents_loaded(len(agent_names)))
                    self.root.after(0, lambda: self.refresh_team_agent_list())
                    self.root.after(0, lambda: self.update_debate_agent_list())
                    self.root.after(0, lambda: self.notebook.select(self.tab_main))
                else:
                    self.root.after(0, lambda: _show_error("Konnte Agenten nicht laden"))
                    
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: _show_error(error_msg))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def search_pool(self):
        query = self.pool_search_entry_pool.get().strip()
        if not query:
            return
        self.pool_listbox.delete(0, tk.END)
        self.pool_listbox.insert(tk.END, f"🔍 Suche nach '{query}'...")
        def _show_error(msg):
            messagebox.showerror("Fehler", msg)
        def search_thread():
            try:
                results = self.sim.search_pool(query, 200)
                self.current_pool_results = results
                self.root.after(0, lambda: self.display_pool_results(results))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: _show_error(error_msg))
        threading.Thread(target=search_thread, daemon=True).start()
    
    def search_by_tags(self):
        tags_text = self.pool_tags_entry.get().strip()
        if not tags_text:
            return
        tags = [t.strip() for t in tags_text.split(',')]
        match_all = self.pool_match_all.get()
        self.pool_listbox.delete(0, tk.END)
        self.pool_listbox.insert(tk.END, f"🔍 Suche nach Tags: {tags_text}...")
        def _show_error(msg):
            messagebox.showerror("Fehler", msg)
        def search_thread():
            try:
                results = self.sim.agent_factory.get_by_tags(tags, match_all, 200)
                self.current_pool_results = results
                self.root.after(0, lambda: self.display_pool_results(results))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: _show_error(error_msg))
        threading.Thread(target=search_thread, daemon=True).start()
    
    def display_pool_results(self, results):
        self.pool_listbox.delete(0, tk.END)
        if not results:
            self.pool_listbox.insert(tk.END, "❌ Keine Ergebnisse")
            return
        for agent in results:
            rank = "Junior"
            if agent.get('metadata'):
                meta = agent['metadata']
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except:
                        meta = {}
                rank = meta.get('initial_rank', 'Junior')
            display = f"{agent['name']} | {rank} | {agent['role'][:40]} | {agent['set_name']}"
            self.pool_listbox.insert(tk.END, display)
    
    def on_pool_select(self, event):
        selection = self.pool_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        line = self.pool_listbox.get(idx)
        
        name = line.split(" | ")[0].strip()
        
        for agent in self.current_pool_results:
            if agent['name'] == name:
                self._show_agent_details(agent)
                return
        
        results = self.sim.search_pool(name, 1)
        if results:
            self._show_agent_details(results[0])
    
    def _show_agent_details(self, agent):
        agent_name = agent['name']
        
        self.pool_detail_basic.delete(1.0, tk.END)
        detail = f"📋 AGENTEN-DETAILS\n\nName: {agent['name']}\nRolle: {agent['role']}\nSet: {agent['set_name']}\nModus: {agent['generation_mode']}\nDatei: {agent['json_file']}\n\nTags: {', '.join(agent.get('tags', []))}\n"
        if 'metadata' in agent and agent['metadata']:
            meta = agent['metadata']
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            for key, value in meta.items():
                detail += f"  {key}: {value}\n"
        self.pool_detail_basic.insert(tk.END, detail)
        
        self.pool_detail_skills.delete(1.0, tk.END)
        if 'metadata' in agent and agent['metadata']:
            meta = agent['metadata']
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            skills = meta.get('skills', {})
            rank = meta.get('initial_rank', 'Junior')
            rank_icons = {"Junior": "⚪", "Senior": "🟢", "Experte": "🔵", "Master": "🏆"}
            rank_icon = rank_icons.get(rank, "⚪")
            
            skills_text = f"⭐ SKILLS & RANG\n\n{rank_icon} RANG: {rank}\n\n📈 SKILLS:\n"
            skills_text += f"  • Fachwissen:     {skills.get('fachwissen', 0.5)*100:.0f}%\n"
            skills_text += f"  • Kommunikation:  {skills.get('kommunikation', 0.5)*100:.0f}%\n"
            skills_text += f"  • Analyse:        {skills.get('analyse', 0.5)*100:.0f}%\n"
            skills_text += f"  • Kreativität:    {skills.get('kreativitaet', 0.5)*100:.0f}%\n"
            skills_text += f"  • Diplomatie:     {skills.get('diplomatie', 0.5)*100:.0f}%\n"
        else:
            skills_text = "⭐ Keine Skill-Daten verfügbar."
        self.pool_detail_skills.insert(tk.END, skills_text)
        
        agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
        
        self.pool_detail_memories.delete(1.0, tk.END)
        memories = self.sim.db.get_agent_memories(agent_id)
        if memories:
            mem_text = f"💎 GEDÄCHTNIS-KRISTALLE ({len(memories)})\n\n"
            for i, mem in enumerate(memories[:20], 1):
                mem_text += f"{i}. 📌 {mem.get('fact', '')[:150]}\n   📚 Thema: {mem.get('topic', 'unbekannt')}\n   ⭐ Wichtigkeit: {mem.get('importance', 0.5):.2f}\n   👁️ Zugriffe: {mem.get('access_count', 1)}\n\n"
        else:
            mem_text = "💎 Keine Erinnerungen vorhanden."
        self.pool_detail_memories.insert(tk.END, mem_text)
        
        self.pool_detail_kg.delete(1.0, tk.END)
        kg_node = self.sim.db.get_node(agent_id)
        if kg_node:
            kg_text = f"🔮 KNOWLEDGE GRAPH\n\nNode ID: {kg_node['node_id']}\nTyp: {kg_node['node_type']}\nWichtigkeit: {kg_node.get('importance', 0.5):.2f}\nZugriffe: {kg_node.get('access_count', 0)}\n"
            connections = self.sim.db.get_node_connections(agent_id)
            if connections['outgoing']:
                kg_text += f"\n📤 BEEINFLUSST ANDERE ({len(connections['outgoing'])}):\n"
                for edge in connections['outgoing'][:10]:
                    kg_text += f"  → {edge.get('to_node', '?')} (Stärke: {edge.get('strength', 0.5):.2f})\n"
            if connections['incoming']:
                kg_text += f"\n📥 WURDE BEEINFLUSST VON ({len(connections['incoming'])}):\n"
                for edge in connections['incoming'][:10]:
                    kg_text += f"  ← {edge.get('from_node', '?')} (Stärke: {edge.get('strength', 0.5):.2f})\n"
        else:
            kg_text = "🔮 Kein Knowledge Graph Knoten gefunden."
        self.pool_detail_kg.insert(tk.END, kg_text)
        
        self.pool_detail_influences.delete(1.0, tk.END)
        influences = self.sim.db.get_influences(agent_id)
        infl_text = f"🔄 EINFLÜSSE\n\nGegebene Einflüsse: {influences.get('given_count', 0)}\n"
        for inf in influences.get('given', [])[:10]:
            infl_text += f"  → {inf.get('to_name', inf.get('to'))} (Stärke: {inf.get('strength', 0.5):.2f})\n"
        infl_text += f"\nErhaltene Einflüsse: {influences.get('received_count', 0)}\n"
        for inf in influences.get('received', [])[:10]:
            infl_text += f"  ← {inf.get('from_name', inf.get('from'))} (Stärke: {inf.get('strength', 0.5):.2f})\n"
        self.pool_detail_influences.insert(tk.END, infl_text)
        
        self.pool_detail_scores.delete(1.0, tk.END)
        scores = self.sim.db.get_agent_score_history(agent_id, 20)
        total_points = sum(s.get('points', 0) for s in scores)
        score_text = f"⭐ PUNKTE & PROGNOSEN\n\nPunkte: {total_points}\n\nPrognosen:\n"
        prognoses = self.sim.db.get_agent_prognoses(agent_id, 10)
        for prog in prognoses[:10]:
            score_text += f"  • {prog.get('topic', '?')}: {prog.get('prediction', '')[:80]}...\n"
        self.pool_detail_scores.insert(tk.END, score_text)
        
        self.pool_detail_citations.delete(1.0, tk.END)
        citations = self.sim.db.get_agent_citations(agent_id, 20)
        cit_text = f"📚 DOKUMENTEN-ZITATE ({len(citations)})\n\n"
        if citations:
            for cit in citations[:20]:
                cit_text += f"  • {cit.get('quoted_text', '')[:100]}\n"
                cit_text += f"    📁 {cit.get('project', '?')}/{cit.get('document', '?')}\n"
                cit_text += f"    ⭐ Genauigkeit: {cit.get('accuracy', 0)*100:.0f}% | Punkte: {cit.get('points_awarded', 0)}\n\n"
        else:
            cit_text += "  Keine Dokumenten-Zitate vorhanden.\n"
        self.pool_detail_citations.insert(tk.END, cit_text)
        
        self.pool_detail_external.delete(1.0, tk.END)
        ext_citations = self.sim.db.get_agent_external_citations(agent_id, 20)
        ext_text = f"📖 EXTERNE ZITATE ({len(ext_citations)})\n\n"
        if ext_citations:
            for cit in ext_citations[:20]:
                ext_text += f"  • {cit.get('source', '?')}\n"
                if cit.get('quoted_text'):
                    ext_text += f"    💬 {cit.get('quoted_text', '')[:100]}\n"
                if cit.get('reference'):
                    ext_text += f"    📖 {cit.get('reference', '')[:100]}\n"
                ext_text += f"    📅 {cit.get('created_at', 'unbekannt')[:19]}\n\n"
        else:
            ext_text += "  Keine externen Zitate vorhanden.\n"
        self.pool_detail_external.insert(tk.END, ext_text)
    
    def export_pool_results_json(self):
        try:
            results = self.current_pool_results
            if not results:
                messagebox.showwarning("Achtung", "Keine Ergebnisse zum Exportieren")
                return
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=f"pool_results_{timestamp}.json"
            )
            if filename:
                export_data = []
                for agent in results:
                    export_data.append({
                        "name": agent.get('name', ''),
                        "role": agent.get('role', ''),
                        "set_name": agent.get('set_name', ''),
                        "generation_mode": agent.get('generation_mode', '')
                    })
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Export", f"Exportiert nach:\n{filename}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Export fehlgeschlagen: {str(e)}")
    
    def export_pool_results_csv(self):
        try:
            results = self.current_pool_results
            if not results:
                messagebox.showwarning("Achtung", "Keine Ergebnisse zum Exportieren")
                return
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"pool_results_{timestamp}.csv"
            )
            if filename:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Name", "Rolle", "Set", "Generierungs-Modus"])
                    for agent in results:
                        writer.writerow([
                            agent.get('name', ''),
                            agent.get('role', ''),
                            agent.get('set_name', ''),
                            agent.get('generation_mode', '')
                        ])
                messagebox.showinfo("Export", f"Exportiert nach:\n{filename}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Export fehlgeschlagen: {str(e)}")
    
    def load_from_pool(self):
        selection = self.pool_listbox.curselection()
        if not selection:
            messagebox.showwarning("Achtung", "Bitte Agenten auswählen!")
            return
        
        agent_names = []
        for idx in selection:
            line = self.pool_listbox.get(idx)
            if line.startswith("❌"):
                continue
            agent_names.append(line.split(" | ")[0])
        
        if not agent_names:
            return
        
        def _show_error(msg):
            messagebox.showerror("Fehler", msg)
        
        def load_thread():
            try:
                if self.sim.load_agents_from_pool(agent_names):
                    self.root.after(0, lambda: self._agents_loaded(len(agent_names)))
                    self.root.after(0, lambda: self.refresh_team_agent_list())
                    self.root.after(0, lambda: self.update_debate_agent_list())
                    self.root.after(0, lambda: self.notebook.select(self.tab_main))
                else:
                    self.root.after(0, lambda: _show_error("Agenten konnten nicht geladen werden!"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: _show_error(error_msg))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
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
    
    def show_knowledge_graph(self):
        stats = self.sim.knowledge_graph.get_stats()
        self.knowledge_text.delete(1.0, tk.END)
        text = f"🔮 KNOWLEDGE GRAPH\n{'='*60}\n\n📊 STATISTIK:\n• Knoten: {stats['kg_nodes']}\n• Kanten: {stats['kg_edges']}\n• Aktive Agenten: {stats['active_agents']}\n• Themen: {stats['topics']}\n• Teams: {stats['teams']}\n• Prognosen: {stats['prognoses']}\n• Diskussionen: {stats['discussions']}\n\n📌 KNOTEN-TYPEN:\n"
        for ntype, count in stats.get('node_types', {}).items():
            text += f"  • {ntype}: {count}\n"
        edges = self.sim.knowledge_graph.get_edges(limit=20)
        if edges:
            text += f"\n🔗 LETZTE KANTEN:\n"
            for edge in edges[-10:]:
                from_val = edge.get('from') or edge.get('from_node', '?')
                to_val = edge.get('to') or edge.get('to_node', '?')
                rel = edge.get('relation', '?')
                text += f"  {from_val} --({rel})--> {to_val}\n"
        self.knowledge_text.insert(tk.END, text)
    
    def show_graph_stats(self):
        self.show_knowledge_graph()
    
    def show_topics(self):
        topics = self.sim.knowledge_graph.get_all_topics()
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "📚 THEMEN\n" + "="*60 + "\n\n")
        if not topics:
            self.knowledge_text.insert(tk.END, "Keine Themen vorhanden.\n")
            return
        for topic in topics:
            self.knowledge_text.insert(tk.END, f"📌 {topic.get('name', 'Unbekannt')}\n   • {topic.get('node_count', 0)} Knoten\n\n")
    
    def show_teams(self):
        teams = self.sim.knowledge_graph.get_all_teams()
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(tk.END, "👥 TEAMS\n" + "="*60 + "\n\n")
        if not teams:
            self.knowledge_text.insert(tk.END, "Keine Teams vorhanden.\n")
            return
        for team in teams:
            self.knowledge_text.insert(tk.END, f"🏆 {team.get('name', 'Unbekannt')}\n   • {team.get('member_count', 0)} Mitglieder\n\n")
    
    def refresh_dashboard(self):
        stats = self.sim.get_db_info()
        self.stats_labels["agents"].config(text=str(stats.get('total_agents', 0)))
        self.stats_labels["active"].config(text=str(stats.get('active_agents', 0)))
        self.stats_labels["teams"].config(text=str(stats.get('teams', 0)))
        self.stats_labels["facts"].config(text=str(stats.get('kg_nodes', 0)))
        self.stats_labels["contributions"].config(text=str(stats.get('contributions', 0)))
        self.stats_labels["points"].config(text=str(stats.get('total_points', 0)))
        self.stats_labels["citations"].config(text=str(stats.get('citations', 0)))
        self.stats_labels["external_citations"].config(text=str(stats.get('external_citations', 0)))
        
        self.rank_leaderboard_listbox.delete(0, tk.END)
        leaderboard = self.sim.db.get_leaderboard_by_rank(15)
        if leaderboard:
            for item in leaderboard:
                rank_icons = {"Junior": "⚪", "Senior": "🟢", "Experte": "🔵", "Master": "🏆"}
                icon = rank_icons.get(item.get('rank', 'Junior'), "⚪")
                name = item.get('name', '?')[:20]
                rank = item.get('rank', '?')
                xp = item.get('experience_points', 0)
                self.rank_leaderboard_listbox.insert(tk.END, f"{icon} {name:20} {rank:8} {xp:6d} XP")
        else:
            self.rank_leaderboard_listbox.insert(tk.END, "Keine Agenten mit Rang")
        
        self.top_points_listbox.delete(0, tk.END)
        leaderboard = self.sim.db.get_leaderboard(10)
        if leaderboard:
            for i, item in enumerate(leaderboard, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                self.top_points_listbox.insert(tk.END, f"{medal} {item.get('name', '?')[:20]:20} {item.get('total_points', 0):4d} Punkte")
        
        self.top_contrib_listbox.delete(0, tk.END)
        conn = self.sim.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT a.name, COUNT(c.contribution_id) as cnt FROM contributions c JOIN agents a ON c.agent_id = a.agent_id GROUP BY a.agent_id ORDER BY cnt DESC LIMIT 10")
            for i, (name, cnt) in enumerate(cursor.fetchall(), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                self.top_contrib_listbox.insert(tk.END, f"{medal} {name[:20]:20} {cnt:4d} Beiträge")
        except:
            self.top_contrib_listbox.insert(tk.END, "Keine Daten")
        finally:
            conn.close()
        
        self.top_facts_listbox.delete(0, tk.END)
        conn = self.sim.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT a.name, COUNT(mc.crystal_id) as cnt FROM memory_crystals mc JOIN memory_rooms mr ON mc.room_id = mr.room_id JOIN agents a ON mr.agent_id = a.agent_id GROUP BY a.agent_id ORDER BY cnt DESC LIMIT 10")
            for i, (name, cnt) in enumerate(cursor.fetchall(), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                self.top_facts_listbox.insert(tk.END, f"{medal} {name[:20]:20} {cnt:4d} Fakten")
        except:
            self.top_facts_listbox.insert(tk.END, "Keine Daten")
        finally:
            conn.close()
        
        self.top_influence_listbox.delete(0, tk.END)
        conn = self.sim.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT a.name, (SELECT COUNT(*) FROM influences WHERE influencer_id = a.agent_id) as given, (SELECT COUNT(*) FROM influences WHERE influenced_id = a.agent_id) as received FROM agents a ORDER BY given + received DESC LIMIT 10")
            for i, (name, given, received) in enumerate(cursor.fetchall(), 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                total = given + received
                self.top_influence_listbox.insert(tk.END, f"{medal} {name[:20]:20} {total:3d} ({given}→{received})")
        except:
            self.top_influence_listbox.insert(tk.END, "Keine Daten")
        finally:
            conn.close()
        
        self.team_text.delete(1.0, tk.END)
        if self.sim.teams:
            for team_name, team_agents in self.sim.teams.items():
                active = sum(1 for a in team_agents if not a.ausgeschlossen)
                points = 0
                for a in team_agents:
                    scores = self.sim.db.get_agent_score_history(a.agent_id, 100)
                    points += sum(s.get('points', 0) for s in scores)
                self.team_text.insert(tk.END, f"🏆 {team_name}\n   • {active}/{len(team_agents)} aktiv\n   • {points} Punkte\n\n")
        
        self.prognosis_listbox.delete(0, tk.END)
        prognoses = self.sim.knowledge_graph.get_prognosis_stats()
        self.prognosis_listbox.insert(tk.END, f"Gesamt: {prognoses.get('total', 0)}")
        self.prognosis_listbox.insert(tk.END, f"Verifiziert: {prognoses.get('verified', 0)}")
        self.prognosis_listbox.insert(tk.END, f"Genauigkeit: {prognoses.get('accuracy', 0):.1f}%")
    
    def test_connection(self):
        provider = self.provider_var.get()
        Config.LM_PROVIDER = provider
        self.sim.lm.provider = provider
        ok, msg = self.sim.lm.test()
        if ok:
            messagebox.showinfo("Erfolg", f"✅ {msg}")
        else:
            messagebox.showerror("Fehler", f"❌ {msg}")
    
    def save_config(self):
        Config.LM_PROVIDER = self.provider_var.get()
        Config.LM_STUDIO_URL = self.lm_url_var.get()
        Config.OLLAMA_URL = self.ollama_url_var.get()
        Config.OLLAMA_MODEL = self.ollama_model_var.get()
        Config.TEMPERATURE = self.temp_var.get()
        Config.MAX_TOKENS = self.tokens_var.get()
        Config.TIMEOUT = self.timeout_var.get()
        
        Config.EMBEDDING_PROVIDER = self.embedding_provider_var.get()
        Config.EMBEDDING_MODEL = self.embedding_model_var.get()
        
        self.sim.lm.provider = Config.LM_PROVIDER
        self.sim.embedding_client.provider = Config.EMBEDDING_PROVIDER
        self.sim.embedding_client.model = Config.EMBEDDING_MODEL
        
        if Config.save_to_file():
            messagebox.showinfo("Erfolg", "✅ Einstellungen gespeichert!")
        else:
            messagebox.showerror("Fehler", "❌ Speichern fehlgeschlagen!")
    
    def toggle_external(self):
        self.sim.plugin_manager.use_external = self.use_external_var.get()
    
    def toggle_plugin(self, key):
        self.sim.plugin_manager.enable_plugin(key, self.plugin_vars[key].get())
    
    def test_search(self):
        query = self.test_entry.get()
        if not query or query == "Suchbegriff...":
            messagebox.showwarning("Achtung", "Bitte Suchbegriff eingeben!")
            return
        self.test_result.delete(1.0, tk.END)
        self.test_result.insert(tk.END, "🔍 Suche läuft...\n")
        self.root.update()
        old_use = self.sim.plugin_manager.use_external
        old_states = {}
        for key, plugin in self.sim.plugin_manager.get_all_plugins().items():
            old_states[key] = plugin.enabled
            plugin.enabled = True
        self.sim.plugin_manager.use_external = True
        try:
            results = self.sim.plugin_manager.search_all(query, 5)
            formatted = self.sim.plugin_manager.format_all_results(results)
            self.test_result.delete(1.0, tk.END)
            self.test_result.insert(tk.END, formatted if formatted else "Keine Ergebnisse.")
        except Exception as e:
            self.test_result.insert(tk.END, f"❌ Fehler: {str(e)}")
        finally:
            self.sim.plugin_manager.use_external = old_use
            for key, enabled in old_states.items():
                if key in self.sim.plugin_manager.get_all_plugins():
                    self.sim.plugin_manager.get_all_plugins()[key].enabled = enabled
    
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
    
    def _update_status(self, text):
        self.statusbar.config(text=text)
    
    def load_url(self):
        url = self.url_entry.get().strip()
        if not url or url == "https://...":
            messagebox.showwarning("Achtung", "Bitte URL eingeben!")
            return
        
        self.doc_preview.delete(1.0, tk.END)
        self.doc_preview.insert(1.0, "⏳ Lade Dokument...")
        self.root.update()
        
        def load_thread():
            try:
                doc = self.sim.load_document(url, "url")
                self.root.after(0, lambda: self.display_document(doc))
            except Exception as e:
                self.root.after(0, lambda: self.doc_preview.delete(1.0, tk.END))
                self.root.after(0, lambda: self.doc_preview.insert(1.0, f"❌ Fehler: {str(e)}"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def browse_file(self):
        filepath = filedialog.askopenfilename(
            title="Dokument auswählen",
            filetypes=[
                ("Alle unterstützten", "*.txt *.pdf *.html *.htm *.json"),
                ("Textdateien", "*.txt"),
                ("PDF", "*.pdf"),
                ("HTML", "*.html *.htm"),
                ("JSON", "*.json")
            ]
        )
        if filepath:
            self.file_path_var.set(filepath)
            self.load_file()
    
    def load_file(self):
        filepath = self.file_path_var.get().strip()
        if not filepath:
            messagebox.showwarning("Achtung", "Bitte Datei auswählen!")
            return
        
        if not os.path.exists(filepath):
            messagebox.showerror("Fehler", "Datei nicht gefunden!")
            return
        
        self.doc_preview.delete(1.0, tk.END)
        self.doc_preview.insert(1.0, "⏳ Lade Dokument...")
        self.root.update()
        
        def load_thread():
            try:
                doc = self.sim.load_document(filepath, "file")
                self.root.after(0, lambda: self.display_document(doc))
            except Exception as e:
                self.root.after(0, lambda: self.doc_preview.delete(1.0, tk.END))
                self.root.after(0, lambda: self.doc_preview.insert(1.0, f"❌ Fehler: {str(e)}"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def load_multiple(self):
        try:
            json_text = self.multi_text.get(1.0, tk.END).strip()
            sources = json.loads(json_text)
            
            if not isinstance(sources, list):
                raise ValueError("JSON muss eine Liste sein")
            
            self.doc_preview.delete(1.0, tk.END)
            self.doc_preview.insert(1.0, "⏳ Lade mehrere Dokumente...")
            self.root.update()
            
            def load_thread():
                try:
                    doc = self.sim.load_multiple_documents(sources)
                    self.root.after(0, lambda: self.display_document(doc))
                except Exception as e:
                    self.root.after(0, lambda: self.doc_preview.delete(1.0, tk.END))
                    self.root.after(0, lambda: self.doc_preview.insert(1.0, f"❌ Fehler: {str(e)}"))
            
            threading.Thread(target=load_thread, daemon=True).start()
            
        except json.JSONDecodeError as e:
            messagebox.showerror("Fehler", f"Ungültiges JSON: {e}")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def display_document(self, doc: Dict):
        self.current_document = doc
        self.doc_preview.delete(1.0, tk.END)
        
        preview = f"📄 {doc['title']}\n"
        preview += f"📁 Quelle: {doc['source']}\n"
        preview += f"📅 Geladen: {doc['loaded_at']}\n"
        preview += f"📏 Länge: {len(doc['content'])} Zeichen\n"
        preview += f"{'='*60}\n\n"
        preview += doc['content'][:2000]
        if len(doc['content']) > 2000:
            preview += "\n... (gekürzt)"
        
        self.doc_preview.insert(1.0, preview)
        self._update_status(f"✅ Dokument geladen: {doc['title']}")
    
    def use_document_for_discussion(self):
        if hasattr(self, 'current_document') and self.current_document:
            self.doc_text.delete(1.0, tk.END)
            self.doc_text.insert(1.0, self.current_document['content'])
            self._update_status(f"📋 Dokument als Diskussionsgrundlage übernommen")
        else:
            messagebox.showwarning("Achtung", "Kein Dokument geladen!")
    
    def show_network_graph(self):
        self.viz_status.config(text="📊 Erstelle Netzwerk-Graph...")
        self.root.update()
        
        def render():
            try:
                nodes, edges = self.sim.get_network_data()
                fig = self.sim.visualization.draw_network_graph(nodes, edges, "Einfluss-Netzwerk")
                self.root.after(0, lambda: self._display_viz(fig))
                self.root.after(0, lambda: self.viz_status.config(text="✅ Netzwerk-Graph geladen"))
            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: self.viz_status.config(text=f"❌ Fehler: {error_msg}"))
        
        threading.Thread(target=render, daemon=True).start()
    
    def show_heatmap(self):
        self.viz_status.config(text="🔥 Erstelle Heatmap...")
        self.root.update()
        
        def render():
            try:
                contributions = []
                for line in self.sim.discussion_log:
                    if ": " in line:
                        parts = line.split(": ", 1)
                        if len(parts) == 2:
                            contributions.append({
                                "agent": parts[0],
                                "content": parts[1],
                                "round": self.sim.current_round
                            })
                
                agents = [a.name for a in self.sim.agents]
                heatmap_data = self.sim.result_analyzer.generate_heatmap_data(contributions, agents)
                
                fig = self.sim.visualization.draw_heatmap(
                    heatmap_data["agents"], heatmap_data["topics"], heatmap_data["matrix"],
                    "Agenten vs. Themen"
                )
                self.root.after(0, lambda: self._display_viz(fig))
                self.root.after(0, lambda: self.viz_status.config(text="✅ Heatmap geladen"))
            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: self.viz_status.config(text=f"❌ Fehler: {error_msg}"))
        
        threading.Thread(target=render, daemon=True).start()
    
    def show_sentiment_timeline(self):
        self.viz_status.config(text="📈 Erstelle Sentiment-Verlauf...")
        self.root.update()
        
        def render():
            try:
                contributions = []
                for line in self.sim.discussion_log:
                    if ": " in line:
                        parts = line.split(": ", 1)
                        if len(parts) == 2:
                            contributions.append({
                                "agent": parts[0],
                                "content": parts[1],
                                "round": self.sim.current_round
                            })
                
                sentiment_data = self.sim.result_analyzer.analyze_sentiment_timeline(contributions)
                fig = self.sim.visualization.draw_timeline(sentiment_data["timeline"], "Sentiment-Verlauf")
                self.root.after(0, lambda: self._display_viz(fig))
                self.root.after(0, lambda: self.viz_status.config(text="✅ Sentiment-Verlauf geladen"))
            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: self.viz_status.config(text=f"❌ Fehler: {error_msg}"))
        
        threading.Thread(target=render, daemon=True).start()
    
    def show_wordcloud(self):
        self.viz_status.config(text="☁️ Erstelle Wortwolke...")
        self.root.update()
        
        def render():
            try:
                contributions = []
                for line in self.sim.discussion_log:
                    if ": " in line:
                        parts = line.split(": ", 1)
                        if len(parts) == 2:
                            contributions.append({
                                "agent": parts[0],
                                "content": parts[1],
                                "round": self.sim.current_round
                            })
                
                wordcloud_data = self.sim.result_analyzer.generate_wordcloud_data(contributions)
                fig = self.sim.visualization.draw_wordcloud(wordcloud_data["words"], "Wortwolke")
                self.root.after(0, lambda: self._display_viz(fig))
                self.root.after(0, lambda: self.viz_status.config(text="✅ Wortwolke geladen"))
            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: self.viz_status.config(text=f"❌ Fehler: {error_msg}"))
        
        threading.Thread(target=render, daemon=True).start()
    
    def show_consensus_gauge(self):
        self.viz_status.config(text="🎯 Erstelle Konsens-Tacho...")
        self.root.update()
        
        def render():
            try:
                contributions = []
                for line in self.sim.discussion_log:
                    if ": " in line:
                        parts = line.split(": ", 1)
                        if len(parts) == 2:
                            contributions.append({
                                "agent": parts[0],
                                "content": parts[1],
                                "round": self.sim.current_round
                            })
                
                consensus_data = self.sim.result_analyzer.measure_consensus(contributions)
                fig = self.sim.visualization.draw_consensus_gauge(
                    consensus_data["overall_consensus"], 
                    f"Konsens: {consensus_data['overall_consensus']*100:.1f}%"
                )
                self.root.after(0, lambda: self._display_viz(fig))
                self.root.after(0, lambda: self.viz_status.config(text="✅ Konsens-Tacho geladen"))
            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: self.viz_status.config(text=f"❌ Fehler: {error_msg}"))
        
        threading.Thread(target=render, daemon=True).start()
    
    def show_argument_tree(self):
        self.viz_status.config(text="🌳 Erstelle Argument-Baum...")
        self.root.update()
        
        def render():
            try:
                contributions = []
                for line in self.sim.discussion_log:
                    if ": " in line:
                        parts = line.split(": ", 1)
                        if len(parts) == 2:
                            contributions.append({
                                "agent": parts[0],
                                "content": parts[1],
                                "round": self.sim.current_round
                            })
                
                argument_map = self.sim.result_analyzer.build_argument_map(contributions)
                fig = self.sim.visualization.draw_argument_tree(argument_map, "Argument-Baum")
                self.root.after(0, lambda: self._display_viz(fig))
                self.root.after(0, lambda: self.viz_status.config(text="✅ Argument-Baum geladen"))
            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: self.viz_status.config(text=f"❌ Fehler: {error_msg}"))
        
        threading.Thread(target=render, daemon=True).start()
    
    def _display_viz(self, fig):
        for widget in self.viz_canvas_frame.winfo_children():
            widget.destroy()
        
        canvas_frame = tb.Frame(self.viz_canvas_frame, bootstyle="dark")
        canvas_frame.pack(fill=BOTH, expand=True)
        
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=BOTH, expand=True)
    
    def export_html_report(self):
        if not self.sim.discussion_log:
            messagebox.showwarning("Achtung", "Keine Diskussion zum Exportieren!")
            return
        
        contributions = []
        for line in self.sim.discussion_log:
            if ": " in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    contributions.append({
                        "agent": parts[0],
                        "content": parts[1],
                        "round": self.sim.current_round
                    })
        
        report = self.sim.result_analyzer.generate_full_report(
            contributions, self.sim.agents, self.sim.current_topic
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialfile=f"report_{timestamp}.html"
        )
        
        if filename:
            try:
                path = self.sim.visualization.export_to_html(report, filename)
                messagebox.showinfo("Export", f"Exportiert nach:\n{path}")
                webbrowser.open(path)
            except Exception as e:
                messagebox.showerror("Fehler", str(e))
    
    def export_pdf_report(self):
        if not self.sim.discussion_log:
            messagebox.showwarning("Achtung", "Keine Diskussion zum Exportieren!")
            return
        
        contributions = []
        for line in self.sim.discussion_log:
            if ": " in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    contributions.append({
                        "agent": parts[0],
                        "content": parts[1],
                        "round": self.sim.current_round
                    })
        
        report = self.sim.result_analyzer.generate_full_report(
            contributions, self.sim.agents, self.sim.current_topic
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"report_{timestamp}.pdf"
        )
        
        if filename:
            try:
                path = self.sim.visualization.export_to_pdf(report, filename)
                messagebox.showinfo("Export", f"Exportiert nach:\n{path}")
            except Exception as e:
                messagebox.showerror("Fehler", f"PDF-Export fehlgeschlagen:\n{e}\n\nHTML wurde stattdessen erstellt.")
                html_path = path.replace('.pdf', '.html')
                if os.path.exists(html_path):
                    webbrowser.open(html_path)
    
    def analyze_current_discussion(self):
        if not self.sim.discussion_log:
            messagebox.showwarning("Achtung", "Keine Diskussion zum Analysieren!")
            return
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, "⏳ Analysiere Diskussion...\n")
        self.root.update()
        
        contributions = []
        for line in self.sim.discussion_log:
            if ": " in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    contributions.append({
                        "agent": parts[0],
                        "content": parts[1],
                        "round": self.sim.current_round
                    })
        
        report = self.sim.result_analyzer.generate_full_report(
            contributions, self.sim.agents, self.sim.current_topic
        )
        
        self.current_report = report
        self._display_report_summary(report)
    
    def _display_report_summary(self, report: Dict):
        self.results_text.delete(1.0, tk.END)
        
        text = f"""
{'='*60}
📊 ANALYSE-BERICHT
{'='*60}

📝 THEMA: {report.get('topic', 'Unbekannt')}
📅 ZEITPUNKT: {report.get('timestamp', 'Unbekannt')}

📈 ZUSAMMENFASSUNG:
  • Beiträge: {report['summary']['total_contributions']}
  • Agenten: {report['summary']['unique_agents']}
  • Runden: {report['summary']['total_rounds']}

{'='*60}
📌 ZENTRALE THESEN ({len(report.get('theses', []))})
{'='*60}
"""
        
        for i, thesis in enumerate(report.get('theses', [])[:10], 1):
            text += f"\n{i}. \"{thesis['thesis']}\"\n"
            text += f"   ✅ Pro: {', '.join(thesis.get('proponents', [])[:3]) or 'keine'}\n"
            text += f"   ❌ Contra: {', '.join(thesis.get('opponents', [])[:3]) or 'keine'}\n"
            text += f"   ⭐ Konfidenz: {thesis['confidence']*100:.0f}%\n"
        
        text += f"\n{'='*60}\n🎯 KONSENS-MESSUNG\n{'='*60}\n"
        consensus = report.get('consensus', {})
        text += f"  • Gesamtkonsens: {consensus.get('overall_consensus', 0)*100:.1f}%\n"
        text += f"  • Polarisierung: {consensus.get('polarization', 0):.2f}\n"
        
        text += f"\n{'='*60}\n💬 TOP-ZITATE\n{'='*60}\n"
        for i, quote in enumerate(report.get('key_quotes', [])[:10], 1):
            type_icon = {"thesis": "💡", "insight": "🔍", "counter": "⚡", "agreement": "✅", "question": "❓"}.get(quote.get('type'), "💬")
            text += f"{i}. {type_icon} {quote['agent']}: \"{quote['text'][:150]}...\"\n\n"
        
        text += f"\n{'='*60}\n🎭 THEMEN-CLUSTER\n{'='*60}\n"
        clusters = report.get('clusters', {}).get('clusters', [])
        for i, cluster in enumerate(clusters[:5], 1):
            text += f"{i}. {cluster['name']}\n"
            text += f"   Keywords: {', '.join(cluster.get('keywords', [])[:5])}\n"
            text += f"   Agenten: {', '.join(cluster.get('agents', [])[:3])}\n"
            text += f"   Beiträge: {cluster.get('size', 0)}\n\n"
        
        self.results_text.insert(1.0, text)
    
    def show_theses(self):
        if not hasattr(self, 'current_report'):
            messagebox.showwarning("Achtung", "Bitte zuerst Analyse starten!")
            return
        
        self.results_text.delete(1.0, tk.END)
        text = "📌 ZENTRALE THESEN\n" + "="*40 + "\n\n"
        
        for i, thesis in enumerate(self.current_report.get('theses', [])[:20], 1):
            text += f"{i}. \"{thesis['thesis']}\"\n"
            text += f"   ✅ Pro: {', '.join(thesis.get('proponents', [])[:5]) or 'keine'}\n"
            text += f"   ❌ Contra: {', '.join(thesis.get('opponents', [])[:5]) or 'keine'}\n"
            text += f"   ⭐ Konfidenz: {thesis['confidence']*100:.0f}%\n\n"
        
        self.results_text.insert(1.0, text)
    
    def show_top_quotes(self):
        if not hasattr(self, 'current_report'):
            messagebox.showwarning("Achtung", "Bitte zuerst Analyse starten!")
            return
        
        self.results_text.delete(1.0, tk.END)
        text = "💬 TOP-ZITATE\n" + "="*40 + "\n\n"
        
        for i, quote in enumerate(self.current_report.get('key_quotes', [])[:20], 1):
            type_icon = {"thesis": "💡", "insight": "🔍", "counter": "⚡", "agreement": "✅", "question": "❓"}.get(quote.get('type'), "💬")
            text += f"{i}. {type_icon} {quote['agent']} (Runde {quote['round']}):\n"
            text += f"   \"{quote['text']}\"\n\n"
        
        self.results_text.insert(1.0, text)
    
    def show_consensus(self):
        if not hasattr(self, 'current_report'):
            messagebox.showwarning("Achtung", "Bitte zuerst Analyse starten!")
            return
        
        self.results_text.delete(1.0, tk.END)
        consensus = self.current_report.get('consensus', {})
        
        text = f"🎯 KONSENS-MESSUNG\n" + "="*40 + "\n\n"
        text += f"📊 Gesamtkonsens: {consensus.get('overall_consensus', 0)*100:.1f}%\n"
        text += f"⚡ Polarisierung: {consensus.get('polarization', 0):.2f}\n\n"
        
        text += "👥 AGENTEN-KONSENS:\n"
        for agent, agreement in consensus.get('agent_agreement', {}).items():
            text += f"  • {agent}: {agreement*100:.0f}% Übereinstimmung\n"
        
        text += "\n📋 KONSENS PRO THESE:\n"
        for thesis, cons in consensus.get('per_thesis', {}).items():
            text += f"  • {thesis[:60]}...: {cons*100:.0f}%\n"
        
        self.results_text.insert(1.0, text)
    
    def show_clusters(self):
        if not hasattr(self, 'current_report'):
            messagebox.showwarning("Achtung", "Bitte zuerst Analyse starten!")
            return
        
        self.results_text.delete(1.0, tk.END)
        clusters = self.current_report.get('clusters', {}).get('clusters', [])
        
        text = f"🎭 THEMEN-CLUSTER\n" + "="*40 + f"\n\nInsgesamt: {len(clusters)} Cluster\n\n"
        
        for i, cluster in enumerate(clusters[:15], 1):
            text += f"{i}. {cluster['name']}\n"
            text += f"   📌 Keywords: {', '.join(cluster.get('keywords', [])[:8])}\n"
            text += f"   👥 Agenten: {', '.join(cluster.get('agents', [])[:5])}\n"
            text += f"   📄 Beiträge: {cluster.get('size', 0)}\n\n"
        
        self.results_text.insert(1.0, text)


def main():
    app = SynthAgoraGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()