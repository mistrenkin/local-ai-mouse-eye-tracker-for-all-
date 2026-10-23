import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("My First App")
window.resize(300, 200)

layout = QVBoxLayout()
label = QLabel("Hello World! PySide6 is working!")
layout.addWidget(label)

window.setLayout(layout)
window.show()

sys.exit(app.exec())
