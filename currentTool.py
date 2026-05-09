import pandas as pd
import os
from backend.engine import AccessFixEngine
from backend.web_scrapper_and_file_handler import fetch_and_save_data

def main():
    print("AccessFix CLI - Starting...")
    url = 'https://calendar.google.com/'
    path = 'data/input.html'

    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)

    # Initialize Engine
    engine = AccessFixEngine()
    
    # Run Agentic Loop
    initial_score, final_df = engine.run_agentic_loop(url, path, max_iterations=3)

    # Calculate final score
    final_score = engine.calculate_severity_score(final_df, 'finalScore')

    print("\n--- Final Results ---")
    print(f"Initial Severity Score: {initial_score}")
    print(f"Final Severity Score:   {final_score}")
    
    if initial_score > 0:
        improvement = ((1 - (final_score / initial_score)) * 100)
        print(f"Total Improvement:      {improvement:.2f}%")
    
    # Save results
    final_df.to_csv('correctionViolations.csv', index=False)
    print("\nCorrected DOM saved to data/corrected.html")
    print("Violation details saved to correctionViolations.csv")

if __name__ == "__main__":
    main()