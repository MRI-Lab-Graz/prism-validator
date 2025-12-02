import argparse
import pandas as pd
import json
import os
import gzip
import numpy as np

def load_sidecar(bids_tsv):
    """Loads the JSON sidecar associated with the TSV."""
    # Try .json, .tsv.json, .tsv.gz.json?
    # Standard BIDS: sub-01_physio.tsv.gz -> sub-01_physio.json
    
    base = bids_tsv.split('.')[0]
    # Handle .tsv.gz
    if bids_tsv.endswith('.tsv.gz'):
        json_path = bids_tsv[:-7] + '.json'
    elif bids_tsv.endswith('.tsv'):
        json_path = bids_tsv[:-4] + '.json'
    else:
        json_path = base + '.json'
        
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            return json.load(f)
    return {}

def export_to_edf(df, output_file, fs, ecg_col, marker_col):
    try:
        import pyedflib
    except ImportError:
        print("Error: pyedflib is not installed. Please run: uv pip install pyedflib")
        return

    print(f"Exporting to EDF+ at {fs} Hz...")
    
    n_channels = 1
    channel_info = []
    
    # ECG Channel
    ch1 = {'label': 'ECG', 'dimension': 'uV', 'sample_frequency': fs, 'physical_max': df[ecg_col].max(), 'physical_min': df[ecg_col].min(), 'digital_max': 32767, 'digital_min': -32768, 'transducer': 'AgAgCl', 'prefilter': ''}
    channel_info.append(ch1)
    
    # We do NOT add marker as a signal channel in EDF+. We use Annotations.
    # But if the user wants it as a signal (e.g. for visual inspection of the trigger line), we can add it.
    # Kubios supports EDF Annotations. Let's try to convert the marker channel to annotations.
    
    annotations = []
    if marker_col:
        # Find changes in marker channel
        # Assuming marker channel is 0 for no event, and >0 for event
        # Or just changes.
        # Let's look for non-zero values.
        
        # Simple logic: Find where marker != 0
        # This depends on how markers are stored. Varioport often has 0 and then a code.
        
        markers = df[marker_col].values
        # Find indices where marker changes or is non-zero
        # If it's a trigger channel (pulses), we want the onset.
        
        # Get indices where value > 0
        # This might be too many if it's a continuous high signal.
        # Let's assume it's a trigger signal where we want onsets.
        
        # Find rising edges
        # Pad with 0 at start
        diffs = np.diff(markers, prepend=0)
        # Onsets: where diff > 0 (or just != 0 if we track all changes)
        # Let's track all changes for safety, or just positive values?
        # Usually markers are discrete codes.
        
        # Let's iterate through changes to be safe
        changes = np.where(diffs != 0)[0]
        
        for idx in changes:
            val = markers[idx]
            if val > 0: # Only mark start of events
                onset = idx / fs
                duration = 0 # Point event
                description = str(int(val))
                annotations.append((onset, duration, description))
                
        print(f"Found {len(annotations)} marker events.")

    try:
        f = pyedflib.EdfWriter(output_file, n_channels, file_type=pyedflib.FILETYPE_EDFPLUS)
        f.setSignalHeaders(channel_info)
        
        # Write data in 1-second blocks (fs samples) to ensure correct EDF structure
        data = df[ecg_col].values
        block_size = int(fs)
        n_samples = len(data)
        
        # Pad data if necessary to match full seconds (EDF records)
        remainder = n_samples % block_size
        if remainder > 0:
            pad_len = block_size - remainder
            # Pad with the last value to avoid artifacts
            padding = np.full(pad_len, data[-1])
            data = np.concatenate([data, padding])
            print(f"Padded data with {pad_len} samples to match 1-second blocks.")
            
        # Write blocks
        for i in range(0, len(data), block_size):
            chunk = data[i:i+block_size]
            f.writePhysicalSamples(chunk)
        
        for onset, duration, desc in annotations:
            f.writeAnnotation(onset, duration, desc)
            
        f.close()

        print(f"Saved to {output_file}")
        print("INSTRUCTIONS FOR KUBIOS (EDF):")
        print("1. Open Kubios HRV.")
        print("2. Open the .edf file.")
        print("3. Kubios should auto-detect Sampling Rate and Markers (Annotations).")
        
    except Exception as e:
        print(f"Error writing EDF: {e}")


def export_to_kubios(bids_tsv, output_file=None, fmt="dat"):
    """
    Converts a BIDS physio TSV to a Kubios-friendly format (ASCII .dat or EDF+).
    """
    
    if not output_file:
        ext = ".edf" if fmt == "edf" else ".dat"
        output_file = bids_tsv.replace(".tsv.gz", ext).replace(".tsv", ext)

    print(f"Reading {bids_tsv}...")
    try:
        df = pd.read_csv(bids_tsv, sep='\t', compression='gzip' if bids_tsv.endswith('.gz') else None)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Load sidecar for FS
    sidecar = load_sidecar(bids_tsv)
    fs = sidecar.get("SamplingFrequency", None)
    
    if not fs:
        print("Warning: SamplingFrequency not found in JSON sidecar.")
        fs_str = input("Please enter Sampling Frequency (Hz): ")
        try:
            fs = float(fs_str)
        except:
            print("Invalid frequency.")
            return
    else:
        print(f"Sampling Frequency: {fs} Hz")

    print("Available columns:", df.columns.tolist())

    # Try to auto-detect ECG and Marker
    ecg_col = next((c for c in df.columns if "EKG" in c.upper() or "ECG" in c.upper()), None)
    marker_col = next((c for c in df.columns if "MARKER" in c.upper() or "TRG" in c.upper()), None)

    if not ecg_col:
        print("Could not auto-detect ECG column.")
        ecg_col = input("Please enter the name of the ECG column: ")
    
    if not marker_col:
        print("Could not auto-detect Marker column. (Leave empty if none)")
        marker_col = input("Please enter the name of the Marker column: ")

    if marker_col and marker_col.strip() == "":
        marker_col = None

    if fmt == "edf":
        export_to_edf(df, output_file, fs, ecg_col, marker_col)
    else:
        # ASCII Export
        # Prepare output DataFrame
        out_df = pd.DataFrame()
        out_df[ecg_col] = df[ecg_col]
        
        if marker_col:
            out_df[marker_col] = df[marker_col]
            print(f"Exporting ECG ({ecg_col}) and Marker ({marker_col})...")
        else:
            print(f"Exporting ECG ({ecg_col}) only...")

        # Save as space-separated or comma-separated
        out_df.to_csv(output_file, sep=',', index=False, header=False)
        
        print(f"Saved to {output_file}")
        print("-" * 40)
        print("INSTRUCTIONS FOR KUBIOS (ASCII):")
        print("1. Open Kubios HRV.")
        print("2. Go to File -> Open.")
        print("3. Select 'Custom ASCII' as file type if needed, or just select the file.")
        print("4. In the import dialog:")
        print("   - Delimiter: Comma")
        print("   - Column 1: ECG")
        if marker_col:
            print("   - Column 2: Stimulus / Event")
        print(f"   - Sampling Rate: {fs} Hz")
        print("-" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export BIDS physio to Kubios format")
    parser.add_argument("input_file", help="Path to BIDS .tsv.gz file")
    parser.add_argument("--output", help="Path to output file", default=None)
    parser.add_argument("--format", choices=["dat", "edf"], default="dat", help="Output format: 'dat' (ASCII) or 'edf' (EDF+)")
    
    args = parser.parse_args()
    
    export_to_kubios(args.input_file, args.output, args.format)
