import os
import csv
from datetime import datetime, timedelta
from PIL import Image
import sys
import pyproj  # Import the projection library
from pyproj import Proj, transform

# Configuration constants
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"  # Correct format for timestamps in TSV files
WCA_FILENAME_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"  # WCA format for timestamps in filenames
ZEUSS_FILENAME_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"  # Zeuss format for timestamps in filenames

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
    """Read and parse TSV data from a file, including sensor and position data."""
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
    try:
        Image.open(os.path.join(image_folder, filename)).verify()
        return True
    except IOError:
        return False

def parse_timestamp_from_filename(filename, data_type):
    """Extract and parse the timestamp from an image filename."""
    try:
        if data_type == "WCA":
            # WCA example: P211C7655_20231102013334.jpg
            parts = filename.split("_")
            timestamp_str = parts[1][:14]  # Assumes the timestamp is the first 14 characters after the first underscore
        elif data_type == "Zeuss":
            # Zeuss example: 20231101T203856Z_0008_HERC_H.264_H2021_NA156_apo8_dtd4.mov.png
            timestamp_str = filename.split("_")[0]  # Timestamp before the first underscore
            timestamp_str = timestamp_str.replace('T', '').replace('Z', '')  # Remove 'T' and 'Z' for ISO 8601 format
        return datetime.strptime(timestamp_str, ZEUSS_FILENAME_TIMESTAMP_FORMAT)
    except ValueError:
        print(f"Error parsing timestamp in filename: {filename}")
        return None


def read_image_filenames(image_folder, data_type):
    """Read all image filenames from a folder and extract their timestamps."""
    image_data = []
    image_files = os.listdir(image_folder)
    total_files = len(image_files)
    processed_files = 0
    for filename in image_files:
        if is_image_file(filename, image_folder):
            timestamp = parse_timestamp_from_filename(filename, data_type)
            if timestamp:
                image_data.append({
                    "FILENAME": filename,
                    "TIMESTAMP": timestamp
                })
        processed_files += 1
        print(f"Progress: {processed_files}/{total_files} files processed", end='\r')
    print()  # Clean line after progress
    return image_data

def estimate_location(image_data, data_rows, utm_zone):
    """Estimate geographical location and sensor data for each image based on its timestamp."""
    matches_made = 0
    for image in image_data:
        relevant_data_rows = [row for row in data_rows if abs(row["TIME"] - image["TIMESTAMP"]) <= timedelta(seconds=2)]
        if relevant_data_rows:
            closest_match = min(relevant_data_rows, key=lambda row: abs(row["TIME"] - image["TIMESTAMP"]))
            lat, lon = closest_match.get("LAT"), closest_match.get("LONG")
            utm_x, utm_y = convert_to_utm(lat, lon, utm_zone)
            base_pitch = 40 if image["FILENAME"].startswith("P") else 0  # Default pitch adjusted to 40
            tsv_pitch = closest_match.get("PITCH", 0)
            image.update({
                "LAT": lat,
                "LONG": lon,
                "UTM_X": utm_x,
                "UTM_Y": utm_y,
                "ALTITUDE_EST": closest_match.get("DEPTH"),
                "HEADING": closest_match.get("HEADING"),
                "PITCH": base_pitch + tsv_pitch,
                "ROLL": closest_match.get("ROLL")
            })
            matches_made += 1
        else:
            image.update({
                "LAT": None, "LONG": None, "UTM_X": None, "UTM_Y": None,
                "ALTITUDE_EST": None, "HEADING": None,
                "PITCH": 40 if image["FILENAME"].startswith("P") else None, "ROLL": None  # Default pitch adjusted to 40
            })
            print(f"No matching TSV data within 2 seconds for image {image['FILENAME']}.")
    return matches_made

def generate_flight_log(image_data, image_folder, coordinate_system):
    """Generate a flight log file from the image data with selectable coordinate system (UTM or GPS)."""
    flight_log_filename = os.path.join(image_folder, "flight_log.txt")
    if os.path.exists(flight_log_filename):
        print(f"Flight log file already exists: {flight_log_filename}")
        sys.exit(1)

    with open(flight_log_filename, "w") as f:
        if coordinate_system == "UTM":
            f.write("Name;X (East);Y (North);Alt;Yaw;Pitch;Roll\n")  # UTM specific header
            for image in image_data:
                line = ";".join(str(x) for x in [
                    image["FILENAME"], image.get("UTM_X", ""), image.get("UTM_Y", ""),
                    image.get("ALTITUDE_EST", ""), image.get("HEADING", ""), image.get("PITCH", ""),
                    image.get("ROLL", "")
                ])
                f.write(line + "\n")
        else:  # GPS Coordinates
            f.write("Name;Lat;Long;Alt;Yaw;Pitch;Roll\n")  # GPS specific header
            for image in image_data:
                line = ";".join(str(x) for x in [
                    image["FILENAME"], image.get("LAT", ""), image.get("LONG", ""),
                    image.get("ALTITUDE_EST", ""), image.get("HEADING", ""), image.get("PITCH", ""),
                    image.get("ROLL", "")
                ])
                f.write(line + "\n")
    print(f"Flight log generated successfully. Location: {flight_log_filename}")

def main():
    data_type = input("Enter the data type to process (Zeuss or WCA): ").strip()
    if data_type not in ["Zeuss", "WCA"]:
        print("Invalid data type entered. Please enter either 'Zeuss' or 'WCA'.")
        sys.exit(1)

    tsv_filepath = input("Enter the full path to the TSV file: ").strip('\"')
    is_valid_file(tsv_filepath)
    image_folder = input("Enter the folder containing the images: ").strip('\"')
    is_valid_directory(image_folder)
    utm_zone = input("Enter the UTM zone number for coordinate conversion (leave blank for GPS coordinates): ").strip()
    coordinate_system = "UTM" if utm_zone else "GPS"
    print("Reading TSV data...")
    data_rows = read_tsv_data(tsv_filepath)
    print("Reading image filenames and timestamps...")
    image_data = read_image_filenames(image_folder, data_type)
    print("Estimating image locations...")
    matches_made = estimate_location(image_data, data_rows, utm_zone)
    print(f"Image locations estimated. Total matches made: {matches_made}")
    print("Generating flight log...")
    generate_flight_log(image_data, image_folder, coordinate_system)
    print(f"Files examined: {len(image_data)}")
    print(f"Data rows interpreted: {len(data_rows)}")

if __name__ == "__main__":
    main()
