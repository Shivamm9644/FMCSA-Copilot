"""
File: apps/validations/checksum_verifier.py
Why it exists:
    Provides deterministic verification of individual Line Data Check Values and File Data Check Values
    in accordance with FMCSA ELD Technical Specifications (49 CFR Part 395, Subpart B, Appendix A).
    This ensures ELD output files remain untampered with and structurally correct before further compliance scoring.

Inputs:
    - line_text (str): A single line of text from the ELD output file.
    - file_content_str (str): The entire contents of the ELD output CSV file.

Outputs:
    - calculate_line_checksum (str): A 2-character uppercase hexadecimal string.
    - verify_file_checksum (dict): A dictionary reporting overall file validity, calculated vs actual checksums,
      and a list of lines that failed checksum validation.

Dependencies:
    - typing (Python Standard Library)
    - re (Python Standard Library)
"""

import re
from typing import Dict, List, Any

def fmcsa_char_to_dec(c: str) -> int:
    """
    Applies the FMCSA character-to-decimal mapping (Table 3).
    Alphanumeric characters (0-9, A-Z, a-z) map to ASCII - 48.
    All other characters (commas, spaces, hyphens, etc.) map to 0.
    """
    if c.isalnum() and c.isascii():
        return ord(c) - 48
    return 0

def rotate_left_3(val: int) -> int:
    """
    Performs a circular shift left (rotate left, no carry) by 3 positions on an 8-bit byte.
    """
    val &= 0xFF
    return ((val << 3) & 0xFF) | (val >> 5)

def calculate_line_checksum(line_text: str) -> str:
    """
    Calculates the 1-byte FMCSA ELD Line Data Check Value.
    1. Removes any trailing carriage returns and newlines.
    2. Sums the converted values of all characters up to (and including) the last comma.
    3. Takes the lower 8-bit byte of the sum.
    4. Rotates left by 3 bits.
    5. XORs with 0x96 (decimal 150).
    6. Formats the result as a 2-digit uppercase hexadecimal string.
    """
    clean_line = line_text.strip().rstrip('\r\n')
    
    # Extract everything up to (and including) the last comma
    if ',' in clean_line:
        parts = clean_line.rsplit(',', 1)
        data_to_checksum = parts[0] + ','
    else:
        data_to_checksum = clean_line

    char_sum = sum(fmcsa_char_to_dec(c) for c in data_to_checksum)
    lower_byte = char_sum & 0xFF
    rotated = rotate_left_3(lower_byte)
    checksum_val = rotated ^ 0x96
    
    return f"{checksum_val:02X}"

def calculate_event_checksum(
    event_type: str,
    event_code: str,
    event_date: str,
    event_time: str,
    vehicle_miles: str,
    engine_hours: str,
    latitude: str,
    longitude: str,
    cmv_number: str,
    username: str
) -> str:
    """
    Calculates the FMCSA ELD Event Data Check Value.
    1. Sums the character values (via Table 3) of all characters in the 10 defined fields.
    2. Takes the lower 8-bit byte of the sum.
    3. Rotates left by 3 bits.
    4. XORs with 0xC3 (decimal 195).
    5. Formats the result as a 2-digit uppercase hexadecimal string.
    """
    fields = [
        event_type, event_code, event_date, event_time,
        vehicle_miles, engine_hours, latitude, longitude,
        cmv_number, username
    ]
    
    char_sum = 0
    for field in fields:
        char_sum += sum(fmcsa_char_to_dec(c) for c in str(field))
        
    lower_byte = char_sum & 0xFF
    rotated = rotate_left_3(lower_byte)
    checksum_val = rotated ^ 0xC3
    
    return f"{checksum_val:02X}"

def verify_file_checksum(file_content_str: str) -> Dict[str, Any]:
    """
    Verifies all line checksums and the file-wide checksum of the ELD output file.
    1. Strips and splits the file by lines.
    2. Isolates the last two lines: the 'End of File:' label line and the File Data Check Value line.
    3. Calculates individual Line Data Check Values, tracking failures.
    4. Sums individual line check values to compute the expected File Data Check Value.
    5. Rotates each of the two 8-bit bytes of the 16-bit sum left by 3 bits, then XORs with 0x969C.
    6. Returns a dictionary summarizing the results.
    """
    raw_lines = file_content_str.splitlines()
    clean_lines = []
    
    for idx, line in enumerate(raw_lines):
        clean_lines.append((idx + 1, line.strip()))
        
    # Filter out empty lines from the end to identify the EOF metadata correctly
    non_empty_lines = [(ln, l) for ln, l in clean_lines if l]
    
    provided_file_checksum = ""
    file_checksum_line_idx = -1
    eof_label_line_idx = -1
    
    # Detect the End of File: label and File Data Check Value lines
    if len(non_empty_lines) >= 2:
        # Check if the second to last non-empty line starts with 'End of File:'
        # and the last non-empty line is a 4-character hex string
        penultimate_ln, penultimate_content = non_empty_lines[-2]
        ultimate_ln, ultimate_content = non_empty_lines[-1]
        
        if penultimate_content.lower().startswith("end of file"):
            eof_label_line_idx = penultimate_ln
            file_checksum_line_idx = ultimate_ln
            provided_file_checksum = ultimate_content.strip()

    line_results = []
    failed_lines = []
    line_checksum_sum = 0
    
    for line_num, line in clean_lines:
        # Skip empty lines, the 'End of File' label line, and the checksum line
        if not line:
            continue
        if line_num == eof_label_line_idx or line_num == file_checksum_line_idx:
            continue
            
        # Standard FMCSA CSV lines have a comma followed by a 2-character hex checksum.
        # Check if the line has commas and ends with a 2-character hex code.
        if ',' in line:
            parts = line.rsplit(',', 1)
            provided_line_chk = parts[1].strip()
            
            # Line check is valid if it matches standard 2-character hex format
            if re.match(r'^[0-9A-Fa-f]{2}$', provided_line_chk):
                expected_line_chk = calculate_line_checksum(line)
                is_valid = (provided_line_chk.upper() == expected_line_chk)
                
                # Accumulate the expected line check value in the running file checksum per FMCSA standard
                try:
                    line_checksum_sum += int(expected_line_chk, 16)
                except ValueError:
                    pass
                
                if not is_valid:
                    failed_lines.append({
                        "line_number": line_num,
                        "content": line,
                        "expected": expected_line_chk,
                        "actual": provided_line_chk
                    })
                
                line_results.append({
                    "line_number": line_num,
                    "calculated": expected_line_chk,
                    "provided": provided_line_chk,
                    "is_valid": is_valid
                })
            else:
                # If there is no valid checksum at the end of the line, skip check
                pass
        else:
            # Lines without commas (like raw section title lines) do not have line checksums
            pass

    # Compute expected 16-bit File Checksum
    # Take the lower 16 bits of the sum
    file_checksum_16 = line_checksum_sum & 0xFFFF
    
    # Split into high and low bytes
    high_byte = (file_checksum_16 >> 8) & 0xFF
    low_byte = file_checksum_16 & 0xFF
    
    # Rotate each byte left by 3 bits
    high_rotated = rotate_left_3(high_byte)
    low_rotated = rotate_left_3(low_byte)
    
    # Recombine and XOR with 0x969C
    combined_rotated = (high_rotated << 8) | low_rotated
    expected_file_checksum_val = combined_rotated ^ 0x969C
    expected_file_checksum_hex = f"{expected_file_checksum_val:04X}"
    
    # Validate the file checksum
    file_checksum_valid = True
    if provided_file_checksum:
        file_checksum_valid = (provided_file_checksum.upper() == expected_file_checksum_hex)
    else:
        # If not provided, it's technically invalid / incomplete
        file_checksum_valid = False
        
    overall_valid = (len(failed_lines) == 0) and file_checksum_valid
    
    return {
        "file_checksum": expected_file_checksum_hex,
        "provided_file_checksum": provided_file_checksum,
        "line_results": line_results,
        "failed_lines": failed_lines,
        "is_valid": overall_valid
    }
