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
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from enum import Enum
from typing import List, Optional, Any
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
    gender: Optional[str] = Field(None, alias="Gender")
    marital_status: Optional[str] = Field(None, alias="Marital Status")
        
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


class EmailConfig(BaseModel):
    """Email configuration for sending validation reports"""
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    sender_email: str = Field(...)
    sender_password: str = Field(...)
    recipient_email: str = Field(...)
    
    @classmethod
    def from_env(cls) -> 'EmailConfig':
        """Create EmailConfig from environment variables"""
        return cls(
            smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
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
                                      "Primary Email", "Company", "Salutation", "Title", "Tags", "Gender", "Marital Status"]
        expected_email_columns = ["Patron ID", "Email"]
        expected_donation_columns = ["Patron ID", "Donation Amount", "Donation Date", 
                                   "Payment Method", "Campaign", "Status"]
        
        self.validate_dataframe_columns(self.constituents_df, expected_constituent_columns, RequiredInputSheets.INPUT_CONSTITUENTS.value)
        self.validate_dataframe_columns(self.emails_df, expected_email_columns, RequiredInputSheets.INPUT_EMAILS.value)
        self.validate_dataframe_columns(self.donations_df, expected_donation_columns, RequiredInputSheets.INPUT_DONATION_HISTORY.value)
        
        print(f"Loaded {len(self.constituents_df)} constituents")
        print(f"Loaded {len(self.emails_df)} email records")
        print(f"Loaded {len(self.donations_df)} donation records")
        
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
    
    def send_email_report(self, email_config: Optional[EmailConfig] = None, additional_attachments: List[str] = None, Vendor_summary: dict = None, include_metadata_log: bool = True) -> bool:
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
            
            # Email body
            attachment_info = "Please find the detailed validation log attached."
            if additional_attachments:
                attachment_info += f"\n\nAdditional files attached: {len(additional_attachments)} Vendor output files"
            
            # Build Vendor summary section if provided
            Vendor_section = ""
            if Vendor_summary:
                Vendor_section = f"""

Vendor Transformation Summary:
============================================================
Total records processed: {Vendor_summary.get('total_records', 0)}
Valid records: {Vendor_summary.get('valid_records', 0)}
Invalid records: {Vendor_summary.get('invalid_records', 0)}
Validation success rate: {Vendor_summary.get('validation_rate', 0):.2f}%
============================================================
"""
            
            body = f"""
Complete Data Processing Report

Input Validation and Vendor Transformation completed successfully for Excel file: {self.excel_file_path}

Input Data Summary:
- Constituents processed: {len(self.constituents_df) if self.constituents_df is not None else 0}
- Email records processed: {len(self.emails_df) if self.emails_df is not None else 0}
- Donation records processed: {len(self.donations_df) if self.donations_df is not None else 0}
{Vendor_section}
{attachment_info}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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
            
            # Send email
            server = smtplib.SMTP(email_config.smtp_server, email_config.smtp_port)
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



