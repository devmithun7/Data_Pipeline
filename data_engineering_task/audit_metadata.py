#!/usr/bin/env python3
"""
Data Import Assignment - Audit Script
Validates the 3 required input sheets and transforms data to Vendor format
Uses Pydantic for robust input data validation
"""

import pandas as pd
import numpy as np
import os
import logging
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from enum import Enum
from typing import List, Optional, Any, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class RequiredInputSheets(str, Enum):
    """Required input sheets for data processing"""
    INPUT_CONSTITUENTS = "Input Constituents"
    INPUT_EMAILS = "Input Emails"
    INPUT_DONATION_HISTORY = "Input Donation History"


class ConstituentRecord(BaseModel):
    """Pydantic model for validating constituent input data"""
    model_config = ConfigDict(populate_by_name=True)
    
    patron_id: int = Field(..., alias="Patron ID")
    first_name: Optional[str] = Field(None, alias="First Name")
    last_name: Optional[str] = Field(None, alias="Last Name")
    date_entered: Optional[Any] = Field(None, alias="Date Entered")  # Can be string or datetime
    primary_email: Optional[str] = Field(None, alias="Primary Email")
    company: Optional[str] = Field(None, alias="Company")
    salutation: Optional[str] = Field(None, alias="Salutation")
    title: Optional[str] = Field(None, alias="Title")  # Job Title
    tags: Optional[str] = Field(None, alias="Tags")
    gender: Optional[str] = Field(None, alias="Gender")  # Contains Marital Status data
        
    @field_validator('patron_id')
    @classmethod
    def validate_patron_id(cls, v):
        if v <= 0:
            raise ValueError('Patron ID must be positive')
        return v


class EmailRecord(BaseModel):
    """Pydantic model for validating email input data"""
    model_config = ConfigDict(populate_by_name=True)
    
    patron_id: int = Field(..., alias="Patron ID")
    email: str = Field(..., alias="Email")
    
    @field_validator('patron_id')
    @classmethod
    def validate_patron_id(cls, v):
        if v <= 0:
            raise ValueError('Patron ID must be positive')
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError('Email must be a non-empty string')
        return v.strip()


class DonationRecord(BaseModel):
    """Pydantic model for validating donation input data"""
    model_config = ConfigDict(populate_by_name=True)
    
    patron_id: int = Field(..., alias="Patron ID")
    donation_amount: int = Field(..., alias="Donation Amount")
    donation_date: Optional[Any] = Field(None, alias="Donation Date")  # Can be string or datetime
    payment_method: Optional[str] = Field(None, alias="Payment Method")
    campaign: Optional[str] = Field(None, alias="Campaign")
    status: Optional[str] = Field(None, alias="Status")
    
    @field_validator('patron_id')
    @classmethod
    def validate_patron_id(cls, v):
        if v <= 0:
            raise ValueError('Patron ID must be positive')
        return v
    
    @field_validator('donation_amount')
    @classmethod
    def validate_donation_amount(cls, v):
        if v < 0:
            raise ValueError('Donation amount cannot be negative')
        return v


class TagRecord(BaseModel):
    """Pydantic model for validating API tag response"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(...)
    name: str = Field(...)
    mapped_name: str = Field(...)
    
    @field_validator('name', 'mapped_name')
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()


class EmailConfig(BaseModel):
    """Email configuration for sending validation reports"""
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=465)  # Use 465 (SSL) instead of 587 (STARTTLS) for better compatibility
    sender_email: str = Field(...)
    sender_password: str = Field(...)
    recipient_email: str = Field(...)
    
    @classmethod
    def from_env(cls) -> 'EmailConfig':
        """Create EmailConfig from environment variables"""
        return cls(
            smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '465')),  # Default to 465 (SSL) for better compatibility
            sender_email=os.getenv('SENDER_EMAIL', ''),
            sender_password=os.getenv('SENDER_PASSWORD', ''),
            recipient_email=os.getenv('RECIPIENT_EMAIL', '')
        )


class DataValidator:
    """Main class for validating the 3 required input sheets"""
    
    def __init__(self, excel_file_path: str):
        self.excel_file_path = excel_file_path
        # Input data from the 3 required sheets
        self.constituents_df = None
        self.emails_df = None
        self.donations_df = None
        # Track validation errors
        self.total_validation_errors = 0
        # API validation results
        self.api_validation_result = None
        self.tag_mappings = {}  # Tag mappings from API (normalized name -> mapped_name)
        # Set up logging for invalid records
        self.setup_logging()
    
    def setup_logging(self) -> None:
        """Set up logging configuration for invalid records"""
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"validation_errors_{timestamp}.log"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, mode='w', encoding='utf-8'),
                logging.StreamHandler()  # Also log to console
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.log_filename = log_filename
        
        # Log session start
        self.logger.info("="*80)
        self.logger.info("VALIDATION SESSION STARTED")
        self.logger.info(f"Excel file: {self.excel_file_path}")
        self.logger.info(f"Log file: {log_filename}")
        self.logger.info("="*80)
        
    def validate_excel_structure(self) -> None:
        """Validate that the 3 required input sheets exist"""
        print("Validating required input sheets...")
        
        if not os.path.exists(self.excel_file_path):
            raise FileNotFoundError(f"Excel file not found: {self.excel_file_path}")
        
        # Get sheet names
        excel_file = pd.ExcelFile(self.excel_file_path)
        sheet_names = excel_file.sheet_names
        
        # Check specifically for the three required input sheets only
        required_sheets = [
            RequiredInputSheets.INPUT_CONSTITUENTS.value,
            RequiredInputSheets.INPUT_EMAILS.value,
            RequiredInputSheets.INPUT_DONATION_HISTORY.value
        ]
        
        missing_sheets = []
        for required_sheet in required_sheets:
            if required_sheet not in sheet_names:
                missing_sheets.append(required_sheet)
        
        if missing_sheets:
            raise ValueError(f"Missing required input sheets: {missing_sheets}")
        
        print(f"All 3 required input sheets found: {required_sheets}")
    
    def validate_api_connection(self, api_url: str = None, timeout: int = 10) -> Dict[str, Any]:
        """
        Validate API connection and response schema, and build tag mapping dictionary
        
        Args:
            api_url: The API endpoint URL (defaults to API_URL from .env)
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with validation results and tag_mappings:
            {
                'success': bool,
                'records_count': int,
                'valid_records': int,
                'invalid_records': int,
                'errors': list,
                'tag_mappings': dict  # Normalized tag name -> mapped_name
            }
        """
        # Use API URL from environment variable if not provided
        if api_url is None:
            api_url = os.getenv('API_URL', 'https://6719768f7fc4c5ff8f4d84f1.mockapi.io/api/v1/tags')
        
        result = {
            'success': False,
            'records_count': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'errors': [],
            'tag_mappings': {}  # Will store normalized tag mappings
        }
        
        try:
            print(f"\nTesting API connection: {api_url}")
            self.logger.info(f"Testing API connection: {api_url}")
            
            # Make API request
            response = requests.get(api_url, timeout=timeout)
            
            if response.status_code == 200:
                print(f"API Response: HTTP {response.status_code} - Success")
                self.logger.info(f"API Response: HTTP {response.status_code} - Success")
                
                # Parse JSON response
                data = response.json()
                
                if not isinstance(data, list):
                    error_msg = "API response is not a list"
                    result['errors'].append(error_msg)
                    print(f"Error: {error_msg}")
                    self.logger.error(error_msg)
                    return result
                
                result['records_count'] = len(data)
                print(f"API returned {len(data)} records")
                self.logger.info(f"API returned {len(data)} records")
                
                # Validate each record against schema and build tag mapping
                valid_count = 0
                invalid_count = 0
                tag_mappings = {}
                
                for idx, record in enumerate(data):
                    try:
                        # Validate with Pydantic model
                        tag_record = TagRecord(**record)
                        valid_count += 1
                        
                        # Build normalized tag mapping (case-insensitive, trimmed)
                        # Key: normalized original name, Value: mapped_name
                        original_name = tag_record.name.strip()
                        mapped_name = tag_record.mapped_name.strip()
                        
                        # Store with normalized key (lowercase, trimmed)
                        normalized_key = original_name.lower().strip()
                        tag_mappings[normalized_key] = mapped_name
                        
                        self.logger.info(f"Tag mapping added: '{original_name}' -> '{mapped_name}'")
                        
                    except ValidationError as e:
                        invalid_count += 1
                        error_msg = f"Record {idx + 1}: Schema validation failed - {e}"
                        result['errors'].append(error_msg)
                        self.logger.error(f"API Record {idx + 1} - Validation Error:")
                        self.logger.error(f"  Record Data: {record}")
                        self.logger.error(f"  Error: {e}")
                
                result['valid_records'] = valid_count
                result['invalid_records'] = invalid_count
                result['success'] = invalid_count == 0
                result['tag_mappings'] = tag_mappings
                
                # Log summary
                print(f"API Validation Summary:")
                print(f"  - Total records: {len(data)}")
                print(f"  - Valid records: {valid_count}")
                print(f"  - Invalid records: {invalid_count}")
                print(f"  - Tag mappings built: {len(tag_mappings)}")
                
                if result['success']:
                    print("API validation passed - All records match expected schema")
                    self.logger.info("API validation passed - All records match expected schema")
                    self.logger.info(f"Built {len(tag_mappings)} tag mappings for transformation")
                else:
                    print(f"API validation completed with {invalid_count} schema mismatches")
                    self.logger.warning(f"API validation completed with {invalid_count} schema mismatches")
                
            else:
                error_msg = f"API returned HTTP {response.status_code} - {response.reason}"
                result['errors'].append(error_msg)
                print(f"Error: {error_msg}")
                self.logger.error(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = f"API request timed out after {timeout} seconds"
            result['errors'].append(error_msg)
            print(f"Error: {error_msg}")
            self.logger.error(error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Failed to connect to API - Check your internet connection"
            result['errors'].append(error_msg)
            print(f"Error: {error_msg}")
            self.logger.error(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during API validation: {str(e)}"
            result['errors'].append(error_msg)
            print(f"Error: {error_msg}")
            self.logger.error(error_msg)
        
        return result
    
    def validate_dataframe_columns(self, df: pd.DataFrame, expected_columns: List[str], sheet_name: str) -> None:
        """Validate that DataFrame has all expected columns"""
        actual_columns = set(df.columns)
        expected_columns_set = set(expected_columns)
        
        missing_columns = expected_columns_set - actual_columns
        if missing_columns:
            raise ValueError(f"Sheet '{sheet_name}' missing required columns: {missing_columns}")
        
        print(f"Sheet '{sheet_name}' has all required columns")
    
    def load_data(self) -> None:
        """Load and validate the 3 required input sheets"""
        print("Loading required input sheets...")
        
        # First validate that the 3 required sheets exist
        self.validate_excel_structure()
        
        # Load the 3 required input sheets
        self.constituents_df = pd.read_excel(self.excel_file_path, sheet_name=RequiredInputSheets.INPUT_CONSTITUENTS.value)
        self.emails_df = pd.read_excel(self.excel_file_path, sheet_name=RequiredInputSheets.INPUT_EMAILS.value)
        self.donations_df = pd.read_excel(self.excel_file_path, sheet_name=RequiredInputSheets.INPUT_DONATION_HISTORY.value)
        
        # Validate column structures for the 3 required sheets
        expected_constituent_columns = ["Patron ID", "First Name", "Last Name", "Date Entered", 
                                      "Primary Email", "Company", "Salutation", "Title", "Tags", "Gender"]
        expected_email_columns = ["Patron ID", "Email"]
        expected_donation_columns = ["Patron ID", "Donation Amount", "Donation Date", 
                                   "Payment Method", "Campaign", "Status"]
        
        self.validate_dataframe_columns(self.constituents_df, expected_constituent_columns, RequiredInputSheets.INPUT_CONSTITUENTS.value)
        self.validate_dataframe_columns(self.emails_df, expected_email_columns, RequiredInputSheets.INPUT_EMAILS.value)
        self.validate_dataframe_columns(self.donations_df, expected_donation_columns, RequiredInputSheets.INPUT_DONATION_HISTORY.value)
        
        print(f"Loaded {len(self.constituents_df)} constituents")
        print(f"Loaded {len(self.emails_df)} email records")
        print(f"Loaded {len(self.donations_df)} donation records")
        
        # Validate API connection and get tag mappings
        print("\nValidating API connection and retrieving tag mappings...")
        self.api_validation_result = self.validate_api_connection()
        
        if self.api_validation_result['success']:
            self.tag_mappings = self.api_validation_result['tag_mappings']
            print(f"Successfully retrieved {len(self.tag_mappings)} tag mappings from API")
        else:
            print("API validation failed or returned no tag mappings")
            self.logger.warning("API validation issues detected - proceeding without tag mappings")
            self.tag_mappings = {}
        
        # Clean data (convert nan to None) before validation
        self.clean_data()
        
        # Validate data using Pydantic models
        self.validate_input_data()
    
    def clean_data(self) -> None:
        """Clean data by converting pandas nan values to None for proper Pydantic validation"""
        print("Cleaning data (converting nan to None)...")
        self.logger.info("Starting data cleaning - converting nan values to None")
        
        # Clean constituents data
        self.constituents_df = self.constituents_df.replace({np.nan: None})
        self.logger.info(f"Cleaned {len(self.constituents_df)} constituent records")
        
        # Clean emails data  
        self.emails_df = self.emails_df.replace({np.nan: None})
        self.logger.info(f"Cleaned {len(self.emails_df)} email records")
        
        # Clean donations data
        self.donations_df = self.donations_df.replace({np.nan: None})
        self.logger.info(f"Cleaned {len(self.donations_df)} donation records")
        
        print("Data cleaning completed")
    
    def validate_input_data(self) -> None:
        """Validate input data using Pydantic models and log invalid records"""
        print("Validating input data with Pydantic models...")
        self.logger.info("Starting data validation with Pydantic models")
        
        validation_errors = []
        
        # Validate constituents data
        self.logger.info(f"Validating {len(self.constituents_df)} constituent records...")
        constituent_errors = 0
        try:
            for index, row in self.constituents_df.iterrows():
                try:
                    ConstituentRecord(**row.to_dict())
                except ValidationError as e:
                    constituent_errors += 1
                    error_msg = f"Constituent row {index + 1}: {e}"
                    validation_errors.append(error_msg)
                    
                    # Log detailed invalid record information
                    self.logger.error(f"INVALID CONSTITUENT RECORD - Row {index + 1}")
                    self.logger.error(f"Patron ID: {row.get('Patron ID', 'N/A')}")
                    self.logger.error(f"Name: {row.get('First Name', 'N/A')} {row.get('Last Name', 'N/A')}")
                    self.logger.error(f"Company: {row.get('Company', 'N/A')}")
                    self.logger.error(f"Email: {row.get('Primary Email', 'N/A')}")
                    self.logger.error(f"Validation Error: {e}")
                    self.logger.error(f"Full Record: {row.to_dict()}")
                    self.logger.error("-" * 60)
                    
            print(f"Validated {len(self.constituents_df)} constituent records")
            if constituent_errors > 0:
                self.logger.warning(f"Found {constituent_errors} invalid constituent records")
        except Exception as e:
            error_msg = f"Constituent validation error: {e}"
            validation_errors.append(error_msg)
            self.logger.error(error_msg)
        
        # Validate emails data
        self.logger.info(f"Validating {len(self.emails_df)} email records...")
        email_errors = 0
        try:
            for index, row in self.emails_df.iterrows():
                try:
                    EmailRecord(**row.to_dict())
                except ValidationError as e:
                    email_errors += 1
                    error_msg = f"Email row {index + 1}: {e}"
                    validation_errors.append(error_msg)
                    
                    # Log detailed invalid record information
                    self.logger.error(f"INVALID EMAIL RECORD - Row {index + 1}")
                    self.logger.error(f"Patron ID: {row.get('Patron ID', 'N/A')}")
                    self.logger.error(f"Email: {row.get('Email', 'N/A')}")
                    self.logger.error(f"Validation Error: {e}")
                    self.logger.error(f"Full Record: {row.to_dict()}")
                    self.logger.error("-" * 60)
                    
            print(f"Validated {len(self.emails_df)} email records")
            if email_errors > 0:
                self.logger.warning(f"Found {email_errors} invalid email records")
        except Exception as e:
            error_msg = f"Email validation error: {e}"
            validation_errors.append(error_msg)
            self.logger.error(error_msg)
        
        # Validate donations data
        self.logger.info(f"Validating {len(self.donations_df)} donation records...")
        donation_errors = 0
        try:
            for index, row in self.donations_df.iterrows():
                try:
                    DonationRecord(**row.to_dict())
                except ValidationError as e:
                    donation_errors += 1
                    error_msg = f"Donation row {index + 1}: {e}"
                    validation_errors.append(error_msg)
                    
                    # Log detailed invalid record information
                    self.logger.error(f"INVALID DONATION RECORD - Row {index + 1}")
                    self.logger.error(f"Patron ID: {row.get('Patron ID', 'N/A')}")
                    self.logger.error(f"Donation Amount: {row.get('Donation Amount', 'N/A')}")
                    self.logger.error(f"Donation Date: {row.get('Donation Date', 'N/A')}")
                    self.logger.error(f"Campaign: {row.get('Campaign', 'N/A')}")
                    self.logger.error(f"Validation Error: {e}")
                    self.logger.error(f"Full Record: {row.to_dict()}")
                    self.logger.error("-" * 60)
                    
            print(f"Validated {len(self.donations_df)} donation records")
            if donation_errors > 0:
                self.logger.warning(f"Found {donation_errors} invalid donation records")
        except Exception as e:
            error_msg = f"Donation validation error: {e}"
            validation_errors.append(error_msg)
            self.logger.error(error_msg)
        
        # Report validation summary
        total_errors = constituent_errors + email_errors + donation_errors
        self.total_validation_errors = total_errors  # Store for later checking
        
        if validation_errors:
            print(f"\nFound {len(validation_errors)} validation issues:")
            for error in validation_errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(validation_errors) > 10:
                print(f"  ... and {len(validation_errors) - 10} more errors")
            
            print("Validation completed with warnings")
            self.logger.warning(f"Validation completed with {total_errors} invalid records")
            self.logger.info(f"Detailed error information logged to: {self.log_filename}")
        else:
            print("All input data validation passed")
            self.logger.info("All input data validation passed - no invalid records found")
        
        print("Validation process completed successfully!")
        self.logger.info("Validation process completed successfully!")
    
    def has_validation_errors(self) -> bool:
        """Check if there were any validation errors during the process"""
        return self.total_validation_errors > 0
    
    def get_tag_mappings(self) -> Dict[str, str]:
        """
        Get tag mappings from API validation
        
        Returns:
            Dictionary mapping normalized tag names to mapped names
        """
        return self.tag_mappings
    
    def send_email_report(self, email_config: Optional[EmailConfig] = None, additional_attachments: List[str] = None, vendor_summary: dict = None, include_metadata_log: bool = True) -> bool:
        """Send validation log file and additional attachments via email"""
        try:
            if email_config is None:
                # Try to load from environment variables
                try:
                    email_config = EmailConfig.from_env()
                except Exception as e:
                    print(f"Email configuration not found: {e}")
                    self.logger.warning(f"Email configuration not found: {e}")
                    return False
            
            # Validate email configuration
            if not all([email_config.sender_email, email_config.sender_password, email_config.recipient_email]):
                print("Incomplete email configuration - skipping email")
                self.logger.warning("Incomplete email configuration - skipping email")
                return False
            
            print("Preparing to send validation report via email...")
            self.logger.info("Preparing to send validation report via email")
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = email_config.sender_email
            msg['To'] = email_config.recipient_email
            msg['Subject'] = f"Complete Data Processing Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Build email body with simple, clean formatting
            if vendor_summary:
                # Email with Vendor transformation results
                body = f"""
DATA PROCESSING REPORT
Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

Hello,

Your data processing has completed successfully. Here's a quick summary:

------------------------------------------------------------------------
SOURCE FILE:
{self.excel_file_path}

------------------------------------------------------------------------
RESULTS:

Input Data Processed:
  - Constituents: {len(self.constituents_df) if self.constituents_df is not None else 0}
  - Emails: {len(self.emails_df) if self.emails_df is not None else 0}
  - Donations: {len(self.donations_df) if self.donations_df is not None else 0}

Vendor Transformation:
  - Total Records: {vendor_summary.get('total_records', 0)}
  - Valid Records: {vendor_summary.get('valid_records', 0)}
  - Invalid Records: {vendor_summary.get('invalid_records', 0)}
  - Success Rate: {vendor_summary.get('validation_rate', 0):.2f}%

------------------------------------------------------------------------
ATTACHED FILES ({len(additional_attachments) if additional_attachments else 0}):

1. Constituent_Unclean.xlsx
   All {vendor_summary.get('total_records', 0)} records included (valid + invalid)

2. Constituent_Clean.xlsx  
   Only {vendor_summary.get('valid_records', 0)} validated records (ready to import)

3. Constituent_tag_count.xlsx
   Tag usage statistics showing each tag and constituent count

4. Vendor_transformation.log
   Error details for {vendor_summary.get('invalid_records', 0)} invalid records

------------------------------------------------------------------------
WHAT TO DO NEXT:

- Import the "Clean_Records" file into your Vendor system
- Review the log file to see why {vendor_summary.get('invalid_records', 0)} records failed validation
- Fix any data issues and re-run if needed

------------------------------------------------------------------------

Questions? Contact your data team.

This is an automated message.
"""
            else:
                # Email with metadata validation failure
                body = f"""
DATA VALIDATION ALERT
Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

Hello,

The validation process found errors in your input data.

------------------------------------------------------------------------
SOURCE FILE:
{self.excel_file_path}

------------------------------------------------------------------------
WHAT HAPPENED:

Your file has {self.total_validation_errors} validation error(s) that need to be fixed 
before we can process the data.

Input Data Found:
  - Constituents: {len(self.constituents_df) if self.constituents_df is not None else 0}
  - Emails: {len(self.emails_df) if self.emails_df is not None else 0}
  - Donations: {len(self.donations_df) if self.donations_df is not None else 0}

STATUS: Failed - Processing stopped to prevent bad data from going through

------------------------------------------------------------------------
ATTACHED FILES:

- validation_errors.log (detailed error information)

------------------------------------------------------------------------
WHAT TO DO NEXT:

1. Open the attached log file to see exactly what's wrong
2. Fix the errors in your Excel file
3. Run the validation again

------------------------------------------------------------------------

Questions? Contact your data team.

This is an automated message.
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach metadata validation log file (only if requested)
            if include_metadata_log:
                if os.path.exists(self.log_filename):
                    with open(self.log_filename, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(self.log_filename)}'
                    )
                    msg.attach(part)
                else:
                    print(f"Metadata log file not found: {self.log_filename}")
                    self.logger.warning(f"Metadata log file not found: {self.log_filename}")
                    return False
            
            # Attach additional files (Vendor output files)
            if additional_attachments:
                for file_path in additional_attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                        
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(file_path)}'
                        )
                        msg.attach(part)
                        print(f"Attached: {os.path.basename(file_path)}")
                    else:
                        print(f"Additional file not found: {file_path}")
                        self.logger.warning(f"Additional file not found: {file_path}")
            
            # Send email with timeout and SSL/TLS support
            if email_config.smtp_port == 465:
                # Use SSL for port 465
                import ssl
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port, timeout=30, context=context)
            else:
                # Use STARTTLS for port 587
                server = smtplib.SMTP(email_config.smtp_server, email_config.smtp_port, timeout=30)
                server.starttls()
            
            server.login(email_config.sender_email, email_config.sender_password)
            text = msg.as_string()
            server.sendmail(email_config.sender_email, email_config.recipient_email, text)
            server.quit()
            
            print(f"Validation report sent successfully to {email_config.recipient_email}")
            self.logger.info(f"Validation report sent successfully to {email_config.recipient_email}")
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            self.logger.error(f"Failed to send email: {e}")
            return False
    
    def run_validation(self, send_email: bool = False, email_config: Optional[EmailConfig] = None) -> None:
        """Run validation process for the 3 required input sheets"""
        print("Starting validation process...")
        self.logger.info("Starting validation process")
        
        # Load and validate the 3 required input sheets
        self.load_data()
        
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Excel file structure validated")
        print(f"All 3 required sheets found and validated")
        print(f"Column structures validated for all sheets")
        print(f"Data validation completed using Pydantic models")
        print(f"Detailed logs saved to: {self.log_filename}")
        print("="*60)
        
        # Send email if requested
        if send_email:
            self.send_email_report(email_config)
        
        # Log final summary
        self.logger.info("="*80)
        self.logger.info("VALIDATION SESSION COMPLETED")
        self.logger.info(f"Excel file: {self.excel_file_path}")
        self.logger.info(f"Total constituents processed: {len(self.constituents_df)}")
        self.logger.info(f"Total emails processed: {len(self.emails_df)}")
        self.logger.info(f"Total donations processed: {len(self.donations_df)}")
        self.logger.info("="*80)




