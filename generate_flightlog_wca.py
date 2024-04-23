import os
import csv
from datetime import datetime, timedelta
from PIL import Image
import sys
import pyproj  # Import the projection library
from pyproj import Proj, transform

# Configuration constants
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"  # Correct format for timestamps in TSV files
FILENAME_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"  # Common format for timestamps in filenames

def is_valid_directory(path):
    """Check if the specified directory is valid and accessible."""
    if not os.path.isdir(path):
        print(f"Directory does not exist: {path}")
        sys.exit(1)

def is_valid_file(path):
    """Check if the specified file is valid and accessible."""
    if not os.path.isfile(path):
        print(f"File does not exist: {path}")
        sys.exit(1)

def read_tsv_data(filename):
    """Read and parse TSV data from a file."""
    data_rows = []
    try:
        with open(filename, "r") as tsvfile:
            reader = csv.reader(tsvfile, delimiter='\t')
            header = next(reader)
            idx_map = {name: index for index, name in enumerate(header)}
            for row in reader:
                data_rows.append({
                    "TIME": datetime.strptime(row[idx_map['time']], TIMESTAMP_FORMAT),
                    "LAT": float(row[idx_map['usbl_lat']]) if row[idx_map['usbl_lat']] else None,
                    "LONG": float(row[idx_map['usbl_lon']]) if row[idx_map['usbl_lon']] else None,
                    "DEPTH": -abs(float(row[idx_map['paro_depth_m']])) if row[idx_map['paro_depth_m']] else None,
                    "HEADING": float(row[idx_map['octans_heading']]) if row[idx_map['octans_heading']] else None,
                    "PITCH": float(row[idx_map['octans_pitch']]) if row[idx_map['octans_pitch']] else None,
                    "ROLL": float(row[idx_map['octans_roll']]) if row[idx_map['octans_roll']] else None
                })
    except Exception as e:
        print(f"Error processing TSV file: {e}")
        sys.exit(1)
    return data_rows

def convert_to_utm(lat, lon, utm_zone):
    """Convert latitude and longitude to UTM coordinates in the specified zone."""
    if not lat or not lon:
        return None, None
    try:
        zone_number = utm_zone[:-1]
        hemisphere = 'north' if utm_zone[-1].upper() == 'N' else 'south'
        proj_string = f"+proj=utm +zone={zone_number} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
        proj_utm = Proj(proj_string, preserve_units=False)
        utm_x, utm_y = proj_utm(lon, lat)
        if hemisphere == 'south':
            utm_y -= 10000000.0
        return utm_x, utm_y
    except Exception as e:
        print(f"Failed to convert to UTM coordinates: {e}")
        return None, None

def is_image_file(filename, image_folder):
    """Check if a specified file is a valid image file."""
    try:
        Image.open(os.path.join(image_folder, filename)).verify()
        return True
    except IOError:
        return False

def parse_timestamp_from_filename(filename, camera_type):
    """Extract and parse the timestamp from an image filename."""
    try:
        # Extract timestamp based on camera type
        if camera_type in ['C', 'P']:  # Cinema or Port
            parts = filename.split("_")
            timestamp_str = parts[1][:14]  # Assumes the timestamp is the first 14 characters after the first underscore
        else:  # Zeuss (no prefix)
            timestamp_str = filename.split("_")[0]  # Timestamp before the first underscore
            timestamp_str = timestamp_str.replace('T', '').replace('Z', '')  # Remove 'T' and 'Z' for ISO 8601 format
        return datetime.strptime(timestamp_str, FILENAME_TIMESTAMP_FORMAT)
    except ValueError:
        print(f"Error parsing timestamp in filename: {filename}")
        return None

def read_image_filenames(image_folder, pitch_values, focal_lengths):
    """Read all image filenames from a folder and extract their timestamps, determine camera type, pitch, and focal length."""
    image_data = []
    image_files = os.listdir(image_folder)
    total_files = len(image_files)
    processed_files = 0
    for filename in image_files:
        if is_image_file(filename, image_folder):
            # Determine camera type by prefix
            if filename.startswith('C'):
                camera_type = 'C'
            elif filename.startswith('P'):
                camera_type = 'P'
            else:
                camera_type = 'Zeuss'  # Default to Zeuss if no prefix
            timestamp = parse_timestamp_from_filename(filename, camera_type)
            if timestamp:
                image_data.append({
                    "FILENAME": filename,
                    "TIMESTAMP": timestamp,
                    "PITCH": pitch_values.get(camera_type, 75),  # Default pitch for Zeuss if not specified
                    "FOCAL_LENGTH": focal_lengths[camera_type]
                })
        processed_files += 1
        print(f"Progress: {processed_files}/{total_files} files processed", end='\r')
    print()  # Clean line after progress
    return image_data

def main():
    # Get pitch values and focal lengths from user
    pitch_values = {
        'C': float(input("Enter the pitch for Cinema Camera (C): ")),
        'P': float(input("Enter the pitch for Port Camera (P): ")),
        'Zeuss': float(input("Enter the pitch for Zeuss Camera: "))
    }
    focal_lengths = {
        'C': '16mm',
        'P': '14mm',
        'Zeuss': '18mm'
    }

    tsv_filepath = input("Enter the full path to the TSV file: ").strip('\"')
    is_valid_file(tsv_filepath)
    image_folder = input("Enter the folder containing the images: ").strip('\"')
    is_valid_directory(image_folder)
    utm_zone = input("Enter the UTM zone number for coordinate conversion (leave blank for GPS coordinates): ").strip()
    coordinate_system = "UTM" if utm_zone else "GPS"
    print("Reading TSV data...")
    data_rows = read_tsv_data(tsv_filepath)
    print("Reading image filenames and timestamps...")
    image_data = read_image_filenames(image_folder, pitch_values, focal_lengths)
    print(f"Files examined: {len(image_data)}")
    print(f"Data rows interpreted: {len(data_rows)}")

if __name__ == "__main__":
    main()
