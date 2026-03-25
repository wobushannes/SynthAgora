#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthesis Tab für SynthAgora GUI
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import threading
import os
from datetime import datetime
from typing import Dict, List, Any, Optional


class SynthesisTab:
    """Tab für Synthesis-Plugins"""
    
    def __init__(self, parent, sim):
        self.parent = parent
        self.sim = sim
        self.frame = tb.Frame(parent)
        self.plugin_manager = sim.plugin_manager
        self.current_result = None
        self.logo_path = None
        self.custom_footer = None
        self.selected_plugin_id = None
        self.current_plugin = None
        
        # Speicher für Plugin-Config-Variablen
        self.plugin_config_vars = {}
        
        self._setup_ui()
        self._load_plugins()
        self._load_role_profile_config()
        self._load_logo_config()
        self._load_footer_config()
    
    def _setup_ui(self):
        # Haupt-Panedwindow
        main_paned = tb.Panedwindow(self.frame, orient=HORIZONTAL)
        main_paned.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # ========== LINKE SEITE: PLUGIN-LISTE ==========
        left_frame = tb.Frame(main_paned, width=350)
        main_paned.add(left_frame, weight=1)
        
        header_left = tb.Frame(left_frame)
        header_left.pack(fill=X, pady=(0,10))
        tb.Label(header_left, text="📦 PLUGINS", font=("Segoe UI", 14, "bold")).pack(side=LEFT)
        reload_btn = tb.Button(header_left, text="🔄", command=self._reload_plugins, 
                               bootstyle="info", width=3)
        reload_btn.pack(side=RIGHT)
        
        # Scrollbare Plugin-Liste
        plugin_canvas = tk.Canvas(left_frame, highlightthickness=0, bg='#1e1e2e')
        plugin_scrollbar = tb.Scrollbar(left_frame, orient=VERTICAL, command=plugin_canvas.yview)
        self.plugins_container = tb.Frame(plugin_canvas, bootstyle="dark")
        
        self.plugins_container.bind("<Configure>", lambda e: plugin_canvas.configure(scrollregion=plugin_canvas.bbox("all")))
        plugin_canvas.create_window((0, 0), window=self.plugins_container, anchor="nw")
        plugin_canvas.configure(yscrollcommand=plugin_scrollbar.set)
        
        plugin_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        plugin_scrollbar.pack(side=RIGHT, fill=Y)
        
        # ========== RECHTE SEITE ==========
        right_frame = tb.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        right_notebook = tb.Notebook(right_frame)
        right_notebook.pack(fill=BOTH, expand=True)
        
        # Tab 1: Vorschau
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
        self.preview_text.insert(1.0, "👈 Wähle links ein Plugin aus")
        self.preview_text.config(state=DISABLED)
        
        # Tab 2: Plugin-Einstellungen
        self.config_tab = tb.Frame(right_notebook)
        right_notebook.add(self.config_tab, text="⚙️ PLUGIN-EINSTELLUNGEN")
        
        self.config_content = tb.Frame(self.config_tab)
        self.config_content.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.config_label = tb.Label(self.config_content, text="Kein Plugin ausgewählt", 
                                      font=("Segoe UI", 12), bootstyle="secondary")
        self.config_label.pack(pady=50)
        
        # Tab 3: Globale Einstellungen
        global_tab = tb.Frame(right_notebook)
        right_notebook.add(global_tab, text="🌍 GLOBAL")
        self._setup_global_tab(global_tab)
    
    def _setup_global_tab(self, parent):
        # Rollenprofil
        profile_frame = tb.LabelFrame(parent, text="🎭 LLM-ROLLENPROFIL")
        profile_frame.pack(fill=X, padx=10, pady=5)
        
        self.role_profile_text = scrolledtext.ScrolledText(profile_frame, height=6, 
                                                            font=("Segoe UI", 10), wrap=tk.WORD)
        self.role_profile_text.pack(fill=X, padx=10, pady=10)
        
        profile_btn_frame = tb.Frame(profile_frame)
        profile_btn_frame.pack(fill=X, padx=10, pady=5)
        tb.Button(profile_btn_frame, text="💾 Speichern", command=self._save_role_profile, 
                  bootstyle="success", width=12).pack(side=LEFT, padx=2)
        tb.Button(profile_btn_frame, text="🔄 Standard", command=self._reset_role_profile, 
                  bootstyle="secondary", width=12).pack(side=LEFT, padx=2)
        
        # Logo
        logo_frame = tb.LabelFrame(parent, text="🏷️ LOGO (HTML-Export)")
        logo_frame.pack(fill=X, padx=10, pady=5)
        
        logo_content = tb.Frame(logo_frame)
        logo_content.pack(fill=X, padx=10, pady=10)
        
        logo_path_frame = tb.Frame(logo_content)
        logo_path_frame.pack(fill=X, pady=5)
        
        self.logo_path_var = tk.StringVar()
        logo_entry = tb.Entry(logo_path_frame, textvariable=self.logo_path_var)
        logo_entry.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        
        tb.Button(logo_path_frame, text="📂 Durchsuchen", command=self._browse_logo, 
                  bootstyle="secondary", width=12).pack(side=RIGHT)
        tb.Button(logo_path_frame, text="🗑️", command=self._clear_logo, 
                  bootstyle="danger", width=3).pack(side=RIGHT, padx=2)
        
        self.logo_preview_label = tb.Label(logo_content, text="Kein Logo", 
                                           bootstyle="secondary", font=("Segoe UI", 8))
        self.logo_preview_label.pack(anchor=W, pady=5)
        
        tb.Button(logo_content, text="💾 Logo speichern", command=self._save_logo, 
                  bootstyle="success", width=15).pack(anchor=W, pady=5)
        
        # Fußzeile
        footer_frame = tb.LabelFrame(parent, text="📝 FUSSZEILE (HTML-Export)")
        footer_frame.pack(fill=X, padx=10, pady=5)
        
        self.footer_text = scrolledtext.ScrolledText(footer_frame, height=3, 
                                                      font=("Segoe UI", 9), wrap=tk.WORD)
        self.footer_text.pack(fill=X, padx=10, pady=10)
        self.footer_text.insert(1.0, "© 2025 SynthAgora | Generiert mit Customer Journey Plugin")
        
        footer_btn_frame = tb.Frame(footer_frame)
        footer_btn_frame.pack(fill=X, padx=10, pady=5)
        tb.Button(footer_btn_frame, text="💾 Speichern", command=self._save_footer, 
                  bootstyle="success", width=12).pack(side=LEFT, padx=2)
        tb.Button(footer_btn_frame, text="🔄 Standard", command=self._reset_footer, 
                  bootstyle="secondary", width=12).pack(side=LEFT, padx=2)
    
    def _browse_logo(self):
        filepath = filedialog.askopenfilename(
            title="Logo auswählen",
            filetypes=[("Bilder", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Alle", "*.*")]
        )
        if filepath:
            self.logo_path_var.set(filepath)
            self.logo_preview_label.config(text=f"✅ {os.path.basename(filepath)}", bootstyle="success")
    
    def _clear_logo(self):
        self.logo_path_var.set("")
        self.logo_preview_label.config(text="Kein Logo", bootstyle="secondary")
    
    def _save_logo(self):
        logo_path = self.logo_path_var.get().strip()
        try:
            from includes.config import Config
            config_path = os.path.join(Config.KNOWLEDGE_FOLDER, "logo_config.json")
            os.makedirs(Config.KNOWLEDGE_FOLDER, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"logo_path": logo_path}, f, indent=2)
            messagebox.showinfo("Erfolg", "Logo gespeichert!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def _load_logo_config(self):
        try:
            from includes.config import Config
            config_path = os.path.join(Config.KNOWLEDGE_FOLDER, "logo_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    path = data.get("logo_path", "")
                    if path and os.path.exists(path):
                        self.logo_path_var.set(path)
                        self.logo_preview_label.config(text=f"✅ {os.path.basename(path)}", bootstyle="success")
        except Exception as e:
            print(f"⚠️ Logo laden fehlgeschlagen: {e}")
    
    def _save_footer(self):
        footer = self.footer_text.get(1.0, tk.END).strip()
        try:
            from includes.config import Config
            config_path = os.path.join(Config.KNOWLEDGE_FOLDER, "footer_config.json")
            os.makedirs(Config.KNOWLEDGE_FOLDER, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"footer": footer}, f, indent=2)
            messagebox.showinfo("Erfolg", "Fußzeile gespeichert!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def _load_footer_config(self):
        try:
            from includes.config import Config
            config_path = os.path.join(Config.KNOWLEDGE_FOLDER, "footer_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    footer = data.get("footer", "")
                    if footer:
                        self.footer_text.delete(1.0, tk.END)
                        self.footer_text.insert(1.0, footer)
        except Exception as e:
            print(f"⚠️ Footer laden fehlgeschlagen: {e}")
    
    def _reset_footer(self):
        default = "© 2025 SynthAgora | Generiert mit Customer Journey Plugin"
        self.footer_text.delete(1.0, tk.END)
        self.footer_text.insert(1.0, default)
        self._save_footer()
    
    def _load_role_profile_config(self):
        try:
            from includes.config import Config
            profile_path = os.path.join(Config.KNOWLEDGE_FOLDER, "role_profile.txt")
            if os.path.exists(profile_path):
                with open(profile_path, 'r', encoding='utf-8') as f:
                    self.role_profile_text.delete(1.0, tk.END)
                    self.role_profile_text.insert(1.0, f.read())
            else:
                default = """Du bist ein Senior Marketing- und CX-Experte mit 15 Jahren Erfahrung.
Dein Stil: Präzise, klar, handlungsorientiert. Kein Marketing-Blabla."""
                self.role_profile_text.insert(1.0, default)
        except Exception as e:
            print(f"⚠️ Rollenprofil laden fehlgeschlagen: {e}")
    
    def _save_role_profile(self):
        profile = self.role_profile_text.get(1.0, tk.END).strip()
        try:
            from includes.config import Config
            profile_path = os.path.join(Config.KNOWLEDGE_FOLDER, "role_profile.txt")
            os.makedirs(Config.KNOWLEDGE_FOLDER, exist_ok=True)
            with open(profile_path, 'w', encoding='utf-8') as f:
                f.write(profile)
            messagebox.showinfo("Erfolg", "Rollenprofil gespeichert!")
            self._update_plugins_role_profile(profile)
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
    
    def _reset_role_profile(self):
        default = """Du bist ein Senior Marketing- und CX-Experte mit 15 Jahren Erfahrung.
Dein Stil: Präzise, klar, handlungsorientiert. Kein Marketing-Blabla."""
        self.role_profile_text.delete(1.0, tk.END)
        self.role_profile_text.insert(1.0, default)
        self._save_role_profile()
    
    def _update_plugins_role_profile(self, profile: str):
        if hasattr(self.plugin_manager, 'get_all_synthesis_plugins'):
            for plugin in self.plugin_manager.get_all_synthesis_plugins().values():
                if hasattr(plugin, 'set_role_profile'):
                    try:
                        plugin.set_role_profile(profile)
                    except:
                        pass
    
    def _get_custom_footer(self) -> str:
        footer = self.footer_text.get(1.0, tk.END).strip()
        return footer if footer else "© 2025 SynthAgora"
    
    def _get_logo_path(self) -> str:
        return self.logo_path_var.get().strip()
    
    def _load_plugins(self):
        for widget in self.plugins_container.winfo_children():
            widget.destroy()
        
        if not hasattr(self.plugin_manager, 'get_all_synthesis_plugins'):
            tb.Label(self.plugins_container, text="PluginManager nicht geladen", 
                     bootstyle="danger").pack(pady=50)
            return
        
        plugins = self.plugin_manager.get_all_synthesis_plugins()
        if not plugins:
            tb.Label(self.plugins_container, text="Keine Plugins gefunden", 
                     bootstyle="warning").pack(pady=50)
            return
        
        for plugin_id, plugin in plugins.items():
            self._create_plugin_card(plugin_id, plugin)
    
    def _create_plugin_card(self, plugin_id: str, plugin):
        card = tb.Frame(self.plugins_container, bootstyle="dark", padding=12)
        card.pack(fill=X, pady=5, padx=5)
        
        plugin_name = plugin.metadata.name if hasattr(plugin, 'metadata') else plugin_id
        
        icons = {
            "Customer Journey": "🧭",
            "Persona Creator": "👤",
            "Beispiel Synthese": "🎨"
        }
        icon = icons.get(plugin_name, "🎨")
        
        header_frame = tb.Frame(card)
        header_frame.pack(fill=X)
        
        tb.Label(header_frame, text=f"{icon} {plugin_name}", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        
        btn = tb.Button(header_frame, text="🚀 GENERIEREN", 
                        command=lambda pid=plugin_id, p=plugin: self._on_generate(pid, p),
                        bootstyle="primary", width=14)
        btn.pack(side=RIGHT)
        
        desc = plugin.metadata.description[:100] if hasattr(plugin, 'metadata') else str(plugin)[:100]
        tb.Label(card, text=desc, wraplength=280, bootstyle="secondary", 
                 font=("Segoe UI", 8), justify=LEFT).pack(anchor=W, pady=(5,0))
        
        card.bind("<Button-1>", lambda e, pid=plugin_id, p=plugin: self._select_plugin(pid, p))
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda e, pid=plugin_id, p=plugin: self._select_plugin(pid, p))
    
    def _on_generate(self, plugin_id: str, plugin):
        """Callback für GENERIEREN Button"""
        self._select_plugin(plugin_id, plugin)
        self._start_generation(plugin_id)
    
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
                    tb.Label(field_frame, text=label, width=20, anchor=W).pack(side=LEFT)
                    
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
                                              values=values, state="readonly", width=15)
                        combo.pack(side=LEFT)
                        
                    elif field_type == 'checkbox':
                        var = tk.BooleanVar(value=default)
                        self.plugin_config_vars[plugin_id][field_name] = var
                        cb = tb.Checkbutton(field_frame, text="", variable=var, bootstyle="info")
                        cb.pack(side=LEFT)
                        status = "Ja" if default else "Nein"
                        tb.Label(field_frame, text=status, bootstyle="secondary").pack(side=LEFT, padx=5)
                    
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
                tb.Label(variant_frame, text="📌 Varianten:", width=20, anchor=W).pack(side=LEFT)
                tb.Label(variant_frame, text=" | ".join(variants), bootstyle="info").pack(side=LEFT)
        
        print(f"[Synthesis] Plugin ausgewählt: {plugin_name}")
    
    def _start_generation(self, plugin_id: str):
        """Startet die Generierung"""
        
        # ========== CONFIG AUSLESEN MIT DEBUG ==========
        plugin_config = {}
        if plugin_id in self.plugin_config_vars:
            print(f"[DEBUG] Plugin Config Vars gefunden für {plugin_id}")
            for field_name, var in self.plugin_config_vars[plugin_id].items():
                value = var.get()
                plugin_config[field_name] = value
                print(f"[DEBUG]   {field_name} = {value} (Typ: {type(value)})")
        else:
            print(f"[DEBUG] Keine Config Vars für {plugin_id}")
        
        # Typ-Konvertierung für Zahlen
        if "persona_count" in plugin_config:
            try:
                plugin_config["persona_count"] = int(plugin_config["persona_count"])
                print(f"[DEBUG] persona_count konvertiert zu: {plugin_config['persona_count']}")
            except:
                pass
        
        # Alle Config-Werte zusammenbauen
        full_config = {
            "role_profile": self.role_profile_text.get(1.0, tk.END).strip(),
            "custom_footer": self._get_custom_footer(),
            "logo_path": self._get_logo_path(),
            **plugin_config
        }
        
        print(f"[DEBUG] FULL CONFIG an Plugin: {full_config}")
        
        # GUI updaten
        self.preview_text.config(state=NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, f"⏳ Generiere {plugin_id}...\n")
        self.preview_text.insert(1.0, f"📋 Config: {full_config}\n\n")
        self.preview_text.config(state=DISABLED)
        self.preview_text.update()
        
        # Thread starten
        thread = threading.Thread(target=self._run_generation, args=(plugin_id, full_config))
        thread.daemon = True
        thread.start()
    
    def _run_generation(self, plugin_id: str, config: Dict):
        """Führt die Generierung im Thread aus"""
        try:
            debate_data = {
                "topic": self.sim.current_topic,
                "log": self.sim.discussion_log,
                "rounds": self.sim.current_round,
                "timestamp": datetime.now().isoformat(),
                "pro_agents": getattr(self.sim, 'debate_settings', {}).get("pro_agents", []),
                "contra_agents": getattr(self.sim, 'debate_settings', {}).get("contra_agents", [])
            }
            
            print(f"[DEBUG] Rufe run_synthesis auf mit config: {config}")
            
            result = self.plugin_manager.run_synthesis(plugin_id, debate_data, [], config)
            self.current_result = result
            
            self.frame.after(0, self._on_generation_success, result, plugin_id)
            
        except Exception as err:
            error_msg = str(err)
            print(f"[DEBUG] Fehler: {error_msg}")
            self.frame.after(0, self._on_generation_error, error_msg)
    
    def _on_generation_success(self, result: Dict, plugin_id: str):
        self._display_result(result)
        messagebox.showinfo("Erfolg", f"{plugin_id} erfolgreich generiert!")
    
    def _on_generation_error(self, error_msg: str):
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
            initialfile=f"synthesis_{timestamp}.json"
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
            initialfile=f"synthesis_{timestamp}{ext}"
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Erfolg", f"Exportiert: {filename}")
    
    def _reload_plugins(self):
        self.plugin_manager.reload_plugins()
        self._load_plugins()
        messagebox.showinfo("Info", "Plugins neu geladen!")
    
    def refresh(self):
        self._load_plugins()