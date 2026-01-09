# Data Engineering Task - Excel Data Validation & CueBox Transformation

A Python-based data validation and transformation pipeline that validates input Excel data against Pydantic schemas and transforms it into CueBox output format with comprehensive error logging and email reporting.

## Table of Contents
- [Overview](#overview)
- [Workflow](#workflow)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Output Files](#output-files)

## Overview

This project processes Excel files containing constituent, email, and donation data. It performs:
1. **Metadata Validation**: Validates input data structure and content
2. **Data Transformation**: Combines data from multiple sheets into CueBox format
3. **Quality Assurance**: Validates transformed records and separates valid/invalid data
4. **Automated Reporting**: Sends email reports with validation logs and output files

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     START: main.py                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Metadata Validation (audit_metadata.py)               │
│  ─────────────────────────────────────────────────────          │
│  • Validate Excel file structure                                │
│  • Check for 3 required sheets:                                 │
│    - Input Constituents                                         │
│    - Input Emails                                               │
│    - Input Donation History                                     │
│  • Validate column structures                                   │
│  • Validate data types using Pydantic models                    │
│  • Log any validation errors                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
                    ┌────────┐
                    │ Errors?│
                    └───┬────┘
                        │
            ┌───────────┴───────────┐
            │                       │
           YES                     NO
            │                       │
            ▼                       ▼
┌───────────────────────┐  ┌──────────────────────────────────────┐
│ STOP & SEND EMAIL     │  │ STEP 2: Load Data for Transformation│
│ ─────────────────     │  │ ──────────────────────────────────   │
│ Attachments:          │  │ • Load constituents DataFrame        │
│ - metadata_log.log    │  │ • Load emails DataFrame              │
│                       │  │ • Load donations DataFrame           │
│ Workflow STOPS here   │  └──────────────┬───────────────────────┘
└───────────────────────┘                 │
                                          ▼
                         ┌────────────────────────────────────────┐
                         │ STEP 3: CueBox Transformation          │
                         │        (audit_data_fields.py)          │
                         │ ─────────────────────────────────────  │
                         │ • Clean and standardize data           │
                         │   - Trim whitespace                    │
                         │   - Standardize timestamps             │
                         │   - Convert nan to None                │
                         │ • Combine data from 3 sheets           │
                         │ • Map to CueBox output schema          │
                         │ • Validate each transformed record     │
                         │ • Log validation errors                │
                         └──────────────┬─────────────────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────────────────┐
                         │ STEP 4: Save Output Files              │
                         │ ─────────────────────────────          │
                         │ • CueBox_Complete_Output_[timestamp]   │
                         │   (all records)                        │
                         │ • CueBox_Clean_Records_[timestamp]     │
                         │   (valid records only)                 │
                         │ • cuebox_transformation_[timestamp].log│
                         │   (validation errors)                  │
                         └──────────────┬─────────────────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────────────────┐
                         │ STEP 5: Send Email Report              │
                         │ ─────────────────────────────          │
                         │ Attachments:                           │
                         │ - CueBox_Complete_Output.xlsx          │
                         │ - CueBox_Clean_Records.xlsx            │
                         │ - cuebox_transformation.log            │
                         │                                        │
                         │ (metadata log NOT included)            │
                         └──────────────┬─────────────────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────────────────┐
                         │         WORKFLOW COMPLETE              │
                         └────────────────────────────────────────┘
```

## Features

### 1. **Metadata Validation** (`audit_metadata.py`)
- Validates Excel file structure and sheet names
- Checks required columns in each sheet
- Validates data types and formats using Pydantic
- Identifies null/empty fields that should have values
- Creates detailed error logs with row-level information

### 2. **Data Transformation** (`audit_data_fields.py`)
- **Data Cleaning**:
  - Trims leading/trailing whitespace
  - Standardizes timestamps to `YYYY-MM-DD HH:MM:SS`
  - Converts pandas NaN to None for proper validation
- **Data Combination**: Merges data from 3 input sheets
- **CueBox Mapping**: Transforms data to CueBox output format
- **Validation**: Validates each transformed record
- **Error Logging**: Creates separate clean and complete output files

### 3. **Email Reporting**
- Conditional email sending based on validation results
- Metadata errors: Sends only metadata log
- Success: Sends CueBox outputs and transformation log
- Includes validation summary statistics

## Requirements

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`
- Gmail account with App Password enabled (for email functionality)
- Excel file with specific sheet structure

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd data_engineering_task
```

### 2. Install `uv` (if not already installed)

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Install Dependencies

```bash
uv sync
```

This will automatically install all required dependencies:
- pandas >= 2.0.0
- pydantic >= 2.0.0
- openpyxl >= 3.0.0
- python-dotenv >= 1.0.0

## Configuration

### 1. Create `.env` File

Create a `.env` file in the project root directory:

```bash
touch .env  # On Unix/macOS
# or
type nul > .env  # On Windows
```

### 2. Populate `.env` with Your Email Configuration

```env
# Email Configuration for Automated Reporting
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password-here
RECIPIENT_EMAIL=recipient-email@example.com

# SMTP Configuration (Gmail defaults)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### 3. Setting Up Gmail App Password

Since Gmail doesn't allow regular passwords for third-party apps, you need to create an App Password:

1. Go to your Google Account settings
2. Navigate to **Security** → **2-Step Verification** (enable if not already enabled)
3. Scroll down to **App passwords**
4. Select **Mail** and your device
5. Copy the generated 16-character password
6. Paste it as `SENDER_PASSWORD` in your `.env` file

**Important**: Use the 16-character App Password, NOT your regular Gmail password.

### 4. Update Excel File Path

In `main.py`, update the Excel file path (line 9):

```python
excel_file_path = r"C:\path\to\your\Excel\file.xlsx"
```

### 5. Enable/Disable Email Sending

In `main.py` (line 12):

```python
send_email = True   # Set to False to disable email sending
```

## Usage

### Run the Data Processing Pipeline

```bash
uv run python main.py
```

### Expected Output

**Console Output:**
```
Starting Data Processing Workflow
============================================================
STEP 1: Metadata Validation (Input Data)
This step validates the structure and quality of input data.
If ANY errors are found, the process will stop here.
------------------------------------------------------------
Loading required input sheets...
All 3 required input sheets found: ['Input Constituents', 'Input Emails', 'Input Donation History']
...
============================================================
METADATA VALIDATION PASSED!
============================================================
...
COMPLETE WORKFLOW FINISHED SUCCESSFULLY!
============================================================
```

## Project Structure

```
data_engineering_task/
│
├── main.py                    # Main entry point - orchestrates workflow
├── audit_metadata.py          # Input data validation module
├── audit_data_fields.py       # CueBox transformation & validation
├── pyproject.toml             # Project dependencies
├── .env                       # Email configuration (create this)
├── README.md                  # This file
│
├── validation_errors_*.log    # Metadata validation logs (if errors)
├── cuebox_transformation_*.log # CueBox validation logs
├── CueBox_Complete_Output_*.xlsx    # All transformed records
└── CueBox_Clean_Records_*.xlsx      # Valid records only
```

## Output Files

### If Metadata Validation Fails:
- `validation_errors_[timestamp].log` - Detailed metadata errors
- Email sent with metadata log attached
- Workflow stops (no CueBox transformation)

### If Metadata Validation Passes:
- `CueBox_Complete_Output_[timestamp].xlsx` - All transformed records
- `CueBox_Clean_Records_[timestamp].xlsx` - Only valid records
- `cuebox_transformation_[timestamp].log` - Transformation validation errors
- Email sent with all 3 files above (metadata log NOT included)

## Input Data Requirements

Your Excel file must contain these 3 sheets with the following columns:

### 1. Input Constituents
- Patron ID
- First Name
- Last Name
- Primary Email
- Phone Number
- Address
- City
- State
- Zip Code
- Country
- Preferred Language
- Organization

### 2. Input Emails
- Patron ID
- Email
- Email Type

### 3. Input Donation History
- Patron ID
- Donation Amount
- Donation Date
- Payment Method
- Campaign
- Status

## Troubleshooting

### Email Not Sending
1. Verify `.env` file exists and has correct values
2. Ensure you're using Gmail App Password (not regular password)
3. Check that 2-Step Verification is enabled on your Google account
4. Verify SMTP settings are correct

### File Not Found Error
1. Check the Excel file path in `main.py` (line 9)
2. Ensure the file exists at the specified location
3. Use raw string (prefix with `r`) for Windows paths

### Validation Errors
1. Check that all 3 required sheets exist in your Excel file
2. Verify column names match exactly (case-sensitive)
3. Review the generated log files for specific error details

## License

This project is licensed under the MIT License.

## Contact

For questions or issues, please contact the development team.

