from flask import Flask, render_template, request, jsonify
import serial
import time
import csv
from datetime import datetime
import os
import re

app = Flask(__name__)

# Configure serial connection (adjust port and baud rate as needed)
SERIAL_PORT = "/dev/ttyS0"  # UART port on Raspberry Pi
BAUD_RATE = 115200

# Path to the CSV log file
LOG_FILE = "test_logs.csv"

# Ensure the CSV file exists and has headers
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["IMEI", "Command", "Response", "Timestamp"])

def send_at_command(command):
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ser.write((command + "\r\n").encode())
        time.sleep(1)  # Wait for the module to respond
        
        # Read raw bytes from the serial port
        raw_response = ser.read_all()
        
        # Try decoding as UTF-8, fallback to Latin-1 if it fails
        try:
            response = raw_response.decode("utf-8").strip()
        except UnicodeDecodeError:
            response = raw_response.decode("latin-1").strip()
        
        ser.close()
        return response
    except Exception as e:
        return f"Error: {str(e)}"

def extract_imei(response):
    # Extract the IMEI from the response of the AT+GSN command
    imei_match = re.search(r"\d{15}", response)  # IMEI is typically 15 digits
    if imei_match:
        return imei_match.group(0)
    return "Unknown"

def log_test_result(imei, command, response):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([imei, command, response, timestamp])

def get_test_logs(page=1, per_page=10):
    with open(LOG_FILE, mode="r") as file:
        reader = csv.reader(file)
        logs = list(reader)[1:]  # Skip header row
    total_logs = len(logs)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_logs = logs[start:end]
    return {
        "logs": paginated_logs,
        "total_logs": total_logs,
        "page": page,
        "per_page": per_page,
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/send_command", methods=["POST"])
def send_command():
    command = request.json.get("command")
    response = send_at_command(command)
    
    # Get IMEI to use as primary key
    imei_response = send_at_command("AT+GSN")
    imei = extract_imei(imei_response)
    
    # Log the test result
    log_test_result(imei, command, response)
    
    return jsonify({"response": response})

@app.route("/check_4g_status", methods=["POST"])
def check_4g_status():
    commands = ["AT+CEREG?", "AT+CSQ", "AT+COPS?", "AT+CGACT?"]
    responses = []
    for cmd in commands:
        response = send_at_command(cmd)
        responses.append(f"{cmd}\n{response}")
    
    # Get IMEI to use as primary key
    imei_response = send_at_command("AT+GSN")
    imei = extract_imei(imei_response)
    
    # Log the test result
    log_test_result(imei, "4G Status Check", "\n".join(responses))
    
    return jsonify({"response": "\n\n".join(responses)})

@app.route("/get_logs", methods=["GET"])
def get_logs():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    logs_data = get_test_logs(page, per_page)
    return jsonify(logs_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
