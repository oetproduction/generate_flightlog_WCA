import os
import csv
from datetime import datetime, timedelta
from PIL import Image
import sys
import pyproj  # Import the projection library
from pyproj import Proj, transform
import simplekml

# Configuration constants
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"  # Correct format for timestamps in TSV files
FILENAME_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"  # Format for timestamps in filenames

def generate_kml(image_data, image_folder):
    kml = simplekml.Kml()
    for image in image_data:
        if 'LAT' in image and 'LONG' in image and image['LAT'] != "Not Available" and image['LONG'] != "Not Available":
            pnt = kml.newpoint(name=image['FILENAME'], coords=[(float(image['LONG']), float(image['LAT']))])
            pnt.description = f"Altitude: {image['ALTITUDE_EST']} meters\nHeading: {image['HEADING']}\nPitch: {image['PITCH']}\nRoll: {image['ROLL']}\nFocal Length: {image['FOCAL_LENGTH']}"
            pnt.altitudemode = simplekml.AltitudeMode.relativetoground
            pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/camera.png'
    kml.save(os.path.join(image_folder, "flight_data.kml"))
    print(f"KML file generated successfully. Location: {os.path.join(image_folder, 'flight_data.kml')}")
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
    try:
        Image.open(os.path.join(image_folder, filename)).verify()
        return True
    except IOError:
        return False

def parse_timestamp_from_filename(filename):
    """Extract and parse the timestamp from an image filename, handling different camera types."""
    try:
        if filename.startswith('C') or filename.startswith('P'):
            # Assumes timestamp follows first underscore
            timestamp_str = filename.split("_")[1][:14]
        else:  # Default to 'Zeuss' camera type
            timestamp_str = filename.split("_")[0]
        return datetime.strptime(timestamp_str, FILENAME_TIMESTAMP_FORMAT)
    except ValueError:
        print(f"Error parsing timestamp in filename: {filename}")
        return None

def read_image_filenames(image_folder):
    """Read all image filenames from a folder and extract their timestamps."""
    image_data = []
    image_files = os.listdir(image_folder)
    total_files = len(image_files)
    processed_files = 0
    for filename in image_files:
        if is_image_file(filename, image_folder):
            timestamp = parse_timestamp_from_filename(filename)
            if timestamp:
                camera_type = 'Zeuss' if not filename[0].isalpha() else filename[0]
                image_data.append({
                    "FILENAME": filename,
                    "TIMESTAMP": timestamp,
                    "CAMERA_TYPE": camera_type
                })
        processed_files += 1
        print(f"Progress: {processed_files}/{total_files} files processed", end='\r')
    print()  # Clean line after progress
    return image_data

def estimate_location(image_data, data_rows, utm_zone, camera_pitches, camera_focal_lengths):
    matches_made = 0
    no_match_count = 0
    convert_utm = bool(utm_zone.strip())  # Check if UTM zone is provided and not just blank
    for image in list(image_data):  # Use list to safely modify while iterating
        relevant_data_rows = [row for row in data_rows if abs(row["TIME"] - image["TIMESTAMP"]) <= timedelta(seconds=2)]
        if relevant_data_rows:
            closest_match = min(relevant_data_rows, key=lambda row: abs(row["TIME"] - image["TIMESTAMP"]))
            if closest_match.get("LAT") is not None and closest_match.get("LONG") is not None:
                utm_x, utm_y = (convert_to_utm(closest_match["LAT"], closest_match["LONG"], utm_zone) if convert_utm else ("Not Applicable", "Not Applicable"))
                image.update({
                    "LAT": closest_match["LAT"],
                    "LONG": closest_match["LONG"],
                    "UTM_X": utm_x,
                    "UTM_Y": utm_y,
                    "ALTITUDE_EST": closest_match["DEPTH"],
                    "HEADING": closest_match["HEADING"],
                    "PITCH": camera_pitches.get(image["CAMERA_TYPE"]),
                    "ROLL": closest_match["ROLL"],
                    "FOCAL_LENGTH": camera_focal_lengths.get(image["CAMERA_TYPE"])
                })
                matches_made += 1
            else:
                image_data.remove(image)
                no_match_count += 1
        else:
            image_data.remove(image)
            no_match_count += 1
    return matches_made, no_match_count


def generate_flight_log(image_data, image_folder, coordinate_system):
    """Generate a flight log file from the image data with selectable coordinate system (UTM or GPS)."""
    flight_log_filename = os.path.join(image_folder, "flight_log.txt")
    if os.path.exists(flight_log_filename):
        print(f"Flight log file already exists: {flight_log_filename}")
        sys.exit(1)

    with open(flight_log_filename, "w") as f:
        header = "Name;X (East);Y (North);Alt;Yaw;Pitch;Roll;FocalLength\n" if coordinate_system == "UTM" \
            else "Name;Lat;Long;Alt;Yaw;Pitch;Roll;FocalLength\n"
        f.write(header)
        for image in image_data:
            if coordinate_system == "UTM":
                line_elements = [
                    image["FILENAME"],
                    image["UTM_X"], 
                    image["UTM_Y"],
                    image["ALTITUDE_EST"], 
                    image["HEADING"], 
                    image["PITCH"], 
                    image["ROLL"], 
                    image["FOCAL_LENGTH"]
                ]
            else:  # GPS Coordinates
                line_elements = [
                    image["FILENAME"],
                    image["LAT"], 
                    image["LONG"],
                    image["ALTITUDE_EST"], 
                    image["HEADING"], 
                    image["PITCH"], 
                    image["ROLL"], 
                    image["FOCAL_LENGTH"]
                ]
            line = ";".join(map(str, line_elements))
            f.write(line + "\n")
    print(f"Flight log generated successfully. Location: {flight_log_filename}")

def main():
    # Set default values for pitch and focal length settings
    default_pitches = {'C': 30, 'P': 85, 'Zeuss': 80}
    default_focal_lengths = {'C': '16mm', 'P': '14mm', 'Zeuss': '20mm'}

    # Optionally, ask users if they want to change these defaults
    change_defaults = input("Do you want to change the default settings for pitch and focal length? (y/n): ").lower()
    if change_defaults == 'y':
        pitch_c = float(input("Enter the pitch for Cinema Camera (C) [Default: 30]: ") or default_pitches['C'])
        pitch_p = float(input("Enter the pitch for Port Camera (P) [Default: 85]: ") or default_pitches['P'])
        pitch_zeuss = float(input("Enter the pitch for Zeuss Camera (default/no prefix) [Default: 80]: ") or default_pitches['Zeuss'])
        focal_c = input("Enter the focal length for Cinema Camera (C) [Default: 16mm]: ") or default_focal_lengths['C']
        focal_p = input("Enter the focal length for Port Camera (P) [Default: 14mm]: ") or default_focal_lengths['P']
        focal_zeuss = input("Enter the focal length for Zeuss Camera (default/no prefix) [Default: 20mm]: ") or default_focal_lengths['Zeuss']
    else:
        pitch_c, pitch_p, pitch_zeuss = default_pitches.values()
        focal_c, focal_p, focal_zeuss = default_focal_lengths.values()

    camera_pitches = {'C': pitch_c, 'P': pitch_p, 'Zeuss': pitch_zeuss}
    camera_focal_lengths = {'C': focal_c, 'P': focal_p, 'Zeuss': focal_zeuss}

    tsv_filepath = input("Enter the full path to the TSV file: ").strip('\"')
    is_valid_file(tsv_filepath)
    image_folder = input("Enter the folder containing the images: ").strip('\"')
    is_valid_directory(image_folder)
    utm_zone = input("Enter the UTM zone number for coordinate conversion (leave blank for GPS coordinates): ").strip()
    coordinate_system = "UTM" if utm_zone.strip() else "GPS"
    print("Reading TSV data...")
    data_rows = read_tsv_data(tsv_filepath)
    print("Reading image filenames and timestamps...")
    image_data = read_image_filenames(image_folder)
    print("Estimating image locations...")
    matches_made, no_match_count = estimate_location(image_data, data_rows, utm_zone, camera_pitches, camera_focal_lengths)
    print(f"Image locations estimated. Total matches made: {matches_made}")
    print("Generating flight log...")
    generate_flight_log(image_data, image_folder, coordinate_system)
    print("Generating KML file for Google Earth...")
    generate_kml(image_data, image_folder)
    print(f"Files examined: {len(image_data)}")
    print(f"Data rows interpreted: {len(data_rows)}")
    print(f"Images with no matches: {no_match_count}")

if __name__ == "__main__":
    main()

