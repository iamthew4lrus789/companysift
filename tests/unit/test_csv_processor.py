"""Unit tests for CSV processor module."""

import pytest
import tempfile
import pandas as pd
import os
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.models import Company
from src.csv_processor.reader import CSVReader, CSVValidationError
from src.csv_processor.writer import CSVWriter


class TestCSVReader:
    """Test cases for CSV reader functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.valid_csv_content = """CompanyNumber,CompanyName,Postcode,SICCodes
12345678,ACME Corporation,SW1A 1AA,70100
87654321,Global Enterprises,EC1A 1BB,62020
11223344,Tech Solutions Ltd,M1 1CC,62030"""
        
        self.csv_with_extra_columns = """CompanyNumber,CompanyName,Postcode,SICCodes,ExtraField1,ExtraField2
12345678,ACME Corporation,SW1A 1AA,70100,Value1,Value2
87654321,Global Enterprises,EC1A 1BB,62020,Value3,Value4"""
        
        self.csv_missing_optional_fields = """CompanyNumber,CompanyName,Postcode
12345678,ACME Corporation,SW1A 1AA
87654321,Global Enterprises,EC1A 1BB"""
        
        self.csv_with_malformed_rows = """CompanyNumber,CompanyName,Postcode,SICCodes
12345678,ACME Corporation,SW1A 1AA,70100
,Malformed Company,,invalid
87654321,Global Enterprises,EC1A 1BB,62020"""
    
    def test_read_valid_csv(self):
        """Test reading a valid CSV file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.valid_csv_content)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            companies = list(reader.read_companies())
            
            assert len(companies) == 3
            
            # Check first company
            assert companies[0].company_number == "12345678"
            assert companies[0].company_name == "ACME Corporation"
            assert companies[0].postcode == "SW1A 1AA"
            assert companies[0].sic_codes == "70100"
            
            # Check second company
            assert companies[1].company_number == "87654321"
            assert companies[1].company_name == "Global Enterprises"
            assert companies[1].postcode == "EC1A 1BB"
            assert companies[1].sic_codes == "62020"
            
        finally:
            Path(temp_path).unlink()
    
    def test_read_csv_with_extra_columns(self):
        """Test reading CSV with extra columns that should be preserved."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.csv_with_extra_columns)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            companies = list(reader.read_companies())
            
            assert len(companies) == 2
            assert companies[0].extra_data is not None
            assert companies[0].extra_data['ExtraField1'] == 'Value1'
            assert companies[0].extra_data['ExtraField2'] == 'Value2'
            
        finally:
            Path(temp_path).unlink()
    
    def test_read_csv_missing_optional_fields(self):
        """Test reading CSV with missing optional fields (SICCodes)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.csv_missing_optional_fields)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            companies = list(reader.read_companies())
            
            assert len(companies) == 2
            assert companies[0].sic_codes is None
            assert companies[1].sic_codes is None
            
        finally:
            Path(temp_path).unlink()
    
    def test_csv_validation_missing_required_columns(self):
        """Test validation fails when required columns are missing."""
        invalid_csv = """CompanyName,Postcode
ACME Corporation,SW1A 1AA
Global Enterprises,EC1A 1BB"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(invalid_csv)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            with pytest.raises(CSVValidationError) as exc_info:
                list(reader.read_companies())
            
            assert "Missing required columns" in str(exc_info.value)
            assert "CompanyNumber" in str(exc_info.value)
            
        finally:
            Path(temp_path).unlink()
    
    def test_csv_validation_empty_file(self):
        """Test validation fails for empty CSV files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("CompanyNumber,CompanyName,Postcode\n")
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            companies = list(reader.read_companies())
            assert len(companies) == 0
            
        finally:
            Path(temp_path).unlink()
    
    def test_csv_with_malformed_rows(self):
        """Test handling of malformed CSV rows with logging."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.csv_with_malformed_rows)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            
            # Capture log messages
            with patch('src.csv_processor.reader.logger') as mock_logger:
                companies = list(reader.read_companies())
                
                # Should skip malformed row and log warning
                assert len(companies) == 2
                assert mock_logger.warning.called
                
                # Check that warning was logged for missing company number
                warning_calls = [call for call in mock_logger.warning.call_args_list 
                               if 'Missing company number' in str(call[0])]
                assert len(warning_calls) > 0
                
        finally:
            Path(temp_path).unlink()
    
    def test_csv_case_insensitive_columns(self):
        """Test that CSV reader handles case-insensitive column names."""
        csv_with_different_case = """companynumber,companyname,postcode,siccodes
12345678,ACME Corporation,SW1A 1AA,70100
87654321,Global Enterprises,EC1A 1BB,62020"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_with_different_case)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            companies = list(reader.read_companies())
            
            assert len(companies) == 2
            assert companies[0].company_number == "12345678"
            assert companies[0].company_name == "ACME Corporation"
            
        finally:
            Path(temp_path).unlink()
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent CSV file."""
        with pytest.raises(FileNotFoundError):
            reader = CSVReader("nonexistent_file.csv")
            list(reader.read_companies())
    
    def test_get_total_rows(self):
        """Test getting total number of rows in CSV."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.valid_csv_content)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            total_rows = reader.get_total_rows()
            
            # Should be 3 (excluding header)
            assert total_rows == 3
            
        finally:
            Path(temp_path).unlink()
    
    def test_progress_callback(self):
        """Test progress callback during CSV reading."""
        progress_calls = []
        
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.valid_csv_content)
            temp_path = f.name
        
        try:
            reader = CSVReader(temp_path)
            companies = list(reader.read_companies(progress_callback=progress_callback))
            
            # Should have been called for each company
            assert len(progress_calls) == 3
            assert progress_calls[0] == (1, 3)
            assert progress_calls[1] == (2, 3)
            assert progress_calls[2] == (3, 3)
            
        finally:
            Path(temp_path).unlink()


class TestCSVWriter:
    """Test cases for CSV writer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_companies = [
            Company(
                company_number="12345678",
                company_name="ACME Corporation",
                postcode="SW1A 1AA",
                sic_codes="70100"
            ),
            Company(
                company_number="87654321",
                company_name="Global Enterprises",
                postcode="EC1A 1BB",
                sic_codes="62020"
            )
        ]
        
        self.sample_results = [
            # Mock ScoredResult objects with all required attributes
            Mock(
                company=self.sample_companies[0],
                search_result=Mock(url="https://acme.com", title="ACME Corp", snippet="Official website", position=1),
                confidence_score=85.5,
                scoring_details={'domain_match': 90.0, 'tld_relevance': 80.0, 'search_position': 85.0, 'title_match': 75.0},
                error_flag=False,
                error_message=None
            ),
            Mock(
                company=self.sample_companies[1],
                search_result=Mock(url="https://globalenterprises.co.uk", title="Global Enterprises", snippet="Company website", position=2),
                confidence_score=72.3,
                scoring_details={'domain_match': 75.0, 'tld_relevance': 85.0, 'search_position': 70.0, 'title_match': 65.0},
                error_flag=False,
                error_message=None
            )
        ]
    
    def test_write_results_to_csv(self):
        """Test writing results to CSV file."""
        import tempfile
        import os
        
        # Use a temporary directory instead of creating a file first
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, 'test_output.csv')
            
            writer = CSVWriter(temp_path)
            writer.write_results(self.sample_results)
            
            # Read back the CSV and verify contents
            df = pd.read_csv(temp_path)
            
            assert len(df) == 2
            assert 'CompanyNumber' in df.columns
            assert 'CompanyName' in df.columns
            assert 'Postcode' in df.columns
            assert 'SICCodes' in df.columns
            assert 'DiscoveredURL' in df.columns
            assert 'ConfidenceScore' in df.columns
            assert 'SearchPosition' in df.columns
            assert 'ErrorFlag' in df.columns
            
            # Check first row
            assert str(df.iloc[0]['CompanyNumber']) == "12345678"
            assert df.iloc[0]['CompanyName'] == "ACME Corporation"
            assert df.iloc[0]['DiscoveredURL'] == "https://acme.com"
            assert df.iloc[0]['ConfidenceScore'] == 85.5
            assert df.iloc[0]['SearchPosition'] == 1
            assert df.iloc[0]['ErrorFlag'] == False
    
    def test_write_results_with_errors(self):
        """Test writing results that include error records."""
        error_result = Mock(
            company=self.sample_companies[0],
            search_result=None,
            confidence_score=0.0,
            scoring_details={'domain_match': 0.0, 'tld_relevance': 0.0, 'search_position': 0.0, 'title_match': 0.0},
            error_flag=True,
            error_message="API timeout"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, 'test_error_output.csv')
            
            writer = CSVWriter(temp_path)
            writer.write_results([error_result])
            
            # Read back the CSV and verify error handling
            df = pd.read_csv(temp_path)
            
            assert len(df) == 1
            assert df.iloc[0]['ErrorFlag'] == True
            assert df.iloc[0]['ErrorMessage'] == "API timeout"
            assert pd.isna(df.iloc[0]['DiscoveredURL'])
            assert df.iloc[0]['ConfidenceScore'] == 0.0
    
    def test_write_multiple_results_per_company(self):
        """Test writing multiple results for the same company."""
        multiple_results = [
            Mock(
                company=self.sample_companies[0],
                search_result=Mock(url="https://acme.com", title="ACME Corp", snippet="Main site", position=1),
                confidence_score=85.5,
                scoring_details={'domain_match': 90.0, 'tld_relevance': 80.0, 'search_position': 85.0, 'title_match': 75.0},
                error_flag=False,
                error_message=None
            ),
            Mock(
                company=self.sample_companies[0],
                search_result=Mock(url="https://acme.co.uk", title="ACME UK", snippet="UK site", position=3),
                confidence_score=65.2,
                scoring_details={'domain_match': 70.0, 'tld_relevance': 60.0, 'search_position': 65.0, 'title_match': 55.0},
                error_flag=False,
                error_message=None
            )
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, 'test_multiple_output.csv')
            
            writer = CSVWriter(temp_path)
            writer.write_results(multiple_results)
            
            # Read back the CSV
            df = pd.read_csv(temp_path)
            
            assert len(df) == 2
            assert all(str(val) == "12345678" for val in df['CompanyNumber'])
            assert df.iloc[0]['DiscoveredURL'] == "https://acme.com"
            assert df.iloc[1]['DiscoveredURL'] == "https://acme.co.uk"
            assert df.iloc[0]['ConfidenceScore'] == 85.5
            assert df.iloc[1]['ConfidenceScore'] == 65.2
    
    def test_append_to_existing_file(self):
        """Test appending results to existing CSV file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, 'test_append_output.csv')
            
            # Write first batch
            writer = CSVWriter(temp_path)
            writer.write_results([self.sample_results[0]])
            
            # Write second batch (append)
            writer.write_results([self.sample_results[1]])
            
            # Read back the CSV
            df = pd.read_csv(temp_path)
            
            assert len(df) == 2
            assert str(df.iloc[0]['CompanyNumber']) == "12345678"
            assert str(df.iloc[1]['CompanyNumber']) == "87654321"