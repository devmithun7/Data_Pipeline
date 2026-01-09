# Data Engineering Task - Excel Data Validation & CueBox Transformation

A Python-based data validation and transformation pipeline that validates input Excel data against Pydantic schemas and transforms it into CueBox output format with comprehensive error logging and email reporting.

## Table of Contents
- [Overview](#overview)
- [Project Architecture](#project-architecture)
- [Features](#features)
- [Testing & Validation](#testing--validation)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Output Files](#output-files)

## Overview

This project is a data migration and transformation pipeline designed to onboard a new client's constituent and donation data into the CueBox system. The client is transitioning from their legacy software system and needs their historical data properly formatted and validated before import.

### Business Context

The client organization manages relationships with constituents—individuals and companies who attend their events and make donations. This data is critical to their operations as it drives:

- **Marketing outreach campaigns**
- **Fundraising initiatives**
- **Donor relationship management**
- **Event planning and engagement**

Given the sensitivity and importance of this data, accuracy and data quality are paramount. Any errors in the migration could impact the client's ability to effectively engage with their supporters.

### Project Objective

Transform three input spreadsheets exported from the client's legacy system into validated, CueBox-compatible output files that meet the following criteria:

1. **Data Accuracy**: All constituent, email, and donation records are correctly mapped and transformed
2. **Data Quality**: Invalid or problematic records are identified, logged, and separated from clean data
3. **Client Approval**: Output files are ready for client review and sign-off before final import
4. **Audit Trail**: Comprehensive logging ensures transparency and allows for issue resolution

### Input Data Sources

The client has provided three spreadsheets exported from their current system:

- **Input Constituents**: Patron demographic and contact information
- **Input Emails**: Additional email addresses associated with patrons
- **Input Donation History**: Complete donation transaction records

### Deliverables

This pipeline produces:

1. **CueBox Complete Output**: All transformed records with validation status flags
2. **CueBox Clean Records**: Production-ready data containing only validated records
3. **Validation Logs**: Detailed error reports for any data quality issues requiring attention
4. **Email Reports**: Automated notifications with validation results and attached files

### Quality Assurance Approach

The system implements a two-stage validation process:

- **Stage 1 - Metadata Validation**: Ensures input data structure and content meet basic requirements. If this stage fails, the process stops to prevent propagating bad data.
  
- **Stage 2 - Transformation Validation**: Validates the CueBox-formatted output records against business rules, separating valid records from those requiring manual review.

This approach ensures that only high-quality, validated data is presented to the client for final approval and import into CueBox.

## Project Architecture

### Design Philosophy: Two-Phase Audit Approach

This project implements a **two-phase audit architecture** designed to efficiently catch data quality issues at different levels of granularity. This approach optimizes both computational resources and error detection.

### Phase 1: Metadata Validation (Schema Audit)
**Purpose**: Detect schema drift and structural mismatches early

This lightweight phase validates:
- Excel file structure (sheet names, file format)
- Column schema (required columns present, naming conventions)
- Basic data types (integers, strings, dates)
- Required field presence

**Why First?**
- **Fast execution**: Structural validation requires minimal compute resources
- **Fail-fast principle**: Catches fundamental issues before expensive transformations
- **Schema drift detection**: Identifies when client's export format has changed
- **Resource optimization**: Prevents processing millions of records if structure is wrong

**Performance**: O(n) complexity where n = number of rows, but only validates structure

### Phase 2: Business Rules Validation (Field-Level Audit)
**Purpose**: Enforce domain-specific business logic and data quality rules

This comprehensive phase validates:
- Field-level business rules (email formats, required names for persons vs companies)
- Cross-field logic (constituent type determines required fields)
- Data relationships (referential integrity across sheets)
- CueBox-specific requirements (output format compliance)

**Why Second?**
- **Computation-intensive**: Validates each field against business rules
- **Transformation validation**: Ensures combined data meets target system requirements
- **Data quality assurance**: Catches semantic errors that pass structural validation

**Performance**: O(n × m) complexity where n = records, m = validation rules per record

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INPUT: Excel File                              │
│              (Constituents + Emails + Donations)                        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
        ╔═══════════════════════════════════════════════════════╗
        ║  PHASE 1: METADATA VALIDATION (audit_metadata.py)     ║
        ║  ─────────────────────────────────────────────────    ║
        ║  Purpose: Schema Drift Detection                      ║
        ║  Complexity: O(n) - Fast & Lightweight                ║
        ╠═══════════════════════════════════════════════════════╣
        ║  Validations:                                         ║
        ║  ✓ File structure (3 required sheets exist)           ║
        ║  ✓ Column schema (all required columns present)       ║
        ║  ✓ Basic data types (IDs are integers, etc.)          ║
        ║  ✓ Required fields not null                           ║
        ║                                                       ║
        ║  Resources: Minimal compute, quick validation         ║
        ╚═══════════════════════════════════════════════════════╝
                                │
                                ▼
                        ┌───────────────┐
                        │  Any Schema   │
                        │  Mismatches?  │
                        └───────┬───────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                   YES                     NO
                    │                       │
                    ▼                       ▼
    ┌──────────────────────────┐  ┌──────────────────────────┐
    │  STOP PROCESSING         │  │  PROCEED TO PHASE 2      │
    │  ────────────────        │  │  ───────────────         │
    │  • Log schema errors     │  │  All structural checks   │
    │  • Generate error report │  │  passed - safe to        │
    │  • Email notification    │  │  proceed with expensive  │
    │    - Subject: Metadata   │  │  transformation          │
    │      Validation Failed   │  └──────────┬───────────────┘
    │    - Attach: error log   │             │
    │  • Workflow TERMINATES   │             │
    │                          │             ▼
    │  Reason: No point in     │  ┌─────────────────────────────────────┐
    │  expensive processing    │  │  Data Loading & Cleaning            │
    │  if structure is wrong   │  │  ────────────────────────           │
    └──────────────────────────┘  │  • Load validated DataFrames        │
                                  │  • Trim whitespace                  │
                                  │  • Standardize timestamps           │
                                  │  • Convert NaN to None              │
                                  └──────────────┬──────────────────────┘
                                                 │
                                                 ▼
                ╔════════════════════════════════════════════════════════╗
                ║  PHASE 2: BUSINESS RULES VALIDATION                    ║
                ║         (audit_data_fields.py)                         ║
                ║  ─────────────────────────────────────────────────     ║
                ║  Purpose: Field-Level Data Quality Enforcement         ║
                ║  Complexity: O(n × m) - Comprehensive & Intensive      ║
                ╠════════════════════════════════════════════════════════╣
                ║  Transformations:                                      ║
                ║  • Combine data from 3 input sheets                    ║
                ║  • Map to CueBox output schema                         ║
                ║  • Calculate derived fields (donations, background)    ║
                ║                                                        ║
                ║  Field-Level Validations:                              ║
                ║  ✓ Constituent type logic (Person requires First/      ║
                ║    Last name, Company requires Company name)           ║
                ║  ✓ Email format validation                             ║ 
                ║  ✓ Required CueBox fields populated                    ║
                ║  ✓ Business rule compliance per field                  ║
                ║  ✓ Cross-field dependencies validated                  ║
                ║                                                        ║
                ║  Resources: Compute-intensive, detailed validation     ║
                ╚════════════════════════════════════════════════════════╝
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  Separate Valid/Invalid     │
                                  │  Records                    │
                                  └──────────┬──────────────────┘
                                             │
                        ┌────────────────────┼────────────────────┐
                        │                    │                    │
                        ▼                    ▼                    ▼
            ┌──────────────────┐  ┌─────────────────┐  ┌────────────────┐
            │ Complete Output  │  │ Clean Records   │  │ Validation Log │
            │ ──────────────── │  │ ─────────────── │  │ ─────────────  │
            │ ALL records      │  │ VALID records   │  │ Error details  │
            │ (valid+invalid)  │  │ only            │  │ for invalid    │
            │                  │  │                 │  │ records        │
            │ For audit trail  │  │ Ready for       │  │                │
            │                  │  │ CueBox import   │  │ For debugging  │
            └──────────────────┘  └─────────────────┘  └────────────────┘
                        │                    │                    │
                        └────────────────────┼────────────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────────────┐
                                  │  EMAIL NOTIFICATION         │
                                  │  ──────────────────────     │
                                  │  Subject: Data Processing   │
                                  │           Complete          │
                                  │                             │
                                  │  Attachments:               │
                                  │  • Complete output file     │
                                  │  • Clean records file       │
                                  │  • Validation log           │
                                  │                             │
                                  │  Includes:                  │
                                  │  • Validation statistics    │
                                  │  • Success rate %           │
                                  │  • Record counts            │
                                  └─────────────────────────────┘
                                               │
                                               ▼
                                  ┌─────────────────────────────┐
                                  │  CLIENT REVIEW & SIGN-OFF   │
                                  │  Ready for CueBox Import    │
                                  └─────────────────────────────┘
```

### Error Handling Strategy

**Phase 1 Failure**: 
- Workflow immediately terminates
- Email sent with metadata validation log only
- User must fix structural issues before retry
- Prevents wasting resources on fundamentally flawed data

**Phase 2 Completion**:
- Workflow completes regardless of validation errors
- Invalid records separated from valid records
- Email sent with both clean and complete outputs plus error log
- Client can review and decide how to handle invalid records
- Valid records can proceed to import while issues are resolved

### Benefits of This Architecture

1. **Performance Optimization**: Fast structural checks before expensive processing
2. **Early Failure Detection**: Catch schema drift immediately
3. **Resource Efficiency**: Don't transform data that won't pass basic checks
4. **Clear Separation of Concerns**: Structure vs. content validation
5. **Actionable Error Reports**: Different error types handled appropriately
6. **Client-Friendly**: Valid data can be imported while invalid data is reviewed

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

## Testing & Validation

This section documents all validation checks and tests performed during the data processing workflow. The validation strategy follows a two-phase approach to ensure comprehensive data quality assurance.

### Phase 1: Metadata Validation Tests (Schema-Level)

These tests run in `audit_metadata.py` and focus on structural integrity and basic data type validation.

#### 1.1 File Structure Validation
**Test**: Excel file contains exactly 3 required sheets

**Validation Logic**:
```python
Required sheets:
- "Input Constituents"
- "Input Emails"  
- "Input Donation History"
```

**Pass Criteria**: All 3 sheets exist with exact name matches (case-sensitive)

**Failure Impact**: Immediate workflow termination, email notification sent

---

#### 1.2 Column Schema Validation
**Test**: Each sheet contains all required columns

**Validation Logic**:

**Input Constituents** (11 required columns):
- Patron ID, First Name, Last Name, Date Entered, Primary Email
- Company, Salutation, Title, Tags, Gender, Marital Status

**Input Emails** (2 required columns):
- Patron ID, Email

**Input Donation History** (6 required columns):
- Patron ID, Donation Amount, Donation Date, Payment Method, Campaign, Status

**Pass Criteria**: All required columns present in each sheet (exact name match)

**Failure Impact**: Immediate workflow termination

---

#### 1.3 Data Type Validation (Pydantic Models)
**Test**: Field values conform to expected data types

**Constituent Records**:
- `Patron ID`: Must be positive integer
- `First Name, Last Name`: String (optional but validated if present)
- `Primary Email`: String (optional but validated format if present)
- `Date Entered`: Any date-compatible format
- `Title`: String (job title - used in background info)
- `Marital Status`: String (used in background info)

**Email Records**:
- `Patron ID`: Must be positive integer  
- `Email`: String (optional)

**Donation Records**:
- `Patron ID`: Must be positive integer
- `Donation Amount`: Numeric (validated if present)
- `Donation Date`: Any date-compatible format
- `Payment Method, Campaign, Status`: String (optional)

**Pass Criteria**: All field values match expected data types

**Failure Behavior**: Invalid records logged with full details, workflow continues

---

#### 1.4 Null/Empty Field Detection
**Test**: Identify records with missing critical data

**Validation Logic**: 
- Detects `NaN`, `None`, or empty string values in fields
- Converts pandas `NaN` to `None` for proper validation
- Logs records with missing required fields

**Pass Criteria**: All required fields contain non-null values

**Failure Behavior**: Records logged as validation warnings

---

### Phase 2: Business Rules Validation (Field-Level)

These tests run in `audit_data_fields.py` and enforce CueBox-specific business logic and data quality rules.

#### 2.1 Constituent Type Validation
**Test**: Determine and validate constituent type (Person vs Company)

**Validation Logic**:
```python
If "Company" field has value → Type = "Company"
Else if "First Name" OR "Last Name" has value → Type = "Person"  
Else → Default to "Person"
```

**Pass Criteria**: Valid constituent type assigned to each record

**Failure Impact**: Record flagged as invalid if type cannot be determined

---

#### 2.2 Name Field Validation (Type-Dependent)
**Test**: Required name fields based on constituent type

**Person Records**:
- `CB First Name`: REQUIRED (must not be empty)
- `CB Last Name`: REQUIRED (must not be empty)
- `CB Company Name`: Optional

**Company Records**:
- `CB Company Name`: REQUIRED (must not be empty)
- `CB First Name`: Optional
- `CB Last Name`: Optional

**Pass Criteria**: Required name fields populated based on constituent type

**Failure Impact**: Record marked as invalid and logged

---

#### 2.3 Constituent ID Validation
**Test**: Each record has a valid unique identifier

**Validation Logic**:
- `CB Constituent ID` must not be null or empty
- Must be a valid value that can identify the constituent

**Pass Criteria**: Valid ID present for each constituent

**Failure Impact**: Record marked as invalid

---

#### 2.4 Created At Timestamp Validation
**Test**: Validate and standardize date/time values

**Validation Logic**:
- Accepts various date formats
- Standardizes to `YYYY-MM-DD HH:MM:SS` format
- Handles null/empty values appropriately

**Pass Criteria**: Valid timestamp or empty (if acceptable)

**Failure Impact**: Warning logged if timestamp cannot be parsed

---

#### 2.5 Email Format Validation
**Test**: Validate email address formats

**Validation Logic**:
- `CB Email 1` and `CB Email 2` must be valid email formats (if present)
- Empty values allowed (emails are optional)
- Format: Must contain `@` and valid domain structure

**Pass Criteria**: Valid email format or empty

**Failure Behavior**: Invalid formats logged but workflow continues

---

#### 2.6 Background Information Formatting
**Test**: Properly format job title and marital status

**Validation Logic**:
```python
If both Title AND Marital Status present:
  → "Job Title: [Title]; Marital Status: [Status]"
  
If only Title present:
  → "Job Title: [Title]"
  
If only Marital Status present:
  → "Marital Status: [Status]"
  
If neither present:
  → "" (empty string)
```

**Pass Criteria**: Background information properly formatted

**Failure Impact**: N/A (formatting always succeeds)

---

#### 2.7 Donation Aggregation Validation
**Test**: Calculate accurate donation statistics per constituent

**Validation Logic**:
- `CB Lifetime Donation Amount`: Sum of all donations for constituent
- `CB Most Recent Donation Date`: Latest donation date
- `CB Most Recent Donation Amount`: Amount of most recent donation
- Handles constituents with zero donations (returns empty values)

**Pass Criteria**: Accurate donation calculations

**Failure Impact**: Empty values if calculations fail

---

#### 2.8 Data Cleaning Validations
**Test**: Standardize data before transformation

**Cleaning Operations**:
1. **Whitespace Trimming**: Remove leading/trailing spaces from all text fields
2. **NaN Conversion**: Convert pandas NaN to None for proper validation
3. **Timestamp Standardization**: Convert all dates to `YYYY-MM-DD HH:MM:SS`
4. **Empty String Handling**: Treat empty strings consistently

**Pass Criteria**: All data cleaned and standardized

**Failure Impact**: N/A (cleaning always attempted)

---

### Validation Summary Statistics

After both phases complete, the system generates:

```
Validation Success Rate = (Valid Records / Total Records) × 100

Example Output:
- Total records processed: 150
- Valid records: 148
- Invalid records: 2
- Validation success rate: 98.67%
```

### Test Output Files

**Metadata Validation Log** (`validation_errors_[timestamp].log`):
- Contains Phase 1 validation errors
- Only generated if metadata validation fails
- Includes row numbers, field values, and error descriptions

**CueBox Transformation Log** (`cuebox_transformation_[timestamp].log`):
- Contains Phase 2 validation errors
- Generated for every run
- Includes full record data and specific validation failures

**Complete Output** (`CueBox_Complete_Output_[timestamp].xlsx`):
- All records (both valid and invalid)
- Useful for audit trail and review

**Clean Output** (`CueBox_Clean_Records_[timestamp].xlsx`):
- Only valid records that passed all validations
- Ready for CueBox import

### Validation Error Reporting

**Error Log Format**:
```
ERROR - VALIDATION FAILED - Record #[row_number]
ERROR - Patron ID: [id]
ERROR - Constituent Type: [type]
ERROR - Validation Errors:
ERROR -   - [Specific error message 1]
ERROR -   - [Specific error message 2]
ERROR - Full Record Data:
ERROR -   [Complete record details]
------------------------------------------------------------
```

### QA Process

1. **Automated Validation**: All records automatically validated through both phases
2. **Separation of Concerns**: Valid and invalid records separated for review
3. **Detailed Logging**: Every validation error captured with context
4. **Email Notifications**: Stakeholders notified of validation results
5. **Manual Review**: Client reviews complete output and clean records before import

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


