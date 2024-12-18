import sys
import os
import time
import mailbox
import csv
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
                             QLabel, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import qdarkstyle
from concurrent.futures import ThreadPoolExecutor


class MboxToCsvThread(QThread):
    update_progress = pyqtSignal(int)
    completed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, mbox_file, csv_file):
        super().__init__()
        self.mbox_file = mbox_file
        self.csv_file = csv_file

    def process_message(self, message):
        """ Extracts the email fields and processes them into a row for CSV. """
        try:
            # Extract email fields
            date = message.get("date", "")
            sender = message.get("from", "")
            recipient = message.get("to", "")
            subject = message.get("subject", "")

            # Get the email body (handles plain text and HTML)
            if message.is_multipart():
                body = ""
                for part in message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(part.get_content_charset('utf-8'), errors='ignore')
                        break
            else:
                body = message.get_payload(decode=True).decode(message.get_content_charset('utf-8'), errors='ignore')

            return [date, sender, recipient, subject, body]
        except Exception as e:
            return None

    def run(self):
        try:
            # Check if the mbox file exists
            if not os.path.exists(self.mbox_file):
                self.error.emit(f"Error: mbox file '{self.mbox_file}' not found.")
                return

            self.update_progress.emit(0)
            start_time = time.time()

            # Open the mbox file
            mbox = mailbox.mbox(self.mbox_file)

            # Open the CSV file for writing
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Date", "From", "To", "Subject", "Body"])

                # Use ThreadPoolExecutor to process messages in parallel
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = []
                    total_messages = len(mbox)
                    for idx, message in enumerate(mbox):
                        future = executor.submit(self.process_message, message)
                        futures.append(future)

                        # Update progress every 100 messages
                        if (idx + 1) % 100 == 0:
                            self.update_progress.emit(int((idx + 1) / total_messages * 100))

                    # Write the results as they are processed
                    for future in futures:
                        result = future.result()
                        if result:
                            writer.writerow(result)

            self.completed.emit(f"Conversion completed in {time.time() - start_time:.2f} seconds. CSV file saved to '{self.csv_file}'.")

        except Exception as e:
            self.error.emit(f"Error: {e}")


class MboxToCsvGUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Mbox to CSV Converter")
        self.setGeometry(300, 100, 600, 450)

        self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

        # GUI Font Size
        font = QFont()
        font.setPointSize(12) 

        # Create the layout and widgets
        layout = QVBoxLayout()

        self.mbox_file_input = QLineEdit(self)
        self.mbox_file_input.setPlaceholderText("Select the Mbox File")
        self.mbox_file_input.setFont(font)  
        layout.addWidget(self.mbox_file_input)

        self.browse_button = QPushButton("Browse", self)
        self.browse_button.setFont(font)  
        self.browse_button.clicked.connect(self.browse_mbox_file)
        layout.addWidget(self.browse_button)

        self.csv_file_input = QLineEdit(self)
        self.csv_file_input.setPlaceholderText("Select the CSV Output File")
        self.csv_file_input.setFont(font)  
        layout.addWidget(self.csv_file_input)

        self.browse_button_csv = QPushButton("Browse", self)
        self.browse_button_csv.setFont(font)  
        self.browse_button_csv.clicked.connect(self.browse_csv_file)
        layout.addWidget(self.browse_button_csv)

        self.start_button = QPushButton("Start Conversion", self)
        self.start_button.setFont(font)  
        self.start_button.clicked.connect(self.start_conversion)
        layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFont(font)
        layout.addWidget(self.progress_bar)

        self.result_label = QLabel(self)
        self.result_label.setFont(font)  
        layout.addWidget(self.result_label)

        self.setLayout(layout)

        # Thread for the conversion process
        self.thread = None

    def browse_mbox_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Mbox File", "", "Mbox Files (*.mbox)")
        if file:
            self.mbox_file_input.setText(file)

    def browse_csv_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv)")
        if file:
            self.csv_file_input.setText(file)

    def start_conversion(self):
        mbox_file = self.mbox_file_input.text()
        csv_file = self.csv_file_input.text()

        if not mbox_file or not csv_file:
            QMessageBox.warning(self, "Input Error", "Please select both the Mbox file and the CSV output file.")
            return

        self.result_label.clear()
        self.progress_bar.setValue(0)

        self.thread = MboxToCsvThread(mbox_file, csv_file)
        self.thread.update_progress.connect(self.update_progress)
        self.thread.completed.connect(self.show_completed_message)
        self.thread.error.connect(self.show_error_message)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def show_completed_message(self, message):
        self.result_label.setText(message)

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)


def main():
    app = QApplication(sys.argv)
    window = MboxToCsvGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
