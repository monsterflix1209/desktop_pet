import sys
from PySide6.QtWidgets import QApplication, QStyle
import desktop_pet_v3 as v3

# Compatibility injection: V3 uses QStyle for the system-tray icon.
v3.QStyle = QStyle

if __name__ == '__main__':
    sys.exit(v3.main())
