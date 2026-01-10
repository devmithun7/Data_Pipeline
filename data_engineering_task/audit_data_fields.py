#!/usr/bin/env python3
"""
Data Fields Audit Module
Defines field mappings, validation rules, and transformation logic for combining
Input Constituents, Input Emails, and Input Donation History into Vendor output format
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import pandas as pd
import logging
import os
from datetime import datetime


class InputSheets(str, Enum):
    """Input sheet names"""
    INPUT_CONSTITUENTS = "Input Constituents"
    INPUT_EMAILS = "Input Emails"
    INPUT_DONATION_HISTORY = "Input Donation History"


class VendorOutputColumns(str, Enum):
    """Vendor output column definitions"""
    CB_CONSTITUENT_ID = "CB Constituent ID"
    CB_CONSTITUENT_TYPE = "CB Constituent Type"
    CB_FIRST_NAME = "CB First Name"
    CB_LAST_NAME = "CB Last Name"
    CB_COMPANY_NAME = "CB Company Name"
    CB_CREATED_AT = "CB Created At"
    CB_EMAIL_1 = "CB Email 1 (Standardized)"
    CB_EMAIL_2 = "CB Email 2 (Standardized)"
    CB_TITLE = "CB Title"
    CB_TAGS = "CB Tags"
    CB_BACKGROUND_INFO = "CB Background Information"
    CB_LIFETIME_DONATION = "CB Lifetime Donation Amount"
    CB_RECENT_DONATION_DATE = "CB Most Recent Donation Date"
    CB_RECENT_DONATION_AMOUNT = "CB Most Recent Donation Amount"
    
    @classmethod
    def get_ordered_columns(cls) -> List[str]:
        """Return columns in the exact order for output file"""
        return [
            cls.CB_CONSTITUENT_ID.value,
            cls.CB_CONSTITUENT_TYPE.value,
            cls.CB_FIRST_NAME.value,
            cls.CB_LAST_NAME.value,
            cls.CB_COMPANY_NAME.value,
            cls.CB_CREATED_AT.value,
            cls.CB_EMAIL_1.value,
            cls.CB_EMAIL_2.value,
            cls.CB_TITLE.value,
            cls.CB_TAGS.value,
            cls.CB_BACKGROUND_INFO.value,
            cls.CB_LIFETIME_DONATION.value,
            cls.CB_RECENT_DONATION_DATE.value,
            cls.CB_RECENT_DONATION_AMOUNT.value
        ]


class FieldMappingRules:
    """Defines how input fields map to Vendor output fields"""
    
    # Direct field mappings from Input Constituents
    CONSTITUENT_MAPPINGS = {
        "Patron ID": VendorOutputColumns.CB_CONSTITUENT_ID.value,
        "First Name": VendorOutputColumns.CB_FIRST_NAME.value,
        "Last Name": VendorOutputColumns.CB_LAST_NAME.value,
        "Company": VendorOutputColumns.CB_COMPANY_NAME.value,
        "Date Entered": VendorOutputColumns.CB_CREATED_AT.value,
        "Primary Email": VendorOutputColumns.CB_EMAIL_1.value,
        "Salutation": VendorOutputColumns.CB_TITLE.value,
        "Tags": VendorOutputColumns.CB_TAGS.value
    }
    
    @classmethod
    def determine_constituent_type(cls, row: dict) -> str:
        """Determine if constituent is Person or Company based on data"""
        company = row.get("Company", "").strip() if row.get("Company") else ""
        first_name = row.get("First Name", "").strip() if row.get("First Name") else ""
        last_name = row.get("Last Name", "").strip() if row.get("Last Name") else ""
        
        # If company field has value, it's a Company
        if company:
            return "Company"
        # If first name or last name exists, it's a Person
        elif first_name or last_name:
            return "Person"
        else:
            return "Person"  # Default to Person if unclear
    
    @classmethod
    def get_constituent_emails(cls, patron_id: int, emails_df: pd.DataFrame, primary_email: str = "") -> tuple:
        """
        Get up to 2 emails for a constituent with priority logic based on email count
        
        BUSINESS RULE:
        If constituent has MORE THAN 3 emails in Input Emails sheet:
          1. CB Email 1 = Primary Email from Input Constituents sheet
          2. CB Email 2 = 1st email from Input Emails sheet (earliest row)
          3. Remaining emails from Input Emails are ignored
        
        If constituent has 3 OR FEWER emails:
          1. CB Email 1 = First email from Input Emails sheet
          2. CB Email 2 = Second email from Input Emails sheet
          3. If no emails in Input Emails, use Primary Email as fallback for CB Email 1
        
        Args:
            patron_id: Constituent's Patron ID
            emails_df: Input Emails dataframe  
            primary_email: Primary Email from Input Constituents sheet
            
        Returns:
            tuple: (email_1, email_2) - Both standardized and cleaned
        
        Examples:
            Patron has 5 emails (>3):
              Primary Email: "john@company.com"
              Input Emails: ["john.doe@gmail.com", "j.doe@work.com", ...]
              Result: ("john@company.com", "john.doe@gmail.com")
            
            Patron has 2 emails (<=3):
              Primary Email: "mary@company.com"
              Input Emails: ["mary.smith@gmail.com", "msmith@work.com"]
              Result: ("mary.smith@gmail.com", "msmith@work.com")
        """
        # Get all emails for this patron from Input Emails sheet (already cleaned)
        constituent_emails = emails_df[emails_df["Patron ID"] == patron_id]["Email"].tolist()
        
        # Filter out empty/invalid emails
        constituent_emails = [email for email in constituent_emails if email and str(email).strip()]
        
        email_count = len(constituent_emails)
        
        # CASE 1: More than 3 emails -> Prioritize Primary Email from Constituents
        if email_count > 3:
            email_1 = primary_email if primary_email and str(primary_email).strip() else ""
            email_2 = constituent_emails[0] if len(constituent_emails) > 0 else ""
        
        # CASE 2: 3 or fewer emails -> Use Input Emails order, Primary as fallback
        else:
            email_1 = constituent_emails[0] if len(constituent_emails) > 0 else (primary_email if primary_email else "")
            email_2 = constituent_emails[1] if len(constituent_emails) > 1 else ""
        
        return email_1, email_2
    
    @classmethod
    def calculate_donation_summary(cls, patron_id: int, donations_df: pd.DataFrame) -> tuple:
        """Calculate donation summary for a constituent"""
        constituent_donations = donations_df[donations_df["Patron ID"] == patron_id]
        
        if constituent_donations.empty:
            # No donations - return empty strings
            return "", "", ""
        
        # Calculate lifetime donation amount
        lifetime_amount = constituent_donations["Donation Amount"].sum()
        
        # Get most recent donation (by date)
        most_recent = constituent_donations.loc[constituent_donations["Donation Date"].idxmax()]
        recent_date = most_recent["Donation Date"]
        recent_amount = most_recent["Donation Amount"]
        
        return str(lifetime_amount), str(recent_date), str(recent_amount)
    
    @classmethod
    def format_background_information(cls, row: dict) -> str:
        """
        Format background information string from job title and marital status.
        
        Rules:
        - If both present: "Job Title: Professor; Marital Status: Married"
        - If only job title: "Job Title: Professor"
        - If only marital status: "Marital Status: Married"
        - If neither present: empty string
        - "Unknown" marital status is treated as not present
        """
        job_title = str(row.get("Title", "")).strip() if row.get("Title") else ""
        marital_status = str(row.get("Gender", "")).strip() if row.get("Gender") else ""
        
        # Treat "Unknown" as blank/not present
        if marital_status.lower() == "unknown":
            marital_status = ""
        
        parts = []
        
        if job_title:
            parts.append(f"Job Title: {job_title}")
        
        if marital_status:
            parts.append(f"Marital Status: {marital_status}")
        
        return "; ".join(parts)


class VendorValidationRules:
    """Validation rules for Vendor output columns"""
    
    @classmethod
    def validate_cb_constituent_id(cls, value: Any) -> List[str]:
        """Validate CB Constituent ID - must be unique ID per constituent"""
        errors = []
        if not value or str(value).strip() == "":
            errors.append("CB Constituent ID is required")
        return errors
    
    @classmethod
    def validate_cb_constituent_type(cls, value: Any) -> List[str]:
        """Validate CB Constituent Type - must be 'Person' or 'Company'"""
        errors = []
        if not value:
            errors.append("CB Constituent Type is required")
        elif value not in ["Person", "Company"]:
            errors.append("CB Constituent Type must be either 'Person' or 'Company'")
        return errors
    
    @classmethod
    def validate_cb_name_fields(cls, row_data: dict) -> List[str]:
        """Validate name fields based on constituent type"""
        errors = []
        constituent_type = row_data.get(VendorOutputColumns.CB_CONSTITUENT_TYPE.value)
        
        if constituent_type == "Person":
            first_name = row_data.get(VendorOutputColumns.CB_FIRST_NAME.value, "").strip()
            last_name = row_data.get(VendorOutputColumns.CB_LAST_NAME.value, "").strip()
            
            if not first_name:
                errors.append("CB First Name is required when CB Constituent Type is 'Person'")
            if not last_name:
                errors.append("CB Last Name is required when CB Constituent Type is 'Person'")
                
        elif constituent_type == "Company":
            company_name = row_data.get(VendorOutputColumns.CB_COMPANY_NAME.value, "").strip()
            if not company_name:
                errors.append("CB Company Name is required when CB Constituent Type is 'Company'")
        
        return errors
    
    @classmethod
    def validate_cb_created_at(cls, value: Any) -> List[str]:
        """Validate CB Created At - required timestamp"""
        errors = []
        if not value or str(value).strip() == "" or str(value).strip().lower() == "nan":
            errors.append("CB Created At is required - timestamp of when constituent was first created")
        return errors
    
    @classmethod
    def validate_cb_email(cls, value: Any, field_name: str) -> List[str]:
        """Validate CB Email fields - if present, must be standardized and well formatted"""
        errors = []
        if value and str(value).strip():
            email = str(value).strip()
            # Basic email format validation
            if "@" not in email or "." not in email.split("@")[-1]:
                errors.append(f"{field_name} must be a standardized and well formatted email for a valid domain")
        return errors
    
    @classmethod
    def validate_cb_title(cls, value: Any) -> List[str]:
        """Validate CB Title - must be one of allowed values or empty string"""
        errors = []
        if value is not None:
            title = str(value).strip()
            allowed_titles = ["Mr.", "Mrs.", "Ms.", "Dr.", ""]
            if title not in allowed_titles:
                errors.append("CB Title must be one of 'Mr.', 'Mrs.', 'Ms.', 'Dr.', or empty string")
        return errors
    
    @classmethod
    def validate_cb_donation_fields(cls, row_data: dict) -> List[str]:
        """Validate donation fields - should be empty string if constituent has never donated"""
        errors = []
        
        lifetime_amount = row_data.get(VendorOutputColumns.CB_LIFETIME_DONATION.value, "")
        recent_date = row_data.get(VendorOutputColumns.CB_RECENT_DONATION_DATE.value, "")
        recent_amount = row_data.get(VendorOutputColumns.CB_RECENT_DONATION_AMOUNT.value, "")
        
        # Check consistency - if no donations, all should be empty
        has_lifetime = lifetime_amount and str(lifetime_amount).strip()
        has_recent_date = recent_date and str(recent_date).strip()
        has_recent_amount = recent_amount and str(recent_amount).strip()
        
        # If constituent has donations, all three fields should have values
        if any([has_lifetime, has_recent_date, has_recent_amount]):
            if not has_lifetime:
                errors.append("CB Lifetime Donation Amount should have value if constituent has donated")
            if not has_recent_date:
                errors.append("CB Most Recent Donation Date should have value if constituent has donated")
            if not has_recent_amount:
                errors.append("CB Most Recent Donation Amount should have value if constituent has donated")
        
        return errors
    
    @classmethod
    def validate_Vendor_row(cls, row_data: dict) -> List[str]:
        """Validate a complete Vendor output row"""
        all_errors = []
        
        # Validate individual fields
        all_errors.extend(cls.validate_cb_constituent_id(row_data.get(VendorOutputColumns.CB_CONSTITUENT_ID.value)))
        all_errors.extend(cls.validate_cb_constituent_type(row_data.get(VendorOutputColumns.CB_CONSTITUENT_TYPE.value)))
        all_errors.extend(cls.validate_cb_created_at(row_data.get(VendorOutputColumns.CB_CREATED_AT.value)))
        all_errors.extend(cls.validate_cb_email(row_data.get(VendorOutputColumns.CB_EMAIL_1.value), "CB Email 1"))
        all_errors.extend(cls.validate_cb_email(row_data.get(VendorOutputColumns.CB_EMAIL_2.value), "CB Email 2"))
        all_errors.extend(cls.validate_cb_title(row_data.get(VendorOutputColumns.CB_TITLE.value)))
        
        # Validate dependent fields
        all_errors.extend(cls.validate_cb_name_fields(row_data))
        all_errors.extend(cls.validate_cb_donation_fields(row_data))
        
        return all_errors


class DataCleaner:
    """Handles data cleaning and standardization before validation"""
    
    @classmethod
    def clean_and_standardize_dataframes(cls, constituents_df: pd.DataFrame, 
                                       emails_df: pd.DataFrame, 
                                       donations_df: pd.DataFrame,
                                       tag_mappings: Dict[str, str] = None) -> tuple:
        """
        Clean and standardize all three input dataframes
        
        Args:
            constituents_df: Input Constituents dataframe
            emails_df: Input Emails dataframe
            donations_df: Input Donation History dataframe
            tag_mappings: Dictionary mapping normalized tag names to mapped names (from API)
        
        Returns:
            Tuple of (clean_constituents, clean_emails, clean_donations)
        """
        
        # Clean each dataframe
        clean_constituents = cls.clean_constituents_data(constituents_df.copy(), tag_mappings)
        clean_emails = cls.clean_emails_data(emails_df.copy())
        clean_donations = cls.clean_donations_data(donations_df.copy())
        
        return clean_constituents, clean_emails, clean_donations
    
    @classmethod
    def clean_constituents_data(cls, df: pd.DataFrame, tag_mappings: Dict[str, str] = None) -> pd.DataFrame:
        """
        Clean and standardize Input Constituents data
        
        Applies the following cleaning operations:
        - Trims whitespace from all string columns
        - Converts names to title case
        - Removes special characters from names
        - Standardizes email addresses (lowercase, removes spaces)
        - Standardizes salutation/title values
        - Cleans and standardizes tags
        - Maps tags using API-provided mappings (if available)
        - Standardizes timestamp format
        
        Args:
            df: Input Constituents dataframe
            tag_mappings: Optional dictionary mapping normalized tag names to mapped names (from API)
        """
        
        # Trim whitespace from all string columns
        string_columns = ["First Name", "Last Name", "Primary Email", "Company", 
                         "Salutation", "Title", "Tags", "Gender"]
        for col in string_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                # Replace 'nan' string with empty string
                df[col] = df[col].replace('nan', '')
        
        # Standardize email addresses
        if "Primary Email" in df.columns:
            df["Primary Email"] = df["Primary Email"].apply(cls.standardize_email)
        
        # Standardize salutation/title
        if "Salutation" in df.columns:
            df["Salutation"] = df["Salutation"].apply(cls.standardize_title)
        
        # Standardize names (proper case, remove special characters)
        if "First Name" in df.columns:
            df["First Name"] = df["First Name"].apply(cls.standardize_name)
        if "Last Name" in df.columns:
            df["Last Name"] = df["Last Name"].apply(cls.standardize_name)
        if "Company" in df.columns:
            df["Company"] = df["Company"].apply(cls.standardize_company_name)
        
        # Clean and map tags using API mappings
        if "Tags" in df.columns:
            if tag_mappings:
                # Apply API-based tag mapping
                df["Tags"] = df["Tags"].apply(lambda tags: cls.map_tags_with_api(tags, tag_mappings))
            else:
                # Just standardize tags without mapping
                df["Tags"] = df["Tags"].apply(cls.standardize_tags)
        
        # Standardize date format for Date Entered
        if "Date Entered" in df.columns:
            df["Date Entered"] = df["Date Entered"].apply(cls.standardize_timestamp)
        
        return df
    
    @classmethod
    def clean_emails_data(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize Input Emails data
        
        Applies the following cleaning operations:
        - Trims whitespace
        - Converts email to lowercase
        - Removes spaces from email addresses
        - Validates basic email format
        """
        
        # Trim whitespace from email column
        if "Email" in df.columns:
            df["Email"] = df["Email"].astype(str).str.strip()
            # Replace 'nan' string with empty string
            df["Email"] = df["Email"].replace('nan', '')
            # Standardize email addresses
            df["Email"] = df["Email"].apply(cls.standardize_email)
        
        return df
    
    @classmethod
    def clean_donations_data(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize Input Donation History data
        
        Applies the following cleaning operations:
        - Trims whitespace from string columns
        - Standardizes payment method values
        - Converts campaign names to title case
        - Standardizes donation status values
        """
        
        # Trim whitespace from string columns
        string_columns = ["Payment Method", "Campaign", "Status"]
        for col in string_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                # Replace 'nan' string with empty string
                df[col] = df[col].replace('nan', '')
        
        # Standardize payment method
        if "Payment Method" in df.columns:
            df["Payment Method"] = df["Payment Method"].apply(cls.standardize_payment_method)
        
        # Standardize campaign names
        if "Campaign" in df.columns:
            df["Campaign"] = df["Campaign"].apply(cls.standardize_campaign_name)
        
        # Standardize status
        if "Status" in df.columns:
            df["Status"] = df["Status"].apply(cls.standardize_status)
        
        return df
    
    @classmethod
    def standardize_email(cls, email: str) -> str:
        """
        Standardize email address format
        - Converts to lowercase
        - Removes all whitespace
        - Validates basic email format (@, domain)
        - Removes special characters except @ . _ - +
        """
        if not email or email == 'nan' or email.strip() == '':
            return ''
        
        email = str(email).strip().lower()
        
        # Remove all spaces
        email = email.replace(' ', '')
        
        # Basic email validation
        if '@' not in email:
            return ''
        
        parts = email.split('@')
        if len(parts) != 2:
            return ''
        
        local_part, domain = parts
        
        # Check if domain has at least one dot
        if '.' not in domain:
            return ''
        
        # Remove special characters except allowed ones
        import re
        local_part = re.sub(r'[^a-z0-9._+\-]', '', local_part)
        domain = re.sub(r'[^a-z0-9.\-]', '', domain)
        
        if local_part and domain:
            return f"{local_part}@{domain}"
        else:
            return ''
    
    @classmethod
    def standardize_title(cls, title: str) -> str:
        """Standardize salutation/title format"""
        if not title or title == 'nan' or title.strip() == '':
            return ''
        
        title = str(title).strip()
        
        # Standardize common titles
        title_mapping = {
            'mr': 'Mr.',
            'mr.': 'Mr.',
            'mister': 'Mr.',
            'mrs': 'Mrs.',
            'mrs.': 'Mrs.',
            'ms': 'Ms.',
            'ms.': 'Ms.',
            'miss': 'Ms.',
            'dr': 'Dr.',
            'dr.': 'Dr.',
            'doctor': 'Dr.',
            'prof': 'Dr.',
            'prof.': 'Dr.',
            'professor': 'Dr.'
        }
        
        return title_mapping.get(title.lower(), title)
    
    @classmethod
    def standardize_name(cls, name: str) -> str:
        """
        Standardize person name (proper case)
        - Applies title case
        - Removes special characters except hyphens and apostrophes
        - Handles multi-part names properly (e.g., O'Brien, Mary-Jane)
        """
        if not name or name == 'nan' or name.strip() == '':
            return ''
        
        name = str(name).strip()
        
        # Remove special characters except letters, spaces, hyphens, and apostrophes
        import re
        name = re.sub(r"[^a-zA-Z\s\-']", '', name)
        
        # Remove multiple spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        if not name:
            return ''
        
        # Convert to proper case (first letter uppercase, rest lowercase)
        # Handle names with spaces, hyphens, apostrophes
        words = []
        for word in name.replace('-', ' - ').replace("'", " ' ").split():
            if word in ['-', "'"]:
                words.append(word)
            elif len(word) > 0:
                words.append(word[0].upper() + word[1:].lower())
        
        result = ''.join(words).replace(' - ', '-').replace(" ' ", "'")
        return result
    
    @classmethod
    def standardize_company_name(cls, company: str) -> str:
        """Standardize company name"""
        if not company or company == 'nan' or company.strip() == '':
            return ''
        
        company = str(company).strip()
        
        # Basic company name standardization
        # Capitalize first letter of each word, but preserve common abbreviations
        words = []
        for word in company.split():
            # Common business abbreviations that should stay uppercase
            if word.upper() in ['LLC', 'INC', 'CORP', 'LTD', 'CO', 'LP', 'PLC']:
                words.append(word.upper())
            else:
                words.append(word.capitalize())
        
        return ' '.join(words)
    
    @classmethod
    def standardize_tags(cls, tags: str) -> str:
        """Standardize tags format"""
        if not tags or tags == 'nan' or tags.strip() == '':
            return ''
        
        tags = str(tags).strip()
        
        # Split by comma, clean each tag, rejoin
        tag_list = []
        for tag in tags.split(','):
            cleaned_tag = tag.strip()
            if cleaned_tag:
                tag_list.append(cleaned_tag)
        
        return ', '.join(tag_list)
    
    @classmethod
    def map_tags_with_api(cls, tags: str, tag_mappings: Dict[str, str]) -> str:
        """
        Map tags using API-provided tag mapping dictionary
        
        Process:
        1. Split comma-separated tags
        2. Normalize each tag (lowercase, trim whitespace)
        3. Look up in API mapping dictionary
        4. Use mapped_name if found, else keep original
        5. Filter out empty tags
        6. Join back with comma separator
        
        Args:
            tags: Comma-separated string of tags
            tag_mappings: Dictionary mapping normalized tag names to mapped names
                         (from API: name -> mapped_name)
        
        Returns:
            Comma-separated string of mapped tags
        
        Examples:
            Input: "Donor, volunteer, VIP"
            API mappings: {"donor": "Major Donor", "volunteer": "Active Volunteer"}
            Output: "Major Donor, Active Volunteer, VIP"
        """
        if not tags or tags == 'nan' or str(tags).strip() == '':
            return ''
        
        if not tag_mappings:
            # No mappings available, return standardized tags
            return cls.standardize_tags(tags)
        
        tags_str = str(tags).strip()
        
        # Split by comma and process each tag
        mapped_tags = []
        for tag in tags_str.split(','):
            # Clean and normalize the tag
            cleaned_tag = tag.strip()
            
            # Skip empty tags
            if not cleaned_tag:
                continue
            
            # Normalize for lookup (lowercase, trimmed)
            normalized_tag = cleaned_tag.lower().strip()
            
            # Look up in API mapping dictionary
            if normalized_tag in tag_mappings:
                # Use mapped name from API
                mapped_tag = tag_mappings[normalized_tag]
                mapped_tags.append(mapped_tag)
            else:
                # Keep original tag if no mapping exists
                mapped_tags.append(cleaned_tag)
        
        return ', '.join(mapped_tags)
    
    @classmethod
    def standardize_payment_method(cls, method: str) -> str:
        """Standardize payment method"""
        if not method or method == 'nan' or method.strip() == '':
            return ''
        
        method = str(method).strip()
        
        # Standardize common payment methods
        method_mapping = {
            'credit card': 'Credit Card',
            'creditcard': 'Credit Card',
            'cc': 'Credit Card',
            'debit card': 'Debit Card',
            'debitcard': 'Debit Card',
            'check': 'Check',
            'cheque': 'Check',
            'cash': 'Cash',
            'paypal': 'PayPal',
            'bank transfer': 'Bank Transfer',
            'banktransfer': 'Bank Transfer',
            'wire transfer': 'Wire Transfer',
            'wiretransfer': 'Wire Transfer'
        }
        
        return method_mapping.get(method.lower(), method.title())
    
    @classmethod
    def standardize_campaign_name(cls, campaign: str) -> str:
        """Standardize campaign name"""
        if not campaign or campaign == 'nan' or campaign.strip() == '':
            return ''
        
        campaign = str(campaign).strip()
        
        # Convert to title case
        return campaign.title()
    
    @classmethod
    def standardize_status(cls, status: str) -> str:
        """Standardize donation status"""
        if not status or status == 'nan' or status.strip() == '':
            return ''
        
        status = str(status).strip()
        
        # Standardize common statuses
        status_mapping = {
            'paid': 'Paid',
            'complete': 'Paid',
            'completed': 'Paid',
            'success': 'Paid',
            'successful': 'Paid',
            'pending': 'Pending',
            'processing': 'Pending',
            'failed': 'Failed',
            'error': 'Failed',
            'cancelled': 'Cancelled',
            'canceled': 'Cancelled',
            'refunded': 'Refunded'
        }
        
        return status_mapping.get(status.lower(), status.title())
    
    @classmethod
    def standardize_timestamp(cls, timestamp: str) -> str:
        """Standardize timestamp format to YYYY-MM-DD HH:MM:SS"""
        if not timestamp or timestamp == 'nan' or str(timestamp).strip() == '':
            return ''
        
        timestamp_str = str(timestamp).strip()
        
        # If it's already 'nan' string, return empty
        if timestamp_str.lower() == 'nan':
            return ''
        
        try:
            import pandas as pd
            from datetime import datetime
            
            # Try to parse the timestamp using pandas (handles many formats)
            parsed_date = pd.to_datetime(timestamp_str, errors='coerce')
            
            # If parsing failed, return original
            if pd.isna(parsed_date):
                return timestamp_str
            
            # Format as standard timestamp: YYYY-MM-DD HH:MM:SS
            return parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception:
            # If any error occurs, return the original timestamp
            return timestamp_str


class DataCombiner:
    """Combines data from the three input sheets into Vendor output format"""
    
    @classmethod
    def combine_data(cls, constituents_df: pd.DataFrame, emails_df: pd.DataFrame, 
                    donations_df: pd.DataFrame, tag_mappings: Dict[str, str] = None) -> pd.DataFrame:
        """
        Combine the three input sheets into Vendor output format with cleaning
        
        Args:
            constituents_df: Input Constituents dataframe
            emails_df: Input Emails dataframe
            donations_df: Input Donation History dataframe
            tag_mappings: Dictionary mapping normalized tag names to mapped names (from API)
        
        Returns:
            DataFrame in Vendor output format
        """
        
        # First, clean and standardize all input data
        print("Cleaning and standardizing input data...")
        if tag_mappings:
            print(f"Applying {len(tag_mappings)} tag mappings from API...")
        clean_constituents, clean_emails, clean_donations = DataCleaner.clean_and_standardize_dataframes(
            constituents_df, emails_df, donations_df, tag_mappings
        )
        print("Data cleaning completed")
        
        output_rows = []
        
        # Use cleaned data for processing
        for _, constituent_row in clean_constituents.iterrows():
            patron_id = constituent_row["Patron ID"]
            
            # Start with constituent data
            output_row = {}
            
            # Map basic constituent fields
            for input_field, output_field in FieldMappingRules.CONSTITUENT_MAPPINGS.items():
                output_row[output_field] = constituent_row.get(input_field, "")
            
            # Determine constituent type
            output_row[VendorOutputColumns.CB_CONSTITUENT_TYPE.value] = FieldMappingRules.determine_constituent_type(constituent_row.to_dict())
            
            # Get Primary Email from constituent
            primary_email = constituent_row.get("Primary Email", "")
            
            # Get emails from cleaned Input Emails sheet with priority logic
            email_1, email_2 = FieldMappingRules.get_constituent_emails(patron_id, clean_emails, primary_email)
            
            output_row[VendorOutputColumns.CB_EMAIL_1.value] = email_1
            output_row[VendorOutputColumns.CB_EMAIL_2.value] = email_2
            
            # Calculate donation summary from cleaned Input Donation History sheet
            lifetime_amount, recent_date, recent_amount = FieldMappingRules.calculate_donation_summary(patron_id, clean_donations)
            output_row[VendorOutputColumns.CB_LIFETIME_DONATION.value] = lifetime_amount
            output_row[VendorOutputColumns.CB_RECENT_DONATION_DATE.value] = recent_date
            output_row[VendorOutputColumns.CB_RECENT_DONATION_AMOUNT.value] = recent_amount
            
            # Format Background Information (Job Title and Marital Status)
            output_row[VendorOutputColumns.CB_BACKGROUND_INFO.value] = FieldMappingRules.format_background_information(constituent_row.to_dict())
            
            output_rows.append(output_row)
        
        # Create DataFrame with Vendor output format
        output_df = pd.DataFrame(output_rows)
        
        # Ensure all required columns exist
        for column in VendorOutputColumns:
            if column.value not in output_df.columns:
                output_df[column.value] = ""
        
        # Reorder columns to match the specified output format
        ordered_columns = VendorOutputColumns.get_ordered_columns()
        output_df = output_df[ordered_columns]
        
        return output_df


class ValidationLogger:
    """Handles logging of validation errors and failed records"""
    
    def __init__(self, log_prefix: str = "Vendor_validation"):
        """Initialize validation logger with timestamped log file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = f"{log_prefix}_{timestamp}.log"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_filename, mode='w', encoding='utf-8'),
                logging.StreamHandler()  # Also log to console
            ],
            force=True  # Override existing logging config
        )
        
        self.logger = logging.getLogger(f"{log_prefix}_logger")
        
        # Log session start
        self.logger.info("="*80)
        self.logger.info("Vendor VALIDATION SESSION STARTED")
        self.logger.info(f"Log file: {self.log_filename}")
        self.logger.info("="*80)
    
    def log_cleaning_summary(self, constituents_count: int, emails_count: int, donations_count: int):
        """Log data cleaning summary"""
        self.logger.info("DATA CLEANING COMPLETED")
        self.logger.info(f"Cleaned {constituents_count} constituent records")
        self.logger.info(f"Cleaned {emails_count} email records")
        self.logger.info(f"Cleaned {donations_count} donation records")
        self.logger.info("-" * 60)
    
    def log_transformation_start(self, total_constituents: int):
        """Log start of data transformation"""
        self.logger.info("STARTING DATA TRANSFORMATION TO Vendor FORMAT")
        self.logger.info(f"Processing {total_constituents} constituents")
        self.logger.info("-" * 60)
    
    def log_validation_failed_record(self, record_data: dict, errors: List[str], row_number: int):
        """Log a failed validation record with full details"""
        constituent_id = record_data.get('CB Constituent ID', 'Unknown')
        constituent_type = record_data.get('CB Constituent Type', 'Unknown')
        
        self.logger.error(f"VALIDATION FAILED - Row {row_number}")
        self.logger.error(f"CB Constituent ID: {constituent_id}")
        self.logger.error(f"CB Constituent Type: {constituent_type}")
        
        # Log specific validation errors
        self.logger.error("Validation Errors:")
        for i, error in enumerate(errors, 1):
            self.logger.error(f"  {i}. {error}")
        
        # Log full record data
        self.logger.error("Full Record Data:")
        for field, value in record_data.items():
            self.logger.error(f"  {field}: {value}")
        
        self.logger.error("-" * 60)
    
    def log_validation_summary(self, total_records: int, valid_records: int, invalid_records: int):
        """Log validation summary"""
        validation_rate = (valid_records / total_records * 100) if total_records > 0 else 0
        
        self.logger.info("VALIDATION SUMMARY")
        self.logger.info(f"Total records processed: {total_records}")
        self.logger.info(f"Valid records: {valid_records}")
        self.logger.info(f"Invalid records: {invalid_records}")
        self.logger.info(f"Validation success rate: {validation_rate:.2f}%")
        
        if invalid_records > 0:
            self.logger.warning(f"Found {invalid_records} records with validation errors")
            self.logger.warning("See detailed error logs above for specific issues")
        else:
            self.logger.info("All records passed validation successfully!")
    
    def log_session_end(self):
        """Log session end"""
        self.logger.info("="*80)
        self.logger.info("Vendor VALIDATION SESSION COMPLETED")
        self.logger.info(f"Detailed logs saved to: {self.log_filename}")
        self.logger.info("="*80)
    
    def get_log_filename(self) -> str:
        """Get the log filename"""
        return self.log_filename


class VendorValidator:
    """Main validator class that combines data transformation and validation with logging"""
    
    def __init__(self, log_prefix: str = "Vendor_validation"):
        """Initialize validator with logging"""
        self.logger = ValidationLogger(log_prefix)
        self.validation_errors = []
        self.valid_records = 0
        self.invalid_records = 0
    
    def validate_and_transform_data(self, constituents_df: pd.DataFrame, 
                                  emails_df: pd.DataFrame, 
                                  donations_df: pd.DataFrame,
                                  tag_mappings: Dict[str, str] = None) -> pd.DataFrame:
        """
        Complete data transformation and validation with logging
        
        Args:
            constituents_df: Input Constituents dataframe
            emails_df: Input Emails dataframe
            donations_df: Input Donation History dataframe
            tag_mappings: Dictionary mapping normalized tag names to mapped names (from API)
        
        Returns:
            DataFrame in Vendor output format with all records (valid and invalid)
        """
        
        # Step 1: Clean and combine data
        output_df = DataCombiner.combine_data(constituents_df, emails_df, donations_df, tag_mappings)
        
        # Log cleaning summary
        self.logger.log_cleaning_summary(len(constituents_df), len(emails_df), len(donations_df))
        
        # Log transformation start
        self.logger.log_transformation_start(len(constituents_df))
        
        # Step 2: Validate each output record
        print("Validating Vendor output records...")
        self.logger.logger.info("STARTING Vendor OUTPUT VALIDATION")
        
        for index, row in output_df.iterrows():
            row_data = row.to_dict()
            validation_errors = VendorValidationRules.validate_Vendor_row(row_data)
            
            if validation_errors:
                self.invalid_records += 1
                self.validation_errors.extend(validation_errors)
                # Log failed record with full details
                self.logger.log_validation_failed_record(row_data, validation_errors, index + 1)
            else:
                self.valid_records += 1
        
        # Step 3: Log validation summary
        total_records = len(output_df)
        self.logger.log_validation_summary(total_records, self.valid_records, self.invalid_records)
        
        # Console summary
        if self.invalid_records > 0:
            print(f"Validation completed with {self.invalid_records} failed records")
            print(f"Detailed error logs saved to: {self.logger.get_log_filename()}")
        else:
            print(f"All {total_records} records passed validation!")
        
        # End logging session
        self.logger.log_session_end()
        
        return output_df
    
    def get_validation_summary(self) -> dict:
        """Get validation summary statistics"""
        total_records = self.valid_records + self.invalid_records
        return {
            'total_records': total_records,
            'valid_records': self.valid_records,
            'invalid_records': self.invalid_records,
            'validation_rate': (self.valid_records / total_records * 100) if total_records > 0 else 0,
            'log_file': self.logger.get_log_filename()
        }
    
    def get_valid_records_only(self, output_df: pd.DataFrame) -> pd.DataFrame:
        """Filter and return only valid records from the output DataFrame"""
        valid_rows = []
        
        print("Filtering valid records...")
        
        for index, row in output_df.iterrows():
            row_data = row.to_dict()
            validation_errors = VendorValidationRules.validate_Vendor_row(row_data)
            
            # If no validation errors, include this record
            if not validation_errors:
                valid_rows.append(row_data)
        
        valid_df = pd.DataFrame(valid_rows)
        
        # Ensure all required columns exist in the same order as original
        if not valid_df.empty:
            valid_df = valid_df.reindex(columns=output_df.columns, fill_value="")
        
        print(f"Filtered {len(valid_df)} valid records from {len(output_df)} total records")
        
        return valid_df
    
    def generate_tag_summary_report(self, constituents_df: pd.DataFrame, tag_mappings: Dict[str, str] = None) -> pd.DataFrame:
        """
        Generate tag summary report by matching ORIGINAL INPUT tags against API and counting constituents
        
        Process:
        1. Read ORIGINAL tags from Input Constituents sheet (before mapping)
        2. Normalize and match against API's "name" field
        3. Count how many constituents have tags that match the API
        4. Show the API's "mapped_name" with the constituent count
        
        Args:
            constituents_df: Original Input Constituents dataframe (BEFORE transformation)
            tag_mappings: Dictionary of API tag mappings (normalized name -> mapped_name)
            
        Returns:
            DataFrame with columns: CB Tag Name (mapped_name), CB Tag Count
        """
        print("Generating tag summary report (matching original tags to API)...")
        
        if not tag_mappings:
            print("Warning: No API tag mappings available. Tag summary will be empty.")
            self.logger.logger.warning("No API tag mappings available for tag summary report")
            return pd.DataFrame(columns=["CB Tag Name", "CB Tag Count"])
        
        # Count constituents for each mapped tag name
        mapped_tag_counts = {}
        
        # Iterate through original constituent records
        for index, row in constituents_df.iterrows():
            original_tags_str = row.get("Tags", "")
            
            # Skip empty tags
            if not original_tags_str or str(original_tags_str).strip() == "" or str(original_tags_str).strip().lower() == "nan":
                continue
            
            # Split original tags by comma
            original_tags = [tag.strip() for tag in str(original_tags_str).split(',') if tag.strip()]
            
            # Track which mapped tags this constituent has (use set to avoid double-counting)
            constituent_mapped_tags = set()
            
            for original_tag in original_tags:
                if not original_tag:
                    continue
                
                # Normalize the original tag (lowercase, trim) to match against API
                normalized_tag = original_tag.lower().strip()
                
                # Check if this original tag exists in the API mappings
                if normalized_tag in tag_mappings:
                    # Get the mapped name from API
                    mapped_name = tag_mappings[normalized_tag]
                    constituent_mapped_tags.add(mapped_name)
            
            # Count this constituent for each unique mapped tag they have
            for mapped_tag in constituent_mapped_tags:
                mapped_tag_counts[mapped_tag] = mapped_tag_counts.get(mapped_tag, 0) + 1
        
        # Convert to dataframe and sort by count (descending)
        tag_summary_data = [
            {"CB Tag Name": tag, "CB Tag Count": count}
            for tag, count in sorted(mapped_tag_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        tag_summary_df = pd.DataFrame(tag_summary_data)
        
        # If no tags found, create empty dataframe with correct columns
        if tag_summary_df.empty:
            tag_summary_df = pd.DataFrame(columns=["CB Tag Name", "CB Tag Count"])
            print("No original tags matched the API mappings")
        else:
            print(f"Tag summary report generated: {len(tag_summary_df)} unique API-mapped tags found")
        
        self.logger.logger.info(f"Tag summary report: {len(tag_summary_df)} API-mapped tags identified from original data")
        
        # Log all mapped tags with counts
        if not tag_summary_df.empty:
            self.logger.logger.info("API-Mapped Tags by Constituent Count (from original tags):")
            for idx, row in tag_summary_df.iterrows():
                self.logger.logger.info(f"  {row['CB Tag Name']}: {row['CB Tag Count']} constituents")
        
        return tag_summary_df


class ValidationSummary(BaseModel):
    """Model for validation summary information"""
    total_records: int
    valid_records: int
    invalid_records: int
    validation_errors: List[str] = Field(default_factory=list)
    
    @property
    def validation_rate(self) -> float:
        """Calculate validation success rate"""
        if self.total_records == 0:
            return 0.0
        return (self.valid_records / self.total_records) * 100


# Export commonly used classes and functions
__all__ = [
    'InputSheets',
    'VendorOutputColumns',
    'FieldMappingRules',
    'VendorValidationRules',
    'DataCleaner',
    'DataCombiner',
    'ValidationLogger',
    'VendorValidator',
    'ValidationSummary'
]

