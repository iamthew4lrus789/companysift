import pytest
import tempfile
import os
from src.state.checkpoint import CheckpointManager
from src.csv_processor.reader import CSVReader
from src.core.models import Company


class TestStateManagementIntegration:
    """Integration tests for state management system."""

    def setup_method(self):
        """Setup test database."""
        # Create temporary database
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        
        # Initialize checkpoint manager
        self.checkpoint = CheckpointManager(self.db_file.name, batch_size=50)

    def teardown_method(self):
        """Cleanup test database."""
        try:
            os.unlink(self.db_file.name)
        except:
            pass

    def test_end_to_end_checkpoint_workflow(self):
        """Test complete checkpoint workflow with real company data."""
        # Load real company data
        reader = CSVReader('companies_20251231_085147.csv')
        companies = list(reader.read_companies())
        
        if not companies:
            pytest.skip("No companies found in sample file")
            
        # Simulate batch processing
        batch_size = 50
        total_companies = len(companies)
        batches_processed = 0
        
        for batch_num in range(1, (total_companies // batch_size) + 2):
            start_idx = (batch_num - 1) * batch_size
            end_idx = min(batch_num * batch_size, total_companies)
            
            if start_idx >= total_companies:
                break
                
            batch_companies = companies[start_idx:end_idx]
            companies_processed = end_idx
            
            # Create checkpoint
            result = self.checkpoint.create_checkpoint(
                batch_number=batch_num,
                companies_processed=companies_processed
            )
            
            assert result is True
            batches_processed += 1
            
            # Verify checkpoint was created
            latest = self.checkpoint.get_latest_checkpoint()
            assert latest is not None
            assert latest["batch_number"] == batch_num
            assert latest["companies_processed"] == companies_processed

        # Verify final state
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is not None
        assert latest["batch_number"] == batches_processed
        assert latest["companies_processed"] >= min(total_companies, batch_size * batches_processed)
        
        # Verify resume position
        resume_batch, resume_count = self.checkpoint.get_resume_position()
        assert resume_batch == batches_processed + 1
        assert resume_count == latest["companies_processed"]

    def test_interruption_and_resume(self):
        """Test handling interruptions and resuming processing."""
        # Load company data
        reader = CSVReader('companies_20251231_085147.csv')
        companies = list(reader.read_companies())
        
        if len(companies) < 100:
            pytest.skip("Not enough companies for interruption test")
            
        # Process first batch
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        
        # Simulate interruption - create new checkpoint manager (as if program restarted)
        checkpoint2 = CheckpointManager(self.db_file.name, batch_size=50)
        
        # Should resume from where we left off
        resume_batch, resume_count = checkpoint2.get_resume_position()
        assert resume_batch == 2
        assert resume_count == 50
        
        # Process second batch
        checkpoint2.create_checkpoint(batch_number=2, companies_processed=100)
        
        # Verify both checkpoints exist
        all_checkpoints = checkpoint2.get_all_checkpoints()
        assert len(all_checkpoints) == 2
        assert all_checkpoints[0]["batch_number"] == 1
        assert all_checkpoints[1]["batch_number"] == 2

    def test_restart_functionality(self):
        """Test restarting processing from scratch."""
        # Process some batches
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50)
        self.checkpoint.create_checkpoint(batch_number=2, companies_processed=100)
        
        # Verify checkpoints exist
        all_checkpoints = self.checkpoint.get_all_checkpoints()
        assert len(all_checkpoints) == 2
        
        # Restart from scratch
        self.checkpoint.restart_from_scratch()
        
        # Verify checkpoints are cleared
        all_checkpoints = self.checkpoint.get_all_checkpoints()
        assert len(all_checkpoints) == 0
        
        # Should start from beginning
        resume_batch, resume_count = self.checkpoint.get_resume_position()
        assert resume_batch == 1
        assert resume_count == 0

    def test_processing_statistics(self):
        """Test processing statistics tracking."""
        # Create mix of completed and failed checkpoints
        self.checkpoint.create_checkpoint(batch_number=1, companies_processed=50, status="completed")
        self.checkpoint.create_checkpoint(batch_number=2, companies_processed=100, status="failed")
        self.checkpoint.create_checkpoint(batch_number=3, companies_processed=150, status="completed")
        self.checkpoint.create_checkpoint(batch_number=4, companies_processed=200, status="completed")

        # Get statistics
        stats = self.checkpoint.get_processing_stats()
        
        assert stats["total_checkpoints"] == 4
        assert stats["completed_checkpoints"] == 3
        assert stats["failed_checkpoints"] == 1
        assert stats["total_companies_processed"] == 200
        assert stats["completion_rate"] == 75.0

    def test_large_scale_processing(self):
        """Test checkpoint system with large-scale processing simulation."""
        # Simulate processing many batches
        total_batches = 100
        batch_size = 50
        
        for batch_num in range(1, total_batches + 1):
            companies_processed = batch_num * batch_size
            self.checkpoint.create_checkpoint(
                batch_number=batch_num,
                companies_processed=companies_processed
            )

        # Verify final state
        latest = self.checkpoint.get_latest_checkpoint()
        assert latest is not None
        assert latest["batch_number"] == total_batches
        assert latest["companies_processed"] == total_batches * batch_size
        
        # Verify all checkpoints are stored
        all_checkpoints = self.checkpoint.get_all_checkpoints()
        assert len(all_checkpoints) == total_batches
        
        # Verify statistics
        stats = self.checkpoint.get_processing_stats()
        assert stats["total_checkpoints"] == total_batches
        assert stats["total_companies_processed"] == total_batches * batch_size

    def test_checkpoint_with_real_company_data(self):
        """Test checkpoint system with real company data from sample file."""
        # Load real company data
        reader = CSVReader('companies_20251231_085147.csv')
        companies = list(reader.read_companies())
        
        if not companies:
            pytest.skip("No companies found in sample file")
            
        # Process companies in batches
        batch_size = 25
        processed_companies = 0
        
        for batch_num in range(1, 4):  # Process 3 batches
            start_idx = (batch_num - 1) * batch_size
            end_idx = min(batch_num * batch_size, len(companies))
            
            if start_idx >= len(companies):
                break
                
            batch_companies = companies[start_idx:end_idx]
            processed_companies = end_idx
            
            # Create checkpoint with company-specific data
            self.checkpoint.create_checkpoint(
                batch_number=batch_num,
                companies_processed=processed_companies
            )
            
            # Verify checkpoint includes correct company count
            latest = self.checkpoint.get_latest_checkpoint()
            assert latest is not None
            assert latest["companies_processed"] == processed_companies
        
        # Final verification
        final_checkpoint = self.checkpoint.get_latest_checkpoint()
        assert final_checkpoint is not None
        assert final_checkpoint["batch_number"] >= 1
        assert final_checkpoint["companies_processed"] > 0
        assert final_checkpoint["status"] == "completed"