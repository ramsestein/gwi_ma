import csv
import time
import os

class CSVLogger:
    def __init__(self, filename="results/vital_log.csv"):
        self.filename = filename
        self.headers = ["Timestamp", "HR", "SPO2", "RR", "BP_Sys", "BP_Dia", "Raw_Frame_Len"]
        
        # Create dir if needed
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        
        # Initialize file with headers if new
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)

    def log_vitals(self, vital_dict):
        """
        Logs a dictionary of vitals to CSV.
        Expects keys matching self.headers (except Timestamp).
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        row = [
            timestamp,
            vital_dict.get("HR", ""),
            vital_dict.get("SPO2", ""),
            vital_dict.get("RR", ""),
            vital_dict.get("BP_Sys", ""),
            vital_dict.get("BP_Dia", ""),
            vital_dict.get("len", "")
        ]
        
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        
        print(f" [LOG] Saved to CSV: {row}")
