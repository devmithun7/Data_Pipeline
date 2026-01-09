from audit_metadata import DataValidator, EmailConfig
from audit_data_fields import CueBoxValidator, InputSheets
import pandas as pd
import os


def main():
    """Complete data processing workflow with conditional execution based on metadata validation"""
    excel_file_path = r"C:\Users\devmi\Downloads\Copy of Data Import Assignment.xlsx"
    
    # Email configuration - set send_email=True to enable email sending
    send_email = True  # Email enabled - requires .env file with email settings
    
    try:
        print("Starting Data Processing Workflow")
        print("="*60)
        
        # Step 1: Metadata Validation (Critical - Must Pass)
        print("STEP 1: Metadata Validation (Input Data)")
        print("This step validates the structure and quality of input data.")
        print("If ANY errors are found, the process will stop here.")
        print("-"*60)
        
        metadata_validator = DataValidator(excel_file_path)
        metadata_validator.run_validation(send_email=False)  # Don't send email yet
        
        # Check if there were any validation errors in metadata
        has_metadata_errors = metadata_validator.has_validation_errors()
        
        print("\n" + "="*60)
        
        if has_metadata_errors:
            # STOP HERE - Metadata has errors
            print("METADATA VALIDATION FAILED!")
            print("="*60)
            print("Critical errors found in input data (metadata).")
            print("CueBox transformation will NOT be executed.")
            print("Please fix the input data issues before proceeding.")
            print("="*60)
            
            # Send email with metadata validation errors only
            if send_email:
                print("\nSending Metadata Validation Error Report...")
                success = metadata_validator.send_email_report()
                
                if success:
                    print(f"Metadata error report sent successfully")
                    print(f"   {os.path.basename(metadata_validator.log_filename)}")
                else:
                    print("Failed to send email report")
            
            print("\n" + "="*60)
            print("WORKFLOW STOPPED DUE TO METADATA ERRORS")
            print("="*60)
            return  # Exit here - do not proceed to CueBox transformation
        
        # If we reach here, metadata validation passed - proceed to CueBox transformation
        print("METADATA VALIDATION PASSED!")
        print("="*60)
        print("All input data is valid. Proceeding to CueBox transformation...")
        print("="*60)
        
        # Step 2: Load data for CueBox transformation
        print("\nSTEP 2: Loading Data for CueBox Transformation")
        constituents_df = pd.read_excel(excel_file_path, sheet_name=InputSheets.INPUT_CONSTITUENTS.value)
        emails_df = pd.read_excel(excel_file_path, sheet_name=InputSheets.INPUT_EMAILS.value)
        donations_df = pd.read_excel(excel_file_path, sheet_name=InputSheets.INPUT_DONATION_HISTORY.value)
        
        print(f"Loaded {len(constituents_df)} constituents")
        print(f"Loaded {len(emails_df)} email records")
        print(f"Loaded {len(donations_df)} donation records")
        
        print("\n" + "="*60)
        
        # Step 3: CueBox Transformation and Validation
        print("STEP 3: CueBox Data Transformation & Validation")
        cuebox_validator = CueBoxValidator("cuebox_transformation")
        
        # Transform and validate data (includes cleaning, combining, and validation)
        output_df = cuebox_validator.validate_and_transform_data(
            constituents_df, emails_df, donations_df
        )
        
        # Step 4: Save CueBox output files
        print("\n" + "="*60)
        print("STEP 4: Saving CueBox Output Files")
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        
        # Save complete output (all records)
        complete_filename = f"CueBox_Complete_Output_{timestamp}.xlsx"
        output_df.to_excel(complete_filename, index=False)
        print(f"Complete CueBox output saved to: {complete_filename}")
        
        # Filter and save only valid records
        valid_records_df = cuebox_validator.get_valid_records_only(output_df)
        clean_filename = f"CueBox_Clean_Records_{timestamp}.xlsx"
        valid_records_df.to_excel(clean_filename, index=False)
        print(f"Clean records only saved to: {clean_filename}")
        print(f"Clean file contains {len(valid_records_df)} valid records out of {len(output_df)} total")
        
        # Step 5: Final Summary
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        summary = cuebox_validator.get_validation_summary()
        print(f"Total records processed: {summary['total_records']}")
        print(f"Valid records: {summary['valid_records']}")
        print(f"Invalid records: {summary['invalid_records']}")
        print(f"Validation success rate: {summary['validation_rate']:.2f}%")
        print(f"CueBox validation log: {summary['log_file']}")
        print(f"Complete output file: {complete_filename}")
        print(f"Clean records file: {clean_filename}")
        
        # Step 6: Send email with CueBox results and output files
        if send_email:
            print("\n" + "="*60)
            print("STEP 6: Sending CueBox Results Report")
            
            # Prepare list of files to attach (CueBox output and logs)
            attachments = [
                complete_filename,  # Complete CueBox output
                clean_filename,     # Clean records only
                cuebox_validator.logger.get_log_filename()  # CueBox validation log
            ]
            
            # Send comprehensive email with CueBox results and summary (without metadata log since it passed)
            success = metadata_validator.send_email_report(
                additional_attachments=attachments,
                cuebox_summary=summary,
                include_metadata_log=False  # Don't include metadata log when it passed without errors
            )
            
            if success:
                print("CueBox results sent successfully with attachments:")
                print(f"   {os.path.basename(complete_filename)}")
                print(f"   {os.path.basename(clean_filename)}")
                print(f"   {os.path.basename(cuebox_validator.logger.get_log_filename())}")
            else:
                print("Failed to send email report")
        
        print("\n" + "="*60)
        print("COMPLETE WORKFLOW FINISHED SUCCESSFULLY!")
        print("="*60)
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure the Excel file exists at the specified path.")
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
