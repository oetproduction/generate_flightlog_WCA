import os
import csv
from datetime import datetime, timedelta
from PIL import Image  # PIL is used for verifying image files
import sys  # sys is used for accessing command line arguments and exiting the program for errors

# Configuration constants
TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"  # Expected format for timestamps in filenames
COMMON_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}  # Supported image formats

def is_valid_directory(path):
    """Check if the specified directory is valid and accessible.
    Args:
        path (str): Path to the directory to check.
    """
    if not os.path.isdir(path):
        print(f"Directory does not exist: {path}")
        sys.exit(1)

def is_valid_file(path):
    """Check if the specified file is valid and accessible.
    Args:
        path (str): Path to the file to check.
    """
    if not os.path.isfile(path):
        print(f"File does not exist: {path}")
        sys.exit(1)

def read_tsv_data(filename):
    """Read and parse TSV data from a file.
    Assumes a specific TSV format with predefined columns including time, GPS data, and sensor measurements.
    Depth values are converted to negative to reflect below sea level measurements.
    Args:
        filename (str): Path to the TSV file.
    Returns:
        list of dict: Extracted data, each entry containing timestamp, latitude, longitude, negative depth, heading, pitch, and roll.
    """
    data_rows = []
    try:
        with open(filename, "r") as tsvfile:
            reader = csv.reader(tsvfile, delimiter='\t')
            header = next(reader)  # Read the header row
            # Retrieve the indices for necessary columns based on header names
            time_idx = header.index('time')
            depth_idx = header.index('paro_depth_m')
            lat_idx = header.index('usbl_lat')
            lon_idx = header.index('usbl_lon')
            heading_idx = header.index('octans_heading')
            pitch_idx = header.index('octans_pitch')
            roll_idx = header.index('octans_roll')

            for row in reader:
                depth = -abs(float(row[depth_idx])) if row[depth_idx] else None
                data_rows.append({
                    "TIME": datetime.fromisoformat(row[time_idx]),
                    "LAT": row[lat_idx] if row[lat_idx] else None,
                    "LONG": row[lon_idx] if row[lon_idx] else None,
                    "DEPTH": depth,
                    "HEADING": float(row[heading_idx]) if row[heading_idx] else None,
                    "PITCH": float(row[pitch_idx]) if row[pitch_idx] else None,
                    "ROLL": float(row[roll_idx]) if row[roll_idx] else None
                })
    except FileNotFoundError:
        print("TSV file not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"Error processing TSV file: {e}")
        sys.exit(1)
    return data_rows

def is_image_file(filename, image_folder):
    """Check if a specified file is a valid image file based on file extension and by opening it.
    Args:
        filename (str): Filename of the image file.
        image_folder (str): Directory containing the image file.
    Returns:
        bool: True if the file is a valid image, False otherwise.
    """
    try:
        Image.open(os.path.join(image_folder, filename)).verify()
        return True
    except IOError:
        return False

def parse_timestamp_from_filename(filename):
    """Extract and parse the timestamp from an image filename.
    Args:
        filename (str): Filename that includes a timestamp.
    Returns:
        datetime: Parsed timestamp or None if parsing fails.
    """
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
    """Read all image filenames from a folder and extract their timestamps.
    Args:
        image_folder (str): Path to the folder containing images.
    Returns:
        list of dict: List containing filename and timestamp data for each image.
    """
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
    """Estimate geographical location and sensor data for each image based on its timestamp.
    For images starting with 'P', set default pitch to -50 degrees and add TSV data pitch if available.
    Args:
        image_data (list of dict): Image data including filenames and timestamps.
        data_rows (list of dict): Data rows from the TSV file including location and sensor data.
    Returns:
        int: Number of images for which a location and sensor data were successfully estimated.
    """
    matches_made = 0
    for image in image_data:
        # Find data rows within a 2-second window of the image's timestamp
        relevant_data_rows = [row for row in data_rows if abs(row["TIME"] - image["TIMESTAMP"]) <= timedelta(seconds=2)]
        if relevant_data_rows:
            # Select the closest match based on time difference
            closest_match = min(relevant_data_rows, key=lambda row: abs(row["TIME"] - image["TIMESTAMP"]))
            image["LAT_EST"] = closest_match.get("LAT")
            image["LONG_EST"] = closest_match.get("LONG")
            image["ALTITUDE_EST"] = closest_match.get("DEPTH")
            image["HEADING"] = closest_match.get("HEADING")
            
            # Handle pitch for images starting with 'P'
            base_pitch = -50 if image["FILENAME"].startswith("P") else 0
            tsv_pitch = closest_match.get("PITCH", 0)
            image["PITCH"] = base_pitch + tsv_pitch

            image["ROLL"] = closest_match.get("ROLL")
            matches_made += 1
        else:
            print(f"No matching TSV data found within 2 seconds for image {image['FILENAME']}")
            image.update({"LAT_EST": None, "LONG_EST": None, "ALTITUDE_EST": None, "HEADING": None, "PITCH": -50 if image["FILENAME"].startswith("P") else None, "ROLL": None})

    return matches_made




def generate_flight_log(image_data, image_folder):
    """Generate a flight log file from the image data."""
    flight_log_filename = os.path.join(image_folder, "flight_log.txt")
    if os.path.exists(flight_log_filename):
        print(f"Flight log file already exists: {flight_log_filename}")
        sys.exit(1)

    unique_locations = set()
    with open(flight_log_filename, "w") as f:
        f.write("FILENAME;LAT_EST;LONG_EST;ALTITUDE_EST;HEADING;PITCH;ROLL\n")  # Updated header
        for image in image_data:
            line_elements = [
                image["FILENAME"],
                image.get("LAT_EST", ""),
                image.get("LONG_EST", ""),
                image.get("ALTITUDE_EST", ""),
                image.get("HEADING", ""),
                image.get("PITCH", ""),
                image.get("ROLL", "")
            ]
            line = ";".join(map(str, line_elements))

            if line not in unique_locations:
                f.write(line + "\n")
                unique_locations.add(line)

    # Print confirmation message once after writing to the file
    print(f"Flight log generated successfully. Location: {flight_log_filename}")


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
    print(f"Image locations estimated. Total matches made: {matches_made}")

    print("Generating flight log...")
    generate_flight_log(image_data, image_folder)

    print(f"Files examined: {len(image_data)}")
    print(f"Data rows interpreted: {len(data_rows)}")

if __name__ == "__main__":
    main()
