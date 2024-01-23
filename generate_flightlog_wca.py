import os
import csv
from datetime import datetime
from PIL import Image  # Add PIL library for image format checking

# Prompt the user for the path of the TSV file
tsv_folder = input("Enter the path of the folder containing the TSV file: ")
tsv_filename = input("Enter the name of the TSV file: ")

# Prompt the user for the folder where the flight log should be exported
output_folder = input("Enter the folder where the flight log should be exported: ")

# Configuration
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S"
REFERENCE_DEPTH = 0

# Function to read TSV data
def read_tsv_data(filename):
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
        exit()
    return data_rows

# Function to read image filenames and timestamps
def read_image_filenames(image_folder):
    image_data = []
    for filename in os.listdir(image_folder):
        if is_image_file(filename):  # Check if the file is an image
            timestamp_str = filename[:15]
            image_data.append({
                "FILENAME": filename,
                "TIMESTAMP": datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
            })
    return image_data

# Function to check if a file is an image
def is_image_file(filename):
    try:
        Image.open(os.path.join(image_folder, filename))
        return True
    except Exception as e:
        return False

# Function to estimate location
def estimate_location(image_data, data_rows):
    for image in image_data:
        closest_match = min(data_rows, key=lambda row: abs(row["TIME"] - image["TIMESTAMP"]))
        image["LAT_EST"] = closest_match["LAT"]
        image["LONG_EST"] = closest_match["LONG"]
        image["ALTITUDE_EST"] = REFERENCE_DEPTH - float(closest_match["DEPTH"])

# Function to generate flight log
def generate_flight_log(image_data, output_filename):
    unique_locations = set()
    with open(output_filename, "w") as f:
        f.write("FILENAME;LAT_EST;LONG_EST;ALTITUDE_EST\n")  # Header
        for image in image_data:
            line = "{};{};{};{}".format(image["FILENAME"], image["LAT_EST"], image["LONG_EST"], image["ALTITUDE_EST"])
            if line not in unique_locations:
        
