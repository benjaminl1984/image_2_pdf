import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QFileDialog, QProgressBar, QMessageBox, QTextEdit,
                             QSpinBox, QCheckBox, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, A2, A1, A0, letter, legal
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from reportlab.lib.utils import ImageReader
import xml.etree.ElementTree as ET


class ImageToPDFConverter(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, image_files, output_path, images_per_page=9, page_size=A4, high_quality=True):
        super().__init__()
        self.image_files = image_files
        self.output_path = output_path
        self.images_per_page = images_per_page
        self.page_size = page_size
        self.high_quality = high_quality

    def run(self):
        try:
            self.convert_images_to_pdf()
            self.finished_signal.emit(True, "Konvertierung erfolgreich abgeschlossen!")
        except Exception as e:
            self.finished_signal.emit(False, f"Fehler bei der Konvertierung: {str(e)}")

    def convert_images_to_pdf(self):
        if not self.image_files:
            raise ValueError("Keine Bilddateien ausgewählt")

        if self.high_quality:
            c = canvas.Canvas(self.output_path, pagesize=self.page_size, pageCompression=1)
        else:
            c = canvas.Canvas(self.output_path, pagesize=self.page_size)

        page_width, page_height = self.page_size

        # KEIN RAND MEHR: Verfügbarer Platz ist die gesamte Seite
        available_width = page_width
        available_height = page_height

        # Grid-Dimensionen (fest 3x3 für 9 Bilder pro Seite)
        # Wenn images_per_page geändert wird, muss diese Logik angepasst werden.
        # Für 9 Bilder pro Seite ist 3x3 das Standardraster.
        cols = 3
        rows = 3

        # Zellengröße ohne Abstände berechnen
        cell_width = available_width / cols
        cell_height = available_height / rows

        total_files = len(self.image_files)
        files_processed = 0

        # Sicherstellen, dass images_per_page ein Vielfaches von cols*rows ist,
        # oder zumindest die Logik für unvollständige Reihen/Spalten berücksichtigt.
        # Hier gehen wir davon aus, dass images_per_page = 9 ist, was 3x3 entspricht.
        # Wenn images_per_page variieren kann, müsste cols/rows dynamisch berechnet werden.
        # Für diese Anforderung bleiben wir bei 3x3, da "kein Abstand" dies impliziert.
        if self.images_per_page != (cols * rows):
             self.status_updated.emit(f"Warnung: 'Bilder pro Seite' ist nicht {cols*rows}. Layout könnte unerwartet sein.")


        for page_num in range(0, total_files, self.images_per_page):
            page_files = self.image_files[page_num:page_num + self.images_per_page]

            self.status_updated.emit(f"Verarbeite Seite {page_num // self.images_per_page + 1}...")

            if page_num > 0:
                c.showPage()

            for i, image_file in enumerate(page_files):
                row = i // cols
                col = i % cols

                # Position berechnen (von unten links, ReportLab Standard)
                # Da wir von oben links denken, müssen wir y umkehren.
                # Die Zelle beginnt bei (col * cell_width, row * cell_height)
                # und geht bis ((col+1) * cell_width, (row+1) * cell_height)
                # ReportLab's Ursprung ist unten links.
                # x_cell_start = col * cell_width
                # y_cell_start = page_height - (row + 1) * cell_height # Oberer Rand der Zelle

                try:
                    file_extension = Path(image_file).suffix.lower()
                    img_width, img_height = 0, 0 # Initialisierung

                    if file_extension == ".svg":
                        drawing = svg2rlg(image_file)
                        if drawing:
                            img_width = drawing.width
                            img_height = drawing.height
                            if not img_width or not img_height: # Fallback
                                img_width = cell_width
                                img_height = cell_height
                    elif file_extension in [".png", ".jpg", ".jpeg", ".webp"]:
                        img = ImageReader(image_file)
                        img_width, img_height = img.getSize()
                    else:
                        self.status_updated.emit(f"Übersprungen: {os.path.basename(image_file)} (Nicht unterstütztes Format)")
                        continue

                    # Skalierung berechnen, um die Zelle maximal auszufüllen, ohne das Seitenverhältnis zu verzerren
                    # Wir wollen, dass das Bild entweder die Breite oder die Höhe der Zelle ausfüllt.
                    scale_x = cell_width / img_width
                    scale_y = cell_height / img_height
                    scale = min(scale_x, scale_y) # 'min' um sicherzustellen, dass das Bild in die Zelle passt

                    # Für höchste Qualität: Vergrößerung falls möglich (optional, kann zu Pixelierung führen bei Rasterbildern)
                    # Wenn das Ziel ist, die Zelle komplett auszufüllen, ist diese Logik nicht mehr primär.
                    # Die 'min' Skalierung stellt sicher, dass das Bild vollständig sichtbar ist.
                    # Wenn das Bild die Zelle ausfüllen soll (cropping), wäre es 'max'.
                    # Da die Anforderung "so groß wie möglich" und "kein Rand" ist,
                    # aber auch "Seitenverhältnis beibehalten", ist 'min' die richtige Wahl.
                    # Wenn das Bild die Zelle komplett ausfüllen soll (und dabei beschnitten werden darf),
                    # müsste man 'max' nehmen und dann den Überschuss abschneiden.
                    # Für "so groß wie möglich" ohne Beschneidung ist 'min' korrekt.

                    scaled_width = img_width * scale
                    scaled_height = img_height * scale

                    # Zentrierte Position innerhalb der Zelle
                    # x_start der Zelle: col * cell_width
                    # y_start der Zelle (unten links): page_height - (row + 1) * cell_height
                    centered_x = (col * cell_width) + (cell_width - scaled_width) / 2
                    centered_y = (page_height - (row + 1) * cell_height) + (cell_height - scaled_height) / 2


                    if self.high_quality:
                        c.setPageCompression(1) # Hohe Kompression für kleinere Dateigröße

                    if file_extension == ".svg":
                        drawing.scale(scale, scale)
                        renderPDF.draw(drawing, c, centered_x, centered_y)
                        self.status_updated.emit(f"Verarbeitet: {os.path.basename(image_file)} (SVG Skalierung: {scale:.2f}x)")
                    elif file_extension in [".png", ".jpg", ".jpeg", ".webp"]:
                        c.drawImage(img, centered_x, centered_y, width=scaled_width, height=scaled_height)
                        self.status_updated.emit(f"Verarbeitet: {os.path.basename(image_file)} (Rasterbild Skalierung: {scale:.2f}x)")

                except Exception as e:
                    self.status_updated.emit(f"Fehler bei {os.path.basename(image_file)}: {str(e)}")
                    continue

                files_processed += 1
                progress = int((files_processed / total_files) * 100)
                self.progress_updated.emit(progress)

        c.save()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files = []
        self.output_folder = ""
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Bild zu PDF Converter")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        title = QLabel("Bild zu PDF Converter")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        file_section = QWidget()
        file_layout = QVBoxLayout(file_section)

        file_label = QLabel("Bilddateien auswählen:")
        file_layout.addWidget(file_label)

        button_layout = QHBoxLayout()

        self.select_files_btn = QPushButton("Einzelne Dateien auswählen")
        self.select_files_btn.clicked.connect(self.select_files)
        button_layout.addWidget(self.select_files_btn)

        self.select_folder_btn = QPushButton("Ordner auswählen")
        self.select_folder_btn.clicked.connect(self.select_folder)
        button_layout.addWidget(self.select_folder_btn)

        self.clear_btn = QPushButton("Liste leeren")
        self.clear_btn.clicked.connect(self.clear_files)
        button_layout.addWidget(self.clear_btn)

        file_layout.addLayout(button_layout)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(200)
        file_layout.addWidget(self.file_list)

        layout.addWidget(file_section)

        output_section = QWidget()
        output_layout = QVBoxLayout(output_section)

        output_label = QLabel("Ausgabeordner:")
        output_layout.addWidget(output_label)

        output_row = QHBoxLayout()
        self.output_folder_label = QLabel("Nicht ausgewählt")
        self.output_folder_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; border: 1px solid #ccc; border-radius: 3px; }")
        output_row.addWidget(self.output_folder_label)

        self.select_output_btn = QPushButton("Ordner auswählen")
        self.select_output_btn.clicked.connect(self.select_output_folder)
        output_row.addWidget(self.select_output_btn)

        output_layout.addLayout(output_row)
        layout.addWidget(output_section)

        settings_section = QWidget()
        settings_layout = QVBoxLayout(settings_section)

        settings_row1 = QHBoxLayout()
        settings_row1.addWidget(QLabel("Bilder pro Seite:"))
        self.images_per_page_spin = QSpinBox()
        self.images_per_page_spin.setMinimum(1)
        self.images_per_page_spin.setMaximum(12)
        self.images_per_page_spin.setValue(9) # Standardwert 9 beibehalten für 3x3
        settings_row1.addWidget(self.images_per_page_spin)

        settings_row1.addWidget(QLabel("Seitengröße:"))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems([
            "A4 (210×297mm)",
            "A3 (297×420mm)",
            "A2 (420×594mm)",
            "A1 (594×841mm)",
            "A0 (841×1189mm)",
            "Letter (216×279mm)",
            "Legal (216×356mm)"
        ])
        settings_row1.addWidget(self.page_size_combo)
        settings_row1.addStretch()
        settings_layout.addLayout(settings_row1)

        settings_row2 = QHBoxLayout()
        self.high_quality_cb = QCheckBox("Höchste Qualität (300 DPI, Kompression)")
        self.high_quality_cb.setChecked(True)
        self.high_quality_cb.setToolTip("Aktiviert höchste PDF-Qualität mit verbesserter Auflösung")
        settings_row2.addWidget(self.high_quality_cb)
        settings_row2.addStretch()
        settings_layout.addLayout(settings_row2)

        layout.addWidget(settings_section)

        self.convert_btn = QPushButton("PDF erstellen")
        self.convert_btn.clicked.connect(self.convert_files)
        self.convert_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        layout.addWidget(self.convert_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        self.status_label = QLabel("Bereit")
        layout.addWidget(self.status_label)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ausgabeordner auswählen")
        if folder:
            self.output_folder = folder
            display_path = folder
            if len(display_path) > 60:
                display_path = "..." + display_path[-57:]
            self.output_folder_label.setText(display_path)
            self.output_folder_label.setToolTip(folder)
            self.log_message(f"Ausgabeordner gesetzt: {folder}")

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Bilddateien auswählen",
            "",
            "Bilddateien (*.svg *.png *.jpg *.jpeg *.webp);;SVG Files (*.svg);;PNG Files (*.png);;JPG Files (*.jpg *.jpeg);;WebP Files (*.webp);;All Files (*)"
        )
        if files:
            self.image_files.extend(files)
            self.update_file_list()
            self.log_message(f"{len(files)} Dateien hinzugefügt")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner mit Bilddateien auswählen")
        if folder:
            image_files_in_folder = []
            for ext in ["*.svg", "*.png", "*.jpg", "*.jpeg", "*.webp"]:
                image_files_in_folder.extend(list(Path(folder).glob(ext)))

            if image_files_in_folder:
                self.image_files.extend([str(f) for f in image_files_in_folder])
                self.update_file_list()
                self.log_message(f"{len(image_files_in_folder)} Bilddateien aus Ordner hinzugefügt")
            else:
                QMessageBox.information(self, "Info", "Keine unterstützten Bilddateien im ausgewählten Ordner gefunden")

    def clear_files(self):
        self.image_files.clear()
        self.update_file_list()
        self.log_message("Dateiliste geleert")

    def update_file_list(self):
        self.file_list.clear()
        for file_path in self.image_files:
            self.file_list.addItem(os.path.basename(file_path))

        self.image_files = list(dict.fromkeys(self.image_files))

    def convert_files(self):
        if not self.image_files:
            QMessageBox.warning(self, "Warnung", "Keine Bilddateien ausgewählt!")
            return

        if self.output_folder:
            output_file = os.path.join(self.output_folder, "converted_images.pdf")
            counter = 1
            base_name = "converted_images"
            while os.path.exists(output_file):
                output_file = os.path.join(self.output_folder, f"{base_name}_{counter:03d}.pdf")
                counter += 1
            self.log_message(f"Ausgabedatei: {os.path.basename(output_file)}")
        else:
            output_file, _ = QFileDialog.getSaveFileName(
                self,
                "PDF-Datei speichern",
                "converted_images.pdf",
                "PDF Files (*.pdf);;All Files (*)"
            )
            if not output_file:
                return

        page_sizes = {
            0: A4, 1: A3, 2: A2, 3: A1, 4: A0, 5: letter, 6: legal
        }
        selected_page_size = page_sizes.get(self.page_size_combo.currentIndex(), A4)

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_text.clear()

        self.converter = ImageToPDFConverter(
            self.image_files,
            output_file,
            self.images_per_page_spin.value(),
            selected_page_size,
            self.high_quality_cb.isChecked()
        )
        self.converter.progress_updated.connect(self.update_progress)
        self.converter.status_updated.connect(self.update_status)
        self.converter.finished_signal.connect(self.conversion_finished)
        self.converter.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, message):
        self.status_label.setText(message)
        self.log_message(message)

    def log_message(self, message):
        self.status_text.append(message)
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def conversion_finished(self, success, message):
        self.convert_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            reply = QMessageBox.question(
                self,
                "Erfolg",
                f"{message}\n\nMöchten Sie den Ausgabeordner öffnen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.Yes and self.output_folder:
                if sys.platform == "win32":
                    os.startfile(self.output_folder)
                elif sys.platform == "darwin":
                    os.system(f"open '{self.output_folder}'")
                else:
                    os.system(f"xdg-open '{self.output_folder}'")

            self.status_label.setText("Konvertierung abgeschlossen")
        else:
            QMessageBox.critical(self, "Fehler", message)
            self.status_label.setText("Konvertierung fehlgeschlagen")

        self.log_message(message)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
