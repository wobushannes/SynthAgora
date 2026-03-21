#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migrations-Tools für SynthAgora
- JSON -> SQLite Migration
- Agenten-JSONs in Datenbank importieren (NUR NEUE)
- Knowledge Graph migrieren (NUR EINMAL)
- Duplikatbereinigung
"""

import json
import os
import glob
import hashlib
import re
import threading
from datetime import datetime
from typing import List, Dict, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import ttkbootstrap as tb
from ttkbootstrap.constants import *

from .database import SynthAgoraDB
from .config import Config


class MigrationTool:
    """Tool für Migration von JSON zu SQLite"""
    
    def __init__(self, db: SynthAgoraDB = None):
        self.db = db or SynthAgoraDB()
        self.stats = {
            "agent_sets": 0,
            "agents": 0,
            "nodes": 0,
            "edges": 0,
            "errors": 0,
            "skipped": 0,
            "kg_skipped": False
        }
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        self.progress_callback = callback
    
    def _update_progress(self, message: str, current: int = None, total: int = None):
        if self.progress_callback:
            self.progress_callback(message, current, total)
    
    def migrate_all(self, agents_folder: str = None, knowledge_file: str = None) -> Dict:
        """Führt alle Migrationen durch"""
        self.stats = {
            "agent_sets": 0,
            "agents": 0,
            "nodes": 0,
            "edges": 0,
            "errors": 0,
            "skipped": 0,
            "kg_skipped": False
        }
        
        self._update_progress("🚀 Starte Migration...")
        print("🚀 Starte Migration...")
        
        if agents_folder is None:
            agents_folder = Config.AGENTS_FOLDER
        
        self._migrate_agents_folder(agents_folder)
        
        if knowledge_file is None:
            knowledge_file = os.path.join(Config.KNOWLEDGE_FOLDER, "knowledge_graph.json")
        
        if os.path.exists(knowledge_file):
            if self.db.get_setting('kg_migrated', False):
                print("⏭️ Knowledge Graph bereits migriert (überspringe)")
                self.stats["kg_skipped"] = True
                self._update_progress("⏭️ Knowledge Graph bereits migriert")
            else:
                self._migrate_knowledge_graph(knowledge_file)
                self.db.set_setting('kg_migrated', True, 'bool')
        
        print(f"✅ Migration abgeschlossen: {self.stats}")
        self._update_progress(f"✅ Fertig: {self.stats['agents']} neue Agenten")
        return self.stats
    
    def _migrate_agents_folder(self, folder: str):
        """Migriert NUR NEUE Agenten-JSONs im Ordner"""
        if not os.path.exists(folder):
            print(f"⚠️ Ordner nicht gefunden: {folder}")
            return
        
        # Bereits migrierte JSONs ermitteln
        conn = None
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT json_file FROM agent_pool")
            existing_files = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Fehler beim Lesen der migrierten Dateien: {e}")
            existing_files = []
        finally:
            if conn:
                conn.close()
        
        json_files = glob.glob(f"{folder}/*.json")
        new_files = [f for f in json_files if f not in existing_files]
        
        print(f"📁 {len(new_files)} neue JSONs, {len(existing_files)} bereits migriert")
        self._update_progress(f"📁 {len(new_files)} neue JSONs gefunden")
        
        for idx, json_file in enumerate(new_files):
            try:
                self._migrate_agent_set(json_file)
                self.stats["agent_sets"] += 1
                self._update_progress(f"📄 Migriere {idx+1}/{len(new_files)}: {os.path.basename(json_file)}")
            except Exception as e:
                print(f"❌ Fehler bei {json_file}: {e}")
                self.stats["errors"] += 1
        
        self.stats["skipped"] = len(existing_files)
    
    def _migrate_agent_set(self, json_file: str):
        """Migriert EIN Agenten-Set in den Pool"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        set_name = data.get("name", os.path.basename(json_file))
        agents = data.get("agents", [])
        
        print(f"  → Set: {set_name} ({len(agents)} Agenten)")
        
        for idx, agent in enumerate(agents):
            try:
                # Eindeutige ID generieren
                unique = f"{set_name}_{agent['name']}_{idx}".encode()
                agent_id = f"agent_{hashlib.md5(unique).hexdigest()[:12]}"
                
                # Tags extrahieren (aus Rolle) - FIX: role kann Liste sein
                tags = []
                if "role" in agent and agent["role"]:
                    role_value = agent["role"]
                    # Wenn role eine Liste ist, in String umwandeln
                    if isinstance(role_value, list):
                        role_value = " ".join(str(r) for r in role_value)
                    elif not isinstance(role_value, str):
                        role_value = str(role_value)
                    
                    role_clean = re.sub(r'[\(\)\[\]\,\.]', '', role_value)
                    tags.extend(role_clean.lower().split())
                
                # Team als Tag
                if "team" in agent and agent["team"]:
                    team_val = agent["team"]
                    if isinstance(team_val, list):
                        team_val = " ".join(str(t) for t in team_val)
                    tags.append(str(team_val).lower())
                
                # Charakter-Typ als Tag
                if "charakter_typ" in agent and agent["charakter_typ"]:
                    char_val = agent["charakter_typ"]
                    if isinstance(char_val, list):
                        char_val = " ".join(str(c) for c in char_val)
                    tags.append(str(char_val).lower())
                
                # Generation-Input als Tag
                if data.get("generation_input"):
                    tags.append(data["generation_input"].lower())
                
                # Entferne Duplikate und leere Einträge
                tags = [t for t in list(set(tags)) if t and len(t) > 1 and t != "none"]
                
                # Generation-Modus erkennen
                mode = data.get("generation_mode", "import")
                
                # Skills aus agent holen
                skills = agent.get("skills", {})
                if isinstance(skills, str):
                    try:
                        skills = json.loads(skills)
                    except:
                        skills = {}
                
                # Initialen Rang aus agent oder default
                initial_rank = agent.get("initial_rank", agent.get("rank", "Junior"))
                
                # Metadata zusammenbauen
                metadata = {
                    "education": agent.get("education", ""),
                    "background": agent.get("background", ""),
                    "goals": agent.get("goals", []),
                    "fears": agent.get("fears", []),
                    "team": agent.get("team", ""),
                    "charakter_typ": agent.get("charakter_typ", "Realist"),
                    "skills": skills,
                    "initial_rank": initial_rank
                }
                
                # In Pool speichern
                self.db.add_to_pool({
                    "agent_id": agent_id,
                    "set_name": set_name,
                    "name": agent["name"],
                    "role": agent.get("role", ""),
                    "tags": json.dumps(tags),
                    "json_file": json_file,
                    "generation_mode": mode,
                    "generation_date": data.get("generation_date", datetime.now().isoformat()),
                    "metadata": json.dumps(metadata)
                })
                
                self.stats["agents"] += 1
                
            except Exception as e:
                print(f"    ❌ Agent {idx}: {e}")
                self.stats["errors"] += 1
    
    def _migrate_knowledge_graph(self, json_file: str):
        """Migriert alten Knowledge Graph in SQLite"""
        if not os.path.exists(json_file):
            print(f"⚠️ Knowledge Graph nicht gefunden: {json_file}")
            return
        
        print(f"📚 Migriere Knowledge Graph: {json_file}")
        self._update_progress("📚 Migriere Knowledge Graph...")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 1. Nodes migrieren
        nodes = data.get("nodes", {})
        for node_id, node in nodes.items():
            try:
                props = node.get("properties", {})
                if isinstance(props, dict):
                    props = json.dumps(props)
                self.db.add_node(node_id, node.get("type", "unknown"), props)
                self.stats["nodes"] += 1
            except Exception as e:
                print(f"  ❌ Node {node_id}: {e}")
                self.stats["errors"] += 1
        
        # 2. Edges migrieren
        edges = data.get("edges", [])
        for edge in edges:
            try:
                self.db.add_edge(
                    edge["from"],
                    edge["to"],
                    edge.get("relation", "verbunden"),
                    edge.get("strength", 1.0)
                )
                self.stats["edges"] += 1
            except Exception as e:
                print(f"  ❌ Edge: {e}")
                self.stats["errors"] += 1
        
        # 3. Teams migrieren
        teams = data.get("teams", {})
        for team_id, team in teams.items():
            try:
                self.db.add_team(team_id, team.get("name", team_id))
                for member in team.get("members", []):
                    self.db.add_team_member(team_id, member)
            except:
                pass
        
        print(f"  → {self.stats['nodes']} Nodes, {self.stats['edges']} Edges migriert")
    
    def import_single_agent_json(self, json_file: str) -> int:
        """Importiert EINE JSON-Datei in den Pool"""
        old_count = self.stats["agents"]
        self._migrate_agent_set(json_file)
        return self.stats["agents"] - old_count
    
    def cleanup_duplicates(self) -> int:
        """Bereinigt Duplikate im Pool"""
        return self.db.cleanup_duplicates()


# ===================== GUI FENSTER FÜR MIGRATION =====================

class MigrationWindow:
    """Eigenständiges Fenster für Migration"""
    
    def __init__(self, parent):
        self.parent = parent
        self.window = tb.Toplevel(parent)
        self.window.title("🔄 JSON → SQLite Migration")
        self.window.geometry("700x650")
        
        self.db = SynthAgoraDB()
        self.migration = MigrationTool(self.db)
        self.migration.set_progress_callback(self.update_progress)
        
        self._setup_ui()
        self._refresh_stats()
    
    def _setup_ui(self):
        header = tb.Label(self.window, text="🔄 Migration von JSON zu SQLite",
                         font=("Segoe UI", 16, "bold"), bootstyle="primary")
        header.pack(pady=10)
        
        main_frame = tb.Frame(self.window)
        main_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        # ===== STATISTIK =====
        stats_frame = tb.LabelFrame(main_frame, text="📊 Aktuelle Statistik")
        stats_frame.pack(fill=X, pady=5)
        
        stats_content = tb.Frame(stats_frame)
        stats_content.pack(fill=X, padx=10, pady=10)
        
        self.stats_text = scrolledtext.ScrolledText(stats_content, height=8, 
                                                    font=("Consolas", 9))
        self.stats_text.pack(fill=X)
        
        # ===== AGENTEN MIGRATION =====
        agent_frame = tb.LabelFrame(main_frame, text="📁 Agenten-JSONs importieren")
        agent_frame.pack(fill=X, pady=5)
        
        agent_content = tb.Frame(agent_frame)
        agent_content.pack(fill=X, padx=10, pady=10)
        
        tb.Label(agent_content, text="Ordner mit Agenten-JSONs:").pack(anchor=W)
        
        folder_frame = tb.Frame(agent_content)
        folder_frame.pack(fill=X, pady=5)
        
        self.agent_folder_var = tk.StringVar(value=Config.AGENTS_FOLDER)
        folder_entry = tb.Entry(folder_frame, textvariable=self.agent_folder_var)
        folder_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        
        tb.Button(folder_frame, text="📁 Durchsuchen",
                 command=self.browse_agents_folder,
                 bootstyle="primary").pack(side=RIGHT)
        
        self.migrate_agents_btn = tb.Button(agent_content, text="🚀 Agenten importieren (nur neue)",
                                            command=self.migrate_agents,
                                            bootstyle="success", width=30)
        self.migrate_agents_btn.pack(pady=10)
        
        # ===== KNOWLEDGE GRAPH MIGRATION =====
        kg_frame = tb.LabelFrame(main_frame, text="🔮 Knowledge Graph migrieren")
        kg_frame.pack(fill=X, pady=5)
        
        kg_content = tb.Frame(kg_frame)
        kg_content.pack(fill=X, padx=10, pady=10)
        
        self.kg_status_var = tk.StringVar(value="Prüfe Status...")
        kg_status_label = tb.Label(kg_content, textvariable=self.kg_status_var,
                                   bootstyle="info")
        kg_status_label.pack(anchor=W, pady=5)
        
        tb.Label(kg_content, text="Alte knowledge_graph.json:").pack(anchor=W)
        
        kg_file_frame = tb.Frame(kg_content)
        kg_file_frame.pack(fill=X, pady=5)
        
        default_kg = os.path.join(Config.KNOWLEDGE_FOLDER, "knowledge_graph.json")
        self.kg_file_var = tk.StringVar(value=default_kg if os.path.exists(default_kg) else "")
        kg_entry = tb.Entry(kg_file_frame, textvariable=self.kg_file_var)
        kg_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        
        tb.Button(kg_file_frame, text="📁 Durchsuchen",
                 command=self.browse_kg_file,
                 bootstyle="primary").pack(side=RIGHT)
        
        self.migrate_kg_btn = tb.Button(kg_content, text="🔮 Knowledge Graph migrieren (nur einmal)",
                                        command=self.migrate_kg,
                                        bootstyle="primary", width=30)
        self.migrate_kg_btn.pack(pady=10)
        
        # ===== BEREINIGUNG =====
        cleanup_frame = tb.LabelFrame(main_frame, text="🧹 Pool bereinigen")
        cleanup_frame.pack(fill=X, pady=5)
        
        cleanup_content = tb.Frame(cleanup_frame)
        cleanup_content.pack(fill=X, padx=10, pady=10)
        
        tb.Button(cleanup_content, text="🧹 Duplikate entfernen",
                 command=self.cleanup_pool,
                 bootstyle="warning", width=30).pack()
        
        # ===== ALLES MIGRIEREN =====
        all_frame = tb.Frame(main_frame)
        all_frame.pack(fill=X, pady=10)
        
        self.migrate_all_btn = tb.Button(all_frame, text="⚡ ALLES MIGRIEREN",
                                         command=self.migrate_all,
                                         bootstyle="success", width=30)
        self.migrate_all_btn.pack()
        
        # ===== FORTSCHRITT =====
        progress_frame = tb.Frame(main_frame)
        progress_frame.pack(fill=X, pady=10)
        
        self.progress_bar = tb.Progressbar(progress_frame, mode='indeterminate', 
                                           bootstyle="striped")
        self.progress_bar.pack(fill=X)
        
        self.status_label = tb.Label(progress_frame, text="Bereit", 
                                     bootstyle="secondary")
        self.status_label.pack(pady=5)
        
        tb.Button(main_frame, text="Schließen",
                 command=self.window.destroy,
                 bootstyle="secondary").pack(pady=10)
        
        self._update_kg_status()
    
    def _refresh_stats(self):
        """Aktualisiert Statistik-Anzeige"""
        try:
            stats = self.db.get_stats()
            pool_stats = self.db.get_pool_stats()
            
            text = f"""📊 DATENBANK-STATISTIK:

Agenten-Pool: {pool_stats['total']} Agenten
  • Sets: {pool_stats['unique_sets']}
  • JSON-Dateien: {pool_stats.get('unique_json_files', 0)}
  • Nach Modus: {', '.join([f'{k}={v}' for k,v in pool_stats['by_mode'].items()])}

Knowledge Graph:
  • Nodes: {stats['kg_nodes']}
  • Edges: {stats['kg_edges']}
  • Migriert: {'✅' if stats.get('kg_migrated', False) else '❌'}

System:
  • Aktive Agenten: {stats['active_agents']}
  • Diskussionen: {stats['discussions']}
  • Prognosen: {stats['prognoses']}"""
            
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, text)
        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, f"❌ Fehler: {str(e)}")
    
    def _update_kg_status(self):
        """Aktualisiert Knowledge Graph Status-Anzeige"""
        if self.db.get_setting('kg_migrated', False):
            self.kg_status_var.set("✅ Knowledge Graph wurde bereits migriert")
            self.migrate_kg_btn.config(state=tk.DISABLED)
        else:
            self.kg_status_var.set("⏳ Knowledge Graph wurde NOCH NICHT migriert")
            self.migrate_kg_btn.config(state=tk.NORMAL)
    
    def update_progress(self, message: str, current: int = None, total: int = None):
        """Aktualisiert Fortschrittsanzeige"""
        self.status_label.config(text=message)
        if current is not None and total is not None:
            self.progress_bar['value'] = (current / total) * 100
        self.window.update_idletasks()
    
    def browse_agents_folder(self):
        folder = filedialog.askdirectory(initialdir=Config.AGENTS_FOLDER)
        if folder:
            self.agent_folder_var.set(folder)
    
    def browse_kg_file(self):
        file = filedialog.askopenfilename(
            initialdir=Config.KNOWLEDGE_FOLDER,
            filetypes=[("JSON files", "*.json")]
        )
        if file:
            self.kg_file_var.set(file)
    
    def migrate_agents(self):
        """Nur Agenten migrieren (nur neue)"""
        def run():
            self.migrate_agents_btn.config(state=tk.DISABLED)
            self.migrate_all_btn.config(state=tk.DISABLED)
            self.progress_bar.start(10)
            
            folder = self.agent_folder_var.get()
            self.migration._migrate_agents_folder(folder)
            
            self.window.after(0, self.progress_bar.stop)
            self.window.after(0, self._refresh_stats)
            self.window.after(0, self.migrate_agents_btn.config, {'state': tk.NORMAL})
            self.window.after(0, self.migrate_all_btn.config, {'state': tk.NORMAL})
            self.window.after(0, lambda: messagebox.showinfo("Fertig", 
                f"{self.migration.stats['agents']} neue Agenten importiert!"))
        
        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()
    
    def migrate_kg(self):
        """Nur Knowledge Graph migrieren (nur einmal)"""
        def run():
            self.migrate_kg_btn.config(state=tk.DISABLED)
            self.migrate_all_btn.config(state=tk.DISABLED)
            self.progress_bar.start(10)
            
            kg_file = self.kg_file_var.get()
            if kg_file and os.path.exists(kg_file):
                self.migration._migrate_knowledge_graph(kg_file)
                self.db.set_setting('kg_migrated', True, 'bool')
                self.window.after(0, lambda: messagebox.showinfo("Fertig", 
                    f"{self.migration.stats['nodes']} Nodes, {self.migration.stats['edges']} Edges migriert!"))
            else:
                self.window.after(0, lambda: messagebox.showerror("Fehler", "Datei nicht gefunden!"))
            
            self.window.after(0, self.progress_bar.stop)
            self.window.after(0, self._refresh_stats)
            self.window.after(0, self._update_kg_status)
            self.window.after(0, self.migrate_kg_btn.config, {'state': tk.NORMAL})
            self.window.after(0, self.migrate_all_btn.config, {'state': tk.NORMAL})
        
        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()
    
    def cleanup_pool(self):
        """Entfernt Duplikate aus dem Pool"""
        if messagebox.askyesno("Pool bereinigen", 
                              "Backup wird erstellt.\nDuplikate werden entfernt.\nFortfahren?"):
            try:
                backup = self.db.backup()
                deleted = self.migration.cleanup_duplicates()
                self._refresh_stats()
                messagebox.showinfo("Fertig", 
                    f"✅ {deleted} Duplikate entfernt!\nBackup: {backup}")
            except Exception as e:
                messagebox.showerror("Fehler", str(e))
    
    def migrate_all(self):
        """Alles migrieren"""
        def run():
            self.migrate_all_btn.config(state=tk.DISABLED)
            self.migrate_agents_btn.config(state=tk.DISABLED)
            self.migrate_kg_btn.config(state=tk.DISABLED)
            self.progress_bar.start(10)
            
            folder = self.agent_folder_var.get()
            kg_file = self.kg_file_var.get() if self.kg_file_var.get() else None
            
            stats = self.migration.migrate_all(folder, kg_file)
            
            self.window.after(0, self.progress_bar.stop)
            self.window.after(0, self._refresh_stats)
            self.window.after(0, self._update_kg_status)
            self.window.after(0, self.migrate_all_btn.config, {'state': tk.NORMAL})
            self.window.after(0, self.migrate_agents_btn.config, {'state': tk.NORMAL})
            self.window.after(0, self.migrate_kg_btn.config, {'state': tk.NORMAL})
            
            msg = f"{stats['agents']} neue Agenten"
            if stats['nodes'] > 0:
                msg += f", {stats['nodes']} Nodes, {stats['edges']} Edges"
            if stats['kg_skipped']:
                msg += " (KG bereits migriert)"
            
            self.window.after(0, lambda: messagebox.showinfo("Fertig", msg))
        
        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()


# ==================== KOMMANDOZEILEN-MIGRATION ====================

def main_cli():
    """Für direkten Aufruf: python -m includes.migrate"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SynthAgora Migration Tool")
    parser.add_argument("--agents", help="Agenten-Ordner migrieren")
    parser.add_argument("--kg", help="Knowledge Graph JSON migrieren")
    parser.add_argument("--all", action="store_true", help="Alles migrieren")
    parser.add_argument("--cleanup", action="store_true", help="Duplikate entfernen")
    parser.add_argument("--force-kg", action="store_true", help="Knowledge Graph erneut migrieren (trotz Status)")
    
    args = parser.parse_args()
    
    db = SynthAgoraDB()
    migrator = MigrationTool(db)
    
    if args.cleanup:
        deleted = migrator.cleanup_duplicates()
        print(f"✅ {deleted} Duplikate entfernt")
    
    elif args.all:
        stats = migrator.migrate_all(args.agents, args.kg)
        print(json.dumps(stats, indent=2))
    
    elif args.agents:
        migrator._migrate_agents_folder(args.agents)
        print(json.dumps(migrator.stats, indent=2))
    
    elif args.kg:
        if args.force_kg or not db.get_setting('kg_migrated', False):
            if os.path.exists(args.kg):
                migrator._migrate_knowledge_graph(args.kg)
                db.set_setting('kg_migrated', True, 'bool')
                print(json.dumps(migrator.stats, indent=2))
            else:
                print(f"❌ Datei nicht gefunden: {args.kg}")
        else:
            print("⏭️ Knowledge Graph bereits migriert (use --force-kg to override)")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main_cli()