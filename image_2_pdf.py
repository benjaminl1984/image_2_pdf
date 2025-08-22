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
import xml.etree.ElementTree as ET


class SVGToPDFConverter(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, svg_files, output_path, images_per_page=9, page_size=A4, high_quality=True):
        super().__init__()
        self.svg_files = svg_files
        self.output_path = output_path
        self.images_per_page = images_per_page
        self.page_size = page_size
        self.high_quality = high_quality
        
    def run(self):
        try:
            self.convert_svgs_to_pdf()
            self.finished_signal.emit(True, "Konvertierung erfolgreich abgeschlossen!")
        except Exception as e:
            self.finished_signal.emit(False, f"Fehler bei der Konvertierung: {str(e)}")
    
    def convert_svgs_to_pdf(self):
        if not self.svg_files:
            raise ValueError("Keine SVG-Dateien ausgewählt")
        
        # PDF mit hoher Qualität erstellen
        if self.high_quality:
            # Hohe DPI für beste Qualität (300 DPI)
            c = canvas.Canvas(self.output_path, pagesize=self.page_size, pageCompression=1)
        else:
            c = canvas.Canvas(self.output_path, pagesize=self.page_size)
        
        page_width, page_height = self.page_size
        
        # Berechnung des verfügbaren Platzes (mit Rand)
        margin = 20
        available_width = page_width - 2 * margin
        available_height = page_height - 2 * margin
        
        # Grid-Dimensionen (3x3)
        cols = 3
        rows = 3
        cell_width = available_width / cols
        cell_height = available_height / rows
        
        total_files = len(self.svg_files)
        files_processed = 0
        
        for page_num in range(0, total_files, self.images_per_page):
            page_files = self.svg_files[page_num:page_num + self.images_per_page]
            
            self.status_updated.emit(f"Verarbeite Seite {page_num // self.images_per_page + 1}...")
            
            # Wenn nicht die erste Seite, neue Seite hinzufügen
            if page_num > 0:
                c.showPage()
            
            for i, svg_file in enumerate(page_files):
                row = i // cols
                col = i % cols
                
                # Position berechnen (von oben links)
                x = margin + col * cell_width
                y = page_height - margin - (row + 1) * cell_height
                
                try:
                    # SVG mit höchster Qualität laden
                    drawing = svg2rlg(svg_file)
                    
                    if drawing:
                        # Originale SVG-Dimensionen
                        svg_width = drawing.width
                        svg_height = drawing.height
                        
                        # Fallback falls width/height nicht definiert
                        if not svg_width or not svg_height:
                            svg_width = cell_width - 10
                            svg_height = cell_height - 10
                        
                        # Maximale Skalierung für beste Qualität
                        scale_x = (cell_width - 10) / svg_width  # 10px Padding
                        scale_y = (cell_height - 10) / svg_height
                        scale = min(scale_x, scale_y)
                        
                        # Für höchste Qualität: Vergrößerung falls möglich
                        if self.high_quality:
                            max_scale = min(2.0, scale)  # Maximal 2x Vergrößerung
                            scale = max(scale, max_scale)
                        
                        # Zentrierte Position in der Zelle
                        scaled_width = svg_width * scale
                        scaled_height = svg_height * scale
                        centered_x = x + (cell_width - scaled_width) / 2
                        centered_y = y + (cell_height - scaled_height) / 2
                        
                        # Qualitäts-Einstellungen für ReportLab
                        if self.high_quality:
                            # Anti-Aliasing aktivieren
                            c.setPageCompression(1)
                        
                        # SVG in PDF rendern mit optimaler Skalierung
                        drawing.scale(scale, scale)
                        renderPDF.draw(drawing, c, centered_x, centered_y)
                        
                        self.status_updated.emit(f"Verarbeitet: {os.path.basename(svg_file)} (Skalierung: {scale:.2f}x)")
                    
                except Exception as e:
                    self.status_updated.emit(f"Fehler bei {os.path.basename(svg_file)}: {str(e)}")
                    continue
                
                files_processed += 1
                progress = int((files_processed / total_files) * 100)
                self.progress_updated.emit(progress)
        
        c.save()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.svg_files = []
        self.output_folder = ""
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("SVG zu PDF Converter")
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Titel
        title = QLabel("SVG zu PDF Converter")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Dateien auswählen Bereich
        file_section = QWidget()
        file_layout = QVBoxLayout(file_section)
        
        file_label = QLabel("SVG-Dateien auswählen:")
        file_layout.addWidget(file_label)
        
        # Buttons für Dateiauswahl
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
        
        # Dateiliste
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(200)
        file_layout.addWidget(self.file_list)
        
        layout.addWidget(file_section)
        
        # Ausgabeordner Bereich
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
        
        # Einstellungen
        settings_section = QWidget()
        settings_layout = QVBoxLayout(settings_section)
        
        # Erste Zeile: Bilder pro Seite und Seitengröße
        settings_row1 = QHBoxLayout()
        settings_row1.addWidget(QLabel("Bilder pro Seite:"))
        self.images_per_page_spin = QSpinBox()
        self.images_per_page_spin.setMinimum(1)
        self.images_per_page_spin.setMaximum(12)
        self.images_per_page_spin.setValue(9)
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
        
        # Zweite Zeile: Qualitäts-Einstellungen
        settings_row2 = QHBoxLayout()
        self.high_quality_cb = QCheckBox("Höchste Qualität (300 DPI, Kompression)")
        self.high_quality_cb.setChecked(True)
        self.high_quality_cb.setToolTip("Aktiviert höchste PDF-Qualität mit verbesserter Auflösung")
        settings_row2.addWidget(self.high_quality_cb)
        settings_row2.addStretch()
        settings_layout.addLayout(settings_row2)
        
        layout.addWidget(settings_section)
        
        # Convert Button
        self.convert_btn = QPushButton("PDF erstellen")
        self.convert_btn.clicked.connect(self.convert_files)
        self.convert_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        layout.addWidget(self.convert_btn)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status/Log Bereich
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)
        
        # Status Label
        self.status_label = QLabel("Bereit")
        layout.addWidget(self.status_label)
    
    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ausgabeordner auswählen")
        if folder:
            self.output_folder = folder
            # Pfad kürzen falls zu lang
            display_path = folder
            if len(display_path) > 60:
                display_path = "..." + display_path[-57:]
            self.output_folder_label.setText(display_path)
            self.output_folder_label.setToolTip(folder)  # Vollständiger Pfad im Tooltip
            self.log_message(f"Ausgabeordner gesetzt: {folder}")
    
    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "SVG-Dateien auswählen", 
            "", 
            "SVG Files (*.svg);;All Files (*)"
        )
        if files:
            self.svg_files.extend(files)
            self.update_file_list()
            self.log_message(f"{len(files)} Dateien hinzugefügt")
    
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner mit SVG-Dateien auswählen")
        if folder:
            svg_files = list(Path(folder).glob("*.svg"))
            if svg_files:
                self.svg_files.extend([str(f) for f in svg_files])
                self.update_file_list()
                self.log_message(f"{len(svg_files)} SVG-Dateien aus Ordner hinzugefügt")
            else:
                QMessageBox.information(self, "Info", "Keine SVG-Dateien im ausgewählten Ordner gefunden")
    
    def clear_files(self):
        self.svg_files.clear()
        self.update_file_list()
        self.log_message("Dateiliste geleert")
    
    def update_file_list(self):
        self.file_list.clear()
        for file_path in self.svg_files:
            self.file_list.addItem(os.path.basename(file_path))
        
        # Duplikate entfernen
        self.svg_files = list(dict.fromkeys(self.svg_files))
    
    def convert_files(self):
        if not self.svg_files:
            QMessageBox.warning(self, "Warnung", "Keine SVG-Dateien ausgewählt!")
            return
        
        # Ausgabedatei bestimmen
        if self.output_folder:
            # Automatischen Dateinamen generieren
            output_file = os.path.join(self.output_folder, "converted_svgs.pdf")
            
            # Falls Datei bereits existiert, Nummer anhängen
            counter = 1
            base_name = "converted_svgs"
            while os.path.exists(output_file):
                output_file = os.path.join(self.output_folder, f"{base_name}_{counter:03d}.pdf")
                counter += 1
            
            self.log_message(f"Ausgabedatei: {os.path.basename(output_file)}")
        else:
            # Dialog für Dateispeicherung
            output_file, _ = QFileDialog.getSaveFileName(
                self, 
                "PDF-Datei speichern", 
                "converted_svgs.pdf", 
                "PDF Files (*.pdf);;All Files (*)"
            )
            
            if not output_file:
                return
        
        # Seitengröße bestimmen
        page_sizes = {
            0: A4, 1: A3, 2: A2, 3: A1, 4: A0, 5: letter, 6: legal
        }
        selected_page_size = page_sizes.get(self.page_size_combo.currentIndex(), A4)
        
        # UI für Konvertierung vorbereiten
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_text.clear()
        
        # Converter Thread starten
        self.converter = SVGToPDFConverter(
            self.svg_files, 
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
        # Automatisch nach unten scrollen
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def conversion_finished(self, success, message):
        self.convert_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            # Bei erfolgreichem Export - Option zum Ordner öffnen
            reply = QMessageBox.question(
                self, 
                "Erfolg", 
                f"{message}\n\nMöchten Sie den Ausgabeordner öffnen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes and self.output_folder:
                # Ordner im Dateimanger öffnen
                if sys.platform == "win32":
                    os.startfile(self.output_folder)
                elif sys.platform == "darwin":  # macOS
                    os.system(f"open '{self.output_folder}'")
                else:  # Linux
                    os.system(f"xdg-open '{self.output_folder}'")
            
            self.status_label.setText("Konvertierung abgeschlossen")
        else:
            QMessageBox.critical(self, "Fehler", message)
            self.status_label.setText("Konvertierung fehlgeschlagen")
        
        self.log_message(message)


def main():
    app = QApplication(sys.argv)
    
    # Anwendungs-Style setzen
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()