import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd
import os
import time

CSV_FILE = os.path.join("results", "vital_log.csv")

def animate(i):
    try:
        # Read only the last 60 lines for performance
        if not os.path.exists(CSV_FILE):
            print("Waiting for CSV...", end='\r')
            return
            
        # Error handling for empty or locked file
        try:
            df = pd.read_csv(CSV_FILE)
        except pd.errors.EmptyDataError:
            return
            
        if df.empty:
            return

        # Keep last 60 samples
        df = df.tail(60)
        
        # Parse timestamp if needed, but index is simpler for rolling plot
        x = range(len(df))
        
        # Clear and Plot
        ax1.clear()
        ax2.clear()
        
        # Heart Rate (Red)
        if "HR" in df.columns:
            # Clean non-numeric data
            hr_data = pd.to_numeric(df["HR"], errors='coerce')
            ax1.plot(x, hr_data, 'r-', label='Heart Rate (bpm)')
            ax1.set_ylabel("BPM")
            ax1.legend(loc='upper left')
            ax1.set_ylim(0, 200)
            ax1.grid(True, alpha=0.3)
            
            # Show latest value
            if not hr_data.empty and not pd.isna(hr_data.iloc[-1]):
                ax1.set_title(f"HR: {int(hr_data.iloc[-1])} | SPO2: {df['SPO2'].iloc[-1] if 'SPO2' in df else '?'}")

        # SPO2 (Blue)
        if "SPO2" in df.columns:
            spo2_data = pd.to_numeric(df["SPO2"], errors='coerce')
            ax2.plot(x, spo2_data, 'b-', label='SpO2 (%)')
            ax2.set_ylabel("%")
            ax2.legend(loc='upper left')
            ax2.set_ylim(50, 100)
            ax2.grid(True, alpha=0.3)
            
    except Exception as e:
        # Don't crash on read errors (common when file is being written to)
        pass

if __name__ == "__main__":
    print(f"--- Real-Time Plotter Watching {CSV_FILE} ---")
    
    try:
        # Check imports first
        import matplotlib
        print(f" [Info] Matplotlib Backend: {matplotlib.get_backend()}")

        # Setup Plot
        fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
        fig.suptitle("IntelliVue MX750 - Live Vitals")
        
        # Update every 1000ms
        ani = animation.FuncAnimation(fig, animate, interval=1000)
        
        print(" [Info] Plotting started. Press Ctrl+C to stop.")
        plt.show()
        
    except KeyboardInterrupt:
        print("Plotter closed by user.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Plotter crashed: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to close window...") # Keep window open to see error
