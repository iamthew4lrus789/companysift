"""CSV reader module for Company Website Discovery Tool."""

import logging
import pandas as pd
from pathlib import Path
from typing import Iterator, Optional, Callable, Dict, Any

from src.core.models import Company


logger = logging.getLogger(__name__)


class CSVValidationError(Exception):
    """Raised when CSV validation fails."""
    pass


class CSVReader:
    """CSV reader for company data with validation and error handling."""
    
    def __init__(self, file_path: str):
        """Initialize CSV reader.
        
        Args:
            file_path: Path to the CSV file
            
        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        self._required_columns = {'companynumber', 'companyname', 'postcode'}
        self._column_mapping = {
            'companynumber': ['CompanyNumber', 'company_number'],
            'companyname': ['CompanyName', 'company_name'],
            'postcode': ['Postcode', 'postcode'],
            'siccodes': ['SICCodes', 'sic_codes']
        }
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to lowercase and map variations.
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            DataFrame with normalized column names
        """
        df_copy = df.copy()
        column_mapping = {}
        
        # Create mapping from actual columns to normalized names
        for normalized_name, variations in self._column_mapping.items():
            for col in df_copy.columns:
                col_lower = col.lower().strip()
                for variation in variations:
                    if col_lower == variation.lower():
                        column_mapping[col] = normalized_name
                        break
        
        # Rename columns
        df_copy = df_copy.rename(columns=column_mapping)
        
        return df_copy
    
    def _validate_csv(self, df: pd.DataFrame) -> None:
        """Validate CSV structure and required columns.
        
        Args:
            df: DataFrame to validate
            
        Raises:
            CSVValidationError: If validation fails
        """
        if df.empty:
            logger.warning("CSV file is empty")
            return
        
        # Convert columns to lowercase for case-insensitive comparison
        normalized_columns = {col.lower() for col in df.columns}
        
        # Check for required columns
        missing_columns = []
        for required in self._required_columns:
            if required not in normalized_columns:
                # Try to find a matching column using original names for error message
                found = False
                for variations in self._column_mapping[required]:
                    if variations.lower() in normalized_columns:
                        found = True
                        break
                if not found:
                    # Use the capitalized version for error message
                    missing_columns.append(self._column_mapping[required][0])
        
        if missing_columns:
            raise CSVValidationError(f"Missing required columns: {missing_columns}")
    
    def _validate_row(self, row: pd.Series, row_index: int) -> Optional[Dict[str, Any]]:
        """Validate a single row and return data or None if invalid.
        
        Args:
            row: DataFrame row
            row_index: Row index for logging
            
        Returns:
            Dictionary with row data or None if invalid
        """
        try:
            # Check for required fields, handling NaN values
            company_number = str(row.get('companynumber', '')).strip() if pd.notna(row.get('companynumber')) else ''
            company_name = str(row.get('companyname', '')).strip() if pd.notna(row.get('companyname')) else ''
            postcode = str(row.get('postcode', '')).strip() if pd.notna(row.get('postcode')) else ''
            
            # Validate required fields
            if not company_number:
                logger.warning(f"Row {row_index + 2}: Missing company number, skipping")
                return None
            if not company_name:
                logger.warning(f"Row {row_index + 2}: Missing company name, skipping")
                return None
            if not postcode:
                logger.warning(f"Row {row_index + 2}: Missing postcode, skipping")
                return None
            
            # Create valid row data
            row_data = {
                'companynumber': company_number,
                'companyname': company_name,
                'postcode': postcode,
                'siccodes': row.get('siccodes', None)
            }
            
            # Add any extra columns
            for col in row.index:
                if col not in row_data and not col.startswith('unnamed'):
                    row_data[col] = str(row[col]) if pd.notna(row[col]) else ''
            
            return row_data
            
        except Exception as e:
            logger.warning(f"Row {row_index + 2}: Error validating row: {e}, skipping")
            return None
    
    def read_companies(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> Iterator[Company]:
        """Read companies from CSV file with validation and error handling.
        
        Args:
            progress_callback: Optional callback function(current, total) for progress updates
            
        Yields:
            Company objects
            
        Raises:
            CSVValidationError: If CSV structure is invalid
        """
        logger.info(f"Reading companies from CSV: {self.file_path}")
        
        try:
            # Read CSV with pandas for robust parsing
            df = pd.read_csv(self.file_path, dtype=str)  # Read all as strings
            
            if df.empty:
                logger.warning("CSV file is empty")
                return
            
            # Normalize column names
            df = self._normalize_columns(df)
            
            # Validate CSV structure
            self._validate_csv(df)
            
            total_rows = len(df)
            logger.info(f"Found {total_rows} companies in CSV")
            
            processed_count = 0
            valid_count = 0
            
            # Process each row
            for index, row in df.iterrows():
                processed_count += 1
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(processed_count, total_rows)
                
                # Validate row
                row_data = self._validate_row(row, index)
                if row_data is None:
                    continue
                
                try:
                    # Create Company object
                    company = Company.from_csv_row(row_data)
                    valid_count += 1
                    yield company
                    
                except Exception as e:
                    logger.warning(f"Row {index + 2}: Error creating Company object: {e}, skipping")
                    continue
            
            logger.info(f"Successfully processed {valid_count} out of {total_rows} companies")
            
        except pd.errors.EmptyDataError:
            logger.warning("CSV file is empty or contains no data")
            return
            
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise CSVValidationError(f"Error reading CSV file: {e}")
    
    def get_total_rows(self) -> int:
        """Get total number of rows in CSV file (excluding header).
        
        Returns:
            Total number of data rows
        """
        try:
            df = pd.read_csv(self.file_path)
            return len(df)
        except Exception as e:
            logger.error(f"Error counting rows in CSV: {e}")
            return 0