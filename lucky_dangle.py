import sys
import os
import winreg
import math
from PyQt6.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QAction, QFont, QColor, QPainterPath, QPen, QImage
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class LuckyDangleApp(QWidget):
    def __init__(self):
        super().__init__()

        #Initializing the Audio Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        audio_path = resource_path("bell_sound.wav")
        self.player.setSource(QUrl.fromLocalFile(audio_path))
        self.audio_output.setVolume(0.9)

        # 1. Frameless, Always on Top, Hidden from Taskbar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 2. Window Dimensions (Full Screen)
        screen = QApplication.primaryScreen().geometry()
        self.resize(screen.width(), screen.height())

        # 3. Elastic Spring Physics State
        self.target_rest_length = 150  # NEW: The final length of the string
        self.rest_length = 150       # The natural length of the string
        self.charm_x = self.width() - 300
        self.charm_y = self.rest_length
        self.vel_x = 0.0
        self.vel_y = 0.0

        self.spring_k = 0.1          # Stiffness of the elastic (higher = stiffer)
        self.damping = 0.92          # Friction/Air resistance (lower = stops faster)
        self.gravity = 2.0           # Downward pull
        self.is_dragging = False

        default_charm = resource_path(os.path.join('charms', 'Nazar.png'))

        #Load default image on Start-up
        self.load_charm(default_charm)

        # 4. Animation Engine (~60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16)

        self.setup_tray()
        self.move_to_top_center()

        # Trigger an initial drop-in swing
        self.swing(10)

    def load_charm(self, image_path):
        self.current_image = os.path.basename(image_path)
        if not os.path.exists(image_path):
            fallback = QPixmap(80, 80)
            fallback.fill(Qt.GlobalColor.transparent)
            painter = QPainter(fallback)
            painter.setBrush(QColor(255, 100, 100))
            painter.drawEllipse(0, 0, 80, 80)
            painter.end()
            self.charm_img = fallback
        else:
            high_res_image = QImage(image_path)
            # Shrink it smoothly
            scaled_image = high_res_image.scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.charm_img = QPixmap.fromImage(scaled_image)
        # SHADOW GENERATOR BLOCK ---
            shadow_img = QImage(scaled_image.size(), QImage.Format.Format_ARGB32_Premultiplied)
            shadow_img.fill(Qt.GlobalColor.transparent)

            shadow_painter = QPainter(shadow_img)
            shadow_painter.drawPixmap(0, 0, self.charm_img)
            # SourceIn composition only paints over pixels that already exist (ignoring transparent space)
            shadow_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            shadow_painter.fillRect(shadow_img.rect(), QColor(0, 0, 0, 100)) # 100 is the shadow darkness (0-255)
            shadow_painter.end()

            self.charm_shadow = QPixmap.fromImage(shadow_img)
            self.rest_length = 20
            self.charm_y = 20
            # Clear out any previous swinging momentum
            self.vel_x = 0.0
            # Give it a slight initial downward velocity so it feels heavy when dropped
            self.vel_y = 0.0
        self.update()
    def is_startup_enabled(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "LuckyDangle"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    def toggle_startup(self, enable):
        # Gets the path to your compiled .exe (or the .py script if testing)
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "LuckyDangle"

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{app_path}"')
            else:
                winreg.DeleteValue(key, app_name)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Failed to modify startup registry: {e}")

    def move_to_top_center(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.x(), screen.y())

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        # Generate a dynamic tray icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.drawText(0, 14, "🧿")
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))

        self.tray_menu = QMenu()
        swing_action = QAction("Swing Charm", self)
        swing_action.triggered.connect(lambda: self.swing(15))
        self.tray_menu.addAction(swing_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        self.tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def enterEvent(self, event):
        # Give the charm a gentle push whenever the mouse hovers over it
        self.swing(5)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Optional: You can add behavior when the mouse leaves if desired
        super().leaveEvent(event)

    def swing(self, force):
        self.vel_x += force

    def update_physics(self):
        if self.is_dragging:
            return
        # --- NEW: UNWINDING ANIMATION ---
        # Gracefully unroll the string if it's shorter than the target
        if hasattr(self, 'target_rest_length'):
            if self.rest_length < self.target_rest_length:
                self.rest_length += (self.target_rest_length - self.rest_length) * 0.05

        pivot_x = self.width() - 300
        pivot_y = 0

        # Calculate distance between the pivot and the charm
        dx = self.charm_x - pivot_x
        dy = self.charm_y - pivot_y
        distance = math.sqrt(dx**2 + dy**2)

        if distance == 0:
            distance = 0.01

        # Hooke's Law: The further it stretches past rest_length, the harder it pulls back
        spring_force = (distance - self.rest_length) * self.spring_k

        # Break the force into X and Y directions
        force_x = -spring_force * (dx / distance)
        force_y = -spring_force * (dy / distance)

        # Add gravity pulling down
        force_y += self.gravity

        # Apply forces to velocity, and apply friction (damping)
        self.vel_x = (self.vel_x + force_x) * self.damping
        self.vel_y = (self.vel_y + force_y) * self.damping

        # Move the charm
        self.charm_x += self.vel_x
        self.charm_y += self.vel_y


        self.update() # Trigger a repaint

    def paintEvent(self, event):
        if not hasattr(self, 'charm_x') or not hasattr(self, 'charm_img'):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pivot_x = self.width() - 300
        pivot_y = 0

        dx = self.charm_x - pivot_x
        dy = self.charm_y - pivot_y
        distance = max(math.sqrt(dx**2 + dy**2), 1)
        stretch_ratio = max(0.4, self.rest_length / distance)

        pen = QPen(QColor(150, 150, 150))
        pen.setWidth(max(1, int(3 * stretch_ratio)))
        painter.setPen(pen)

        path = QPainterPath()
        path.moveTo(pivot_x, pivot_y)

        mid_x = (pivot_x + self.charm_x) / 2
        mid_y = (pivot_y + self.charm_y) / 2

        drag_multiplier = 4.0
        ctrl_x = mid_x - (self.vel_x * drag_multiplier)
        ctrl_y = mid_y - (self.vel_y * drag_multiplier)


        string_overlap = 35
        # --- ADJUST THE STRING OVERLAP ---
        # A small overlap (like 5 or 10 pixels) tucks the string neatly behind the image
        string_overlap = 5
        end_y = self.charm_y + string_overlap

        path.quadTo(ctrl_x, ctrl_y, self.charm_x, end_y)
        painter.drawPath(path)



        # --- CALCULATE IMAGE POSITION ---
        img_w = self.charm_img.width()
        img_x = self.charm_x - (img_w / 2.0)
        img_y = self.charm_y

        # --- DRAW THE SHADOW FIRST (Underneath) ---
        if hasattr(self, 'charm_shadow'):
            shadow_offset_x = 5  # Push shadow 5px to the right
            shadow_offset_y = 5  # Push shadow 5px down
            painter.drawPixmap(QPointF(img_x + shadow_offset_x, img_y + shadow_offset_y), self.charm_shadow)

        # --- DRAW THE REAL IMAGE (On Top) ---
        painter.drawPixmap(QPointF(img_x, img_y), self.charm_img)
        painter.end()
    def handle_menu_selection(self, image_path):
        self.load_charm(image_path)

        # Check the newly selected file path for the word "bell"
        if "bell" in image_path.lower():
            self.player.stop()  # Force reset the audio state
            self.player.setPosition(0)
            self.player.play()

    def mousePressEvent(self, event):
        # --- THE FIX: Ignore mouse events if the app is still booting up ---
        if not hasattr(self, 'charm_y'):
            return

        # Calculate the distance from the mouse to the center of the image (hitbox)
        img_center_y = self.charm_y + 40 # 40 is half of the 80px image height
        dx = event.position().x() - self.charm_x
        dy = event.position().y() - img_center_y
        distance = math.sqrt(dx**2 + dy**2)

        is_touching_charm = distance <= 45 # 45 pixel radius hitbox

        if not is_touching_charm:
            return

        if event.button() == Qt.MouseButton.LeftButton:
           if "bell" in self.current_image.lower():
               self.player.setPosition(0)
               self.player.play()


        if event.button() == Qt.MouseButton.LeftButton:
            # Grab and drag
            self.is_dragging = True
            self.vel_x = 0.0
            self.vel_y = 0.0

        elif event.button() == Qt.MouseButton.RightButton:
            # Open the dynamic context menu
            self.show_charm_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if not hasattr(self, 'charm_y'):
            return
        if self.is_dragging:
            # The charm maps 1:1 with your mouse pointer
            self.charm_x = event.position().x()
            self.charm_y = event.position().y()
            self.update()

    def mouseReleaseEvent(self, event):
        if not hasattr(self, 'charm_y'):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False

    def show_charm_menu(self, global_pos):
        menu = QMenu(self)

        # --- MOUSE HOVER STYLESHEET BLOCK ---
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff; /* Solid white background */
                border: 1px solid #cccccc; /* Light gray border */
            }
            QMenu::item {
                padding: 6px 25px 6px 20px; /* Spacing around the text */
                color: #000000;             /* Black text */
            }
            QMenu::item:selected {
                background-color: #0078D7;  /* Windows blue highlight */
                color: #ffffff;             /* White text on hover */
            }
            QMenu::icon {
                padding-left: 12px; /* Pushes the icon away from the left edge */
            }
        """)
        # ---------------------------------

        charms_dir = resource_path('charms')

        if not os.path.exists(charms_dir):
            action = QAction("Error: Charms folder missing from build", self)
            action.setEnabled(False)
            menu.addAction(action)
        else:
            # Find all PNG files in the folder
            files = [f for f in os.listdir(charms_dir) if f.endswith('.png')]

            if not files:
                action = QAction("No .png files found in charms folder", self)
                action.setEnabled(False)
                menu.addAction(action)
            else:
                for file in files:
                    clean_name = file.replace('.png', '').replace('_', ' ').title()
                    full_path = os.path.join(charms_dir, file)
                    action = QAction(QIcon(full_path), clean_name, self)

                    action.triggered.connect(
                        lambda checked=False, f=file: self.handle_menu_selection(os.path.join(charms_dir, f))
                    )
                    menu.addAction(action)

        # --- Run at StartUp Menu ---

        menu.addSeparator()

        startup_action = QAction("Run at Startup", self, checkable=True)
        startup_action.setChecked(self.is_startup_enabled())
        startup_action.triggered.connect(self.toggle_startup)
        menu.addAction(startup_action)

        # --- EXIT BUTTON ---
        menu.addSeparator()
        exit_action = QAction("Exit App", self)
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(exit_action)

        menu.exec(global_pos)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LuckyDangleApp()
    window.show()
    sys.exit(app.exec())