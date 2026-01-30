import pytest
import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock

from src.state.checkpoint import CheckpointManager
from src.core.models import Company


class TestCheckpointManager:
    """Test suite for checkpoint management system."""

    def setup_method(self):
        """Setup test database."""
        # Create temporary database
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        
        # Initialize checkpoint manager
        self.checkpoint = CheckpointManager(self.db_file.name)

    def teardown_method(self):
        """Cleanup test database."""
        try:
            os.unlink(self.db_file.name)
        except:
            pass

    def test_checkpoint_initialization(self):
        """Test checkpoint manager initialization."""
        assert self.checkpoint.db_file == self.db_file.name
        assert self.checkpoint.batch_size == 50
        assert self.checkpoint.table_name == "checkpoints"

    def test_database_schema_creation(self):
        """Test that database schema is created correctly."""
        # Connect to database and check schema
        conn = sqlite3.connect(self.db_file.name)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "checkpoints"
        
        # Check table schema
        cursor.execute("PRAGMA table_info(checkpoints)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = ['id', 'batch_number', 'completed_at', 'status', 'companies_processed']
        for col in expected_columns:
            assert col in column_names
            
        conn.close()

    def test_checkpoint_creation(self):
        """Test creating a new checkpoint."""
        # Create checkpoint
        result = self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        
        assert result is True
        
        # Verify in database
        conn = sqlite3.connect(self.db_file.name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM checkpoints WHERE batch_number = 1")
        checkpoint = cursor.fetchone()
        
        assert checkpoint is not None
        assert checkpoint[1] == 1  # batch_number
        assert checkpoint[4] == 50  # companies_processed
        assert checkpoint[3] == "completed"  # status
        
        conn.close()

    def test_checkpoint_retrieval(self):
        """Test retrieving checkpoints."""
        # Create multiple checkpoints
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        self.checkpoint.create_checkpoint(batch_number=2, companies_processed=100)
        self.checkpoint.create_checkpoint(batch_number=3, companies_processed=150)

        # Get latest checkpoint
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is not None
        assert latest["batch_number"] == 3
        assert latest["companies_processed"] == 150
        
        # Get all checkpoints
        all_checkpoints = self.checkpoint.get_all_checkpoints()
        assert len(all_checkpoints) == 3
        assert all_checkpoints[0]["batch_number"] == 1
        assert all_checkpoints[2]["batch_number"] == 3

    def test_resume_from_checkpoint(self):
        """Test resuming from last checkpoint."""
        # Create checkpoints
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        self.checkpoint.create_checkpoint(batch_number=2, companies_processed=100)

        # Get resume position
        resume_batch, resume_count = self.checkpoint.get_resume_position()
        
        assert resume_batch == 3  # Next batch after 2
        assert resume_count == 100  # Total processed so far

    def test_restart_from_scratch(self):
        """Test restarting from scratch."""
        # Create checkpoints
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        self.checkpoint.create_checkpoint(batch_number=2, companies_processed=100)

        # Restart from scratch
        self.checkpoint.restart_from_scratch()
        
        # Check that checkpoints are cleared
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is None
        
        # Resume position should be 1, 0
        resume_batch, resume_count = self.checkpoint.get_resume_position()
        assert resume_batch == 1
        assert resume_count == 0

    def test_batch_processing_tracking(self):
        """Test tracking batch processing."""
        # Simulate processing batches
        companies = []
        for i in range(150):
            companies.append(Company(
                company_number=str(i),
                company_name=f"Company {i}",
                postcode=f"SW1 {i}"
            ))

        # Process in batches
        batch_size = 50
        for batch_num in range(1, 4):  # 3 batches for 150 companies
            start_idx = (batch_num - 1) * batch_size
            end_idx = min(batch_num * batch_size, len(companies))
            batch_companies = companies[start_idx:end_idx]
            
            # Create checkpoint
            self.checkpoint.create_checkpoint(
                batch_number=batch_num,
                companies_processed=end_idx
            )

        # Verify final state
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is not None
        assert latest["batch_number"] == 3
        assert latest["companies_processed"] == 150
        
        # Verify resume position
        resume_batch, resume_count = self.checkpoint.get_resume_position()
        assert resume_batch == 4
        assert resume_count == 150

    def test_checkpoint_with_custom_batch_size(self):
        """Test checkpoint with custom batch size."""
        checkpoint = CheckpointManager(self.db_file.name, batch_size=25)
        
        assert checkpoint.batch_size == 25
        
        # Create checkpoint
        checkpoint.create_checkpoint(batch_number=1, companies_processed=25)
        
        # Resume position should be batch 2
        resume_batch, resume_count = checkpoint.get_resume_position()
        assert resume_batch == 2
        assert resume_count == 25

    def test_error_handling(self):
        """Test error handling."""
        # Test with invalid database file
        with pytest.raises(Exception):
            invalid_checkpoint = CheckpointManager("/invalid/path/database.db")

    def test_checkpoint_status(self):
        """Test checkpoint status tracking."""
        # Create checkpoint with different statuses
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50, status="completed")
        self.checkpoint.create_checkpoint(batch_number=2, companies_processed=100, status="failed")
        self.checkpoint.create_checkpoint(batch_number=3, companies_processed=150, status="completed")

        # Get all checkpoints
        all_checkpoints = self.checkpoint.get_all_checkpoints()
        
        assert len(all_checkpoints) == 3
        assert all_checkpoints[0]["status"] == "completed"
        assert all_checkpoints[1]["status"] == "failed"
        assert all_checkpoints[2]["status"] == "completed"

    def test_checkpoint_timestamps(self):
        """Test checkpoint timestamps."""
        # Create checkpoint
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        
        # Get checkpoint
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is not None
        
        # Check that timestamp is set
        assert "completed_at" in latest
        assert latest["completed_at"] is not None
        
        # Should be a valid datetime
        completed_at = datetime.fromisoformat(latest["completed_at"])
        assert isinstance(completed_at, datetime)

    def test_database_concurrency(self):
        """Test database concurrency handling."""
        # Create multiple checkpoint managers pointing to same database
        checkpoint2 = CheckpointManager(self.db_file.name)
        
        # Both should be able to read/write
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        checkpoint2.create_checkpoint(batch_number=2, companies_processed=100)
        
        # Both should see same data
        latest1 = self.checkpoint.get_latest_checkpoint()
        latest2 = checkpoint2.get_latest_checkpoint()
        assert latest1 is not None
        assert latest2 is not None
        
        assert latest1["batch_number"] == latest2["batch_number"]
        assert latest1["companies_processed"] == latest2["companies_processed"]

    def test_large_batch_numbers(self):
        """Test with large batch numbers."""
        # Create checkpoint with large batch number
        self.checkpoint.create_checkpoint(batch_number=1000, companies_processed=50000)
        
        # Should handle correctly
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is not None
        assert latest["batch_number"] == 1000
        assert latest["companies_processed"] == 50000
        
        # Resume position
        resume_batch, resume_count = self.checkpoint.get_resume_position()
        assert resume_batch == 1001
        assert resume_count == 50000