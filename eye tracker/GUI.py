import sys
import socket
import pynput
from PyQt5.QtCore import Qt, QRect, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QComboBox, QFileDialog
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QBrush

class ControlDashboard(QWidget):
    def __init__(self, overlay_app=None):
        super().__init__()
        self.overlay = overlay_app # reference main cursor application
        self.init_ui()
        
        # Start a fast UI timer to keep the Game/Desktop mode labels in sync 
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_mode_display)
        self.status_timer.start(200)

    def init_ui(self):
        # window
        self.setWindowTitle("cursor system controller")
        self.resize(380, 560)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff; font-family: Arial; font-size: 14px;")

        # main layout
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # title label
        title = QLabel("Accessibility Control Panel")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00ffcc; margin-bottom: 10px;")
        layout.addWidget(title)

        # eye profile selection
        layout.addWidget(QLabel("<b> EYE TRACKING PROFILE </b>"))
        self.profile_dropdown = QComboBox()
        self.profile_dropdown.addItems(["Dual Eye Tracking", "Left Eye Only", "Right Eye Only"])
        self.profile_dropdown.setStyleSheet("background-color: #333333; color: white; padding: 5px; font-weight: bold;")
        
        # Default choice: 1 sets it to 'Left Eye Only' for yourself
        self.profile_dropdown.setCurrentIndex(1)
        self.profile_dropdown.currentIndexChanged.connect(self.change_eye_profile)
        layout.addWidget(self.profile_dropdown)

        # desktop vs game mode toggle
        self.lbl_game_status = QLabel("Current Mode: <b>Desktop Mode</b>")
        self.lbl_game_status.setStyleSheet("font-size: 14px; color: #aaaaaa; padding: 8px; border-radius: 5px; background-color: #2c2c2c; text-align: center;")
        layout.addWidget(self.lbl_game_status)

        # SYSTEM MAPPING MODES
        layout.addWidget(QLabel("<b> TRACKING MODE OPTION </b>"))
        mode_layout = QHBoxLayout()
        self.btn_ai = QPushButton("Automated AI Tracking")
        self.btn_ai.setStyleSheet("background-color: #007acc; padding: 10px; font-weight: bold; border-radius: 5px;")
        self.btn_ai.clicked.connect(self.set_ai_mode)
        
        self.btn_manual = QPushButton("Manual Controls")
        self.btn_manual.setStyleSheet("background-color: #444444; padding: 10px; font-weight: bold; border-radius: 5px;")
        self.btn_manual.clicked.connect(self.set_manual_mode)
        
        mode_layout.addWidget(self.btn_ai)
        mode_layout.addWidget(self.btn_manual)
        layout.addLayout(mode_layout)

        # speed / smoothing sliders
        layout.addWidget(QLabel("<b> SPEED & SMOOTHING ADJUSTMENT </b>"))
        
        # jitter filter alpha slider
        layout.addWidget(QLabel("Filter Responsiveness (Lower = Smoother)"))
        self.slider_alpha = QSlider(Qt.Horizontal)
        self.slider_alpha.setMinimum(5) # 0.05
        self.slider_alpha.setMaximum(50) # 0.50
        
        # Safe default value setup if overlay app isn't active yet
        initial_alpha = int(self.overlay.filter_alpha * 100) if self.overlay else 20
        self.slider_alpha.setValue(initial_alpha)
        self.slider_alpha.valueChanged.connect(self.adjust_smoothing)
        layout.addWidget(self.slider_alpha)

        # Accessibility custom cursor shapes
        layout.addWidget(QLabel("<b> CURSOR SHAPE SELECTION </b>"))
        shape_layout = QHBoxLayout()
        btn_circle = QPushButton("Fallback Circle")
        btn_circle.setStyleSheet("background-color: #333333; padding: 8px; border: 1px solid #555;")
        btn_circle.clicked.connect(lambda: self.change_shape(True))
        
        btn_asset = QPushButton("Custom Asset Image")
        btn_asset.setStyleSheet("background-color: #333333; padding: 8px; border: 1px solid #555;")
        btn_asset.clicked.connect(lambda: self.change_shape(False))
        
        shape_layout.addWidget(btn_circle)
        shape_layout.addWidget(btn_asset)
        layout.addLayout(shape_layout)

        # dynamic asset file chooser button
        self.btn_browse_asset = QPushButton("Browse for Custom Cursor Asset")
        self.btn_browse_asset.setStyleSheet("background-color: #27ae60; padding: 10px; font-weight: bold; border-radius: 5px; color: white;")
        self.btn_browse_asset.clicked.connect(self.browse_custom_asset)
        layout.addWidget(self.btn_browse_asset)

        # actions
        layout.addStretch()
        self.btn_calib = QPushButton("Launch Manual Grid Calibration [C]")
        self.btn_calib.setStyleSheet("background-color: #e67e22; padding: 12px; font-weight: bold; border-radius: 5px; color: black;")
        if self.overlay:
            self.btn_calib.clicked.connect(self.overlay.start_manual_calibration)
        layout.addWidget(self.btn_calib)
        self.setLayout(layout)

    def update_mode_display(self):
        """Refreshes the UI text box when the user hits Numpad 5 on their keyboard."""
        if self.overlay:
            if self.overlay.game_mode:
                self.lbl_game_status.setText("Current Mode: <b>Game Mode</b>")
                self.lbl_game_status.setStyleSheet("font-weight: bold; color: #00ffcc; background-color: #113333; padding: 8px; border-radius: 5px;")
            else:
                self.lbl_game_status.setText("Current Mode: <b>Desktop Mode</b>")
                self.lbl_game_status.setStyleSheet("font-weight: bold; color: #aaaaaa; background-color: #2a2a2a; padding: 8px; border-radius: 5px;")

    def change_eye_profile(self, index):
        """Passes the selected tracking type down to the core camera processing loops."""
        profile_map = {0: "both", 1: "left", 2: "right"}
        chosen_profile = profile_map.get(index, "both")
        if self.overlay and hasattr(self.overlay, 'camera_worker'):
            self.overlay.camera_worker.eye_profile = chosen_profile
            print(f"UI Action: Eye profile successfully switched to: {chosen_profile}")
        else:
            print("UI Action Warning: Main overlay app or tracking thread link not found.")

    def set_ai_mode(self):
        if self.overlay:
            self.overlay.is_auto_calibrating = True
            self.btn_ai.setStyleSheet("background-color: #007acc; padding: 10px; font-weight: bold; border-radius: 5px;")
            self.btn_manual.setStyleSheet("background-color: #444444; padding: 10px; font-weight: bold; border-radius: 5px;")
            print("UI Action: Enabled Background AI Auto-Calibration Mode.")

    def set_manual_mode(self):
        if self.overlay:
            self.overlay.is_auto_calibrating = False
            self.btn_manual.setStyleSheet("background-color: #007acc; padding: 10px; font-weight: bold; border-radius: 5px;")
            self.btn_ai.setStyleSheet("background-color: #444444; padding: 10px; font-weight: bold; border-radius: 5px;")
            print("UI Action: Enabled Manual Target Adjustment Mode.")

    def start_manual_calibration(self):
        """Triggers the background camera thread to snap a new resting center profile."""
        if self.overlay and hasattr(self.overlay, 'camera_worker'):
            self.overlay.camera_worker.is_calibrating_center = True
            print("UI Action: Recalibrating resting center point... Look at the middle of your screen!")

    def adjust_smoothing(self, value):
        if self.overlay:
            self.overlay.filter_alpha = value / 100.0

    def change_shape(self, use_circle_flag):
        if self.overlay:
            self.overlay.use_fallback_circle = use_circle_flag
            self.overlay.update()
            print(f"UI Action: Changed cursor shape status to use_fallback_circle={use_circle_flag}")

    # FIX: Added the missing image browse selector utility
    def browse_custom_asset(self):
        """Opens a file selector dialog box to smoothly change custom overlay targets."""
        file_filter = "Images (*.png *.jpg *.jpeg *.bmp)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Cursor Custom Image Asset", "", file_filter)
        if file_path:
            if self.overlay:
                self.overlay.image_path = file_path
                self.overlay.load_image_asset()
                print(f"UI Action: Successfully updated asset tracker image path to: {file_path}")
            else:
                print(f"Selected file path asset target: {file_path} (No active overlay tracking instance link)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ControlDashboard()
    window.show()
    sys.exit(app.exec_())
