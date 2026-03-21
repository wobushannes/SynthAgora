#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualisierung für SynthAgora
- Netzwerk-Graph (Einflüsse)
- Heatmap (Agent vs. Thema)
- Timeline (Sentiment-Verlauf)
- Wortwolke
- HTML/PDF-Export
"""

import os
import json
import tempfile
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import threading
import webbrowser

# Für Diagramme
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False

from .config import Config


class Visualization:
    """Visualisierungs-Tools für Diskussions-Ergebnisse"""
    
    def __init__(self, parent_frame=None):
        self.parent_frame = parent_frame
        self.current_figure = None
        self.current_canvas = None
        self._lock = threading.Lock()
    
    def draw_network_graph(self, nodes: List[Dict], edges: List[Dict], 
                           title: str = "Einfluss-Netzwerk") -> Figure:
        """
        Zeichnet einen Netzwerk-Graph.
        
        Args:
            nodes: [{"id": str, "name": str, "color": str, "size": float}]
            edges: [{"from": str, "to": str, "strength": float}]
            title: Titel des Graphen
        """
        fig = Figure(figsize=(10, 8), facecolor='#1a1a2e')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        ax.set_title(title, color='white', fontsize=14, pad=20)
        
        # Positionen berechnen (einfach: Kreis- oder Frühlayout)
        n = len(nodes)
        node_ids = [n["id"] for n in nodes]
        node_positions = {}
        
        # Einfaches Kreis-Layout
        for i, node in enumerate(nodes):
            angle = 2 * np.pi * i / n
            radius = 3
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
            node_positions[node["id"]] = (x, y)
        
        # Kanten zeichnen
        for edge in edges:
            if edge["from"] in node_positions and edge["to"] in node_positions:
                x1, y1 = node_positions[edge["from"]]
                x2, y2 = node_positions[edge["to"]]
                strength = edge.get("strength", 0.5)
                alpha = min(1.0, strength)
                linewidth = 1 + strength * 2
                ax.plot([x1, x2], [y1, y2], 'gray', alpha=alpha, linewidth=linewidth, zorder=1)
        
        # Knoten zeichnen
        for node in nodes:
            x, y = node_positions[node["id"]]
            color = node.get("color", "#4a90e2")
            size = node.get("size", 500)
            ax.scatter(x, y, s=size, c=color, alpha=0.8, edgecolors='white', linewidth=1, zorder=2)
            ax.annotate(node.get("name", node["id"]), (x, y), 
                       xytext=(5, 5), textcoords='offset points',
                       color='white', fontsize=8, ha='left')
        
        ax.set_xlim(-4, 4)
        ax.set_ylim(-4, 4)
        ax.axis('off')
        
        fig.tight_layout()
        return fig
    
    def draw_heatmap(self, agents: List[str], topics: List[str], matrix: List[List[float]],
                     title: str = "Agenten vs. Themen") -> Figure:
        """
        Zeichnet eine Heatmap.
        
        Args:
            agents: Liste der Agentennamen
            topics: Liste der Themen
            matrix: 2D Liste mit Werten (0-1)
            title: Titel
        """
        fig = Figure(figsize=(12, 8), facecolor='#1a1a2e')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        
        data = np.array(matrix)
        
        # Heatmap zeichnen
        im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        # Achsen beschriften
        ax.set_xticks(np.arange(len(topics)))
        ax.set_yticks(np.arange(len(agents)))
        ax.set_xticklabels(topics, rotation=45, ha='right', fontsize=8, color='white')
        ax.set_yticklabels(agents, fontsize=8, color='white')
        
        # Werte in Zellen anzeigen
        for i in range(len(agents)):
            for j in range(len(topics)):
                value = data[i, j]
                if value > 0.5:
                    text_color = 'white'
                else:
                    text_color = 'black'
                ax.text(j, i, f'{value:.2f}', ha='center', va='center', 
                       color=text_color, fontsize=7)
        
        ax.set_title(title, color='white', fontsize=14, pad=20)
        ax.set_xlabel('Themen', color='white', fontsize=10)
        ax.set_ylabel('Agenten', color='white', fontsize=10)
        
        # Farbskala
        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Intensität', color='white')
        cbar.ax.yaxis.set_tick_params(color='white')
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
        
        fig.tight_layout()
        return fig
    
    def draw_timeline(self, timeline: List[Dict], title: str = "Sentiment-Verlauf") -> Figure:
        """
        Zeichnet einen Sentiment-Timeline.
        
        Args:
            timeline: [{"round": int, "sentiment": float, "count": int}]
            title: Titel
        """
        fig = Figure(figsize=(10, 6), facecolor='#1a1a2e')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        
        rounds = [t["round"] for t in timeline]
        sentiments = [t["sentiment"] for t in timeline]
        
        # Linie
        ax.plot(rounds, sentiments, 'o-', color='#4a90e2', linewidth=2, markersize=8)
        
        # Bereich füllen
        ax.fill_between(rounds, 0, sentiments, alpha=0.3, color='#4a90e2')
        
        # Horizontale Linie bei 0.5 (neutral)
        ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        
        ax.set_xlabel('Runde', color='white', fontsize=10)
        ax.set_ylabel('Sentiment (0=negativ, 1=positiv)', color='white', fontsize=10)
        ax.set_title(title, color='white', fontsize=14, pad=20)
        ax.set_xlim(min(rounds) - 0.5, max(rounds) + 0.5)
        ax.set_ylim(0, 1)
        
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Werte anzeigen
        for r, s in zip(rounds, sentiments):
            ax.annotate(f'{s:.2f}', (r, s), xytext=(5, 5), textcoords='offset points',
                       color='white', fontsize=8)
        
        fig.tight_layout()
        return fig
    
    def draw_wordcloud(self, words_data: List[Dict], title: str = "Wortwolke") -> Figure:
        """
        Zeichnet eine Wortwolke.
        
        Args:
            words_data: [{"word": str, "count": int, "weight": float}]
            title: Titel
        """
        if not WORDCLOUD_AVAILABLE:
            # Fallback: einfaches Balkendiagramm
            return self._draw_wordcloud_fallback(words_data, title)
        
        fig = Figure(figsize=(12, 8), facecolor='#1a1a2e')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        
        # WordCloud erstellen
        word_freq = {w["word"]: w["count"] for w in words_data}
        wordcloud = WordCloud(width=800, height=600, background_color='#1a1a2e',
                              colormap='viridis', max_words=50).generate_from_frequencies(word_freq)
        
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        ax.set_title(title, color='white', fontsize=14, pad=20)
        
        fig.tight_layout()
        return fig
    
    def _draw_wordcloud_fallback(self, words_data: List[Dict], title: str) -> Figure:
        """Fallback-Wortwolke als Balkendiagramm"""
        fig = Figure(figsize=(10, 8), facecolor='#1a1a2e')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        
        top_words = words_data[:20]
        words = [w["word"] for w in top_words]
        counts = [w["count"] for w in top_words]
        
        # Horizontale Balken
        y_pos = np.arange(len(words))
        ax.barh(y_pos, counts, color='#4a90e2', alpha=0.8)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(words, color='white', fontsize=10)
        ax.set_xlabel('Häufigkeit', color='white', fontsize=10)
        ax.set_title(title, color='white', fontsize=14, pad=20)
        
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        fig.tight_layout()
        return fig
    
    def draw_consensus_gauge(self, consensus: float, title: str = "Konsens") -> Figure:
        """
        Zeichnet ein Konsens-Tachometer.
        
        Args:
            consensus: Wert zwischen 0 und 1
            title: Titel
        """
        fig = Figure(figsize=(6, 6), facecolor='#1a1a2e')
        ax = fig.add_subplot(111, projection='polar')
        ax.set_facecolor('#1a1a2e')
        
        # Tachometer
        theta = np.linspace(0, np.pi, 100)
        r = np.ones_like(theta)
        
        ax.bar(theta, r, width=0.05, color='#2a2a4e', alpha=0.5)
        
        # Zeiger
        angle = consensus * np.pi
        ax.plot([angle, angle], [0, 1], color='#e24a4a', linewidth=3)
        
        # Beschriftung
        ax.set_xticks([0, np.pi/2, np.pi])
        ax.set_xticklabels(['0%', '50%', '100%'], color='white')
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_title(title, color='white', fontsize=14, pad=20)
        
        # Wert in der Mitte
        ax.text(np.pi/2, 0.5, f'{consensus*100:.1f}%', 
               ha='center', va='center', color='white', fontsize=20, fontweight='bold')
        
        fig.tight_layout()
        return fig
    
    def draw_argument_tree(self, argument_map: Dict, title: str = "Argument-Baum") -> Figure:
        """
        Zeichnet einen Argument-Baum.
        
        Args:
            argument_map: Von build_argument_map() zurückgegebenes Dict
            title: Titel
        """
        fig = Figure(figsize=(12, 10), facecolor='#1a1a2e')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1a1a2e')
        ax.axis('off')
        
        # Einfache Baum-Darstellung
        nodes = argument_map.get("nodes", {})
        connections = argument_map.get("connections", [])
        
        # Positionen berechnen (einfaches Tree-Layout)
        positions = {}
        levels = {}
        
        # Root-Level
        positions[0] = (0, 0)
        levels[0] = 0
        
        # Verbindungen verarbeiten
        for conn in connections:
            from_idx = conn["from"]
            to_idx = conn["to"]
            if from_idx not in levels:
                levels[from_idx] = 0
            levels[to_idx] = levels[from_idx] + 1
        
        # Gruppieren nach Level
        level_groups = defaultdict(list)
        for idx, level in levels.items():
            level_groups[level].append(idx)
        
        # Positionen pro Level
        for level, indices in level_groups.items():
            y = -level * 1.5
            x_start = -len(indices) / 2
            for i, idx in enumerate(indices):
                x = x_start + i
                positions[idx] = (x, y)
        
        # Kanten zeichnen
        for conn in connections:
            from_pos = positions.get(conn["from"])
            to_pos = positions.get(conn["to"])
            if from_pos and to_pos:
                ax.plot([from_pos[0], to_pos[0]], [from_pos[1], to_pos[1]], 
                       'gray', alpha=0.5, linewidth=1)
        
        # Knoten zeichnen
        for idx, pos in positions.items():
            node = nodes.get(idx, {})
            argument = node.get("argument", f"Beitrag {idx}")[:50]
            agent = node.get("agent", "")
            
            ax.scatter(pos[0], pos[1], s=300, c='#4a90e2', alpha=0.8, edgecolors='white')
            ax.annotate(f"{agent}\n{argument}", (pos[0], pos[1]), 
                       xytext=(5, 5), textcoords='offset points',
                       color='white', fontsize=7, ha='left')
        
        ax.set_xlim(-5, 5)
        ax.set_ylim(-10, 2)
        ax.set_title(title, color='white', fontsize=14, pad=20)
        
        fig.tight_layout()
        return fig
    
    def export_to_html(self, report: Dict, output_path: str = None) -> str:
        """
        Exportiert Analyse-Bericht als HTML.
        
        Args:
            report: Von generate_full_report() zurückgegebenes Dict
            output_path: Pfad für HTML-Datei (optional)
        
        Returns:
            Pfad zur generierten HTML-Datei
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(Config.EXPORTS_FOLDER, f"report_{timestamp}.html")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # HTML Template
        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SynthAgora Analyse: {report.get('topic', 'Diskussion')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            padding: 40px 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        .header {{
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header .meta {{ color: #aaa; font-size: 0.9em; }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }}
        .stat-card .value {{ font-size: 2.5em; font-weight: bold; color: #4a90e2; }}
        .stat-card .label {{ color: #aaa; margin-top: 10px; }}
        
        .section {{
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 30px;
        }}
        .section h2 {{
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #4a90e2;
            display: inline-block;
        }}
        
        .thesis-list { list-style: none; }
        .thesis-item {{
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .thesis-text {{ font-size: 1.1em; margin-bottom: 10px; }}
        .thesis-confidence {{
            display: inline-block;
            background: #4a90e2;
            border-radius: 20px;
            padding: 2px 10px;
            font-size: 0.8em;
            margin-right: 10px;
        }}
        .thesis-agents {{
            display: flex;
            gap: 10px;
            margin-top: 10px;
            font-size: 0.8em;
            color: #aaa;
        }}
        
        .quote-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .quote-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border-left: 4px solid #4a90e2;
        }}
        .quote-text {{ font-style: italic; margin-bottom: 10px; }}
        .quote-author {{ color: #4a90e2; font-size: 0.9em; }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            color: #666;
            font-size: 0.8em;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.5em; }}
            .stats-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {report.get('topic', 'Diskussions-Analyse')}</h1>
            <div class="meta">Generiert am {report.get('timestamp', datetime.now().isoformat())}</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="value">{report.get('summary', {}).get('total_contributions', 0)}</div>
                <div class="label">Beiträge</div>
            </div>
            <div class="stat-card">
                <div class="value">{report.get('summary', {}).get('unique_agents', 0)}</div>
                <div class="label">Agenten</div>
            </div>
            <div class="stat-card">
                <div class="value">{report.get('summary', {}).get('total_rounds', 0)}</div>
                <div class="label">Runden</div>
            </div>
            <div class="stat-card">
                <div class="value">{report.get('consensus', {}).get('overall_consensus', 0)*100:.1f}%</div>
                <div class="label">Konsens</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📌 Zentrale Thesen</h2>
            <ul class="thesis-list">
"""
        
        # Thesen
        for thesis in report.get('theses', [])[:10]:
            html += f"""
                <li class="thesis-item">
                    <div class="thesis-text">“{thesis['thesis']}”</div>
                    <div>
                        <span class="thesis-confidence">Konfidenz: {thesis['confidence']*100:.0f}%</span>
                        <span>Mentions: {thesis.get('mentions', 1)}</span>
                    </div>
                    <div class="thesis-agents">
                        <span>✅ Pro: {', '.join(thesis.get('proponents', [])[:3]) or 'keine'}</span>
                        <span>❌ Contra: {', '.join(thesis.get('opponents', [])[:3]) or 'keine'}</span>
                    </div>
                </li>
"""
        
        html += """
            </ul>
        </div>
        
        <div class="section">
            <h2>💬 Wichtigste Zitate</h2>
            <div class="quote-grid">
"""
        
        # Zitate
        for quote in report.get('key_quotes', [])[:8]:
            type_icon = {"thesis": "💡", "insight": "🔍", "counter": "⚡", "agreement": "✅", "question": "❓"}.get(quote.get('type'), "💬")
            html += f"""
                <div class="quote-card">
                    <div class="quote-text">“{quote['text']}”</div>
                    <div class="quote-author">{type_icon} {quote['agent']} (Runde {quote['round']})</div>
                </div>
"""
        
        html += f"""
            </div>
        </div>
        
        <div class="section">
            <h2>🎭 Themen-Cluster</h2>
            <ul class="thesis-list">
"""
        
        # Cluster
        for cluster in report.get('clusters', {}).get('clusters', [])[:5]:
            html += f"""
                <li class="thesis-item">
                    <div class="thesis-text">📂 {cluster['name']}</div>
                    <div>Schlüsselwörter: {', '.join(cluster.get('keywords', []))}</div>
                    <div>Agenten: {', '.join(cluster.get('agents', [])[:3])}</div>
                </li>
"""
        
        html += f"""
            </ul>
        </div>
        
        <div class="footer">
            🐟 SynthAgora • KI-gestützte Diskussionsanalyse
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path
    
    def export_to_pdf(self, report: Dict, output_path: str = None) -> str:
        """
        Exportiert Analyse-Bericht als PDF.
        
        Args:
            report: Von generate_full_report() zurückgegebenes Dict
            output_path: Pfad für PDF-Datei (optional)
        
        Returns:
            Pfad zur generierten PDF-Datei
        """
        # Zuerst HTML generieren
        html_path = self.export_to_html(report, output_path)
        
        # HTML in PDF konvertieren (falls wkhtmltopdf verfügbar)
        pdf_path = html_path.replace('.html', '.pdf')
        
        try:
            import pdfkit
            pdfkit.from_file(html_path, pdf_path)
            return pdf_path
        except:
            # Fallback: Browser öffnen für manuellen Export
            webbrowser.open(html_path)
            return html_path
    
    def embed_in_gui(self, figure: Figure, frame=None):
        """Bettet eine Figur in ein GUI-Frame ein"""
        if frame is None:
            frame = self.parent_frame
        
        if frame is None:
            return None
        
        canvas = FigureCanvasTkAgg(figure, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        
        self.current_figure = figure
        self.current_canvas = canvas
        
        return canvas
    
    def clear(self):
        """Löscht die aktuelle Visualisierung"""
        if self.current_canvas:
            self.current_canvas.get_tk_widget().destroy()
            self.current_canvas = None
            self.current_figure = None


if __name__ == "__main__":
    viz = Visualization()
    print("Visualisierung initialisiert")
    print(f"WordCloud verfügbar: {WORDCLOUD_AVAILABLE}")