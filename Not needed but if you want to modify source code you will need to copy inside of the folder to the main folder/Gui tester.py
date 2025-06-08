from gui import Ui_MainWindow
from PyQt5.QtWidgets import QApplication, QMainWindow

class MyApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

app = QApplication([])
window = MyApp()
window.INJECT.clicked.connect(print)
window.show()
app.exec_()
