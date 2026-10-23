import sys
import socket
import pynput
import cv2
import mediapipe as mp
import math
import platform
from PyQt5.QtCore import Qt, QRect, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QBrush

class CommandListener(QThread):
    command_received = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('localhost', 5005))
        server.listen(1)
        while True:
            try:
                conn, addr = server.accept()
                data = conn.recv(1024).decode('utf-8').strip().lower()
                if data:
                    self.command_received.emit(data)
                conn.close()
            except Exception as e:
                print(f"Socket error: {e}")
                break

class CameraWorker(QThread):
    frame_ready = pyqtSignal(QPixmap)
    coordinates_ready = pyqtSignal(float, float) 

    def __init__(self):
        super().__init__()
        self.ml_features_x = []
        self.ml_features_y = []
        self.ml_targets_x = []
        self.ml_targets_y = []

        self.ml_slope_x = 1.0
        self.ml_intercept_x = 0.0
        self.ml_slope_y = 1.0
        self.ml_intercept_y = 0.0
        self.sensitivity_multiplier = 14.0
        self.eye_profile = "left" 
        
        self.calibrated_center_x = 0.5  
        self.calibrated_center_y = 0.5
        self.is_calibrating_center = False

    def trigger_calibration(self):
        self.is_calibrating_center = True

    def run(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(1)

        mp_face_mesh = mp.solutions.face_mesh
        mp_drawing = mp.solutions.drawing_utils

        # Fetch screen size safely in the main thread space or pass it down
        screen = QApplication.primaryScreen().size()
        screen_width = screen.width()
        screen_height = screen.height()

        with mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            while self.cap.isOpened() and not self.isInterruptionRequested():
                ret, frame = self.cap.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb_frame)
                h, w, ch = rgb_frame.shape

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        landmarks = face_landmarks.landmark

                        le = landmarks[33]
                        re = landmarks[263]
                        nose_tip = landmarks[1] 

                        left_eye_center = landmarks[159]
                        right_eye_center = landmarks[386]

                        VISIBILTY_THRESHOLD = 0.5

                        eye_span_dx = re.x - le.x
                        eye_span_dy = re.y - le.y
                        current_face_scale = math.sqrt(eye_span_dx ** 2 + eye_span_dy ** 2)

                        if current_face_scale < 0.01: 
                            current_face_scale = 0.01

                        if self.eye_profile == "left":
                            raw_offset_x = (left_eye_center.x - le.x) / current_face_scale
                            raw_offset_y = (left_eye_center.y - nose_tip.y) / current_face_scale
                        else: 
                            raw_offset_x = (right_eye_center.x - re.x) / current_face_scale
                            raw_offset_y = (right_eye_center.y - nose_tip.y) / current_face_scale   

                        target_eye_x = raw_offset_x * w
                        target_eye_y = raw_offset_y * h

                        if left_eye_center.visibility >= VISIBILTY_THRESHOLD and right_eye_center.visibility >= VISIBILTY_THRESHOLD:
                            target_eye_x = ((left_eye_center.x + right_eye_center.x) / 2) * w
                            target_eye_y = ((left_eye_center.y + right_eye_center.y) / 2) * h
                        elif left_eye_center.visibility >= VISIBILTY_THRESHOLD:
                            target_eye_x = left_eye_center.x * w
                            target_eye_y = left_eye_center.y * h
                        else:
                            target_eye_x = landmarks[1].x * w
                            target_eye_y = landmarks[1].y * h

                        if len(self.ml_features_x) >= 30:
                            mean_fx = sum(self.ml_features_x) / len(self.ml_features_x)
                            mean_fy = sum(self.ml_features_y) / len(self.ml_features_y)
                            mean_tx = sum(self.ml_targets_x) / len(self.ml_targets_x)
                            mean_ty = sum(self.ml_targets_y) / len(self.ml_targets_y)

                            num_x, den_x = 0, 0
                            num_y, den_y = 0, 0

                            for fx, fy, tx, ty in zip(self.ml_features_x, self.ml_features_y, self.ml_targets_x, self.ml_targets_y):
                                num_x += (fx - mean_fx) * (tx - mean_tx)
                                den_x += (fx - mean_fx) ** 2
                                num_y += (fy - mean_fy) * (ty - mean_ty)
                                den_y += (fy - mean_fy) ** 2

                            if den_x != 0:
                                self.ml_slope_x = num_x / den_x
                                self.ml_intercept_x = mean_tx - (self.ml_slope_x * mean_fx)
                            if den_y != 0:
                                self.ml_slope_y = num_y / den_y
                                self.ml_intercept_y = mean_ty - (self.ml_slope_y * mean_fy)

                            target_eye_x = (target_eye_x * self.ml_slope_x) + self.ml_intercept_x
                            target_eye_y = (target_eye_y * self.ml_slope_y) + self.ml_intercept_y

                        GAIN_X = self.sensitivity_multiplier
                        GAIN_Y = self.sensitivity_multiplier
                        raw_norm_x = target_eye_x / w
                        raw_norm_y = target_eye_y / h

                        if self.is_calibrating_center:
                            self.calibrated_center_x = raw_norm_x
                            self.calibrated_center_y = raw_norm_y
                            self.is_calibrating_center = False
                            print(f"System: Calibrated resting center to: ({raw_norm_x:.3f}, {raw_norm_y:.3f})")

                        diff_x = raw_norm_x - self.calibrated_center_x
                        diff_y = raw_norm_y - self.calibrated_center_y

                        percent_x = 0.5 + (diff_x * GAIN_X)
                        percent_y = 0.5 + (diff_y * GAIN_Y)

                        final_screen_x = percent_x * screen_width
                        final_screen_y = percent_y * screen_height

                        # Safe Data Hand-off: Send coordinates to the GUI overlay thread
                        self.coordinates_ready.emit(final_screen_x, final_screen_y)

                        # Draw landmarks safely
                        mp_drawing.draw_landmarks(
                            image=rgb_frame,
                            landmark_list=face_landmarks,
                            connections=mp_face_mesh.FACEMESH_TESSELATION,
                            landmark_drawing_spec=None,
                            connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=1)
                        )

                # Render frame outputs to GUI safely
                bytes_per_line = ch * w
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                self.frame_ready.emit(pixmap)

        self.cap.release()

    def stop(self):
        self.requestInterruption()
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

class FullScreenOverlay(QWidget):
    command_received_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.screen_width = QApplication.primaryScreen().size().width()
        self.screen_height = QApplication.primaryScreen().size().height()
        
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        if platform.system() == "Windows":
            self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput)
        else:
            self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.X11BypassWindowManagerHint)

        self.camera_worker = CameraWorker()
        self.camera_worker.frame_ready.connect(self.update_video_display)
        self.camera_worker.coordinates_ready.connect(self.apply_jitter)
        self.camera_worker.start()

        self.image_path = r"C:\Users\darks\OneDrive\Desktop\Wolf Adopt-20260810T172531Z-1-001\Wolf Adopt\Twitch Emotes\File 5 Static Emotes Mist\File 5 Static Emotes Mist lagi\28\1.png"
        self.scale_factor = 1.0
        self.load_image_asset()
        self.initUI()
        
        self.move_speed = 10
        self.mouse_x = self.rect().center().x()
        self.mouse_y = self.rect().center().y()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.track_mouse)
        self.timer.start(16)

        self.listener = CommandListener(self)
        self.listener.command_received.connect(self.handle_external_command)
        self.listener.start()

        self.mouse_controller = pynput.mouse.Controller()
        self.latest_frame = None
        self.latest_video_frame = None
        
        self.is_calibrating = False
        self.calibration_index = 0
        self.calibration_points = []
        self.calibration_data = {}

        self.smoothed_mouse_x = None
        self.smoothed_mouse_y = None
        
        self.game_mode = False
        self.game_sensitivity = 15.0
        self.game_center_x = 0.5
        self.game_center_y = 0.5
        self.filter_alpha = 0.2  

        self.ml_features_x = []
        self.ml_features_y = []
        self.ml_targets_x = []
        self.ml_targets_y = []
        
        self.ml_slope_x, self.ml_intercept_x = -3.0, self.screen_width // 2
        self.ml_slope_y, self.ml_intercept_y = 3.0, self.screen_height // 2
        self.is_auto_calibrating = True

    def update_auto_calibration_model(self, raw_face_x, raw_face_y, true_screen_x, true_screen_y, face_scale):
        if face_scale <= 0:
            face_scale = 1.0
        norm_face_x = raw_face_x / face_scale
        norm_face_y = raw_face_y / face_scale

        self.ml_features_x.append(norm_face_x)
        self.ml_features_y.append(norm_face_y)
        self.ml_targets_x.append(true_screen_x)
        self.ml_targets_y.append(true_screen_y)

        if len(self.ml_features_x) > 300:
            self.ml_features_x.pop(0)
            self.ml_features_y.pop(0)
            self.ml_targets_x.pop(0)
            self.ml_targets_y.pop(0)

    def update_video_display(self, processed_pixmap):
        self.latest_video_frame = processed_pixmap
        self.update()

    def apply_jitter(self, target_x, target_y):
        if self.smoothed_mouse_x is None or self.smoothed_mouse_y is None:
            self.smoothed_mouse_x = target_x
            self.smoothed_mouse_y = target_y
        else:
            self.smoothed_mouse_x = (self.filter_alpha * target_x) + ((1 - self.filter_alpha) * self.smoothed_mouse_x)
            self.smoothed_mouse_y = (self.filter_alpha * target_y) + ((1 - self.filter_alpha) * self.smoothed_mouse_y)

        self.mouse_x = int(self.smoothed_mouse_x)
        self.mouse_y = int(self.smoothed_mouse_y)

        if not self.game_mode:
            self.mouse_controller.position = (self.mouse_x, self.mouse_y)
        else:
            current_raw_x = target_x / self.screen_width if self.screen_width else 0.5
            current_raw_y = target_y / self.screen_height if self.screen_height else 0.5
            delta_x = (current_raw_x - self.game_center_x) * self.game_sensitivity
            delta_y = (current_raw_y - self.game_center_y) * self.game_sensitivity

            if abs(delta_x) > 1.0 or abs(delta_y) > 1.0:
                self.mouse_controller.move(int(delta_x), int(delta_y))

        self.update()

    def handle_external_command(self, command):
        if "left" in command or "click" in command:
            self.mouse_controller.click(pynput.mouse.Button.left, 1)
            print("External Trigger: Left Click")
        elif "right" in command:
            self.mouse_controller.click(pynput.mouse.Button.right, 1)
            print("External Trigger: Right Click")

    def load_image_asset(self):
        self.original_pixmap = QPixmap(self.image_path)
        if self.original_pixmap.isNull():
            print(f"Warning: Could not load image from '{self.image_path}'. Using fallback circle.")
            self.use_fallback_circle = True
            self.original_pixmap = QPixmap(100, 100)
            self.original_pixmap.fill(Qt.transparent)
        else:
            self.use_fallback_circle = False
            self.scaled_pixmap = self.original_pixmap

    def initUI(self):
        self.showFullScreen()
        self.setWindowTitle('Overlay Window')
        self.setMouseTracking(True)

    def track_mouse(self):
        cursor_pos = self.cursor().pos()
        self.mouse_x = cursor_pos.x()
        self.mouse_y = cursor_pos.y()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.use_fallback_circle:
            brush = QBrush(QColor(0, 255, 0, 255))
            painter.setBrush(brush)
            painter.setPen(QPen(Qt.NoPen))
            radius = int(50 * self.scale_factor)
            diameter = 2 * radius
            x = self.mouse_x - radius
            y = self.mouse_y - radius
            painter.drawEllipse(int(x), int(y), diameter, diameter)
        else:
            painter.setPen(QPen(Qt.NoPen))
            new_width = int(self.original_pixmap.width() * self.scale_factor)
            new_height = int(self.original_pixmap.height() * self.scale_factor)
            self.scaled_pixmap = self.original_pixmap.scaled(
                new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            w = self.scaled_pixmap.width()
            h = self.scaled_pixmap.height()
            x = self.mouse_x - int(w / 2)
            y = self.mouse_y - int(h / 2)
            painter.drawPixmap(int(x), int(y), self.scaled_pixmap)

    def start_manual_calibration(self):
        self.is_calibrating = True
        self.calibration_index = 0
        self.calibration_data = {}
        w, h = self.width(), self.height()
        margin_x, margin_y = int(w * 0.1), int(h * 0.1)
        xs = [margin_x, w // 2, w - margin_x]
        ys = [margin_y, h // 2, h - margin_y]
        self.calibration_points = [(x,y) for y in ys for x in xs]
        print(f"Calibration Started. Look at point 1 and left-click.")
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.camera_worker.stop()
            self.close()
        elif event.key() in [Qt.Key_Up, Qt.Key_W]:
            self.mouse_y -= self.move_speed
            self.update()
        elif event.key() in [Qt.Key_Left, Qt.Key_A]:
            self.mouse_x -= self.move_speed
            self.update()
        elif event.key() in [Qt.Key_Down, Qt.Key_S]:
            self.mouse_y += self.move_speed
            self.update()
        elif event.key() in [Qt.Key_Right, Qt.Key_D]:
            self.mouse_x -= self.move_speed
            self.update()
        elif event.key() == Qt.Key_C:
            self.start_manual_calibration()
        elif event.key() == Qt.Key_5 and (event.modifiers() & Qt.KeypadModifier):
            self.game_mode = not self.game_mode
            if self.game_mode:
                self.game_center_y = self.mouse_y / self.height() if self.height() else 0.5
                self.game_center_x = self.mouse_x / self.width() if self.width() else 0.5
                print("Game Mode Activated. Resting center point captured.")
            else:
                print("Desktop mode activated. Absolute mapping restored.")
            self.update()
            self.smoothed_mouse_x = None
            self.smoothed_mouse_y = None

if __name__ == "__main__":
    from GUI import ControlDashboard
    app = QApplication(sys.argv)
    overlay = FullScreenOverlay()
    overlay.show()
    dashboard = ControlDashboard(overlay_app=overlay)
    dashboard.show()
    sys.exit(app.exec_())
