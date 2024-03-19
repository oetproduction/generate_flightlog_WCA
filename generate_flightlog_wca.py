import os
import csv
from datetime import datetime
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
            next(reader)  # Skip the header row if present
            for row in reader:
                data_rows.append({
                    "TIME": datetime.fromisoformat(row[0]),
                    "LAT": row[1],
                    "LONG": row[2],
                    "DEPTH": row[3]
                })
    except FileNotFoundError:
        print("TSV file not found.")
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
    timestamp_str = parts[1].split(".")[0]  # Extract and clean timestamp
    try:
        return datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
    except ValueError:
        print(f"Error parsing timestamp in filename: {filename}")
        return None

def read_image_filenames(image_folder):
    """Read image filenames and timestamps from the given folder."""
    image_data = []
    for filename in os.listdir(image_folder):
        if is_image_file(filename, image_folder):
            timestamp = parse_timestamp_from_filename(filename)
            if timestamp:
                image_data.append({
                    "FILENAME": filename,
                    "TIMESTAMP": timestamp
                })
    return image_data

def estimate_location(image_data, data_rows):
    """Estimate location for each image based on timestamp."""
    for image in image_data:
        closest_match = min(data_rows, key=lambda row: abs(row["TIME"] - image["TIMESTAMP"]))
        image["LAT_EST"] = closest_match["LAT"]
        image["LONG_EST"] = closest_match["LONG"]
        image["ALTITUDE_EST"] = float(closest_match["DEPTH"])

def generate_flight_log(image_data, image_folder):
    """Generate a flight log file from the image data."""
    flight_log_filename = os.path.join(image_folder, "flight_log.txt")
    if os.path.exists(flight_log_filename):
        print(f"Flight log file already exists: {flight_log_filename}")
        sys.exit(1)
    
    unique_locations = set()
    with open(flight_log_filename, "w") as f:
        f.write("FILENAME;LAT_EST;LONG_EST;ALTITUDE_EST\n")  # Header
        for image in image_data:
            line = "{};{};{};{}".format(image["FILENAME"], image["LAT_EST"], image["LONG_EST"], image["ALTITUDE_EST"])
            if line not in unique_locations:
                f.write(line + "\n")
                unique_locations.add(line)

def main():
    tsv_filepath = input("Enter the full path to the TSV file: ").strip('\"')
    is_valid_file(tsv_filepath)

    image_folder = input("Enter the folder containing the images: ").strip('\"')
    is_valid_directory(image_folder)

    data_rows = read_tsv_data(tsv_filepath)
    image_data = read_image_filenames(image_folder)

    estimate_location(image_data, data_rows)
    generate_flight_log(image_data, image_folder)

    print("Files examined: {}".format(len(image_data)))
    print("Data rows interpreted: {}".format(len(data_rows)))

if __name__ == "__main__":
    main()
