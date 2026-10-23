import sys 
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QWidget 
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen
import cv2 

class CameraWorker:
    def __init__(self):
        # Fallback loop: test camera 0, then 1, then 2
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(2)
            
        if not self.cap.isOpened():
            print("❌ STAGE 1 ERROR: Windows cannot find any working webcam hardware!")
        else:
            print("✅ STAGE 1 SUCCESS: Camera connected successfully.")

class FullScreenOverlay(QWidget):
    def __init__(self):
        super().__init__()
        print("🚀 STAGE 2: Initializing the window layer...")
        
        # Test camera link first
        self.camera = CameraWorker()
        
        self.initUI()
        self.mouse_x = 0
        self.mouse_y = 0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.track_mouse)
        self.timer.start(16) 
        print("✅ STAGE 3 SUCCESS: Window system is fully active.")

    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.showFullScreen()
        self.setMouseTracking(True)

    def track_mouse(self):
        cursor_pos = self.cursor().pos()
        self.mouse_x = cursor_pos.x()
        self.mouse_y = cursor_pos.y()
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.NoPen))
        painter.setBrush(QBrush(QColor(0, 255, 0, 255))) # Green tracking dot
        painter.drawEllipse(int(self.mouse_x - 25), int(self.mouse_y - 25), 50, 50)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            print("🛑 Closing program.")
            self.close()

if __name__ == '__main__':
    print("🎬 Starting verification script...")
    app = QApplication(sys.argv)
    overlay = FullScreenOverlay()
    sys.exit(app.exec_())
