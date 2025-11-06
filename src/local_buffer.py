"""
Local Buffer
SQLite-based local storage for offline operation
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any


class LocalBuffer:
    """Local SQLite buffer for telemetry data"""
    
    def __init__(self, db_path: str, max_size_mb: int = 500):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        self.max_size_mb = max_size_mb
        
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    sent INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sent 
                ON telemetry(sent, created_at)
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Local buffer initialized at {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise
    
    def store(self, data: Dict[str, Any]) -> bool:
        """Store telemetry data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO telemetry (timestamp, data)
                VALUES (?, ?)
            ''', (data.get('timestamp'), json.dumps(data)))
            
            conn.commit()
            conn.close()
            
            # Check and cleanup if needed
            self._cleanup_old_data()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store data: {e}")
            return False
    
    def get_unsent(self, limit: int = 100) -> List[Dict]:
        """Get unsent records"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, timestamp, data
                FROM telemetry
                WHERE sent = 0
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))
            
            records = []
            for row in cursor.fetchall():
                records.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'data': json.loads(row[2])
                })
            
            conn.close()
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve unsent data: {e}")
            return []
    
    def mark_sent(self, record_id: int) -> bool:
        """Mark record as sent"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE telemetry
                SET sent = 1
                WHERE id = ?
            ''', (record_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark record as sent: {e}")
            return False
    
    def _cleanup_old_data(self):
        """Remove old data to prevent database from growing too large"""
        try:
            # Remove data older than 7 days that has been sent
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM telemetry
                WHERE sent = 1 AND created_at < ?
            ''', (cutoff,))
            
            deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} old records")
                
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
    
    def get_stats(self) -> Dict:
        """Get buffer statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM telemetry WHERE sent = 0')
            unsent = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM telemetry WHERE sent = 1')
            sent = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'unsent_count': unsent,
                'sent_count': sent,
                'total_count': unsent + sent
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {'unsent_count': 0, 'sent_count': 0, 'total_count': 0}
    
    def close(self):
        """Close database connection"""
        # SQLite connections are closed after each operation
        self.logger.info("Local buffer closed")