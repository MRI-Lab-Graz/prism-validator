import struct
import json
import argparse
import numpy as np
import pandas as pd


def read_varioport_header(f):
    """
    Reads the Varioport file header and channel definitions.
    Based on the R code 'read_vpd.R' and inspection of VPDATA.RAW.
    """
    f.seek(0)

    # 1. File Header
    # Byte 2: Header Length
    f.seek(2)
    hdrlen = struct.unpack(">H", f.read(2))[0]

    # Byte 4: Channel Offset
    f.seek(4)
    choffs = struct.unpack(">H", f.read(2))[0]

    # Byte 6: Header Type
    f.seek(6)
    hdrtype = struct.unpack(">B", f.read(1))[0]

    # Byte 7: Channel Count
    f.seek(7)
    chcnt = struct.unpack(">B", f.read(1))[0]

    # Byte 20: Global Scan Rate (Not in R code, but found in file)
    f.seek(20)
    scnrate = struct.unpack(">H", f.read(2))[0]
    if scnrate == 0:
        print("Warning: Global Scan Rate at offset 20 is 0. Defaulting to 150 Hz.")
        scnrate = 150

    print(
        f"Header Info: Length={hdrlen}, Type={hdrtype}, Channels={chcnt}, BaseRate={scnrate}"
    )

    # 2. Channel Definitions
    channels = []
    for i in range(chcnt):
        offset = choffs + i * 40
        f.seek(offset)
        ch_def = f.read(40)

        name = ch_def[0:6].decode("ascii", errors="ignore").strip()
        unit = ch_def[6:10].decode("ascii", errors="ignore").strip()
        # data_size: 0=uint8, 1=uint16. Actual bytes = val + 1
        dsize_code = ch_def[11]
        dsize = dsize_code + 1

        scnfac = ch_def[12]
        strfac = ch_def[14]

        mul = struct.unpack(">H", ch_def[16:18])[0]
        doffs = struct.unpack(">H", ch_def[18:20])[0]
        div = struct.unpack(">H", ch_def[20:22])[0]

        # Offset to data (relative to some base, R code adds hdrlen)
        offs_val = struct.unpack(">I", ch_def[24:28])[0]
        abs_offs = offs_val + hdrlen

        chlen = struct.unpack(">I", ch_def[28:32])[0]

        # Calculate effective sampling rate
        # chscnrate = scnrate / scnfac
        # chstrrate = chscnrate / strfac
        if scnfac == 0:
            scnfac = 1
        if strfac == 0:
            strfac = 1
        fs = scnrate / (scnfac * strfac)

        chan_info = {
            "index": i,
            "name": name,
            "unit": unit,
            "dsize": dsize,
            "scnfac": scnfac,
            "strfac": strfac,
            "mul": mul,
            "doffs": doffs,
            "div": div,
            "abs_offs": abs_offs,
            "chlen": chlen,
            "fs": fs,
        }
        channels.append(chan_info)
        print(
            f"Channel {i}: {name} ({unit}), fs={fs:.2f}Hz, len={chlen}, dsize={dsize}"
        )

    return hdrlen, hdrtype, channels


def get_default_scaling(name):
    """
    Returns default scaling parameters based on Varioport Toolbox (MATLAB).
    Used if file header contains invalid values (e.g. mul=0).
    """
    # Defaults from Varioport_Toolbox load_channel_data.m
    # offset = 32767
    defaults = {
        "EDA": {"doffs": 32767, "mul": 10, "div": 6400},
        "EMG1": {"doffs": 32767, "mul": 1297, "div": 10000},
        "EMG2": {"doffs": 32767, "mul": 1297, "div": 10000},
        "AUX": {
            "doffs": 32767,
            "mul": 1,
            "div": 1,
        },  # Toolbox says "no factors given... possible to omit offset", but code uses offset.
        "UBATT": {
            "doffs": 0,
            "mul": 127,
            "div": 10000,
        },  # Toolbox doesn't subtract offset for UBATT
        "BATT": {"doffs": 0, "mul": 127, "div": 10000},  # Alias
    }

    # Check for partial matches (e.g. "EDA " or "EDA1")
    for key in defaults:
        if name.upper().startswith(key):
            return defaults[key]
    return None


def convert_varioport(raw_path, output_path, sidecar_path, task_name="rest"):
    """
    Converts a Varioport .RAW file to BIDS .tsv.gz and .json.
    """

    with open(raw_path, "rb") as f:
        hdrlen, hdrtype, channels = read_varioport_header(f)

        # Identify active channels
        # In the test file, EKG has len=-1 (0xFFFFFFFF), others have 0.
        # We assume only channels with len != 0 are active.
        # BUT: Marker channel often has len=0 but is present in Type 7 streams (checking file size divisibility).
        active_channels = []
        for c in channels:
            if c["chlen"] != 0:
                active_channels.append(c)
            elif "marker" in c["name"].lower():
                # Force include marker if it looks like it might be in the stream
                # We'll verify block alignment later
                print(f"Force-including channel {c['name']} despite len=0")
                active_channels.append(c)

        if not active_channels:
            print(
                "No active channels found (all have length 0). Assuming all are active?"
            )
            active_channels = channels

        print(
            f"Found {len(active_channels)} active channels: {[c['name'] for c in active_channels]}"
        )

        # Check if all active channels have the same sampling rate
        if not active_channels:
            print("Error: No channels to process.")
            return

        fs_set = set(c["fs"] for c in active_channels)
        if len(fs_set) > 1:
            print(
                f"Warning: Multiple sampling rates detected: {fs_set}. Assuming interleaved data follows the highest rate (or first channel)."
            )
            # We do NOT filter channels here anymore, we assume they are all in the stream.
            # We use the maximum FS for the sidecar and upsampling target.
            
        target_fs = max(c["fs"] for c in active_channels)
        channel_data = {}

        if hdrtype == 6:
            # Type 6: Reconfigured / Demultiplexed
            # Data for each channel is at specific offsets
            print(
                "Detected Type 6 (Reconfigured) file. Reading channels independently."
            )

            for ch in active_channels:
                name = ch["name"]
                print(f"Processing channel: {name}")

                data_start = ch["abs_offs"]
                data_len_bytes = ch["chlen"]

                f.seek(data_start)
                raw_bytes = f.read(data_len_bytes)

                dsize = ch["dsize"]
                num_samples = len(raw_bytes) // dsize

                if dsize == 2:
                    # Big Endian uint16
                    fmt = f">{num_samples}H"
                    raw_values = struct.unpack(fmt, raw_bytes[: num_samples * dsize])
                elif dsize == 1:
                    fmt = f">{num_samples}B"
                    raw_values = struct.unpack(fmt, raw_bytes[: num_samples * dsize])
                else:
                    print(f"Skipping channel {name}: Unsupported data size {dsize}")
                    continue

                # Apply scaling
                doffs = ch["doffs"]
                mul = ch["mul"]
                div = ch["div"]

                # Check for invalid scaling parameters and apply defaults if needed
                if mul == 0 or div == 0:
                    print(
                        f"  Warning: Invalid scaling (mul={mul}, div={div}). Checking defaults..."
                    )
                    defaults = get_default_scaling(name)
                    if defaults:
                        doffs = defaults["doffs"]
                        mul = defaults["mul"]
                        div = defaults["div"]
                        print(
                            f"  Applied defaults for {name}: doffs={doffs}, mul={mul}, div={div}"
                        )
                    else:
                        print(
                            f"  No defaults found for {name}. Using raw values (mul=1, div=1, doffs=0)."
                        )
                        doffs = 0
                        mul = 1
                        div = 1

                if div == 0:
                    div = 1  # Safety

                data_array = np.array(raw_values, dtype=float)
                data_array = (data_array - doffs) * mul / div

                channel_data[name] = data_array

        else:
            # Type 7: Raw / Multiplexed (or other)
            # The data starts after the header and is interleaved.
            print(
                f"Detected Type {hdrtype} (Raw/Multiplexed). Warning: Assuming interleaved data for active channels."
            )

            data_start = hdrlen
            f.seek(data_start)

            # Read all remaining data
            raw_bytes = f.read()
            num_bytes = len(raw_bytes)

            # Calculate total block size (sum of dsize of all active channels)
            # This assumes 1 sample per channel per block (round robin)
            block_size = sum(c["dsize"] for c in active_channels)
            num_blocks = num_bytes // block_size

            print(
                f"Read {num_bytes} bytes. Block size={block_size}. Expected samples per channel={num_blocks}."
            )

            for ch in active_channels:
                name = ch["name"]
                dsize = ch["dsize"]

                # Extract strided data
                # This is slow in pure Python, but let's try
                # Better: use numpy frombuffer with stride?
                # But dsize varies.

                # If all dsize are same (e.g. 2), we can use numpy reshape
                if all(c["dsize"] == dsize for c in active_channels):
                    # Assuming uniform dsize
                    # dt = np.dtype(np.uint16).newbyteorder('>') if dsize == 2 else np.dtype(np.uint8)
                    # all_data = np.frombuffer(raw_bytes, dtype=dt)
                    # Reshape: (num_blocks, num_channels)
                    # But we need to know channel order. Assuming active_channels order matches file order.
                    # active_channels is sorted by index?
                    # We should sort active_channels by 'index' just in case
                    pass

                # Fallback to simple extraction for now (imperfect but better than before)
                # Actually, let's just warn and try to read as single stream if only 1 channel
                if len(active_channels) == 1:
                    # Same logic as before
                    if dsize == 2:
                        fmt = f">{num_blocks}H"
                        raw_values = struct.unpack(fmt, raw_bytes[: num_blocks * dsize])
                    else:
                        fmt = f">{num_blocks}B"
                        raw_values = struct.unpack(fmt, raw_bytes[: num_blocks * dsize])

                    # Scaling logic (same as above)
                    doffs = ch["doffs"]
                    mul = ch["mul"]
                    div = ch["div"]
                    if mul == 0 or div == 0:
                        defaults = get_default_scaling(name)
                        if defaults:
                            doffs = defaults["doffs"]
                            mul = defaults["mul"]
                            div = defaults["div"]
                        else:
                            doffs = 0
                            mul = 1
                            div = 1
                    if div == 0:
                        div = 1

                    data_array = np.array(raw_values, dtype=float)
                    data_array = (data_array - doffs) * mul / div
                    channel_data[name] = data_array
                else:
                    # Multiple channels, interleaved
                    print(f"Reading {len(active_channels)} interleaved channels using numpy...")
                    dtype_list = []
                    for c in active_channels:
                        # dsize=2 -> >u2, dsize=1 -> >u1
                        if c["dsize"] == 2:
                            fmt = '>u2'
                        elif c["dsize"] == 1:
                            fmt = '>u1'
                        else:
                            print(f"Unsupported dsize {c['dsize']} for channel {c['name']}")
                            return
                        # Sanitize name for numpy field
                        safe_name = c["name"].replace(" ", "_").replace("(", "").replace(")", "")
                        dtype_list.append((safe_name, fmt))
                    
                    dt = np.dtype(dtype_list)
                    
                    # Read data
                    # Ensure we only read complete blocks
                    valid_bytes = num_blocks * block_size
                    try:
                        raw_data = np.frombuffer(raw_bytes[:valid_bytes], dtype=dt)
                    except Exception as e:
                        print(f"Error reading buffer: {e}")
                        return

                    # Process each channel
                    for i, c in enumerate(active_channels):
                        name = c["name"]
                        safe_name = dtype_list[i][0]
                        raw_vals = raw_data[safe_name]
                        
                        # Scaling
                        doffs = c["doffs"]
                        mul = c["mul"]
                        div = c["div"]
                        
                        if mul == 0 or div == 0:
                            defaults = get_default_scaling(name)
                            if defaults:
                                doffs = defaults["doffs"]
                                mul = defaults["mul"]
                                div = defaults["div"]
                            else:
                                doffs = 0
                                mul = 1
                                div = 1
                        if div == 0: div = 1
                        
                        data_array = raw_vals.astype(float)
                        data_array = (data_array - doffs) * mul / div
                        channel_data[name] = data_array

        # Create DataFrame
        if not channel_data:
            print("No data extracted.")
            return

        # Check lengths
        lengths = [len(d) for d in channel_data.values()]
        max_len = max(lengths)
        
        if len(set(lengths)) > 1:
            print(f"Warning: Channel lengths differ: {lengths}. Upsampling to maximum {max_len}.")
            
            for k in channel_data:
                current_len = len(channel_data[k])
                if current_len < max_len:
                    print(f"  Upsampling {k} from {current_len} to {max_len}...")
                    
                    old_indices = np.linspace(0, 1, current_len)
                    new_indices = np.linspace(0, 1, max_len)
                    
                    # If it's a marker channel, use nearest neighbor (step) to preserve integer codes
                    if "marker" in k.lower() or "trg" in k.lower():
                         indices = np.round((new_indices) * (current_len - 1)).astype(int)
                         channel_data[k] = channel_data[k][indices]
                    else:
                        # Linear interpolation for continuous signals
                        channel_data[k] = np.interp(new_indices, old_indices, channel_data[k])

        df = pd.DataFrame(channel_data)

        # Save to TSV
        print(f"Saving to {output_path}...")
        df.to_csv(output_path, sep="\t", index=False, compression="gzip")

        # Create Sidecar JSON
        sidecar = {
            "TaskName": task_name,
            "SamplingFrequency": target_fs,
            "StartTime": 0,
            "Columns": list(channel_data.keys()),
            "Manufacturer": "Becker Meditec",
            "ManufacturersModelName": "Varioport",
            "Note": "Converted from VPDATA.RAW using reverse-engineered specs.",
        }

        with open(sidecar_path, "w") as jf:
            json.dump(sidecar, jf, indent=4)

        print("Conversion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Varioport RAW to BIDS")
    parser.add_argument("input_file", help="Path to VPDATA.RAW")
    parser.add_argument("output_tsv", help="Path to output .tsv.gz")
    parser.add_argument("output_json", help="Path to output .json")

    args = parser.parse_args()

    convert_varioport(args.input_file, args.output_tsv, args.output_json)
