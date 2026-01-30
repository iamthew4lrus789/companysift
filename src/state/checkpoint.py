"""
Checkpoint management system for state persistence.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, List, Any


class CheckpointManager:
    """
    Manage processing checkpoints using SQLite database.
    
    This module provides functionality to track processing progress,
    resume from interruptions, and restart from scratch.
    """
    
    def __init__(self, db_file: str, batch_size: int = 50, table_name: str = "checkpoints"):
        """
        Initialize the checkpoint manager.
        
        Args:
            db_file: Path to SQLite database file
            batch_size: Number of companies per batch
            table_name: Name of the checkpoints table
            
        Raises:
            Exception: If database cannot be initialized
        """
        self.db_file = db_file
        self.batch_size = batch_size
        self.table_name = table_name
        
        # Initialize database
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database schema."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Create checkpoints table if it doesn't exist
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_number INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    companies_processed INTEGER NOT NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            raise Exception(f"Failed to initialize database: {e}")

    def create_checkpoint(self, batch_number: int, companies_processed: int, 
                         status: str = "completed") -> bool:
        """
        Create a new checkpoint.
        
        Args:
            batch_number: Batch number being completed
            companies_processed: Total companies processed so far
            status: Checkpoint status (completed/failed)
            
        Returns:
            True if checkpoint was created successfully
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Insert new checkpoint
            cursor.execute(f'''
                INSERT INTO {self.table_name} 
                (batch_number, completed_at, status, companies_processed)
                VALUES (?, ?, ?, ?)
            ''', (batch_number, datetime.now().isoformat(), status, companies_processed))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.Error as e:
            print(f"Error creating checkpoint: {e}")
            return False

    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest checkpoint.
        
        Returns:
            Dictionary with checkpoint data, or None if no checkpoints exist
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Get the checkpoint with highest batch number
            cursor.execute(f'''
                SELECT batch_number, completed_at, status, companies_processed
                FROM {self.table_name}
                ORDER BY batch_number DESC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "batch_number": result[0],
                    "completed_at": result[1],
                    "status": result[2],
                    "companies_processed": result[3]
                }
            else:
                return None
                
        except sqlite3.Error as e:
            print(f"Error getting latest checkpoint: {e}")
            return None

    def get_all_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Get all checkpoints.
        
        Returns:
            List of checkpoint dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute(f'''
                SELECT batch_number, completed_at, status, companies_processed
                FROM {self.table_name}
                ORDER BY batch_number ASC
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "batch_number": row[0],
                    "completed_at": row[1],
                    "status": row[2],
                    "companies_processed": row[3]
                }
                for row in results
            ]
            
        except sqlite3.Error as e:
            print(f"Error getting all checkpoints: {e}")
            return []

    def get_resume_position(self) -> tuple[int, int]:
        """
        Get the position to resume processing from.
        
        Returns:
            Tuple of (next_batch_number, total_companies_processed)
        """
        latest = self.get_latest_checkpoint()
        
        if latest:
            next_batch = latest["batch_number"] + 1
            total_processed = latest["companies_processed"]
            return next_batch, total_processed
        else:
            return 1, 0

    def restart_from_scratch(self) -> bool:
        """
        Clear all checkpoints and restart from scratch.
        
        Returns:
            True if checkpoints were cleared successfully
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Delete all checkpoints
            cursor.execute(f"DELETE FROM {self.table_name}")
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.Error as e:
            print(f"Error restarting from scratch: {e}")
            return False

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Get total checkpoints
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            total_checkpoints = cursor.fetchone()[0]
            
            # Get completed checkpoints
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name} WHERE status = 'completed'")
            completed_checkpoints = cursor.fetchone()[0]
            
            # Get failed checkpoints
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name} WHERE status = 'failed'")
            failed_checkpoints = cursor.fetchone()[0]
            
            # Get total companies processed
            cursor.execute(f"SELECT MAX(companies_processed) FROM {self.table_name}")
            total_processed = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                "total_checkpoints": total_checkpoints,
                "completed_checkpoints": completed_checkpoints,
                "failed_checkpoints": failed_checkpoints,
                "total_companies_processed": total_processed,
                "completion_rate": completed_checkpoints / total_checkpoints * 100 if total_checkpoints > 0 else 0
            }
            
        except sqlite3.Error as e:
            print(f"Error getting processing stats: {e}")
            return {
                "total_checkpoints": 0,
                "completed_checkpoints": 0,
                "failed_checkpoints": 0,
                "total_companies_processed": 0,
                "completion_rate": 0
            }