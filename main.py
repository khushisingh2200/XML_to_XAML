import os
import time
import logging
import configparser
from logging.handlers import RotatingFileHandler
import utilities
import subprocess
import sys
import socket
import threading

# Load config
config = configparser.ConfigParser()
config.read('config.ini')


def setup_logging():
    log_file = config.get('LOGGING', 'filename', fallback='xml.log')
    log_format = config.get('LOGGING', 'format', raw=True,
                            fallback='%(asctime)s - %(levelname)s - %(message)s')

    handler = RotatingFileHandler(log_file, maxBytes=1 * 1024 * 1024, backupCount=0)
    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
        format=log_format
    )
    logging.info("Logging initialized")
    return log_file


def udp_listener():
    udp_ip = config.get('UDP', 'host', fallback='127.0.0.1')
    udp_port = config.getint('UDP', 'port', fallback=5005)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((udp_ip, udp_port))

    logging.info("Listening for UDP events on {}:{}...".format(udp_ip, udp_port))

    while True:
        data, addr = sock.recvfrom(1024)
        message = data.decode('utf-8')
        logging.info("Received event: {}".format(message))

        if "CMD_EXEC_OK" in message:
            logging.info(" Success event detected.")
        elif "CMD_EXEC_FAIL" in message:
            logging.warning(" Failure event detected.")
        else:
            logging.debug("Unrecognized event format.")


def udp_sender():
    udp_ip = config.get('UDP', 'host', fallback='127.0.0.1')
    udp_port = config.getint('UDP', 'port', fallback=5005)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    events = [
        "CMD_EXEC_OK: Command A executed successfully",
        "CMD_EXEC_FAIL: Command B failed due to timeout",
        "CMD_EXEC_OK: Command C executed successfully"
    ]
    while True:
        for event in events:
            sock.sendto(event.encode('utf-8'), (udp_ip, udp_port))
            logging.info("Sent event: {}".format(event))

            time.sleep(2)


def main_program(log_file):
    start_time = time.time()

    input_folder = os.path.abspath(os.path.normpath(config.get('SETTINGS', 'input_folder', fallback='.')))
    output_folder = os.path.abspath(os.path.normpath(config.get('SETTINGS', 'output_folder', fallback='output')))
    file_format = config.get('SETTINGS', 'file_format', fallback='*.xml')

    logging.info('Configuration loaded. Input folder: %s, Output folder: %s, File format: %s',
                 input_folder, output_folder, file_format)

    files = utilities.get_files(input_folder, file_format)

    if not files:
        logging.warning('No files to process in %s', input_folder)
        print("No files to process.")
        return

    print("\nFiles found:")
    for file in files:
        print(file)

    print("\nOutput Files:")
    for file in files:
        logging.info('Processing file: %s', file)
        canvas_elements = utilities.parse_xml(file)

        if canvas_elements:
            output_file = os.path.join(output_folder, os.path.basename(file).replace(".xml", ".xaml"))
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            with open(output_file, "w") as f:
                f.write("\n".join(canvas_elements))

            logging.info('File saved to %s', output_file)
            print("Saved to {}".format(output_file))

        else:
            logging.warning('No shapes found in %s', file)
            print("No shapes found in {}".format(file))

    print("\nValidating generated files...")
    utilities.validate_conversion_all(input_folder, output_folder, file_format)

    end_time = time.time()
    print("\nExecution Time: {:.2f} seconds".format(end_time - start_time))


def launch_comparison_script():
    script_path = os.path.abspath("shape_runner.py")
    subprocess.Popen([sys.executable, script_path])


if __name__ == "__main__":
    log_file = setup_logging()

    # Start UDP listener in background thread
    listener_thread = threading.Thread(target=udp_listener, daemon=True)
    listener_thread.start()

    # Start UDP sender in background thread
    sender_thread = threading.Thread(target=udp_sender, daemon=True)
    sender_thread.start()

    main_program(log_file)
