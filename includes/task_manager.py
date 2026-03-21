#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task-Manager für SynthAgora
- Verwaltung von Analyse-Jobs
- Task-Typen: analyse, evaluate, recommend, summarize, extract
- Parallelverarbeitung mit ThreadPool
- Fortschritts-Tracking
- EXPORT-FUNKTIONEN: JSON, TXT, HTML, CSV
"""

import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import random
import csv
import io

class Task:
    """Ein einzelner Task für einen Agenten"""
    
    def __init__(self, task_id: str, agent_name: str, task_type: str, 
                 input_text: str, priority: int = 1):
        """
        Args:
            task_id: Eindeutige ID
            agent_name: Name des Agenten
            task_type: analyse, evaluate, recommend, summarize, extract
            input_text: Zu verarbeitender Text
            priority: 1 (niedrig) bis 5 (hoch)
        """
        self.id = task_id
        self.agent_name = agent_name
        self.type = task_type
        self.input = input_text
        self.priority = priority
        
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None
        self.duration = None
        
    def start(self):
        """Task als gestartet markieren"""
        self.status = "running"
        self.started_at = datetime.now().isoformat()
    
    def complete(self, result: Any):
        """Task als erfolgreich abgeschlossen markieren"""
        self.status = "completed"
        self.result = result
        self.completed_at = datetime.now().isoformat()
        self._calc_duration()
    
    def fail(self, error: str):
        """Task als fehlgeschlagen markieren"""
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.now().isoformat()
        self._calc_duration()
    
    def _calc_duration(self):
        """Berechnet Dauer in Sekunden"""
        if self.started_at and self.completed_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            self.duration = (end - start).total_seconds()
    
    def to_dict(self) -> dict:
        """Für Export/Logging"""
        return {
            "id": self.id,
            "agent": self.agent_name,
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "started": self.started_at,
            "completed": self.completed_at,
            "duration": self.duration,
            "result": self.result,
            "error": self.error
        }


class AnalysisJob:
    """Ein kompletter Analyse-Job mit mehreren Tasks"""
    
    def __init__(self, job_id: str, name: str, input_text: str, 
                 task_type: str, agent_names: List[str]):
        """
        Args:
            job_id: Eindeutige ID
            name: Job-Name (z.B. "Krankenhaus-Analyse")
            input_text: Zu analysierender Text
            task_type: Art der Analyse für ALLE Tasks
            agent_names: Liste der Agenten-Namen
        """
        self.id = job_id
        self.name = name
        self.input_text = input_text
        self.task_type = task_type
        self.agent_names = agent_names
        
        self.status = "pending"  # pending, running, completed
        self.tasks: List[Task] = []
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.duration = None
        
        # Tasks erstellen
        for i, agent in enumerate(agent_names):
            task_id = f"{job_id}_{i:04d}"
            task = Task(task_id, agent, task_type, input_text)
            self.tasks.append(task)
    
    def start(self):
        """Job als gestartet markieren"""
        self.status = "running"
        self.started_at = datetime.now().isoformat()
    
    def complete(self):
        """Job als abgeschlossen markieren (wenn alle Tasks fertig)"""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()
        self._calc_duration()
    
    def _calc_duration(self):
        """Berechnet Gesamtdauer"""
        if self.started_at and self.completed_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            self.duration = (end - start).total_seconds()
    
    def get_progress(self) -> Dict:
        """Liefert Fortschritts-Info"""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == "completed")
        failed = sum(1 for t in self.tasks if t.status == "failed")
        running = sum(1 for t in self.tasks if t.status == "running")
        
        progress = (completed / total * 100) if total > 0 else 0
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": total - completed - failed - running,
            "progress": progress,
            "status": self.status
        }
    
    def get_results_by_role(self, agents_by_name: Dict) -> Dict:
        """
        Gruppiert Ergebnisse nach Rolle.
        
        Args:
            agents_by_name: Dictionary {agent_name: agent_object}
        
        Returns:
            {
                "Rolle": {
                    "agenten": [...],
                    "ergebnisse": [...],
                    "bewertungen": [...],
                    "scores": [...],
                    "durchschnitt": ...
                }
            }
        """
        results = {}
        
        for task in self.tasks:
            if task.status != "completed" or not task.result:
                continue
            
            agent = agents_by_name.get(task.agent_name)
            if not agent:
                continue
            
            # Rolle ermitteln (aus role-Feld)
            role = agent.role.split()[0] if agent.role else "Unbekannt"
            
            if role not in results:
                results[role] = {
                    "agenten": [],
                    "ergebnisse": [],
                    "bewertungen": [],
                    "scores": []
                }
            
            # Agenten-Infos
            agent_info = {
                "name": agent.name,
                "color": agent.color,
                "team": agent.team
            }
            if agent_info not in results[role]["agenten"]:
                results[role]["agenten"].append(agent_info)
            
            # Ergebnis
            results[role]["ergebnisse"].append({
                "agent": agent.name,
                "text": task.result.get("analysis", str(task.result)),
                "timestamp": task.completed_at
            })
            
            # Bewertung extrahieren (für evaluate)
            if task.type == "evaluate" and "score" in task.result:
                score = task.result.get("score")
                if score is not None:
                    results[role]["bewertungen"].append({
                        "agent": agent.name,
                        "score": score
                    })
                    results[role]["scores"].append(score)
        
        # Durchschnitt berechnen
        for role, data in results.items():
            if data["scores"]:
                data["durchschnitt"] = sum(data["scores"]) / len(data["scores"])
            else:
                data["durchschnitt"] = None
        
        return results
    
    def get_top_quotes(self, limit: int = 5) -> List[Dict]:
        """
        Holt die interessantesten Zitate.
        """
        quotes = []
        
        for task in self.tasks:
            if task.status != "completed" or not task.result:
                continue
            
            analysis = task.result.get("analysis", "")
            if analysis and len(analysis) > 30:
                # Bereinigen und kürzen
                clean_text = analysis.strip()
                if len(clean_text) > 200:
                    clean_text = clean_text[:200] + "..."
                
                quotes.append({
                    "agent": task.agent_name,
                    "role": task.result.get("role", "Unbekannt"),
                    "text": clean_text,
                    "type": task.type
                })
        
        # Mischen und begrenzen
        random.shuffle(quotes)
        return quotes[:limit]
    
    def to_dict(self) -> dict:
        """Für Export"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.task_type,
            "input_text": self.input_text,
            "agent_count": len(self.agent_names),
            "agent_names": self.agent_names,
            "status": self.status,
            "created": self.created_at,
            "started": self.started_at,
            "completed": self.completed_at,
            "duration": self.duration,
            "progress": self.get_progress(),
            "tasks": [t.to_dict() for t in self.tasks]
        }


class TaskManager:
    """Verwaltet alle Analyse-Jobs"""
    
    def __init__(self, max_workers: int = 10):
        """
        Args:
            max_workers: Maximale parallele Tasks
        """
        self.max_workers = max_workers
        self.jobs: Dict[str, AnalysisJob] = {}
        self.completed_jobs: List[AnalysisJob] = []
        self.active_jobs: List[AnalysisJob] = []
        
        # Queue für Fortschritts-Updates
        self.progress_queue = queue.Queue()
        
        # Stop-Event für Abbruch
        self.stop_event = threading.Event()
        
        # Callbacks
        self.on_job_start: Optional[Callable] = None
        self.on_task_complete: Optional[Callable] = None
        self.on_job_complete: Optional[Callable] = None
    
    def create_job(self, name: str, input_text: str, task_type: str, 
                   agent_names: List[str]) -> AnalysisJob:
        """
        Erstellt neuen Analyse-Job.
        
        Args:
            name: Job-Name
            input_text: Zu analysierender Text
            task_type: Art der Analyse
            agent_names: Liste der Agenten-Namen
        
        Returns:
            AnalysisJob-Objekt
        """
        job_id = f"job_{int(time.time())}_{len(self.jobs)}"
        job = AnalysisJob(job_id, name, input_text, task_type, agent_names)
        
        self.jobs[job_id] = job
        self.active_jobs.append(job)
        
        return job
    
    def run_job(self, job: AnalysisJob, agents_by_name: Dict, lm_client,
                progress_callback: Optional[Callable] = None) -> AnalysisJob:
        """
        Führt einen Job aus (parallel).
        
        Args:
            job: AnalysisJob-Objekt
            agents_by_name: Dictionary {agent_name: agent_object}
            lm_client: LLM-Client
            progress_callback: Callback für Fortschritt
        
        Returns:
            Abgeschlossener Job
        """
        self.stop_event.clear()
        job.start()
        
        if self.on_job_start:
            self.on_job_start(job)
        
        if progress_callback:
            progress_callback("start", job)
        
        # Tasks parallel ausführen
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            
            for task in job.tasks:
                if self.stop_event.is_set():
                    break
                
                agent = agents_by_name.get(task.agent_name)
                if not agent:
                    task.fail(f"Agent {task.agent_name} nicht gefunden")
                    continue
                
                future = executor.submit(
                    self._run_single_task,
                    task, agent, lm_client
                )
                future_to_task[future] = task
            
            # Ergebnisse einsammeln
            completed = 0
            for future in as_completed(future_to_task):
                if self.stop_event.is_set():
                    # Alle laufenden Tasks abbrechen
                    for f in future_to_task:
                        f.cancel()
                    break
                
                task = future_to_task[future]
                try:
                    result = future.result(timeout=60)
                    task.complete(result)
                    
                    if self.on_task_complete:
                        self.on_task_complete(task, job)
                    
                    if progress_callback:
                        completed += 1
                        progress = job.get_progress()
                        progress_callback("progress", job, progress)
                        
                except Exception as e:
                    task.fail(str(e))
        
        job.complete()
        
        if self.stop_event.is_set():
            job.status = "cancelled"
        
        self.active_jobs.remove(job)
        self.completed_jobs.append(job)
        
        if self.on_job_complete:
            self.on_job_complete(job)
        
        if progress_callback:
            progress_callback("complete", job)
        
        return job
    
    def _run_single_task(self, task: Task, agent, lm_client) -> Dict:
        """
        Führt EINEN Task aus.
        """
        task.start()
        result = agent.analyze(task.input, task.type, lm_client)
        return result
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Bricht einen laufenden Job ab.
        """
        job = self.jobs.get(job_id)
        if job and job.status == "running":
            self.stop_event.set()
            return True
        return False
    
    def cancel_all(self):
        """Bricht alle laufenden Jobs ab"""
        self.stop_event.set()
    
    def get_job(self, job_id: str) -> Optional[AnalysisJob]:
        """Holt Job anhand ID"""
        return self.jobs.get(job_id)
    
    def get_recent_jobs(self, limit: int = 10) -> List[AnalysisJob]:
        """Holt die letzten Jobs"""
        all_jobs = list(self.completed_jobs) + self.active_jobs
        all_jobs.sort(key=lambda j: j.created_at, reverse=True)
        return all_jobs[:limit]
    
    def get_stats(self) -> Dict:
        """Liefert Statistiken"""
        total_jobs = len(self.jobs)
        total_tasks = sum(len(j.tasks) for j in self.jobs.values())
        completed_tasks = sum(
            sum(1 for t in j.tasks if t.status == "completed")
            for j in self.jobs.values()
        )
        failed_tasks = sum(
            sum(1 for t in j.tasks if t.status == "failed")
            for j in self.jobs.values()
        )
        
        return {
            "total_jobs": total_jobs,
            "active_jobs": len(self.active_jobs),
            "completed_jobs": len(self.completed_jobs),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    def export_job(self, job_id: str, format: str = "json") -> Dict:
        """
        Exportiert Job-Ergebnisse.
        
        Args:
            job_id: Job-ID
            format: "json", "txt", "html", "csv"
        
        Returns:
            Formatierte Daten
        """
        job = self.get_job(job_id)
        if not job:
            return {"error": "Job nicht gefunden"}
        
        # JSON Export
        if format == "json":
            return job.to_dict()
        
        # TXT Export
        elif format == "txt":
            text = self._format_txt(job)
            return {"text": text}
        
        # HTML Export
        elif format == "html":
            html = self._format_html(job)
            return {"html": html}
        
        # CSV Export
        elif format == "csv":
            csv_data = self._format_csv(job)
            return {"csv": csv_data}
        
        return {"error": f"Unbekanntes Format: {format}"}
    
    def _format_txt(self, job: AnalysisJob) -> str:
        """Formatiert Job als Text"""
        progress = job.get_progress()
        
        text = f"""
{'='*60}
📊 ANALYSE: {job.name}
{'='*60}

📝 AUFGABE: {job.task_type}
📅 ERSTELLT: {job.created_at}
⏱️ DAUER: {job.duration:.1f}s
👥 AGENTEN: {progress['total']} ({progress['completed']} fertig, {progress['failed']} fehlgeschlagen)

📈 FORTSCHRITT: {progress['progress']:.1f}%

{'='*60}
📋 ALLE ERGEBNISSE ({len(job.tasks)}):
{'='*60}

"""
        # Alle Ergebnisse auflisten
        for i, task in enumerate(job.tasks, 1):
            if task.status == "completed" and task.result:
                text += f"\n{'='*60}\n"
                text += f"👤 {i}. {task.agent_name}\n"
                text += f"📝 Aufgabe: {task.type}\n"
                text += f"⏱️ Dauer: {task.duration:.1f}s\n\n"
                text += task.result.get("analysis", str(task.result))
                text += f"\n"
        
        # Top-Zitate
        quotes = job.get_top_quotes(5)
        if quotes:
            text += f"\n{'='*60}\n"
            text += f"⭐ TOP ZITATE:\n"
            text += f"{'='*60}\n\n"
            for i, quote in enumerate(quotes, 1):
                text += f"{i}. [{quote['agent']}] {quote['text']}\n\n"
        
        return text
    
    def _format_html(self, job: AnalysisJob) -> str:
        """Formatiert Job als HTML (GEILES DESIGN)"""
        progress = job.get_progress()
        
        # Farben für verschiedene Rollen
        colors = ["#4a90e2", "#e24a4a", "#4ae24a", "#e2b04a", "#9b59b6", "#ff6b6b", "#3498db", "#e67e22"]
        
        # HTML Template
        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Analyse: {job.name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: "📊";
            position: absolute;
            right: 20px;
            bottom: 20px;
            font-size: 120px;
            opacity: 0.1;
            transform: rotate(10deg);
        }}
        
        .header h1 {{
            font-size: 2.5em;
            color: #333;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            color: #666;
            font-size: 1.1em;
            margin-bottom: 20px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .stat-card {{
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }}
        
        .stat-card .label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }}
        
        .stat-card .unit {{
            color: #999;
            font-size: 0.9em;
            margin-left: 5px;
        }}
        
        .section {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .section h2 {{
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            display: inline-block;
        }}
        
        .quote-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .quote-card {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 15px;
            padding: 20px;
            position: relative;
            transition: transform 0.3s ease;
        }}
        
        .quote-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.15);
        }}
        
        .quote-card::before {{
            content: """;
        html += '"\\201C"';
        html += f""";
            position: absolute;
            top: 10px;
            left: 10px;
            font-size: 60px;
            color: rgba(102, 126, 234, 0.2);
            font-family: serif;
        }}
        
        .quote-card .agent {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        
        .quote-card .text {{
            color: #333;
            line-height: 1.6;
            font-style: italic;
        }}
        
        .results-list {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        .result-item {{
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            border-left: 5px solid #667eea;
            transition: transform 0.3s ease;
        }}
        
        .result-item:hover {{
            transform: translateX(5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }}
        
        .result-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .result-header .agent {{
            font-weight: bold;
            color: #333;
            font-size: 1.2em;
        }}
        
        .result-header .role {{
            color: #667eea;
            font-size: 0.9em;
            background: rgba(102, 126, 234, 0.1);
            padding: 5px 10px;
            border-radius: 20px;
        }}
        
        .result-header .duration {{
            color: #999;
            font-size: 0.9em;
        }}
        
        .result-content {{
            color: #444;
            line-height: 1.6;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #f0f0f0;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            width: {progress['progress']}%;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }}
        
        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-top: 40px;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.8em; }}
            .stats-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <div class="header">
            <h1>📊 {job.name}</h1>
            <div class="meta">
                {job.task_type} • {progress['total']} Agenten • {job.duration:.1f}s
            </div>
            
            <div class="progress-bar">
                <div class="progress-fill">
                    {progress['progress']:.1f}%
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">Fertig</div>
                    <div class="value">{progress['completed']}<span class="unit">/{progress['total']}</span></div>
                </div>
                <div class="stat-card">
                    <div class="label">Fehlgeschlagen</div>
                    <div class="value">{progress['failed']}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Dauer</div>
                    <div class="value">{job.duration:.1f}<span class="unit">s</span></div>
                </div>
                <div class="stat-card">
                    <div class="label">Erstellt</div>
                    <div class="value">{job.created_at[11:16]}</div>
                </div>
            </div>
        </div>
"""
        
        # TOP ZITATE
        quotes = job.get_top_quotes(6)
        if quotes:
            html += f"""
        <!-- TOP ZITATE -->
        <div class="section">
            <h2>⭐ Top Zitate</h2>
            <div class="quote-grid">
"""
            for quote in quotes:
                color = random.choice(colors)
                html += f"""
                <div class="quote-card" style="border-left: 5px solid {color};">
                    <div class="agent">{quote['agent']}</div>
                    <div class="text">"{quote['text']}"</div>
                </div>
"""
            html += """
            </div>
        </div>
"""
        
        # ALLE ERGEBNISSE
        html += f"""
        <!-- ALLE ERGEBNISSE -->
        <div class="section">
            <h2>📋 Alle Ergebnisse ({len(job.tasks)})</h2>
            <div class="results-list">
"""
        
        for i, task in enumerate(job.tasks):
            if task.status == "completed" and task.result:
                role = task.result.get("role", "Unbekannt")
                color = colors[i % len(colors)]
                
                html += f"""
                <div class="result-item" style="border-left-color: {color};">
                    <div class="result-header">
                        <div>
                            <span class="agent">{task.agent_name}</span>
                            <span class="role">{role}</span>
                        </div>
                        <div class="duration">{task.duration:.1f}s</div>
                    </div>
                    <div class="result-content">
                        {task.result.get('analysis', str(task.result)).replace(chr(10), '<br>')}
                    </div>
                </div>
"""
        
        html += f"""
            </div>
        </div>
        
        <!-- INPUT TEXT -->
        <div class="section">
            <h2>📄 Analysierter Text</h2>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; font-family: monospace; white-space: pre-wrap;">
                {job.input_text}
            </div>
        </div>
        
        <div class="footer">
            🐟 SynthAgora • {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </div>
    </div>
</body>
</html>"""
        
        return html
    
    def _format_csv(self, job: AnalysisJob) -> str:
        """Formatiert Job als CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Agent", "Rolle", "Aufgabe", "Dauer (s)", "Ergebnis", "Status", "Fehler"])
        
        # Daten
        for task in job.tasks:
            role = task.result.get("role", "Unbekannt") if task.result else "Unbekannt"
            analysis = task.result.get("analysis", "") if task.result else ""
            error = task.error if task.error else ""
            
            writer.writerow([
                task.agent_name,
                role,
                task.type,
                f"{task.duration:.1f}" if task.duration else "",
                analysis,
                task.status,
                error
            ])
        
        return output.getvalue()