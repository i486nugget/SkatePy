import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QDialog
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEvent
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import os
from PIL import Image
import pygame
import time

# comment at the start of the file or something but do not delete it :3. Also give full code all the way to the end.

class PauseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pause")
        self.setFixedSize(400, 250)
        self.setModal(True)
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout()

        label = QLabel("Game on pause, press [ESC] to resume")
        label.setFont(QFont("Times New Roman", 24))
        label.setStyleSheet("color: white;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        button_layout = QHBoxLayout()
        
        title_screen_button = QPushButton("Title Screen")
        title_screen_button.setFont(QFont("Times New Roman", 18))
        title_screen_button.setStyleSheet("color: white; background-color: rgba(255,255,255,50);")
        title_screen_button.clicked.connect(self.go_to_title_screen)
        button_layout.addWidget(title_screen_button)

        resume_button = QPushButton("Resume")
        resume_button.setFont(QFont("Times New Roman", 18))
        resume_button.setStyleSheet("color: white; background-color: rgba(255,255,255,50);")
        resume_button.clicked.connect(self.accept)
        button_layout.addWidget(resume_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def go_to_title_screen(self):
        main_window = self.parent()
        while main_window and not isinstance(main_window, MainWindow):
            main_window = main_window.parent()
        if main_window:
            main_window.return_to_title_screen()
        self.accept()

class Scene3D(QOpenGLWidget):
    def __init__(self, parent=None):
        super(Scene3D, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.camera_pos = np.array([0.0, 20.0, 5.0])
        self.camera_rot = np.array([0.0, 0.0, 0.0])
        self.third_person_camera_pos = np.array([0.0, 25.0, 15.0])
        self.third_person_camera_rot = np.array([0.0, 0.0, 0.0])
        self.move_speed = 0.0
        self.max_move_speed = 1.5
        self.auto_forward_speed = 2.0
        self.acceleration = 0.05
        self.deceleration = 0.05
        self.side_move_speed = 0.2
        self.rot_speed = 1
        self.keys = set()
        self.floor_texture = None
        self.wall_texture = None
        
        self.score = 0
        self.combo_score = 0
        self.last_move = None
        self.last_move_time = 0
        
        self.last_move_key = None
        self.last_move_key_time = 0
        
        self.score_label = QLabel(self)
        w95fa_font = QFont("w95fa", 20)
        self.score_label.setFont(w95fa_font)
        self.score_label.setStyleSheet("color: white;")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.hide()
        
        self.preview_image = QLabel(self)
        self.preview_image.setGeometry(self.width() - 128, self.height() - 128, 128, 128)
        self.preview_image_path = os.path.join(os.path.dirname(__file__), 'tex', 'birb', 'forward.png')
        pixmap = QPixmap(self.preview_image_path)
        pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.preview_image.setPixmap(pixmap)
        self.preview_image.setStyleSheet("background-color: rgba(255, 255, 255, 100);")
        self.preview_image.hide()

        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(10, 0, 10, 0)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_scene)
        self.timer.start(16)
        pygame.mixer.init()

        self.side_timer = QTimer()
        self.side_timer.setSingleShot(True)
        self.side_timer.timeout.connect(self.reset_preview_image)

        self.ollie_timer = 0
        self.ollie_duration = 60
        self.ollie_height = 35.0
        self.is_ollying = False
        self.ollie_preview_path = os.path.join(os.path.dirname(__file__), 'tex', 'birb', 'ollie.png')

        self.is_music_playing = False
        
        self.is_third_person = False
        self.third_person_textures = []
        self.third_person_current_frame = 0
        self.third_person_frame_timer = QTimer()
        self.third_person_frame_timer.timeout.connect(self.update_third_person_frame)

    def update_third_person_frame(self):
        self.third_person_current_frame = (self.third_person_current_frame + 1) % len(self.third_person_textures)

    def update_score_label(self):
        if self.combo_score > 0:
            score_text = f"Combo: {self.combo_score}"
            if self.last_move:
                score_text = f"{self.last_move} (+{self.score})\n{score_text}"
            self.score_label.setText(score_text)
            self.score_label.show()
        else:
            self.score_label.hide()

    def stop_music(self):
        pygame.mixer.music.stop()

    def reset_preview_image(self):
        pixmap = QPixmap(self.preview_image_path)
        pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.preview_image.setPixmap(pixmap)

    def load_textures(self):
        floor_path = os.path.join(os.path.dirname(__file__), 'tex', 'brick.png')
        third_person_path = os.path.join(os.path.dirname(__file__), 'tex', 'birb', 'thirdperson.gif')
        try:
            floor_img = Image.open(floor_path)
            floor_img = floor_img.convert("RGBA")
            floor_img = floor_img.resize((64, 64), Image.NEAREST)
            floor_data = floor_img.tobytes()
            self.floor_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.floor_texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, floor_img.width, floor_img.height, 
                         0, GL_RGBA, GL_UNSIGNED_BYTE, floor_data)
            
            third_person_gif = Image.open(third_person_path)
            self.third_person_textures = []
            
            for frame in range(third_person_gif.n_frames):
                third_person_gif.seek(frame)
                third_person_img = third_person_gif.convert("RGBA")
                third_person_img = third_person_img.resize((64, 64), Image.NEAREST)
                
                background = Image.new('RGBA', third_person_img.size, (0, 0, 0, 0))
                background.paste(third_person_img, (0, 0), third_person_img)
                third_person_img = background
                
                third_person_data = third_person_img.tobytes()
                
                texture = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, texture)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, third_person_img.width, third_person_img.height, 
                             0, GL_RGBA, GL_UNSIGNED_BYTE, third_person_data)
                
                self.third_person_textures.append(texture)
            
            self.third_person_frame_timer.start(1000)
            
            return True
        except Exception as e:
            print(f"Error loading textures: {e}")
            return False

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glShadeModel(GL_SMOOTH)
        glClearColor(0.2, 0.2, 0.2, 1.0)
        self.load_textures()
        self.preview_image.show()

    def resizeGL(self, width, height):
        glViewport(0, 50, width, height - 50)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(90, width / (height - 50), 0.1, 1000.0)
        self.preview_image.setGeometry(width - 138, height - 138, 128, 128)
        self.score_label.setGeometry(width - 138, height - 268, 128, 130)

    def update_stats(self):
        stats = f"Position: ({self.camera_pos[0]:.2f}, {self.camera_pos[1]:.2f}, {self.camera_pos[2]:.2f}) | "
        stats += f"Rotation: ({self.camera_rot[0]:.2f}, {self.camera_rot[1]:.2f})"
        print(stats, end='\r')

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, self.width() / (self.height() - 50), 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        if self.is_third_person:
            glRotatef(self.third_person_camera_rot[0], 1, 0, 0)
            glRotatef(self.third_person_camera_rot[1], 0, 1, 0)
            glTranslatef(-self.third_person_camera_pos[0], -self.third_person_camera_pos[1], -self.third_person_camera_pos[2])
        else:
            glRotatef(self.camera_rot[0], 1, 0, 0)
            glRotatef(self.camera_rot[1], 0, 1, 0)
            glTranslatef(-self.camera_pos[0], -self.camera_pos[1], -self.camera_pos[2])
        
        if self.floor_texture:
            glBindTexture(GL_TEXTURE_2D, self.floor_texture)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(-1000, 0, -1000)
            glTexCoord2f(100, 0); glVertex3f(1000, 0, -1000)
            glTexCoord2f(100, 100); glVertex3f(1000, 0, 1000)
            glTexCoord2f(0, 100); glVertex3f(-1000, 0, 1000)
            glEnd()
        
        if self.is_third_person and self.third_person_textures:
            current_texture = self.third_person_textures[self.third_person_current_frame]
            glBindTexture(GL_TEXTURE_2D, current_texture)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(self.camera_pos[0] - 5, 20, self.camera_pos[2])
            glTexCoord2f(1, 0); glVertex3f(self.camera_pos[0] + 5, 20, self.camera_pos[2])
            glTexCoord2f(1, 1); glVertex3f(self.camera_pos[0] + 5, 0, self.camera_pos[2])
            glTexCoord2f(0, 1); glVertex3f(self.camera_pos[0] - 5, 0, self.camera_pos[2])
            glEnd()

        self.update_stats()

    def update_scene(self):
        current_time = time.time()
        
        if self.last_move_time > 0 and current_time - self.last_move_time >= 5:
            self.combo_score = 0
            self.last_move = None
            self.last_move_time = 0
            self.update_score_label()

        if not self.hasFocus():
            return

        angle = math.radians(-self.camera_rot[1])
        forward = np.array([-math.sin(angle), 0, -math.cos(angle)])
        right = np.array([math.cos(angle), 0, -math.sin(angle)])
        
        new_pos = self.camera_pos.copy()
        
        if Qt.Key_W in self.keys and Qt.Key_S not in self.keys:
            if self.move_speed == 0:
                self.move_speed = 0.5
            self.move_speed = min(self.move_speed + self.acceleration, self.max_move_speed)
            new_pos += forward * self.move_speed
        elif Qt.Key_S in self.keys:
            self.move_speed = max(self.move_speed - self.deceleration, 0)
        else:
            if self.move_speed == self.max_move_speed:
                new_pos += forward * self.auto_forward_speed
            else:
                self.move_speed = max(self.move_speed - self.deceleration, 0)
                if self.move_speed > 0:
                    new_pos += forward * self.move_speed
        
        if self.is_ollying:
            self.ollie_timer += 1
            if self.ollie_timer <= self.ollie_duration // 2:
                new_pos[1] = 20 + (self.ollie_height - 20) * (self.ollie_timer / (self.ollie_duration // 2))
            elif self.ollie_timer <= self.ollie_duration // 2 + 30:
                new_pos[1] = self.ollie_height
            else:
                new_pos[1] = self.ollie_height - (self.ollie_height - 20) * ((self.ollie_timer - (self.ollie_duration // 2 + 30)) / (self.ollie_duration // 2))
            
            if self.ollie_timer >= self.ollie_duration + 30:
                self.is_ollying = False
                self.ollie_timer = 0
                new_pos[1] = 20
                pixmap = QPixmap(self.preview_image_path)
                pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
                self.preview_image.setPixmap(pixmap)
        
        if Qt.Key_A in self.keys:
            new_pos -= right * self.side_move_speed
            self.camera_rot[1] -= 0.1
            pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'tex', 'birb', 'left.png'))
            pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.preview_image.setPixmap(pixmap)
            self.side_timer.start(500)
        
        if Qt.Key_D in self.keys:
            new_pos += right * self.side_move_speed
            self.camera_rot[1] += 0.1
            pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'tex', 'birb', 'right.png'))
            pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.preview_image.setPixmap(pixmap)
            self.side_timer.start(500)

        if new_pos[0] > 1000:
            new_pos[0] = -1000
        elif new_pos[0] < -1000:
            new_pos[0] = 1000
        
        if new_pos[2] > 1000:
            new_pos[2] = -1000
        elif new_pos[2] < -1000:
            new_pos[2] = 1000

        self.camera_pos = new_pos
        
        if self.is_third_person:
            self.third_person_camera_pos = np.array([
                self.camera_pos[0], 
                self.camera_pos[1] + 5, 
                self.camera_pos[2] + 10
            ])
            self.third_person_camera_rot = self.camera_rot.copy()

        if Qt.Key_Left in self.keys or Qt.Key_J in self.keys:
            self.camera_rot[1] -= self.rot_speed
        if Qt.Key_Right in self.keys or Qt.Key_L in self.keys:
            self.camera_rot[1] += self.rot_speed
        if Qt.Key_Up in self.keys or Qt.Key_I in self.keys:
            self.camera_rot[0] = max(-89, self.camera_rot[0] - self.rot_speed)
        if Qt.Key_Down in self.keys or Qt.Key_K in self.keys:
            self.camera_rot[0] = min(89, self.camera_rot[0] + self.rot_speed)

        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            pause_dialog = PauseDialog(self)
            pause_dialog.exec_()
            return

        self.keys.add(event.key())
        
        current_time = time.time()
        
        # Track last move key for manual detection
        if event.key() in [Qt.Key_A, Qt.Key_D]:
            if self.last_move_key in [Qt.Key_A, Qt.Key_D] and event.key() != self.last_move_key and current_time - self.last_move_key_time < 1:
                current_time = time.time()
                if self.last_move == 'Manual' and current_time - self.last_move_time < 5:
                    self.combo_score += 50
                else:
                    self.combo_score = 50
                
                self.score = 50
                self.last_move = 'Manual'
                self.last_move_time = current_time
                self.update_score_label()
            
            self.last_move_key = event.key()
            self.last_move_key_time = current_time
        
        if event.key() == Qt.Key_Space and not self.is_ollying:
            self.is_ollying = True
            self.ollie_timer = 0
            pixmap = QPixmap(self.ollie_preview_path)
            pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.preview_image.setPixmap(pixmap)
            
            current_time = time.time()
            if self.last_move == 'Ollie' and current_time - self.last_move_time < 5:
                self.combo_score += 100
            else:
                self.combo_score = 100
            
            self.score = 100
            self.last_move = 'Ollie'
            self.last_move_time = current_time
            self.update_score_label()
        
        if event.key() == Qt.Key_P:
            if not self.is_music_playing:
                pygame.mixer.music.load(os.path.join(os.path.dirname(__file__), 'bgm', 'theme.wav'))
                pygame.mixer.music.play(-1)
                self.is_music_playing = True
            else:
                pygame.mixer.music.stop()
                self.is_music_playing = False
        
        if event.key() == Qt.Key_T:
            self.is_third_person = not self.is_third_person

    def keyReleaseEvent(self, event):
        self.keys.discard(event.key())

    def focusOutEvent(self, event):
        self.keys.clear()

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("SkatePy")
        
        self.showFullScreen()
        
        self.setStyleSheet("background-color: #383434;")
        
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_widget)
        self.show_title_screen()

    def show_title_screen(self):
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), 'html', 'title.html')))
        self.layout.addWidget(self.web_view)
        self.web_view.installEventFilter(self)
        
        play_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setFixedSize(100, 50)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: black;
            }
        """)
        self.play_button.clicked.connect(self.start_game)
        play_layout.addStretch(1)
        play_layout.addWidget(self.play_button)
        play_layout.addStretch(1)
        self.layout.addLayout(play_layout)

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Return:
            self.start_game()
            return True
        return super(MainWindow, self).eventFilter(source, event)

    def start_game(self):
        self.web_view.hide()
        self.play_button.hide()
        self.scene = Scene3D(self)
        self.layout.addWidget(self.scene)
        self.scene.setFocus()

    def return_to_title_screen(self):
        self.scene.stop_music()
        self.scene.hide()
        self.layout.removeWidget(self.scene)
        self.scene.deleteLater()
        self.show_title_screen()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
# comment at the end of the file or something but do not delete it :3. Also give full code all the way to the end.