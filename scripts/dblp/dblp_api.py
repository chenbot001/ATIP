import pandas as pd
from dblpy import get_publications
from tqdm import tqdm
import time
import os
import sys

class DBLPProcessor:
    """
    A class to handle searching DBLP, collecting results, and saving them
    with auto-save and index-based resume capabilities.
    """
    def __init__(self, titles_df, target_venues, output_path, save_interval=1000):
        self.titles_df = titles_df.reset_index().rename(columns={'index': 'InputIndex'})
        self.target_venues = target_venues
        self.output_path = output_path
        self.save_interval = save_interval
        self.collected_records = []
        self.header_written = os.path.exists(output_path)

    def save_progress(self):
        """Saves the currently collected records to the output CSV file."""
        if not self.collected_records:
            return

        df_to_save = pd.DataFrame(self.collected_records)
        df_to_save.to_csv(
            self.output_path, 
            mode='a', 
            header=not self.header_written, 
            index=False
        )
        
        # This print statement will appear above the progress bar
        tqdm.write(f"\n💾 Auto-saved {len(self.collected_records)} records to {self.output_path}")
        
        self.header_written = True
        self.collected_records.clear()

    def run(self):
        """Executes the main processing loop with resume and interrupt handling."""
        
        titles_to_process = self.titles_df
        if self.header_written: # Use self.header_written as a proxy for file existence
            print("📝 Output file found. Checking for last processed index to resume...")
            try:
                existing_df = pd.read_csv(self.output_path)
                if not existing_df.empty and 'InputIndex' in existing_df.columns:
                    last_processed_index = existing_df['InputIndex'].max()
                    start_index = last_processed_index + 1
                    
                    if start_index < len(self.titles_df):
                        titles_to_process = self.titles_df.iloc[start_index:]
                        print(f"✅ Resuming from index {start_index}...")
                    else:
                        print("✅ All titles have already been processed. Nothing to do.")
                        return # Exit the run method
            except Exception as e:
                print(f"⚠️ Could not read resume state from {self.output_path}. Starting from scratch. Error: {e}")
        
        if titles_to_process.empty:
            return

        try:
            progress_bar = tqdm(titles_to_process.iterrows(), total=len(titles_to_process), desc="Querying DBLP API", unit="title")
            for index, row in progress_bar:
                title = row['title']
                
                progress_bar.set_postfix(status="Searching...")
                
                try:
                    publications = get_publications(q=title, max_results=10)
                except Exception as e:
                    tqdm.write(f"\nAn API error occurred for title '{title}': {e}")
                    progress_bar.set_postfix(status="API Error ⚠️")
                    continue

                filtered_results = [p for p in publications if p.venue and any(target in p.venue for target in self.target_venues)] if publications else []

                if filtered_results:
                    progress_bar.set_postfix_str(f"Success ({len(filtered_results)} found ✅)")
                    for p in filtered_results:
                        record = {
                            'InputIndex': index, 
                            'Key': p.key, 
                            'Title': p.title, 
                            'Authors': p.authors, 
                            'Year': p.year, 
                            'Venue': p.venue, 
                            'Type': p.type, 
                            'Pages': p.pages, 
                            'Volume': p.volume, 
                            'Number': p.number, 
                            'Publisher': p.publisher, 
                            'Access': p.access, 
                            'DOI': p.doi, 
                            'EE': p.ee, 
                            'URL': p.url
                        }
                        self.collected_records.append(record)
                else:
                    progress_bar.set_postfix(status="Not Found ❌")
                
                if len(self.collected_records) >= self.save_interval:
                    self.save_progress()
                
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n\n🛑 Keyboard interrupt detected. Saving remaining data before exiting...")
        
        finally:
            self.save_progress()
            print("\n🎉 Processing finished.")

# --- Main execution block ---
if __name__ == "__main__":
    CSV_PATH = os.path.join('revised_data', 'acl_papers_cleaned.csv')
    OUTPUT_CSV_PATH = 'dblp-api_nlp_papers.csv'
    TARGET_VENUES = {'ACL', 'EMNLP', 'NAACL'}

    if not os.path.exists(CSV_PATH):
        print(f"Error: Input file not found at '{CSV_PATH}'")
        sys.exit(1)
        
    print(f"📚 Loading titles from {CSV_PATH}...")
    try:
        titles_df = pd.read_csv(CSV_PATH)
        
        processor = DBLPProcessor(
            titles_df=titles_df, 
            target_venues=TARGET_VENUES, 
            output_path=OUTPUT_CSV_PATH
        )
        processor.run()
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")