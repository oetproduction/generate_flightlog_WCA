import os
import csv
from datetime import datetime, timedelta
from PIL import Image
import sys
import simplekml
from pyproj import Proj

# Constants
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"
FILENAME_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"

def is_valid_directory(path):
    """Ensure the directory exists."""
    if not os.path.isdir(path):
        print(f"Directory does not exist: {path}")
        sys.exit(1)

def is_valid_file(path):
    """Ensure the file exists."""
    if not os.path.isfile(path):
        print(f"File does not exist: {path}")
        sys.exit(1)

def read_tsv_data(filename):
    """Read TSV data and return a list of dictionaries for each row."""
    print("Reading TSV data...")
    data_rows = []
    try:
        with open(filename, "r") as tsvfile:
            reader = csv.reader(tsvfile, delimiter='\t')
            headers = next(reader)
            for row in reader:
                data_rows.append({headers[i]: row[i] for i in range(len(row))})
    except Exception as e:
        print(f"Error processing TSV file: {e}")
        sys.exit(1)
    print("TSV data loaded successfully.")
    return data_rows

def convert_to_utm(lat, lon, utm_zone):
    """Convert geographic coordinates to UTM."""
    if lat is None or lon is None:
        return None, None
    try:
        proj_string = f"+proj=utm +zone={utm_zone[:-1]} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
        proj_utm = Proj(proj_string)
        return proj_utm(lon, lat)
    except Exception as e:
        print(f"Failed to convert to UTM coordinates: {e}")
        return None, None

def is_image_file(filename, image_folder):
    """Check if a file is an image."""
    try:
        Image.open(os.path.join(image_folder, filename)).verify()
        return True
    except IOError:
        return False

def parse_timestamp_from_filename(filename):
    """Extract timestamp from filename."""
    parts = filename.split('_')
    try:
        if len(parts) > 1 and parts[0].isdigit():
            return datetime.strptime(parts[0], FILENAME_TIMESTAMP_FORMAT)
        else:
            return None
    except ValueError:
        print(f"Error parsing timestamp in filename: {filename}")
        return None

def read_image_filenames(image_folder):
    """Read image filenames from a folder."""
    print("Reading image filenames and timestamps...")
    image_data = []
    image_files = os.listdir(image_folder)
    total_files = len(image_files)
    processed_files = 0
    for filename in image_files:
        if is_image_file(filename, image_folder):
            timestamp = parse_timestamp_from_filename(filename)
            if timestamp:
                image_data.append({"FILENAME": filename, "TIMESTAMP": timestamp})
        processed_files += 1
        print(f"Processing {processed_files}/{total_files} files", end='\r')
    print("\nAll image filenames and timestamps read successfully.")
    return image_data

def generate_flight_log(image_data, flight_log_filename, coordinate_system, camera_settings):
    """Generate a flight log file only for entries with valid coordinate data."""
    print(f"Generating flight log at {flight_log_filename}...")
    if os.path.exists(flight_log_filename):
        print(f"Flight log file already exists: {flight_log_filename}")
        return

    with open(flight_log_filename, "w") as file:
        # Define the header based on the coordinate system chosen
        header = "Name;X (East);Y (North);Alt;Yaw;Pitch;Roll;FocalLength\n" if coordinate_system == "UTM" else "Name;Lat;Long;Alt;Yaw;Pitch;Roll;FocalLength\n"
        file.write(header)
        
        # Iterate over each image's data and format it correctly
        for image in image_data:
            if coordinate_system == "UTM" and image.get("UTM_X") and image.get("UTM_Y"):
                line_elements = [
                    image["FILENAME"],
                    image["UTM_X"], 
                    image["UTM_Y"],
                    image.get("ALTITUDE_EST", "N/A"),
                    image.get("HEADING", "N/A"),
                    camera_settings.get(image.get("CAMERA_TYPE", ""), {}).get("pitch", "N/A"),
                    image.get("ROLL", "N/A"),
                    camera_settings.get(image.get("CAMERA_TYPE", ""), {}).get("focal_length", "N/A")
                ]
            elif coordinate_system == "GPS" and image.get("LAT") and image.get("LONG"):
                line_elements = [
                    image["FILENAME"],
                    image["LAT"], 
                    image["LONG"],
                    image.get("ALTITUDE_EST", "N/A"),
                    image.get("HEADING", "N/A"),
                    camera_settings.get(image.get("CAMERA_TYPE", ""), {}).get("pitch", "N/A"),
                    image.get("ROLL", "N/A"),
                    camera_settings.get(image.get("CAMERA_TYPE", ""), {}).get("focal_length", "N/A")
                ]
            else:
                continue  # Skip writing this line if coordinates are not available
            
            # Join elements and write to the flight log if valid
            line = ";".join(map(str, line_elements))
            file.write(line + "\n")
    print(f"Flight log generated successfully at: {flight_log_filename}")


def generate_kml(image_data, kml_filename):
    """Generate a KML file for Google Earth."""
    print(f"Generating KML file at {kml_filename}...")
    kml = simplekml.Kml()
    for image in image_data:
        if image.get("LAT") and image.get("LONG"):
            pnt = kml.newpoint(name=image['FILENAME'], coords=[(image['LONG'], image['LAT'])])
            pnt.description = f"Altitude: {image.get('ALTITUDE_EST', 'N/A')} meters"
    kml.save(kml_filename)
    print(f"KML file generated successfully at: {kml_filename}")

def main():
    # Configuration and input gathering
    default_camera_settings = {
        'C': {'pitch': 30, 'focal_length': '16mm'},
        'P': {'pitch': 85, 'focal_length': '14mm'},
        'Zeuss': {'pitch': None, 'focal_length': None}
    }

    tsv_filepath = input("Enter the full path to the TSV file: ").strip('\"')
    image_folder = input("Enter the folder containing the images: ").strip('\"')
    utm_zone = input("Enter the UTM zone number for coordinate conversion (leave blank for GPS coordinates): ").strip()
    coordinate_system = "UTM" if utm_zone.strip() else "GPS"

    # Validation
    is_valid_file(tsv_filepath)
    is_valid_directory(image_folder)

    # Data processing
    data_rows = read_tsv_data(tsv_filepath)
    image_data = read_image_filenames(image_folder)
    flight_log_filename = os.path.join(image_folder, "general_flight_log.txt")
    kml_filename = os.path.join(image_folder, "flight_data.kml")

    # Output generation
    generate_flight_log(image_data, flight_log_filename, coordinate_system, default_camera_settings)
    generate_kml(image_data, kml_filename)

if __name__ == "__main__":
    main()
