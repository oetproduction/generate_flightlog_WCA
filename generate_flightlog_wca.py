import os
import csv
from datetime import datetime, timedelta
from PIL import Image  # Used for image file verification
import sys  # For command line arguments

# Configuration
TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"
COMMON_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}

def is_valid_directory(path):
    """Check if a directory is valid and accessible."""
    if not os.path.isdir(path):
        print(f"Directory does not exist: {path}")
        sys.exit(1)

def is_valid_file(path):
    """Check if a file is valid and accessible."""
    if not os.path.isfile(path):
        print(f"File does not exist: {path}")
        sys.exit(1)

def read_tsv_data(filename):
    """Read TSV data from the given file."""
    data_rows = []
    try:
        with open(filename, "r") as tsvfile:
            reader = csv.reader(tsvfile, delimiter='\t')
            next(reader)  # Skip the header row
            for row in reader:
                depth = -1 * float(row[13]) if row[13] else None
                data_rows.append({
                    "TIME": datetime.fromisoformat(row[0]),
                    "LAT": row[16],
                    "LONG": row[17],
                    "DEPTH": depth
                })
    except FileNotFoundError:
        print("TSV file not found.")
        sys.exit(1)
    except ValueError:
        print("Error converting depth value to float.")
        sys.exit(1)
    return data_rows

def is_image_file(filename, image_folder):
    """Check if a file is an image using its MIME type."""
    try:
        Image.open(os.path.join(image_folder, filename)).verify()
        return True
    except IOError:
        return False

def parse_timestamp_from_filename(filename):
    """Extract and parse the timestamp from the filename."""
    parts = filename.split("_")
    if len(parts) < 2:
        print(f"Filename does not contain a valid timestamp: {filename}")
        return None
    timestamp_str = parts[1].split(".")[0]
    try:
        return datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
    except ValueError:
        print(f"Error parsing timestamp in filename: {filename}")
        return None

def read_image_filenames(image_folder):
    """Read image filenames and timestamps from the given folder."""
    image_data = []
    image_files = os.listdir(image_folder)
    total_files = len(image_files)
    processed_files = 0
    
    for filename in image_files:
        processed_files += 1
        print(f"Progress: {processed_files}/{total_files} files processed", end='\r')
        
        if is_image_file(filename, image_folder):
            timestamp = parse_timestamp_from_filename(filename)
            if timestamp:
                image_data.append({
                    "FILENAME": filename,
                    "TIMESTAMP": timestamp
                })
    
    print()  # Move to the next line after the progress indicator is completed
    return image_data

def estimate_location(image_data, data_rows):
    """Estimate location for each image based on timestamp."""
    matches_made = 0
    for image in image_data:
        relevant_data_rows = [row for row in data_rows if abs(row["TIME"] - image["TIMESTAMP"]) <= timedelta(seconds=2)]
        if relevant_data_rows:
            closest_match = min(relevant_data_rows, key=lambda row: abs(row["TIME"] - image["TIMESTAMP"]))
            image["LAT_EST"] = closest_match["LAT"]
            image["LONG_EST"] = closest_match["LONG"]
            image["ALTITUDE_EST"] = float(closest_match["DEPTH"])
            matches_made += 1
        else:
            print(f"No matching data within 2 seconds for image {image['FILENAME']}.")
            image["LAT_EST"] = None
            image["LONG_EST"] = None
            image["ALTITUDE_EST"] = None
    
    return matches_made

def generate_flight_log(image_data, image_folder):
    """Generate a flight log file from the image data."""
    flight_log_filename = os.path.join(image_folder, "flight_log.txt")
    if os.path.exists(flight_log_filename):
        print(f"Flight log file already exists: {flight_log_filename}")
        sys.exit(1)

    unique_locations = set()
    with open(flight_log_filename, "w") as f:
        f.write("FILENAME;LAT_EST;LONG_EST;ALTITUDE_EST;PITCH\n")  # Header with "Pitch"
        for image in image_data:
            pitch = ""
            if image["FILENAME"].startswith("P"):
                pitch = -60
            
            line_elements = [
                image["FILENAME"],
                image["LAT_EST"] if image["LAT_EST"] is not None else "",
                image["LONG_EST"] if image["LONG_EST"] is not None else "",
                image["ALTITUDE_EST"] if image["ALTITUDE_EST"] is not None else "",
                str(pitch) if pitch != "" else ""
            ]
            line = ";".join(map(str, line_elements))

            if line not in unique_locations:
                f.write(line + "\n")
                unique_locations.add(line)

def main():
    tsv_filepath = input("Enter the full path to the TSV file: ").strip('\"')
    is_valid_file(tsv_filepath)

    image_folder = input("Enter the folder containing the images: ").strip('\"')
    is_valid_directory(image_folder)

    print("Reading TSV data...")
    data_rows = read_tsv_data(tsv_filepath)
    print("TSV data read successfully.")

    print("Reading image filenames and timestamps...")
    image_data = read_image_filenames(image_folder)
    print("Image filenames and timestamps read successfully.")

    print("Estimating image locations...")
    matches_made = estimate_location(image_data, data_rows)
    print(f"\nImage locations estimated. Total matches made: {matches_made}")

    print("Generating flight log...")
    generate_flight_log(image_data, image_folder)
    flight_log_path = os.path.join(image_folder, "flight_log.txt")
    print(f"Flight log generated successfully. Location: {flight_log_path}")

    print(f"Files examined: {len(image_data)}")
    print(f"Data rows interpreted: {len(data_rows)}")

if __name__ == "__main__":
    main()
