# Data Engineering Task - Excel Data Validation & Vendor Transformation

A Python-based data validation and transformation pipeline for onboarding client constituent and donation data into Vendor with automated quality assurance and email reporting.
Documentation: https://devmithun7.github.io/codelab/#0

## Table of Contents
- [Overview](#overview)
- [Project Architecture](#project-architecture)
- [Key Validations](#key-validations)
- [Installation & Setup](#installation--setup)
- [Usage](#usage)
- [Output Files](#output-files)

## Overview

This project transforms three Excel spreadsheets from a client's legacy system into validated, Vendor-compatible output files ready for client sign-off and import.

**Business Context**: Client manages constituent relationships (individuals and companies) for fundraising and marketing. Data accuracy is critical for donor engagement.

**Input Data Sources**:
- **Input Constituents**: Patron demographic and contact information
- **Input Emails**: Additional email addresses
- **Input Donation History**: Donation transaction records

**Deliverables**:
1. **Vendor Complete Output**: All transformed records (valid + invalid)
2. **Vendor Clean Records**: Production-ready validated records only
3. **Validation Logs**: Detailed error reports for data quality issues
4. **Email Reports**: Automated notifications with results and attachments

## Project Architecture

### Two-Phase Audit Approach

This architecture implements a **fail-fast, resource-optimized** validation strategy:

**Phase 1: Metadata Validation** (Schema Audit)
- **Purpose**: Detect schema drift and structural mismatches early
- **Performance**: O(n) - Fast, lightweight validation
- **Validates**: File structure, column schema, basic data types
- **On Failure**: Immediate stop, email notification, no further processing

**Phase 2: Business Rules Validation** (Field-Level Audit)
- **Purpose**: Enforce Vendor-specific business logic
- **Performance**: O(n × m) - Comprehensive field-level validation
- **Validates**: Business rules, cross-field logic, data relationships
- **On Completion**: Separates valid/invalid records, sends complete results

### Architecture Flow

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
                ║  • Map to Vendor output schema                         ║
                ║  • Calculate derived fields (donations, background)    ║
                ║                                                        ║
                ║  Field-Level Validations:                              ║
                ║  ✓ Constituent type logic (Person/Company)             ║
                ║  ✓ Name requirements based on type                     ║
                ║  ✓ Email format validation                             ║
                ║  ✓ Required Vendor fields populated                    ║
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
            │                  │  │ Vendor import   │  │ For debugging  │
            └──────────────────┘  └─────────────────┘  └────────────────┘
                        │                    │                    │
                        └────────────────────┼────────────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────────────┐
                                  │  EMAIL NOTIFICATION         │
                                  │  ──────────────────────     │
                                  │  Attachments:               │
                                  │  • Complete output file     │
                                  │  • Clean records file       │
                                  │  • Validation log           │
                                  │                             │
                                  │  Includes validation stats  │
                                  └─────────────────────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────────────┐
                                  │  CLIENT REVIEW & SIGN-OFF   │
                                  │  Ready for Vendor Import    │
                                  └─────────────────────────────┘
```

### Architecture Benefits

1. **Performance Optimization**: Fast structural checks before expensive processing
2. **Early Failure Detection**: Catch schema drift immediately  
3. **Resource Efficiency**: Don't transform data that won't pass basic checks
4. **Clear Error Reporting**: Different error types handled appropriately
5. **Client-Friendly**: Valid data can be imported while invalid data is reviewed

## Key Validations

### Phase 1: Metadata Validation
- **File Structure**: 3 required sheets exist ("Input Constituents", "Input Emails", "Input Donation History")
- **Column Schema**: All required columns present in each sheet
- **Data Types**: Patron IDs are integers, dates are parseable, emails have valid format
- **Null Handling**: Required fields contain values

### Phase 2: Business Rules Validation
- **Constituent Type**: Correctly determined as "Person" or "Company" based on data
- **Name Requirements**: Person requires First/Last Name; Company requires Company Name
- **Email Validation**: Valid email format if present (optional field)
- **Background Information**: Formatted as "Job Title: [value]; Marital Status: [value]"
- **Donation Aggregation**: Accurate lifetime amount, recent date/amount calculations
- **Data Cleaning**: Whitespace trimmed, timestamps standardized to YYYY-MM-DD HH:MM:SS

### Validation Output
```
Validation Success Rate = (Valid Records / Total Records) × 100

Example:
- Total: 150 records
- Valid: 148 records  
- Invalid: 2 records
- Success Rate: 98.67%
```

## Installation & Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd data_engineering_task
```

### 2. Install uv Package Manager

**Windows:**
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

Dependencies installed:
- `pandas` >= 2.0.0
- `pydantic` >= 2.0.0  
- `openpyxl` >= 3.0.0
- `python-dotenv` >= 1.0.0

### 4. Configure Email Settings

Create `.env` file in project root:

```env
# Email Configuration
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-16-char-app-password
RECIPIENT_EMAIL=recipient@example.com

# SMTP Configuration (Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

**Gmail App Password Setup**:
1. Go to Google Account → Security → 2-Step Verification (enable it)
2. Navigate to App passwords
3. Generate password for "Mail"
4. Copy 16-character password to `.env`

⚠️ **Important**: Use App Password, NOT your regular Gmail password!

## Usage

### Run the Pipeline

```bash
uv run python main.py
```

### Console Output

**Metadata Validation (Phase 1):**
```
Starting Data Processing Workflow
============================================================
STEP 1: Metadata Validation (Input Data)
------------------------------------------------------------
Loading required input sheets...
All 3 required input sheets found
Loaded 150 constituents
Loaded 250 email records  
Loaded 500 donation records
Validating input data with Pydantic models...
============================================================
METADATA VALIDATION PASSED!
============================================================
```

**Vendor Transformation (Phase 2):**
```
STEP 3: Vendor Data Transformation & Validation
Cleaning and standardizing input data...
Validating Vendor output records...
Validation completed with 2 failed records

FINAL SUMMARY
Total records processed: 150
Valid records: 148
Invalid records: 2
Validation success rate: 98.67%

COMPLETE WORKFLOW FINISHED SUCCESSFULLY!
============================================================
```

## Output Files

### If Metadata Validation Fails (Phase 1):
- `validation_errors_[timestamp].log` - Metadata errors only
- **Email**: Metadata log attached
- **Workflow**: Stops immediately

### If Metadata Validation Passes (Phase 2):
- `Vendor_Complete_Output_[timestamp].xlsx` - All records (valid + invalid)
- `Vendor_Clean_Records_[timestamp].xlsx` - Valid records only (import this)
- `Vendor_transformation_[timestamp].log` - Field-level validation errors
- **Email**: All 3 files attached with validation statistics

## Project Structure

```
data_engineering_task/
│
├── main.py                          # Workflow orchestration
├── audit_metadata.py                # Phase 1: Metadata validation
├── audit_data_fields.py             # Phase 2: Business rules validation
│
├── pyproject.toml                   # Dependencies
├── .env                             # Email config (create this)
├── README.md                        # This file
│
├── validation_errors_*.log          # Phase 1 logs (if errors)
├── Vendor_transformation_*.log      # Phase 2 logs
├── Vendor_Complete_Output_*.xlsx    # All records
└── Vendor_Clean_Records_*.xlsx      # Valid records only
```

## Troubleshooting

**Email not sending?**
- Verify `.env` exists with correct App Password (16 characters)
- Confirm 2-Step Verification enabled on Gmail
- Check SMTP settings: smtp.gmail.com:587

**File not found?**
- Update file path in `main.py` line 9
- Use raw string: `r"C:\Users\..."`
- Ensure file has `.xlsx` extension

**Validation errors?**
- Check sheet names match exactly (case-sensitive)
- Verify all required columns present
- Review log files for specific errors
- Close Excel files before running

**Windows users**: Close ALL Excel files before running the pipeline!

## License

This project is licensed under the MIT License.

## Contact

For questions or issues, please contact the development team.

