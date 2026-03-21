#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite-Datenbank für SynthAgora
- Jede Methode öffnet und schließt ihre eigene Verbindung
- Keine Thread-Local Storage Probleme
"""

import sqlite3
import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from .config import Config


class SynthAgoraDB:
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(Config.KNOWLEDGE_FOLDER, exist_ok=True)
            self.db_path = os.path.join(Config.KNOWLEDGE_FOLDER, "synthagora.db")
        else:
            self.db_path = db_path
        
        self._init_database()
        print(f"✅ Datenbank: {self.db_path}")
    
    def _get_connection(self):
        """Öffnet eine neue Verbindung"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")
        return conn
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)
    
    def is_duplicate_fact(self, fact: str, topic: str, similarity_threshold: float = None) -> bool:
        if similarity_threshold is None:
            similarity_threshold = Config.DUPLICATE_SIMILARITY_THRESHOLD
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fact FROM memory_crystals mc
                JOIN memory_rooms mr ON mc.room_id = mr.room_id
                WHERE mc.topic = ?
            """, (topic,))
            
            facts = [row[0] for row in cursor.fetchall()]
            for existing_fact in facts:
                if self._text_similarity(fact, existing_fact) > similarity_threshold:
                    return True
            return False
        except Exception as e:
            print(f"⚠️ Duplikat-Check fehlgeschlagen: {e}")
            return False
        finally:
            conn.close()
    
    def _normalize_role(self, role: str) -> str:
        if not role:
            return "Unbekannt"
        role_lower = role.lower()
        
        if any(w in role_lower for w in ["arzt", "ärztin", "chirurg"]):
            return "Arzt/Ärztin"
        if any(w in role_lower for w in ["krankenschwester", "pfleger", "pflegekraft"]):
            return "Pflegekraft"
        if any(w in role_lower for w in ["anwalt", "anwältin", "rechtsanwalt"]):
            return "Anwalt/Anwältin"
        if any(w in role_lower for w in ["richter", "richterin"]):
            return "Richter/Richterin"
        if any(w in role_lower for w in ["lehrer", "lehrerin"]):
            return "Lehrer/Lehrerin"
        
        role = re.sub(r'\([^)]*\)', '', role)
        words = role.strip().split()[:2]
        return " ".join(words).strip()
    
    def _tokenize_query(self, query: str) -> List[str]:
        clean = re.sub(r'[^\w\-]', ' ', query)
        return [t.strip() for t in clean.split() if len(t.strip()) > 1]
    
    def _init_database(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_pool (
                    agent_id TEXT PRIMARY KEY,
                    set_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    tags TEXT,
                    json_file TEXT NOT NULL,
                    generation_mode TEXT,
                    generation_date TIMESTAMP,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_name ON agent_pool(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_role ON agent_pool(role)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    pool_id TEXT,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    personality TEXT,
                    color TEXT,
                    team TEXT,
                    team_role TEXT,
                    education TEXT,
                    background TEXT,
                    training_level REAL DEFAULT 1.0,
                    skills TEXT,
                    personality_traits TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT,
                    FOREIGN KEY (pool_id) REFERENCES agent_pool(agent_id) ON DELETE SET NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_unique_name ON agents(name) WHERE is_active = 1")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_skills (
                    agent_id TEXT PRIMARY KEY,
                    fachwissen REAL DEFAULT 0.5,
                    kommunikation REAL DEFAULT 0.5,
                    analyse REAL DEFAULT 0.5,
                    kreativitaet REAL DEFAULT 0.5,
                    diplomatie REAL DEFAULT 0.5,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_expertise (
                    agent_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    expertise_level REAL DEFAULT 0.5,
                    contributions INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (agent_id, topic),
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expertise_agent ON agent_expertise(agent_id)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_evolution (
                    agent_id TEXT PRIMARY KEY,
                    experience_points INTEGER DEFAULT 0,
                    rank TEXT DEFAULT 'Junior',
                    total_discussions INTEGER DEFAULT 0,
                    total_contributions INTEGER DEFAULT 0,
                    total_learned_facts INTEGER DEFAULT 0,
                    total_analyses INTEGER DEFAULT 0,
                    total_influences_given INTEGER DEFAULT 0,
                    total_influences_received INTEGER DEFAULT 0,
                    total_score_points INTEGER DEFAULT 0,
                    rank_achieved_at TIMESTAMP,
                    last_promotion TIMESTAMP,
                    evolution_history TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    importance REAL DEFAULT 0.5
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(node_type)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_edges (
                    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node TEXT NOT NULL,
                    to_node TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    strength REAL DEFAULT 1.0,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    use_count INTEGER DEFAULT 0,
                    FOREIGN KEY (from_node) REFERENCES kg_nodes(node_id) ON DELETE CASCADE,
                    FOREIGN KEY (to_node) REFERENCES kg_nodes(node_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kg_edges_from ON kg_edges(from_node)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kg_edges_to ON kg_edges(to_node)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    topic_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    node_count INTEGER DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_name ON topics(name)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_nodes (
                    topic_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    relevance REAL DEFAULT 1.0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (topic_id, node_id),
                    FOREIGN KEY (topic_id) REFERENCES topics(topic_id) ON DELETE CASCADE,
                    FOREIGN KEY (node_id) REFERENCES kg_nodes(node_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS influences (
                    influence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    influencer_id TEXT NOT NULL,
                    influenced_id TEXT NOT NULL,
                    topic_id TEXT,
                    strength REAL DEFAULT 0.5,
                    description TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified BOOLEAN DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_influences_influencer ON influences(influencer_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_influences_influenced ON influences(influenced_id)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prognoses (
                    prognosis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified BOOLEAN DEFAULT 0,
                    correct BOOLEAN,
                    verification_time TIMESTAMP,
                    verification_notes TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prognoses_agent ON prognoses(agent_id)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checklists (
                    checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    items TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    discussion_id TEXT,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    leader_id TEXT,
                    FOREIGN KEY (leader_id) REFERENCES agents(agent_id) ON DELETE SET NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_members (
                    team_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    role TEXT DEFAULT 'Mitglied',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    PRIMARY KEY (team_id, agent_id),
                    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    reason TEXT,
                    category TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    discussion_id TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_agent ON scores(agent_id)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discussions (
                    discussion_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    purpose TEXT,
                    goal TEXT,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    round_count INTEGER DEFAULT 0,
                    contribution_count INTEGER DEFAULT 0,
                    moderator_id TEXT,
                    summary TEXT,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contributions (
                    contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discussion_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    round_number INTEGER,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_reaction BOOLEAN DEFAULT 0,
                    reacts_to INTEGER,
                    sentiment REAL,
                    metadata TEXT,
                    FOREIGN KEY (discussion_id) REFERENCES discussions(discussion_id) ON DELETE CASCADE,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_rooms (
                    room_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    size REAL DEFAULT 1.0,
                    color TEXT DEFAULT '#4a90e2',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    crystal_count INTEGER DEFAULT 0,
                    properties TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_rooms_agent ON memory_rooms(agent_id)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_crystals (
                    crystal_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    topic TEXT,
                    importance REAL DEFAULT 0.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    position_x REAL,
                    position_y REAL,
                    position_z REAL,
                    connections TEXT,
                    metadata TEXT,
                    FOREIGN KEY (room_id) REFERENCES memory_rooms(room_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_crystals_room ON memory_crystals(room_id)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_halls (
                    hall_id TEXT PRIMARY KEY,
                    from_room TEXT NOT NULL,
                    to_room TEXT NOT NULL,
                    topic TEXT,
                    strength REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    properties TEXT,
                    FOREIGN KEY (from_room) REFERENCES memory_rooms(room_id) ON DELETE CASCADE,
                    FOREIGN KEY (to_room) REFERENCES memory_rooms(room_id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    type TEXT DEFAULT 'string',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trigger_new_agent_skills
                AFTER INSERT ON agents
                BEGIN
                    INSERT OR IGNORE INTO agent_skills (agent_id) VALUES (NEW.agent_id);
                    INSERT OR IGNORE INTO agent_evolution (agent_id) VALUES (NEW.agent_id);
                END;
            """)
            
            defaults = [
                ('db_version', '4.1', 'string', 'Datenbank-Schema-Version'),
                ('total_agent_generations', '0', 'int', 'Anzahl generierter Agenten'),
                ('total_discussions', '0', 'int', 'Anzahl Diskussionen'),
                ('pool_size', '0', 'int', 'Anzahl Agenten im Pool'),
                ('kg_migrated', 'false', 'bool', 'Knowledge Graph bereits migriert'),
                ('last_backup', '', 'string', 'Letztes Backup'),
                ('total_contributions', '0', 'int', 'Alle Beiträge'),
                ('total_prognoses', '0', 'int', 'Alle Prognosen'),
                ('accuracy_average', '0', 'float', 'Durchschnittliche Trefferquote'),
                ('evolution_enabled', 'true', 'bool', 'Agenten-Evolution aktiviert')
            ]
            
            for key, value, typ, desc in defaults:
                cursor.execute(
                    "INSERT OR IGNORE INTO system_settings (key, value, type, description) VALUES (?, ?, ?, ?)",
                    (key, value, typ, desc)
                )
            
            conn.commit()
            print("✅ Datenbank mit ALLEN Tabellen initialisiert")
        except Exception as e:
            print(f"❌ Fehler bei Datenbank-Initialisierung: {e}")
        finally:
            conn.close()
    
    # ==================== POOL-METHODEN ====================
    
    def add_to_pool(self, agent_data: Dict) -> str:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT agent_id FROM agent_pool WHERE name = ? AND json_file = ?", 
                          (agent_data["name"], agent_data["json_file"]))
            existing = cursor.fetchone()
            if existing:
                return existing[0]
            
            metadata_json = json.dumps(agent_data.get("metadata", {}), ensure_ascii=False)
            cursor.execute("""
                INSERT INTO agent_pool 
                (agent_id, set_name, name, role, tags, json_file, generation_mode, generation_date, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_data["agent_id"],
                agent_data["set_name"],
                agent_data["name"],
                agent_data["role"],
                agent_data.get("tags", "[]"),
                agent_data["json_file"],
                agent_data.get("generation_mode", "import"),
                agent_data.get("generation_date", datetime.now().isoformat()),
                metadata_json
            ))
            conn.commit()
            return agent_data["agent_id"]
        finally:
            conn.close()
    
    def get_agent_from_pool_by_name(self, name: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_pool WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                agent = dict(row)
                if agent['tags']:
                    try:
                        agent['tags'] = json.loads(agent['tags'])
                    except:
                        agent['tags'] = []
                if agent['metadata']:
                    try:
                        agent['metadata'] = json.loads(agent['metadata'])
                    except:
                        agent['metadata'] = {}
                return agent
            return None
        finally:
            conn.close()
    
    def get_pool_stats(self) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM agent_pool")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT generation_mode, COUNT(*) FROM agent_pool GROUP BY generation_mode")
            by_mode = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(DISTINCT set_name) FROM agent_pool")
            sets = cursor.fetchone()[0]
            return {"total": total, "by_mode": by_mode, "unique_sets": sets}
        finally:
            conn.close()
    
    def get_pool_stats_normalized(self) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM agent_pool")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT role FROM agent_pool")
            all_roles = [row[0] for row in cursor.fetchall()]
            
            normalized_roles = {}
            for role in all_roles:
                norm_role = self._normalize_role(role)
                normalized_roles[norm_role] = normalized_roles.get(norm_role, 0) + 1
            top_roles = sorted(normalized_roles.items(), key=lambda x: x[1], reverse=True)[:20]
            
            cursor.execute("""
                SELECT json_extract(metadata, '$.charakter_typ') as charakter, COUNT(*) as count
                FROM agent_pool WHERE json_extract(metadata, '$.charakter_typ') IS NOT NULL
                GROUP BY charakter ORDER BY count DESC
            """)
            charaktere = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT json_extract(metadata, '$.team') as team, COUNT(*) as count
                FROM agent_pool WHERE json_extract(metadata, '$.team') IS NOT NULL
                GROUP BY team ORDER BY count DESC
            """)
            teams = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("SELECT generation_mode, COUNT(*) FROM agent_pool GROUP BY generation_mode")
            modes = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("SELECT COUNT(DISTINCT set_name) FROM agent_pool")
            sets = cursor.fetchone()[0]
            
            cursor.execute("SELECT rank, COUNT(*) FROM agent_evolution GROUP BY rank")
            ranks = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total": total, "roles": normalized_roles, "charaktere": charaktere,
                "teams": teams, "modes": modes, "sets": sets, "top_roles": top_roles,
                "top_charaktere": list(charaktere.items())[:20],
                "top_teams": list(teams.items())[:20], "ranks": ranks
            }
        finally:
            conn.close()
    
    def search_pool(self, query: str, limit: int = 100) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            tokens = self._tokenize_query(query)
            if not tokens:
                return []
            
            conditions = []
            params = []
            for token in tokens:
                token_conditions = []
                for field in ["name", "role", "tags"]:
                    token_conditions.append(f"{field} LIKE ?")
                    params.append(f"%{token}%")
                conditions.append("(" + " OR ".join(token_conditions) + ")")
            
            where_clause = " AND ".join(conditions)
            cursor.execute(f"SELECT * FROM agent_pool WHERE {where_clause} ORDER BY name LIMIT ?", params + [limit])
            
            results = []
            for row in cursor.fetchall():
                agent = dict(row)
                if agent['tags']:
                    try:
                        agent['tags'] = json.loads(agent['tags'])
                    except:
                        agent['tags'] = []
                if agent['metadata']:
                    try:
                        agent['metadata'] = json.loads(agent['metadata'])
                    except:
                        agent['metadata'] = {}
                results.append(agent)
            return results
        finally:
            conn.close()
    
    def get_random_from_pool(self, count: int, filters: Dict = None) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM agent_pool"
            params = []
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    where_clauses.append(f"{key} = ?")
                    params.append(value)
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY RANDOM() LIMIT ?"
            params.append(count)
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                agent = dict(row)
                if agent['tags']:
                    try:
                        agent['tags'] = json.loads(agent['tags'])
                    except:
                        agent['tags'] = []
                if agent['metadata']:
                    try:
                        agent['metadata'] = json.loads(agent['metadata'])
                    except:
                        agent['metadata'] = {}
                results.append(agent)
            return results
        finally:
            conn.close()
    
    def get_by_tags(self, tags: List[str], match_all: bool = False, limit: int = 100) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if match_all:
                conditions = ' AND '.join([f"tags LIKE '%{t}%'" for t in tags])
            else:
                conditions = ' OR '.join([f"tags LIKE '%{t}%'" for t in tags])
            cursor.execute(f"SELECT * FROM agent_pool WHERE {conditions} ORDER BY name LIMIT ?", [limit])
            
            results = []
            for row in cursor.fetchall():
                agent = dict(row)
                if agent['tags']:
                    try:
                        agent['tags'] = json.loads(agent['tags'])
                    except:
                        agent['tags'] = []
                if agent['metadata']:
                    try:
                        agent['metadata'] = json.loads(agent['metadata'])
                    except:
                        agent['metadata'] = {}
                results.append(agent)
            return results
        finally:
            conn.close()
    
    def cleanup_duplicates(self) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, json_file, COUNT(*) as count, GROUP_CONCAT(agent_id) as ids
                FROM agent_pool GROUP BY name, json_file HAVING count > 1
            """)
            duplicates = cursor.fetchall()
            deleted = 0
            for row in duplicates:
                ids = row[3].split(',')
                ids.sort()
                delete_ids = ids[:-1]
                for del_id in delete_ids:
                    cursor.execute("DELETE FROM agent_pool WHERE agent_id = ?", (del_id,))
                    deleted += 1
            conn.commit()
            return deleted
        finally:
            conn.close()
    
    # ==================== AKTIVE AGENTEN ====================
    
    def add_agent(self, agent_id: str, agent_data: Dict, pool_id: Optional[str] = None) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if pool_id:
                cursor.execute("SELECT agent_id FROM agent_pool WHERE agent_id = ?", (pool_id,))
                if not cursor.fetchone():
                    pool_id = None
            
            skills_json = json.dumps(agent_data.get('skills', {}), ensure_ascii=False)
            traits_json = json.dumps(agent_data.get('personality_traits', {}), ensure_ascii=False)
            metadata_json = json.dumps(agent_data.get('metadata', {}), ensure_ascii=False)
            
            cursor.execute("SELECT agent_id FROM agents WHERE agent_id = ?", (agent_id,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE agents SET pool_id = ?, name = ?, role = ?, personality = ?, color = ?,
                        team = ?, team_role = ?, education = ?, background = ?,
                        training_level = ?, skills = ?, personality_traits = ?,
                        metadata = ?, updated_at = CURRENT_TIMESTAMP, is_active = 1
                    WHERE agent_id = ?
                """, (pool_id, agent_data.get('name', ''), agent_data.get('role', ''),
                      agent_data.get('personality', ''), agent_data.get('color', '#cccccc'),
                      agent_data.get('team', ''), agent_data.get('team_role', 'Mitglied'),
                      agent_data.get('education', ''), agent_data.get('background', ''),
                      agent_data.get('training_level', 1.0), skills_json, traits_json,
                      metadata_json, agent_id))
            else:
                cursor.execute("""
                    INSERT INTO agents (agent_id, pool_id, name, role, personality, color, team, team_role,
                        education, background, training_level, skills, personality_traits, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (agent_id, pool_id, agent_data.get('name', ''), agent_data.get('role', ''),
                      agent_data.get('personality', ''), agent_data.get('color', '#cccccc'),
                      agent_data.get('team', ''), agent_data.get('team_role', 'Mitglied'),
                      agent_data.get('education', ''), agent_data.get('background', ''),
                      agent_data.get('training_level', 1.0), skills_json, traits_json, metadata_json))
            
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                agent = dict(row)
                for field in ['skills', 'personality_traits', 'metadata']:
                    if agent.get(field):
                        try:
                            agent[field] = json.loads(agent[field])
                        except:
                            agent[field] = {}
                return agent
            return None
        finally:
            conn.close()
    
    def get_all_agents(self, active_only: bool = True, limit: int = 10000, offset: int = 0) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM agents"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY name LIMIT ? OFFSET ?"
            cursor.execute(query, (limit, offset))
            
            agents = []
            for row in cursor.fetchall():
                agent = dict(row)
                for field in ['skills', 'personality_traits', 'metadata']:
                    if agent.get(field):
                        try:
                            agent[field] = json.loads(agent[field])
                        except:
                            agent[field] = {}
                
                # EVOLUTION-DATEN MITLADEN
                evolution = self.get_agent_evolution(agent['agent_id'])
                agent['evolution'] = evolution
                agent['rank'] = evolution.get('rank', 'Junior')
                agent['experience_points'] = evolution.get('experience_points', 0)
                
                agents.append(agent)
            return agents
        finally:
            conn.close()
    
    # ==================== SKILLS & EVOLUTION ====================
    
    def get_agent_skills(self, agent_id: str) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fachwissen, kommunikation, analyse, kreativitaet, diplomatie
                FROM agent_skills WHERE agent_id = ?
            """, (agent_id,))
            row = cursor.fetchone()
            if row:
                return {"fachwissen": row[0], "kommunikation": row[1], "analyse": row[2],
                        "kreativitaet": row[3], "diplomatie": row[4]}
            return {"fachwissen": 0.5, "kommunikation": 0.5, "analyse": 0.5,
                    "kreativitaet": 0.5, "diplomatie": 0.5}
        finally:
            conn.close()
    
    def update_agent_skill(self, agent_id: str, skill: str, increment: float) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {skill} FROM agent_skills WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO agent_skills (agent_id) VALUES (?)", (agent_id,))
                current = 0.5
            else:
                current = row[0]
            new_value = min(1.0, current + increment)
            cursor.execute(f"UPDATE agent_skills SET {skill} = ?, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ?",
                          (new_value, agent_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_agent_evolution(self, agent_id: str) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_evolution WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result['evolution_history']:
                    try:
                        result['evolution_history'] = json.loads(result['evolution_history'])
                    except:
                        result['evolution_history'] = []
                return result
            return {"experience_points": 0, "rank": "Junior", "total_discussions": 0,
                    "total_contributions": 0, "total_learned_facts": 0, "total_analyses": 0,
                    "total_influences_given": 0, "total_influences_received": 0,
                    "total_score_points": 0, "evolution_history": []}
        finally:
            conn.close()
    
    def add_experience(self, agent_id: str, points: int, reason: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT experience_points, rank FROM agent_evolution WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if not row:
                current_points = 0
                current_rank = "Junior"
                cursor.execute("INSERT INTO agent_evolution (agent_id) VALUES (?)", (agent_id,))
            else:
                current_points = row[0]
                current_rank = row[1]
            
            new_points = current_points + points
            rank_order = ["Junior", "Senior", "Experte", "Master"]
            thresholds = [0, 1000, 5000, 20000]
            
            new_rank = current_rank
            rank_promoted = False
            history = []
            
            cursor.execute("SELECT evolution_history FROM agent_evolution WHERE agent_id = ?", (agent_id,))
            hist_row = cursor.fetchone()
            if hist_row and hist_row[0]:
                try:
                    history = json.loads(hist_row[0])
                except:
                    history = []
            
            for i, threshold in enumerate(thresholds):
                if new_points >= threshold and i > rank_order.index(current_rank):
                    new_rank = rank_order[i]
                    rank_promoted = True
            
            if rank_promoted:
                history.append({
                    "timestamp": datetime.now().isoformat(),
                    "old_rank": current_rank,
                    "new_rank": new_rank,
                    "points": new_points,
                    "reason": reason
                })
            
            cursor.execute("""
                UPDATE agent_evolution SET experience_points = ?, rank = ?, evolution_history = ?,
                    last_promotion = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE last_promotion END,
                    rank_achieved_at = CASE WHEN ? AND rank_achieved_at IS NULL THEN CURRENT_TIMESTAMP ELSE rank_achieved_at END
                WHERE agent_id = ?
            """, (new_points, new_rank, json.dumps(history), rank_promoted, rank_promoted, agent_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_agent_expertise(self, agent_id: str) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT topic, expertise_level, contributions, last_updated
                FROM agent_expertise WHERE agent_id = ? ORDER BY expertise_level DESC
            """, (agent_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def update_expertise(self, agent_id: str, topic: str, increment: float = 0.05) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_expertise (agent_id, topic, expertise_level, contributions)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(agent_id, topic) DO UPDATE SET
                    expertise_level = MIN(1.0, expertise_level + ?),
                    contributions = contributions + 1,
                    last_updated = CURRENT_TIMESTAMP
            """, (agent_id, topic, increment, increment))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.agent_id, a.name, a.color, a.team, COALESCE(SUM(s.points), 0) as total_points,
                       COUNT(s.score_id) as score_count, MAX(s.timestamp) as last_score
                FROM agents a LEFT JOIN scores s ON a.agent_id = s.agent_id
                WHERE a.is_active = 1
                GROUP BY a.agent_id ORDER BY total_points DESC, last_score DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_leaderboard_by_rank(self, limit: int = 10) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.name, a.role, a.color, e.rank, e.experience_points,
                       e.total_discussions, e.total_contributions, e.total_learned_facts
                FROM agents a JOIN agent_evolution e ON a.agent_id = e.agent_id
                WHERE a.is_active = 1
                ORDER BY CASE e.rank WHEN 'Master' THEN 1 WHEN 'Experte' THEN 2
                         WHEN 'Senior' THEN 3 WHEN 'Junior' THEN 4 ELSE 5 END,
                         e.experience_points DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_agent_score_history(self, agent_id: str, limit: int = 100) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scores WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
                          (agent_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def add_score(self, agent_id: str, points: int, reason: str = '', category: str = 'general',
                  discussion_id: Optional[str] = None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scores (agent_id, points, reason, category, discussion_id)
                VALUES (?, ?, ?, ?, ?)
            """, (agent_id, points, reason, category, discussion_id))
            cursor.execute("UPDATE agent_evolution SET total_score_points = total_score_points + ? WHERE agent_id = ?",
                          (points, agent_id))
            conn.commit()
        finally:
            conn.close()
    
    # ==================== KNOWLEDGE GRAPH ====================
    
    def add_node(self, node_id: str, node_type: str, properties: Dict) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            props_json = json.dumps(properties, ensure_ascii=False)
            importance = properties.get('importance', 0.5)
            cursor.execute("""
                INSERT OR IGNORE INTO kg_nodes (node_id, node_type, properties, importance)
                VALUES (?, ?, ?, ?)
            """, (node_id, node_type, props_json, importance))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM kg_nodes WHERE node_id = ?", (node_id,))
            row = cursor.fetchone()
            if row:
                node = dict(row)
                if node['properties']:
                    try:
                        node['properties'] = json.loads(node['properties'])
                    except:
                        node['properties'] = {}
                return node
            return None
        finally:
            conn.close()
    
    def add_edge(self, from_node: str, to_node: str, relation: str, strength: float = 1.0,
                 properties: Dict = None) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            props_json = json.dumps(properties or {}, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO kg_edges (from_node, to_node, relation, strength, properties)
                VALUES (?, ?, ?, ?, ?)
            """, (from_node, to_node, relation, strength, props_json))
            edge_id = cursor.lastrowid
            conn.commit()
            return edge_id
        finally:
            conn.close()
    
    def get_edges(self, from_node: Optional[str] = None, to_node: Optional[str] = None,
                  relation: Optional[str] = None, min_strength: float = 0.0, limit: int = 1000) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM kg_edges WHERE strength >= ?"
            params = [min_strength]
            if from_node:
                query += " AND from_node = ?"
                params.append(from_node)
            if to_node:
                query += " AND to_node = ?"
                params.append(to_node)
            if relation:
                query += " AND relation = ?"
                params.append(relation)
            query += " ORDER BY strength DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            
            edges = []
            for row in cursor.fetchall():
                edge = dict(row)
                if edge['properties']:
                    try:
                        edge['properties'] = json.loads(edge['properties'])
                    except:
                        edge['properties'] = {}
                edges.append(edge)
            return edges
        finally:
            conn.close()
    
    def get_node_connections(self, node_id: str, direction: str = 'both') -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            result = {'outgoing': [], 'incoming': [], 'total': 0}
            
            if direction in ['out', 'both']:
                cursor.execute("""
                    SELECT e.*, n.properties as target_properties
                    FROM kg_edges e JOIN kg_nodes n ON e.to_node = n.node_id
                    WHERE e.from_node = ? ORDER BY e.strength DESC LIMIT 500
                """, (node_id,))
                for row in cursor.fetchall():
                    edge = dict(row)
                    if edge['properties']:
                        try:
                            edge['properties'] = json.loads(edge['properties'])
                        except:
                            edge['properties'] = {}
                    result['outgoing'].append(edge)
            
            if direction in ['in', 'both']:
                cursor.execute("""
                    SELECT e.*, n.properties as source_properties
                    FROM kg_edges e JOIN kg_nodes n ON e.from_node = n.node_id
                    WHERE e.to_node = ? ORDER BY e.strength DESC LIMIT 500
                """, (node_id,))
                for row in cursor.fetchall():
                    edge = dict(row)
                    if edge['properties']:
                        try:
                            edge['properties'] = json.loads(edge['properties'])
                        except:
                            edge['properties'] = {}
                    result['incoming'].append(edge)
            
            result['total'] = len(result['outgoing']) + len(result['incoming'])
            return result
        finally:
            conn.close()
    
    def get_node_count(self) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM kg_nodes")
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    def get_edge_count(self) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM kg_edges")
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    # ==================== THEMEN ====================
    
    def add_topic(self, topic_id: str, name: str, description: str = '', properties: Dict = None) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT topic_id FROM topics WHERE topic_id = ?", (topic_id,))
            if cursor.fetchone():
                return False
            props_json = json.dumps(properties or {}, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO topics (topic_id, name, description, properties)
                VALUES (?, ?, ?, ?)
            """, (topic_id, name, description, props_json))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def add_node_to_topic(self, topic_id: str, node_id: str, relevance: float = 1.0):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO topic_nodes (topic_id, node_id, relevance) VALUES (?, ?, ?)",
                          (topic_id, node_id, relevance))
            cursor.execute("""
                UPDATE topics SET node_count = (SELECT COUNT(*) FROM topic_nodes WHERE topic_id = ?),
                    updated_at = CURRENT_TIMESTAMP WHERE topic_id = ?
            """, (topic_id, topic_id))
            conn.commit()
        finally:
            conn.close()
    
    def get_topic_nodes(self, topic_id: str, min_relevance: float = 0.0) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT n.*, tn.relevance FROM kg_nodes n JOIN topic_nodes tn ON n.node_id = tn.node_id
                WHERE tn.topic_id = ? AND tn.relevance >= ? ORDER BY tn.relevance DESC
            """, (topic_id, min_relevance))
            nodes = []
            for row in cursor.fetchall():
                node = dict(row)
                if node['properties']:
                    try:
                        node['properties'] = json.loads(node['properties'])
                    except:
                        node['properties'] = {}
                nodes.append(node)
            return nodes
        finally:
            conn.close()
    
    def get_all_topics(self) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topics ORDER BY node_count DESC, name")
            topics = []
            for row in cursor.fetchall():
                topic = dict(row)
                if topic['properties']:
                    try:
                        topic['properties'] = json.loads(topic['properties'])
                    except:
                        topic['properties'] = {}
                topics.append(topic)
            return topics
        finally:
            conn.close()
    
    # ==================== EINFLÜSSE ====================
    
    def add_influence(self, influencer_id: str, influenced_id: str, topic_id: Optional[str] = None,
                      strength: float = 0.5, description: str = '') -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO influences (influencer_id, influenced_id, topic_id, strength, description)
                VALUES (?, ?, ?, ?, ?)
            """, (influencer_id, influenced_id, topic_id, strength, description))
            influence_id = cursor.lastrowid
            conn.commit()
            return influence_id
        finally:
            conn.close()
    
    def get_influences(self, agent_id: str) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, inf.properties as influencer_props, infd.properties as influenced_props
                FROM influences i
                LEFT JOIN kg_nodes inf ON i.influencer_id = inf.node_id
                LEFT JOIN kg_nodes infd ON i.influenced_id = infd.node_id
                WHERE i.influencer_id = ? OR i.influenced_id = ?
                ORDER BY i.timestamp DESC
            """, (agent_id, agent_id))
            
            given = []
            received = []
            for row in cursor.fetchall():
                infl = dict(row)
                if infl['influencer_id'] == agent_id:
                    given.append({'to': infl['influenced_id'], 'strength': infl['strength'], 'timestamp': infl['timestamp']})
                else:
                    received.append({'from': infl['influencer_id'], 'strength': infl['strength'], 'timestamp': infl['timestamp']})
            
            return {'given': given, 'received': received, 'given_count': len(given), 'received_count': len(received)}
        finally:
            conn.close()
    
    # ==================== PROGNOSEN ====================
    
    def add_prognosis(self, agent_id: str, topic: str, prediction: str, confidence: float = 0.5) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prognoses (agent_id, topic, prediction, confidence)
                VALUES (?, ?, ?, ?)
            """, (agent_id, topic, prediction, confidence))
            prognosis_id = cursor.lastrowid
            conn.commit()
            return prognosis_id
        finally:
            conn.close()
    
    def get_agent_prognoses(self, agent_id: str, limit: int = 100) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM prognoses WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
                          (agent_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_prognosis_stats(self, agent_id: Optional[str] = None) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if agent_id:
                cursor.execute("SELECT COUNT(*) FROM prognoses WHERE agent_id = ?", (agent_id,))
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM prognoses WHERE agent_id = ? AND verified = 1", (agent_id,))
                verified = cursor.fetchone()[0]
                if verified > 0:
                    cursor.execute("SELECT COUNT(*) FROM prognoses WHERE agent_id = ? AND verified = 1 AND correct = 1", (agent_id,))
                    correct = cursor.fetchone()[0]
                    accuracy = (correct / verified) * 100
                else:
                    correct = 0
                    accuracy = 0
            else:
                cursor.execute("SELECT COUNT(*) FROM prognoses")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM prognoses WHERE verified = 1")
                verified = cursor.fetchone()[0]
                if verified > 0:
                    cursor.execute("SELECT COUNT(*) FROM prognoses WHERE verified = 1 AND correct = 1")
                    correct = cursor.fetchone()[0]
                    accuracy = (correct / verified) * 100
                else:
                    correct = 0
                    accuracy = 0
            
            return {"total": total, "verified": verified, "correct": correct, "accuracy": accuracy, "pending": total - verified}
        finally:
            conn.close()
    
    # ==================== TEAMS ====================
    
    def add_team(self, team_id: str, name: str, description: str = '', properties: Dict = None,
                 leader_id: Optional[str] = None) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT team_id FROM teams WHERE team_id = ?", (team_id,))
            if cursor.fetchone():
                return False
            props_json = json.dumps(properties or {}, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO teams (team_id, name, description, properties, leader_id)
                VALUES (?, ?, ?, ?, ?)
            """, (team_id, name, description, props_json, leader_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def add_team_member(self, team_id: str, agent_id: str, role: str = 'Mitglied'):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO team_members (team_id, agent_id, role) VALUES (?, ?, ?)",
                          (team_id, agent_id, role))
            conn.commit()
        finally:
            conn.close()
    
    def get_team(self, team_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,))
            team_row = cursor.fetchone()
            if not team_row:
                return None
            
            team = dict(team_row)
            if team['properties']:
                try:
                    team['properties'] = json.loads(team['properties'])
                except:
                    team['properties'] = {}
            
            cursor.execute("""
                SELECT a.*, tm.role as team_role FROM agents a
                JOIN team_members tm ON a.agent_id = tm.agent_id
                WHERE tm.team_id = ? AND a.is_active = 1 ORDER BY a.name
            """, (team_id,))
            
            members = []
            for row in cursor.fetchall():
                member = dict(row)
                for field in ['skills', 'personality_traits', 'metadata']:
                    if member.get(field):
                        try:
                            member[field] = json.loads(member[field])
                        except:
                            member[field] = {}
                members.append(member)
            
            team['members'] = members
            team['member_count'] = len(members)
            return team
        finally:
            conn.close()
    
    def get_all_teams(self) -> List[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, COUNT(tm.agent_id) as member_count
                FROM teams t LEFT JOIN team_members tm ON t.team_id = tm.team_id
                GROUP BY t.team_id ORDER BY t.name
            """)
            teams = []
            for row in cursor.fetchall():
                team = dict(row)
                if team['properties']:
                    try:
                        team['properties'] = json.loads(team['properties'])
                    except:
                        team['properties'] = {}
                teams.append(team)
            return teams
        finally:
            conn.close()
    
    # ==================== DISKUSSIONEN ====================
    
    def start_discussion(self, discussion_id: str, topic: str, purpose: str = '', goal: str = '',
                         moderator_name: Optional[str] = None, metadata: Dict = None) -> bool:
        """
        Startet eine Diskussion.
        FIX: moderator_name statt moderator_id - sucht oder erstellt den Moderator.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Moderator-ID finden oder erstellen
            moderator_id = None
            if moderator_name:
                # Suche nach Moderator in agents Tabelle
                cursor.execute("SELECT agent_id FROM agents WHERE name = ? AND role LIKE '%Moderator%'", (moderator_name,))
                row = cursor.fetchone()
                if row:
                    moderator_id = row[0]
                else:
                    # Moderator als Agent anlegen, falls nicht existiert
                    import uuid
                    moderator_id = f"mod_{uuid.uuid4().hex[:8]}"
                    try:
                        cursor.execute("""
                            INSERT INTO agents (agent_id, name, role, personality, color, is_active)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (moderator_id, moderator_name, "Diskussionsmoderator", 
                              "Führt die Diskussion neutral und fair.", "#c586c0", 1))
                    except:
                        # Falls schon existiert, nochmal versuchen zu finden
                        cursor.execute("SELECT agent_id FROM agents WHERE name = ?", (moderator_name,))
                        row2 = cursor.fetchone()
                        if row2:
                            moderator_id = row2[0]
            
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO discussions (discussion_id, topic, purpose, goal, moderator_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (discussion_id, topic, purpose, goal, moderator_id, metadata_json))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ start_discussion Fehler: {e}")
            # Fallback: Diskussion ohne Moderator speichern
            try:
                metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
                cursor.execute("""
                    INSERT INTO discussions (discussion_id, topic, purpose, goal, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (discussion_id, topic, purpose, goal, metadata_json))
                conn.commit()
                return True
            except Exception as e2:
                print(f"❌ start_discussion Fallback fehlgeschlagen: {e2}")
                return False
        finally:
            conn.close()
    
    def end_discussion(self, discussion_id: str, summary: str = ''):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE discussions SET end_time = CURRENT_TIMESTAMP, summary = ? WHERE discussion_id = ?",
                          (summary, discussion_id))
            conn.commit()
        except Exception as e:
            print(f"⚠️ end_discussion Fehler: {e}")
        finally:
            conn.close()
    
    def add_contribution(self, discussion_id: str, agent_id: str, content: str, round_number: int = 0,
                         is_reaction: bool = False, reacts_to: Optional[int] = None,
                         sentiment: Optional[float] = None, metadata: Dict = None) -> Optional[int]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT agent_id FROM agents WHERE agent_id = ? AND is_active = 1", (agent_id,))
            if not cursor.fetchone():
                # Agent existiert nicht, erstelle temporären Eintrag
                try:
                    cursor.execute("""
                        INSERT INTO agents (agent_id, name, role, is_active)
                        VALUES (?, ?, ?, ?)
                    """, (agent_id, agent_id, "Unbekannt", 1))
                except:
                    pass
            
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO contributions (discussion_id, agent_id, round_number, content, is_reaction, reacts_to, sentiment, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (discussion_id, agent_id, round_number, content, 1 if is_reaction else 0, reacts_to, sentiment, metadata_json))
            
            contrib_id = cursor.lastrowid
            cursor.execute("""
                UPDATE discussions SET contribution_count = contribution_count + 1,
                    round_count = MAX(round_count, ?) WHERE discussion_id = ?
            """, (round_number + 1, discussion_id))
            conn.commit()
            return contrib_id
        except Exception as e:
            print(f"⚠️ add_contribution Fehler: {e}")
            return None
        finally:
            conn.close()
    
    # ==================== GEDÄCHTNIS ====================
    
    def create_memory_room(self, room_id: str, agent_id: str, name: str, size: float = 1.0,
                           color: str = '#4a90e2', properties: Dict = None) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT room_id FROM memory_rooms WHERE room_id = ?", (room_id,))
            if cursor.fetchone():
                return False
            props_json = json.dumps(properties or {}, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO memory_rooms (room_id, agent_id, name, size, color, properties)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (room_id, agent_id, name, size, color, props_json))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_memory_room(self, agent_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_rooms WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                room = dict(row)
                if room['properties']:
                    try:
                        room['properties'] = json.loads(room['properties'])
                    except:
                        room['properties'] = {}
                return room
            
            room_id = f"room_{agent_id}"
            self.create_memory_room(room_id, agent_id, f"{agent_id}s Gedächtnis", size=1.0, color='#4a90e2')
            
            cursor.execute("SELECT * FROM memory_rooms WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                room = dict(row)
                if room['properties']:
                    try:
                        room['properties'] = json.loads(room['properties'])
                    except:
                        room['properties'] = {}
                return room
            return None
        finally:
            conn.close()
    
    def add_memory_crystal(self, crystal_id: str, room_id: str, fact: str, topic: Optional[str] = None,
                           importance: float = 0.5, position: Tuple[float, float, float] = (0, 0, 0),
                           connections: List[str] = None, metadata: Dict = None) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.is_duplicate_fact(fact, topic):
                return False
            
            cursor.execute("SELECT crystal_id FROM memory_crystals WHERE crystal_id = ?", (crystal_id,))
            if cursor.fetchone():
                return False
            
            x, y, z = position
            conn_json = json.dumps(connections or [], ensure_ascii=False)
            meta_json = json.dumps(metadata or {}, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO memory_crystals (crystal_id, room_id, fact, topic, importance,
                    position_x, position_y, position_z, connections, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (crystal_id, room_id, fact, topic, importance, x, y, z, conn_json, meta_json))
            
            cursor.execute("UPDATE memory_rooms SET crystal_count = crystal_count + 1, updated_at = CURRENT_TIMESTAMP WHERE room_id = ?",
                          (room_id,))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_agent_memories(self, agent_id: str, limit: int = 1000) -> List[Dict]:
        room = self.get_memory_room(agent_id)
        if not room:
            return []
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM memory_crystals WHERE room_id = ?
                ORDER BY importance DESC, access_count DESC, accessed_at DESC LIMIT ?
            """, (room['room_id'], limit))
            
            crystals = []
            for row in cursor.fetchall():
                crystal = dict(row)
                if crystal['connections']:
                    try:
                        crystal['connections'] = json.loads(crystal['connections'])
                    except:
                        crystal['connections'] = []
                if crystal['metadata']:
                    try:
                        crystal['metadata'] = json.loads(crystal['metadata'])
                    except:
                        crystal['metadata'] = {}
                crystals.append(crystal)
            return crystals
        finally:
            conn.close()
    
    # ==================== SYSTEM ====================
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value, type FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return default
            
            value = row['value']
            value_type = row['type']
            
            if value_type == 'int':
                return int(value)
            elif value_type == 'float':
                return float(value)
            elif value_type == 'bool':
                return value.lower() == 'true'
            elif value_type == 'json':
                try:
                    return json.loads(value)
                except:
                    return {}
            return value
        finally:
            conn.close()
    
    def set_setting(self, key: str, value: Any, value_type: str = None, description: str = None):
        if value_type is None:
            if isinstance(value, bool):
                value_type = 'bool'
                value = str(value).lower()
            elif isinstance(value, int):
                value_type = 'int'
                value = str(value)
            elif isinstance(value, float):
                value_type = 'float'
                value = str(value)
            elif isinstance(value, (dict, list)):
                value_type = 'json'
                value = json.dumps(value, ensure_ascii=False)
            else:
                value_type = 'string'
                value = str(value)
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key FROM system_settings WHERE key = ?", (key,))
            if cursor.fetchone():
                cursor.execute("UPDATE system_settings SET value = ?, type = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                              (value, value_type, key))
            else:
                cursor.execute("INSERT INTO system_settings (key, value, type, description) VALUES (?, ?, ?, ?)",
                              (key, value, value_type, description or ""))
            conn.commit()
        finally:
            conn.close()
    
    def get_stats(self) -> Dict:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            stats = {}
            cursor.execute("SELECT COUNT(*) FROM agent_pool")
            stats['pool_size'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
            stats['active_agents'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM agents")
            stats['total_agents'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM kg_nodes")
            stats['kg_nodes'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM kg_edges")
            stats['kg_edges'] = cursor.fetchone()[0]
            cursor.execute("SELECT node_type, COUNT(*) FROM kg_nodes GROUP BY node_type")
            stats['node_types'] = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) FROM topics")
            stats['topics'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM teams")
            stats['teams'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM prognoses")
            stats['prognoses'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM discussions")
            stats['discussions'] = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(contribution_count) FROM discussions")
            stats['contributions'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT AVG(fachwissen) FROM agent_skills")
            stats['avg_fachwissen'] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT AVG(kommunikation) FROM agent_skills")
            stats['avg_kommunikation'] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT AVG(analyse) FROM agent_skills")
            stats['avg_analyse'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT rank, COUNT(*) FROM agent_evolution GROUP BY rank")
            stats['ranks'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            stats['db_version'] = self.get_setting('db_version', 'unknown')
            stats['kg_migrated'] = self.get_setting('kg_migrated', False)
            
            return stats
        finally:
            conn.close()
    
    def backup(self, backup_path: str = None) -> str:
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(Config.KNOWLEDGE_FOLDER, f"backup_{timestamp}.db")
        
        import shutil
        shutil.copy2(self.db_path, backup_path)
        self.set_setting('last_backup', backup_path)
        return backup_path