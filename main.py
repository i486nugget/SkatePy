import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton
from PyQt5.QtGui import QImage, QFont, QPixmap
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

class Scene3D(QOpenGLWidget):
    def __init__(self, parent=None):
        super(Scene3D, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.camera_pos = np.array([0.0, 20.0, 5.0])
        self.camera_rot = np.array([0.0, 0.0, 0.0])
        self.move_speed = 1
        self.rot_speed = 1
        self.keys = set()
        self.floor_texture = None
        self.wall_texture = None
        
        self.score = 0
        self.last_move = None
        self.last_move_count = 0
        self.last_move_time = 0
        
        self.score_label = QLabel(self)
        w95fa_font = QFont("w95fa", 20)
        self.score_label.setFont(w95fa_font)
        self.score_label.setStyleSheet("color: white;")
        self.score_label.setAlignment(Qt.AlignCenter)
        
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

    def update_score_label(self):
        score_text = f"{self.score}"
        if self.last_move:
            if self.last_move_count > 1:
                score_text += f"\n{self.last_move} (x{self.last_move_count})"
            else:
                score_text += f"\n{self.last_move}"
        self.score_label.setText(score_text)
        self.score_label.show()

    def stop_music(self):
        pygame.mixer.music.stop()

    def reset_preview_image(self):
        pixmap = QPixmap(self.preview_image_path)
        pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.preview_image.setPixmap(pixmap)

    def load_textures(self):
        floor_path = os.path.join(os.path.dirname(__file__), 'tex', 'brick.png')
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
            
            return True
        except Exception as e:
            print(f"Error loading textures: {e}")
            return False

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glShadeModel(GL_SMOOTH)
        glClearColor(0.2, 0.2, 0.2, 1.0)
        self.load_textures()
        self.preview_image.show()
        self.score_label.show()

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

        self.update_stats()

    def update_scene(self):
        if not self.hasFocus():
            return

        angle = math.radians(-self.camera_rot[1])
        forward = np.array([-math.sin(angle), 0, -math.cos(angle)])
        right = np.array([math.cos(angle), 0, -math.sin(angle)])
        
        new_pos = self.camera_pos.copy()
        
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
            new_pos -= right * self.move_speed
            self.camera_rot[1] -= 0.1
            pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'tex', 'birb', 'left.png'))
            pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.preview_image.setPixmap(pixmap)
            self.side_timer.start(500)
        
        if Qt.Key_D in self.keys:
            new_pos += right * self.move_speed
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

        if Qt.Key_Left in self.keys:
            self.camera_rot[1] -= self.rot_speed
        if Qt.Key_Right in self.keys:
            self.camera_rot[1] += self.rot_speed
        if Qt.Key_Up in self.keys:
            self.camera_rot[0] = max(-89, self.camera_rot[0] - self.rot_speed)
        if Qt.Key_Down in self.keys:
            self.camera_rot[0] = min(89, self.camera_rot[0] + self.rot_speed)

        self.update()

    def keyPressEvent(self, event):
        self.keys.add(event.key())
        
        if event.key() == Qt.Key_Space and not self.is_ollying:
            self.is_ollying = True
            self.ollie_timer = 0
            pixmap = QPixmap(self.ollie_preview_path)
            pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.preview_image.setPixmap(pixmap)
            
            current_time = time.time()
            if self.last_move == 'Ollie' and current_time - self.last_move_time < 5:
                self.last_move_count += 1
            else:
                self.last_move = 'Ollie'
                self.last_move_count = 1
            
            self.last_move_time = current_time
            self.score += 100
            self.update_score_label()
        
        if event.key() == Qt.Key_P:
            if not self.is_music_playing:
                pygame.mixer.music.load(os.path.join(os.path.dirname(__file__), 'bgm', 'title.wav'))
                pygame.mixer.music.play(-1)
                self.is_music_playing = True
            else:
                pygame.mixer.music.stop()
                self.is_music_playing = False

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
