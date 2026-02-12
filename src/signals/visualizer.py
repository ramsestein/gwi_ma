import sys
import matplotlib.pyplot as plt
import numpy as np

def visualize_data(filename):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    # Convert to numpy array of integers
    values = np.frombuffer(data, dtype=np.uint8)
    
    print(f"Visualizing {len(values)} bytes...")
    print("Close the window to exit.")

    plt.figure(figsize=(15, 6))
    
    # Plot raw byte values
    plt.plot(values, label='Raw Byte Value (0-255)', alpha=0.7)
    
    # Prepare title info
    plt.title(f"Raw Data Visualization: {filename}")
    plt.xlabel("Byte Index")
    plt.ylabel("Value (uint8)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Add a secondary plot for "Packet view" if needed, but simple linear plot is best first step
    # to see if there are wave-like structures.
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualizer.py <CAPTURE_FILE>")
        print("Requires: pip install matplotlib numpy")
    else:
        visualize_data(sys.argv[1])
