import pyedflib
import numpy as np
import os

filename = "test_debug.edf"
n_channels = 1
fs = 100
duration = 10
nsamples = fs * duration
data = np.random.randn(nsamples).astype(np.float64)

print(f"Creating {filename} with {nsamples} samples...")
print(f"Data shape: {data.shape}")

try:
    f = pyedflib.EdfWriter(filename, n_channels, file_type=pyedflib.FILETYPE_EDFPLUS)
    
    ch_info = {
        'label': 'ECG', 
        'dimension': 'uV', 
        'sample_frequency': fs, 
        'physical_max': data.max(), 
        'physical_min': data.min(), 
        'digital_max': 32767, 
        'digital_min': -32768, 
        'transducer': 'test', 
        'prefilter': ''
    }
    
    f.setSignalHeaders([ch_info])
    
    # Try writing with writePhysicalSamples in blocks
    print("Writing samples in blocks...")
    # Write 1 second at a time
    block_size = fs
    for i in range(0, len(data), block_size):
        chunk = data[i:i+block_size]
        if len(chunk) < block_size:
            # Pad with zeros if last block is incomplete?
            # EDF requires full blocks usually.
            chunk = np.pad(chunk, (0, block_size - len(chunk)), 'constant')
        f.writePhysicalSamples(chunk)



    
    f.close()
    print("Closed.")
    
    size = os.path.getsize(filename)
    print(f"File size: {size} bytes")
    
    # Read back
    f_read = pyedflib.EdfReader(filename)
    print(f"Read back: {f_read.getNSamples()[0]} samples")
    f_read.close()
    
except Exception as e:
    print(f"Error: {e}")
