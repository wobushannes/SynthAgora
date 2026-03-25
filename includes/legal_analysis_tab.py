#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legal Analysis Tab für SynthAgora GUI
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import threading
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional


class LegalAnalysisTab:
    """Tab für Rechtsanalyse-Plugins"""
    
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tb.Frame(parent)
        self.plugin_manager = sim.plugin_manager
        self.current_result = None
        self.selected_plugin_id = None
        self.current_plugin = None
        
        self.plugin_config_vars = {}
        
        self._setup_ui()
        self._load_plugins()
        self._load_role_profile_config()
        self._refresh_debate_info()
    
    def _setup_ui(self):
        main_paned = tb.Panedwindow(self.frame, orient=HORIZONTAL)
        main_paned.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tb.Frame(main_paned, width=350)
        main_paned.add(left_frame, weight=1)
        
        header_left = tb.Frame(left_frame)
        header_left.pack(fill=X, pady=(0,10))
        tb.Label(header_left, text="⚖️ LEGAL PLUGINS", font=("Segoe UI", 14, "bold")).pack(side=LEFT)
        reload_btn = tb.Button(header_left, text="🔄", command=self._reload_plugins, 
                               bootstyle="info", width=3)
        reload_btn.pack(side=RIGHT)
        
        plugin_canvas = tk.Canvas(left_frame, highlightthickness=0, bg='#1e1e2e')
        plugin_scrollbar = tb.Scrollbar(left_frame, orient=VERTICAL, command=plugin_canvas.yview)
        self.plugins_container = tb.Frame(plugin_canvas, bootstyle="dark")
        
        self.plugins_container.bind("<Configure>", lambda e: plugin_canvas.configure(scrollregion=plugin_canvas.bbox("all")))
        plugin_canvas.create_window((0, 0), window=self.plugins_container, anchor="nw")
        plugin_canvas.configure(yscrollcommand=plugin_scrollbar.set)
        
        plugin_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        plugin_scrollbar.pack(side=RIGHT, fill=Y)
        
        right_frame = tb.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        right_notebook = tb.Notebook(right_frame)
        right_notebook.pack(fill=BOTH, expand=True)
        
        preview_tab = tb.Frame(right_notebook)
        right_notebook.add(preview_tab, text="📄 VORSCHAU")
        
        preview_controls = tb.Frame(preview_tab)
        preview_controls.pack(fill=X, padx=10, pady=5)
        
        tb.Label(preview_controls, text="Format:").pack(side=LEFT)
        self.format_var = tk.StringVar(value="markdown")
        format_combo = ttk.Combobox(preview_controls, textvariable=self.format_var, 
                                     values=["markdown", "json", "html"], state="readonly", width=12)
        format_combo.pack(side=LEFT, padx=5)
        
        tb.Button(preview_controls, text="📋 Kopieren", command=self._copy_result, 
                  bootstyle="info").pack(side=LEFT, padx=2)
        tb.Button(preview_controls, text="💾 Speichern", command=self._save_result, 
                  bootstyle="success").pack(side=LEFT, padx=2)
        tb.Button(preview_controls, text="📤 Export", command=self._export_result, 
                  bootstyle="primary").pack(side=LEFT, padx=2)
        
        self.preview_text = scrolledtext.ScrolledText(preview_tab, font=("Consolas", 10), height=15)
        self.preview_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.preview_text.insert(1.0, "👈 Wähle links ein Legal-Plugin aus")
        self.preview_text.config(state=DISABLED)
        
        self.config_tab = tb.Frame(right_notebook)
        right_notebook.add(self.config_tab, text="⚙️ PLUGIN-EINSTELLUNGEN")
        
        self.config_content = tb.Frame(self.config_tab)
        self.config_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.config_label = tb.Label(self.config_content, text="Kein Plugin ausgewählt", 
                                      font=("Segoe UI", 12), bootstyle="secondary")
        self.config_label.pack(pady=50)
        
        global_tab = tb.Frame(right_notebook)
        right_notebook.add(global_tab, text="🌍 GLOBAL")
        self._setup_global_tab(global_tab)
    
    def _setup_global_tab(self, parent):
        profile_frame = tb.LabelFrame(parent, text="🎭 LLM-ROLLENPROFIL (für Analyse)")
        profile_frame.pack(fill=X, padx=10, pady=5)
        
        self.role_profile_text = scrolledtext.ScrolledText(profile_frame, height=8, 
                                                            font=("Segoe UI", 10), wrap=tk.WORD)
        self.role_profile_text.pack(fill=X, padx=10, pady=10)
        
        profile_btn_frame = tb.Frame(profile_frame)
        profile_btn_frame.pack(fill=X, padx=10, pady=5)
        tb.Button(profile_btn_frame, text="💾 Speichern", command=self._save_role_profile, 
                  bootstyle="success", width=12).pack(side=LEFT, padx=2)
        tb.Button(profile_btn_frame, text="🔄 Standard", command=self._reset_role_profile, 
                  bootstyle="secondary", width=12).pack(side=LEFT, padx=2)
        
        info_frame = tb.LabelFrame(parent, text="ℹ️ AKTUELLE DEBATTE")
        info_frame.pack(fill=X, padx=10, pady=5)
        
        self.debate_info_label = tb.Label(info_frame, text="Keine Debatte aktiv", 
                                           bootstyle="secondary", wraplength=500, justify=tk.LEFT)
        self.debate_info_label.pack(anchor=W, padx=10, pady=10)
        
        btn_frame = tb.Frame(info_frame)
        btn_frame.pack(fill=X, padx=10, pady=5)
        tb.Button(btn_frame, text="🔄 Aktualisieren", command=self._refresh_debate_info, 
                  bootstyle="info", width=15).pack(side=LEFT, padx=2)
        
        doc_info_frame = tb.LabelFrame(parent, text="📄 DOKUMENTE AUS PROJEKTEN")
        doc_info_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        self.doc_info_text = scrolledtext.ScrolledText(doc_info_frame, height=6, 
                                                        font=("Consolas", 9), wrap=tk.WORD)
        self.doc_info_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        tb.Button(doc_info_frame, text="🔄 Projekte laden", command=self._refresh_doc_info, 
                  bootstyle="info", width=15).pack(anchor=W, padx=10, pady=5)
    
    def _refresh_debate_info(self):
        topic = getattr(self.sim, 'current_topic', 'Kein Thema')
        rounds = getattr(self.sim, 'current_round', 0)
        log_count = len(getattr(self.sim, 'discussion_log', []))
        is_running = getattr(self.sim, 'is_running', False)
        
        status = "🟢 Läuft" if is_running else "⚪ Inaktiv"
        
        info_text = f"""Status: {status}
Thema: {topic}
Runden: {rounds}
Beiträge: {log_count}
Agenten: {len(getattr(self.sim, 'agents', []))}"""
        
        self.debate_info_label.config(text=info_text)
    
    def _refresh_doc_info(self):
        self.doc_info_text.delete(1.0, tk.END)
        
        try:
            projects = self.sim.list_projects()
            if not projects:
                self.doc_info_text.insert(1.0, "Keine Projekte gefunden.")
                return
            
            total_docs = 0
            total_chunks = 0
            
            for proj in projects:
                name = proj.get('name', '?')
                docs = proj.get('document_count', 0)
                chunks = proj.get('chunk_count', 0)
                total_docs += docs
                total_chunks += chunks
                self.doc_info_text.insert(tk.END, f"📁 {name}: {docs} Dokumente, {chunks} Chunks\n")
            
            self.doc_info_text.insert(tk.END, f"\n📊 GESAMT: {total_docs} Dokumente, {total_chunks} Chunks")
            
        except Exception as e:
            self.doc_info_text.insert(1.0, f"Fehler beim Laden: {e}")
    
    def _load_role_profile_config(self):
        try:
            from includes.config import Config
            profile_path = os.path.join(Config.KNOWLEDGE_FOLDER, "legal_role_profile.txt")
            if os.path.exists(profile_path):
                with open(profile_path, 'r', encoding='utf-8') as f:
                    self.role_profile_text.delete(1.0, tk.END)
                    self.role_profile_text.insert(1.0, f.read())
            else:
                default = """Du bist ein Senior Legal Analyst und Compliance-Experte mit 20 Jahren Erfahrung.
Dein Stil: Präzise, faktenbasiert, strukturiert. Du vergleichst Rechtsnormen und extrahierst Gemeinsamkeiten und Unterschiede.
Deine Antworten sind klar, nachvollziehbar und mit Quellen belegt."""
                self.role_profile_text.insert(1.0, default)
        except Exception as e:
            print(f"⚠️ Rollenprofil laden fehlgeschlagen: {e}")
    
    def _save_role_profile(self):
        profile = self.role_profile_text.get(1.0, tk.END).strip()
        try:
            from includes.config import Config
            profile_path = os.path.join(Config.KNOWLEDGE_FOLDER, "legal_role_profile.txt")
            os.makedirs(Config.KNOWLEDGE_FOLDER, exist_ok=True)
            with open(profile_path, 'w', encoding='utf-8') as f:
                f.write(profile)
            messagebox.showinfo("Erfolg", "Rollenprofil gespeichert!")
            self._update_plugins_role_profile(profile)
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def _reset_role_profile(self):
        default = """Du bist ein Senior Legal Analyst und Compliance-Experte mit 20 Jahren Erfahrung.
Dein Stil: Präzise, faktenbasiert, strukturiert. Du vergleichst Rechtsnormen und extrahierst Gemeinsamkeiten und Unterschiede.
Deine Antworten sind klar, nachvollziehbar und mit Quellen belegt."""
        self.role_profile_text.delete(1.0, tk.END)
        self.role_profile_text.insert(1.0, default)
        self._save_role_profile()
    
    def _update_plugins_role_profile(self, profile: str):
        if hasattr(self.plugin_manager, 'get_all_legal_plugins'):
            for plugin in self.plugin_manager.get_all_legal_plugins().values():
                if hasattr(plugin, 'set_role_profile'):
                    try:
                        plugin.set_role_profile(profile)
                    except:
                        pass
                if hasattr(plugin, 'set_simulation'):
                    try:
                        plugin.set_simulation(self.sim)
                    except:
                        pass
    
    def _load_plugins(self):
        for widget in self.plugins_container.winfo_children():
            widget.destroy()
        
        if not hasattr(self.plugin_manager, 'get_all_legal_plugins'):
            tb.Label(self.plugins_container, text="PluginManager nicht geladen oder keine Legal-Plugins", 
                     bootstyle="danger").pack(pady=50)
            return
        
        plugins = self.plugin_manager.get_all_legal_plugins()
        if not plugins:
            tb.Label(self.plugins_container, text="Keine Legal-Plugins gefunden\n\nLege eine .py Datei in plugins/legal/ ab", 
                     bootstyle="warning").pack(pady=50)
            return
        
        for plugin_id, plugin in plugins.items():
            if hasattr(plugin, 'set_simulation'):
                try:
                    plugin.set_simulation(self.sim)
                except:
                    pass
            self._create_plugin_card(plugin_id, plugin)
    
    def _create_plugin_card(self, plugin_id: str, plugin):
        card = tb.Frame(self.plugins_container, bootstyle="dark", padding=12)
        card.pack(fill=X, pady=5, padx=5)
        
        plugin_name = plugin.metadata.name if hasattr(plugin, 'metadata') else plugin_id
        
        icons = {
            "Normenvergleich": "⚖️",
            "Widerspruchs-Matrix": "🔄",
            "Pflichten-Katalog": "📋",
            "Risikoanalyse": "⚠️",
            "Fristen-Tracker": "⏰",
            "Argumentations-Netzwerk": "🔗",
            "Stimmungs-Tracker": "😊",
            "Zitier-Netzwerk": "🔁",
            "Thesen-Extraktor": "💡"
        }
        icon = icons.get(plugin_name, "⚖️")
        
        header_frame = tb.Frame(card)
        header_frame.pack(fill=X)
        
        tb.Label(header_frame, text=f"{icon} {plugin_name}", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        
        btn = tb.Button(header_frame, text="🚀 ANALYSE STARTEN", 
                        command=lambda pid=plugin_id, p=plugin: self._on_analyze(pid, p),
                        bootstyle="primary", width=16)
        btn.pack(side=RIGHT)
        
        desc = plugin.metadata.description[:100] if hasattr(plugin, 'metadata') else str(plugin)[:100]
        tb.Label(card, text=desc, wraplength=280, bootstyle="secondary", 
                 font=("Segoe UI", 8), justify=LEFT).pack(anchor=W, pady=(5,0))
        
        card.bind("<Button-1>", lambda e, pid=plugin_id, p=plugin: self._select_plugin(pid, p))
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda e, pid=plugin_id, p=plugin: self._select_plugin(pid, p))
    
    def _on_analyze(self, plugin_id: str, plugin):
        self._select_plugin(plugin_id, plugin)
        self._start_analysis(plugin_id)
    
    def _select_plugin(self, plugin_id: str, plugin):
        self.selected_plugin_id = plugin_id
        self.current_plugin = plugin
        
        for widget in self.config_content.winfo_children():
            widget.destroy()
        
        plugin_name = plugin.metadata.name if hasattr(plugin, 'metadata') else plugin_id
        self.config_label = tb.Label(self.config_content, text=f"⚙️ {plugin_name}", 
                                      font=("Segoe UI", 14, "bold"))
        self.config_label.pack(anchor=W, pady=(0,10))
        
        if hasattr(plugin, 'get_config_fields'):
            config_fields = plugin.get_config_fields()
            if config_fields:
                if plugin_id not in self.plugin_config_vars:
                    self.plugin_config_vars[plugin_id] = {}
                
                for field_name, field_config in config_fields.items():
                    field_frame = tb.Frame(self.config_content)
                    field_frame.pack(fill=X, pady=5)
                    
                    label = field_config.get('label', field_name)
                    tb.Label(field_frame, text=label, width=25, anchor=W).pack(side=LEFT)
                    
                    field_type = field_config.get('type', 'text')
                    default = field_config.get('default', '')
                    
                    if field_type == 'spinbox':
                        min_val = field_config.get('min', 1)
                        max_val = field_config.get('max', 10)
                        var = tk.StringVar(value=str(default))
                        self.plugin_config_vars[plugin_id][field_name] = var
                        spin = tb.Spinbox(field_frame, from_=min_val, to=max_val, 
                                          textvariable=var, width=8)
                        spin.pack(side=LEFT)
                        
                    elif field_type == 'combobox':
                        values = field_config.get('values', [])
                        var = tk.StringVar(value=default)
                        self.plugin_config_vars[plugin_id][field_name] = var
                        combo = ttk.Combobox(field_frame, textvariable=var, 
                                              values=values, state="readonly", width=20)
                        combo.pack(side=LEFT)
                        
                    elif field_type == 'checkbox':
                        var = tk.BooleanVar(value=default)
                        self.plugin_config_vars[plugin_id][field_name] = var
                        cb = tb.Checkbutton(field_frame, text="", variable=var, bootstyle="info")
                        cb.pack(side=LEFT)
                        status = "Ja" if default else "Nein"
                        tb.Label(field_frame, text=status, bootstyle="secondary").pack(side=LEFT, padx=5)
                    
                    elif field_type == 'text':
                        var = tk.StringVar(value=default)
                        self.plugin_config_vars[plugin_id][field_name] = var
                        entry = tb.Entry(field_frame, textvariable=var, width=40)
                        entry.pack(side=LEFT, fill=X, expand=True)
                    
                    if field_config.get('tooltip'):
                        tb.Label(field_frame, text="ⓘ", bootstyle="secondary").pack(side=LEFT, padx=5)
            else:
                tb.Label(self.config_content, text="Dieses Plugin hat keine Einstellungen.", 
                         bootstyle="secondary").pack()
        else:
            tb.Label(self.config_content, text="Dieses Plugin hat keine Einstellungen.", 
                     bootstyle="secondary").pack()
        
        if hasattr(plugin, 'get_variants'):
            variants = plugin.get_variants()
            if variants:
                variant_frame = tb.Frame(self.config_content)
                variant_frame.pack(fill=X, pady=10)
                tb.Label(variant_frame, text="📌 Varianten:", width=25, anchor=W).pack(side=LEFT)
                tb.Label(variant_frame, text=" | ".join(variants), bootstyle="info").pack(side=LEFT)
        
        print(f"[LegalAnalysis] Plugin ausgewählt: {plugin_name}")
    
    def _load_documents_from_vectorstore(self, project_names: List[str]) -> List[Dict]:
        """Lädt Dokumente direkt aus dem Vectorstore"""
        documents = []
        
        for project_name in project_names:
            project = self.sim.project_manager.get_project(project_name)
            if not project:
                continue
            
            if not hasattr(project, 'vector_store') or not hasattr(project.vector_store, 'collection'):
                continue
            
            try:
                collection = project.vector_store.collection
                
                # Versuche alle Chunks zu holen
                try:
                    count = collection.count()
                    print(f"[LegalAnalysis] Projekt '{project_name}' hat {count} Chunks")
                    
                    if count == 0:
                        continue
                    
                    # Hole alle Chunks (max 5000)
                    limit = min(count, 5000)
                    all_data = collection.get(limit=limit)
                    
                except Exception as e:
                    print(f"[LegalAnalysis] collection.get() fehlgeschlagen: {e}")
                    continue
                
                if not all_data or 'metadatas' not in all_data or not all_data['metadatas']:
                    print(f"[LegalAnalysis] Keine Metadaten in Projekt '{project_name}'")
                    continue
                
                metadatas = all_data['metadatas']
                documents_list = all_data.get('documents', [])
                
                if not documents_list:
                    documents_list = [''] * len(metadatas)
                
                doc_map = {}
                for i, meta in enumerate(metadatas):
                    if not meta:
                        continue
                    
                    doc_title = meta.get('document', meta.get('source', 'Unbekannt'))
                    doc_source = meta.get('source', '')
                    
                    if doc_title not in doc_map:
                        doc_map[doc_title] = {
                            "content": [],
                            "metadata": {
                                "title": doc_title,
                                "source": doc_source,
                                "project": project_name,
                                "chunks": 0,
                                "filename": os.path.basename(doc_source) if doc_source else doc_title
                            }
                        }
                    
                    if i < len(documents_list) and documents_list[i]:
                        doc_map[doc_title]["content"].append(documents_list[i])
                    doc_map[doc_title]["metadata"]["chunks"] += 1
                
                for doc_title, data in doc_map.items():
                    if data["content"]:
                        documents.append({
                            "content": "\n\n".join(data["content"][:20]),
                            "metadata": data["metadata"]
                        })
                    else:
                        documents.append({
                            "content": f"[Dokument: {doc_title} – kein Text verfügbar]",
                            "metadata": data["metadata"]
                        })
                
                print(f"[LegalAnalysis] Projekt '{project_name}': {len(doc_map)} Dokumente geladen")
                
            except Exception as e:
                print(f"[LegalAnalysis] Fehler bei Projekt '{project_name}': {e}")
                import traceback
                traceback.print_exc()
        
        return documents
    
    def _start_analysis(self, plugin_id: str):
        plugin_config = {}
        if plugin_id in self.plugin_config_vars:
            for field_name, var in self.plugin_config_vars[plugin_id].items():
                value = var.get()
                plugin_config[field_name] = value
        
        role_profile = self.role_profile_text.get(1.0, tk.END).strip()
        
        debate_data = {
            "topic": getattr(self.sim, 'current_topic', "Kein Thema"),
            "log": getattr(self.sim, 'discussion_log', []),
            "rounds": getattr(self.sim, 'current_round', 0),
            "timestamp": datetime.now().isoformat(),
            "pro_agents": getattr(self.sim, 'debate_settings', {}).get("pro_agents", []),
            "contra_agents": getattr(self.sim, 'debate_settings', {}).get("contra_agents", [])
        }
        
        # Aktive Projekte aus Debatte holen
        active_projects = getattr(self.sim, 'debate_settings', {}).get("projects", [])
        
        if not active_projects and hasattr(self.sim, 'project_manager'):
            projects = self.sim.list_projects()
            active_projects = [p.get('name') for p in projects]
        
        print(f"[LegalAnalysis] Aktive Projekte: {active_projects}")
        
        # Dokumente aus Vectorstore laden
        documents = self._load_documents_from_vectorstore(active_projects)
        print(f"[LegalAnalysis] {len(documents)} Dokumente aus Vectorstore geladen")
        
        # Zitierte Dateien aus Debatte extrahieren
        log_text = "\n".join(debate_data["log"])
        zitate_pattern = r'\[([^:\]]+)::([^\]]+)\]'
        matches = re.findall(zitate_pattern, log_text)
        
        zitierte_dateien = set()
        for projekt, datei in matches:
            zitierte_dateien.add(datei)
        
        print(f"[LegalAnalysis] Zitierte Dateien: {len(zitierte_dateien)}")
        for zd in list(zitierte_dateien)[:5]:
            print(f"   - {zd}")
        
        # Filtere Dokumente nach zitierten Dateien
        relevante_docs = []
        for doc in documents:
            source = doc.get("metadata", {}).get("source", "")
            title = doc.get("metadata", {}).get("title", "")
            filename = doc.get("metadata", {}).get("filename", "")
            
            for zit_datei in zitierte_dateien:
                if zit_datei in source or zit_datei in title or zit_datei in filename:
                    relevante_docs.append(doc)
                    break
        
        seen = set()
        docs_final = []
        for doc in relevante_docs:
            key = doc.get("metadata", {}).get("title", doc.get("metadata", {}).get("source", ""))
            if key not in seen:
                seen.add(key)
                docs_final.append(doc)
        
        if not docs_final:
            print("[LegalAnalysis] Keine relevanten Dokumente, verwende alle")
            max_dok = int(plugin_config.get("max_dokumente", 5))
            docs_final = documents[:max_dok]
        
        print(f"[LegalAnalysis] Final {len(docs_final)} Dokumente für Analyse")
        for d in docs_final[:3]:
            print(f"   - {d.get('metadata', {}).get('title', '?')}")
        
        full_config = {
            "role_profile": role_profile,
            **plugin_config
        }
        
        self.preview_text.config(state=NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, f"⏳ Analysiere mit {plugin_id}...\n")
        self.preview_text.insert(1.0, f"📋 Debatte: {debate_data['topic']}\n")
        self.preview_text.insert(1.0, f"💬 Beiträge: {len(debate_data['log'])}\n")
        self.preview_text.insert(1.0, f"📄 Dokumente gesamt: {len(documents)}\n")
        self.preview_text.insert(1.0, f"📌 Zitierte Dateien: {len(zitierte_dateien)}\n")
        self.preview_text.insert(1.0, f"📚 Relevante Dokumente: {len(docs_final)}\n\n")
        self.preview_text.insert(1.0, "⏳ Warte auf LLM-Antwort...\n")
        self.preview_text.config(state=DISABLED)
        self.preview_text.update()
        
        thread = threading.Thread(target=self._run_analysis, args=(plugin_id, debate_data, docs_final, full_config))
        thread.daemon = True
        thread.start()
    
    def _run_analysis(self, plugin_id: str, debate_data: Dict, documents: List[Dict], config: Dict):
        try:
            if hasattr(self.plugin_manager, 'run_legal_analysis'):
                result = self.plugin_manager.run_legal_analysis(plugin_id, debate_data, documents, config)
            else:
                plugin = self.plugin_manager.get_legal_plugin(plugin_id)
                if not plugin:
                    raise Exception(f"Plugin {plugin_id} nicht gefunden")
                
                if hasattr(plugin, 'set_lm') and hasattr(self.sim, 'lm'):
                    plugin.set_lm(self.sim.lm)
                
                if hasattr(plugin, 'set_role_profile') and config.get('role_profile'):
                    plugin.set_role_profile(config['role_profile'])
                
                if hasattr(plugin, 'set_simulation'):
                    plugin.set_simulation(self.sim)
                
                result = plugin.analyze(debate_data, documents, config)
            
            self.current_result = result
            self.frame.after(0, self._on_analysis_success, result, plugin_id)
            
        except Exception as err:
            error_msg = str(err)
            import traceback
            traceback.print_exc()
            self.frame.after(0, self._on_analysis_error, error_msg)
    
    def _on_analysis_success(self, result: Dict, plugin_id: str):
        self._display_result(result)
        messagebox.showinfo("Erfolg", f"{plugin_id} Analyse abgeschlossen!")
    
    def _on_analysis_error(self, error_msg: str):
        self._show_error(error_msg)
    
    def _display_result(self, result: Dict):
        self.preview_text.config(state=NORMAL)
        self.preview_text.delete(1.0, tk.END)
        
        format_type = self.format_var.get()
        
        if format_type == "json":
            text = json.dumps(result, indent=2, ensure_ascii=False)
        elif format_type == "html":
            text = result.get("_html", json.dumps(result, indent=2, ensure_ascii=False))
        else:
            text = result.get("_markdown", json.dumps(result, indent=2, ensure_ascii=False))
        
        self.preview_text.insert(1.0, text)
        self.preview_text.config(state=DISABLED)
    
    def _show_error(self, error_msg: str):
        self.preview_text.config(state=NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, f"❌ Fehler:\n{error_msg}")
        self.preview_text.config(state=DISABLED)
        messagebox.showerror("Fehler", error_msg)
    
    def _copy_result(self):
        if not self.current_result:
            messagebox.showwarning("Achtung", "Kein Ergebnis!")
            return
        format_type = self.format_var.get()
        if format_type == "json":
            text = json.dumps(self.current_result, indent=2, ensure_ascii=False)
        elif format_type == "html":
            text = self.current_result.get("_html", "")
        else:
            text = self.current_result.get("_markdown", "")
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        messagebox.showinfo("Kopiert", "In Zwischenablage!")
    
    def _save_result(self):
        if not self.current_result:
            messagebox.showwarning("Achtung", "Kein Ergebnis!")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"legal_analysis_{timestamp}.json"
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.current_result, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Erfolg", f"Gespeichert: {filename}")
    
    def _export_result(self):
        if not self.current_result:
            messagebox.showwarning("Achtung", "Kein Ergebnis!")
            return
        format_type = self.format_var.get()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".json" if format_type == "json" else ".html" if format_type == "html" else ".md"
        content = ""
        if format_type == "json":
            content = json.dumps(self.current_result, indent=2, ensure_ascii=False)
        elif format_type == "html":
            content = self.current_result.get("_html", "")
        else:
            content = self.current_result.get("_markdown", "")
        
        filename = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{format_type.upper()}", f"*{ext}")],
            initialfile=f"legal_analysis_{timestamp}{ext}"
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Erfolg", f"Exportiert: {filename}")
    
    def _reload_plugins(self):
        if hasattr(self.plugin_manager, 'reload_legal_plugins'):
            self.plugin_manager.reload_legal_plugins()
        else:
            self.plugin_manager.reload_plugins()
        self._load_plugins()
        messagebox.showinfo("Info", "Legal-Plugins neu geladen!")
    
    def refresh(self):
        self._load_plugins()
        self._refresh_debate_info()
        self._refresh_doc_info()