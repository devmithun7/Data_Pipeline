from audit_metadata import DataValidator, EmailConfig
from audit_data_fields import VendorValidator, InputSheets
import pandas as pd
import os
import gdown
from dotenv import load_dotenv

load_dotenv()


def download_from_google_drive(file_id, output_path):
    try:
        print(f"Downloading file from Google Drive...")
        print(f"File ID: {file_id}")
        
        url = f"https://drive.google.com/uc?id={file_id}&export=download"
        
        print("Downloading file...")
        gdown.download(url, output_path, quiet=False, fuzzy=True)
        print(f"File downloaded successfully to: {output_path}")
        return output_path
            
    except Exception as e:
        print(f"Error downloading from Google Drive: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure the file sharing is set to 'Anyone with the link can view'")
        print("2. Verify the file ID is correct")
        print("3. Check your internet connection")
        raise


def extract_file_id_from_url(url):
    import re
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None


def main():
    local_file_path = os.getenv("LOCAL_FILE_PATH")
    gdrive_url = os.getenv("GDRIVE_URL")
    gdrive_file_id = os.getenv("GDRIVE_FILE_ID")
    
    if local_file_path and os.path.exists(local_file_path):
        print(f"Using local file: {local_file_path}")
        excel_file_path = local_file_path
    elif gdrive_url:
        file_id = extract_file_id_from_url(gdrive_url)
        if not file_id:
            print("ERROR: Could not extract file ID from GDRIVE_URL")
            return
        print("Downloading input file from Google Drive")
        print(f"URL: {gdrive_url}")
        print(f"File ID: {file_id}")
        print("="*60)
        excel_file_path = "input_data.xlsx"
        download_from_google_drive(file_id, excel_file_path)
        print("="*60)
    elif gdrive_file_id:
        print("Downloading input file from Google Drive")
        print("="*60)
        excel_file_path = "input_data.xlsx"
        download_from_google_drive(gdrive_file_id, excel_file_path)
        print("="*60)
    else:
        print("ERROR: No input file configured")
        print("Either set LOCAL_FILE_PATH, GDRIVE_URL, or GDRIVE_FILE_ID in .env file")
        return
    
    send_email = True
    
    try:
        print("Starting Data Processing Workflow")
        print("="*60)
        
        print("STEP 1: Metadata Validation (Input Data)")
        print("This step validates the structure and quality of input data.")
        print("If ANY errors are found, the process will stop here.")
        print("-"*60)
        
        metadata_validator = DataValidator(excel_file_path)
        metadata_validator.run_validation(send_email=False)
        
        has_metadata_errors = metadata_validator.has_validation_errors()
        
        print("\n" + "="*60)
        
        if has_metadata_errors:
            print("METADATA VALIDATION FAILED!")
            print("="*60)
            print("Critical errors found in input data (metadata).")
            print("Vendor transformation will NOT be executed.")
            print("Please fix the input data issues before proceeding.")
            print("="*60)
            
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
            return
        
        print("METADATA VALIDATION PASSED!")
        print("="*60)
        print("All input data is valid. Proceeding to Vendor transformation...")
        print("="*60)
        
        print("\nSTEP 2: Loading Data for Vendor Transformation")
        constituents_df = pd.read_excel(excel_file_path, sheet_name=InputSheets.INPUT_CONSTITUENTS.value, engine='openpyxl')
        emails_df = pd.read_excel(excel_file_path, sheet_name=InputSheets.INPUT_EMAILS.value, engine='openpyxl')
        donations_df = pd.read_excel(excel_file_path, sheet_name=InputSheets.INPUT_DONATION_HISTORY.value, engine='openpyxl')
        
        print(f"Loaded {len(constituents_df)} constituents")
        print(f"Loaded {len(emails_df)} email records")
        print(f"Loaded {len(donations_df)} donation records")
        
        print("\n" + "="*60)
        
        print("STEP 3: Vendor Data Transformation & Validation")
        Vendor_validator = VendorValidator("Vendor_transformation")
        
        tag_mappings = metadata_validator.get_tag_mappings()
        if tag_mappings:
            print(f"Using {len(tag_mappings)} tag mappings from API for transformation")
        else:
            print("No tag mappings available - tags will not be transformed")
        
        output_df = Vendor_validator.validate_and_transform_data(
            constituents_df, emails_df, donations_df, tag_mappings
        )
        
        print("\n" + "="*60)
        print("STEP 4: Saving Vendor Output Files")
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        
        complete_filename = f"Constituent_Unclean_{timestamp}.xlsx"
        output_df.to_excel(complete_filename, index=False)
        print(f"Complete Vendor output saved to: {complete_filename}")
        
        valid_records_df = Vendor_validator.get_valid_records_only(output_df)
        clean_filename = f"Constituent_Clean_{timestamp}.xlsx"
        valid_records_df.to_excel(clean_filename, index=False)
        print(f"Clean records only saved to: {clean_filename}")
        print(f"Clean file contains {len(valid_records_df)} valid records out of {len(output_df)} total")
        
        all_records_tag_df, clean_records_tag_df = Vendor_validator.generate_tag_summary_report(
            constituents_df, tag_mappings, output_df
        )
        
        tag_summary_filename = f"Constituent_tag_count_{timestamp}.xlsx"
        with pd.ExcelWriter(tag_summary_filename, engine='openpyxl') as writer:
            all_records_tag_df.to_excel(writer, sheet_name='All Records', index=False)
            clean_records_tag_df.to_excel(writer, sheet_name='Clean Records', index=False)
        
        print(f"Tag summary report saved to: {tag_summary_filename}")
        print(f"  - All Records: {len(all_records_tag_df)} unique API-mapped tags")
        print(f"  - Clean Records: {len(clean_records_tag_df)} unique API-mapped tags")
        
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        summary = Vendor_validator.get_validation_summary()
        print(f"Total records processed: {summary['total_records']}")
        print(f"Valid records: {summary['valid_records']}")
        print(f"Invalid records: {summary['invalid_records']}")
        print(f"Validation success rate: {summary['validation_rate']:.2f}%")
        print(f"Vendor validation log: {summary['log_file']}")
        print(f"Complete output file: {complete_filename}")
        print(f"Clean records file: {clean_filename}")
        print(f"Tag summary file: {tag_summary_filename}")
        
        if send_email:
            print("\n" + "="*60)
            print("STEP 6: Sending Vendor Results Report")
            
            attachments = [
                complete_filename,
                clean_filename,
                tag_summary_filename,
                Vendor_validator.logger.get_log_filename()
            ]
            
            success = metadata_validator.send_email_report(
                additional_attachments=attachments,
                vendor_summary=summary,
                include_metadata_log=False
            )
            
            if success:
                print("Vendor results sent successfully with attachments:")
                print(f"   {os.path.basename(complete_filename)}")
                print(f"   {os.path.basename(clean_filename)}")
                print(f"   {os.path.basename(tag_summary_filename)}")
                print(f"   {os.path.basename(Vendor_validator.logger.get_log_filename())}")
            else:
                print("Failed to send email report")
        
       
        print("COMPLETE WORKFLOW FINISHED SUCCESSFULLY!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure the Excel file exists at the specified path.")
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

