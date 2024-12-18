import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget, QLabel, QVBoxLayout, QWidget, QComboBox, QHBoxLayout, QPushButton, QProgressBar
from PyQt5.QtGui import QImage, QFont
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEvent
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import os
from PIL import Image
import pygame

class Scene3D(QOpenGLWidget):
    def __init__(self, parent=None):
        super(Scene3D, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.camera_pos = np.array([0.0, 20.0, 5.0])
        self.camera_rot = np.array([0.0, 0.0, 0.0])
        self.move_speed = 1
        self.sprint_speed_multiplier = 1.5
        self.rot_speed = 0.8
        self.keys = set()
        self.floor_texture = None
        self.wall_texture = None
        self.enemy_texture = None
        self.enemies = []
        self.health = 100

        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(10, 0, 10, 0)

        self.health_bar = QProgressBar()
        self.health_bar.setMaximum(100)
        self.health_bar.setValue(self.health)
        self.health_bar.setStyleSheet("""
            QProgressBar {
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: RED;
                width: 10px;
                margin: 0.5px;
            }
        """)
        self.controls_layout.addWidget(self.health_bar)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: white;")
        self.controls_layout.addWidget(self.stats_label)

        self.song_selector = QComboBox()
        self.song_selector.addItems(self.get_song_list())
        self.song_selector.currentIndexChanged.connect(self.change_song)
        self.song_selector.setStyleSheet("""
            QComboBox {
                background-color: white;
                color: black;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: darkgray;
                border-left-style: solid;
            }
        """)
        self.controls_layout.addWidget(self.song_selector)

        self.stop_music_button = QPushButton("Stop Music")
        self.stop_music_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: black;
            }
        """)
        self.stop_music_button.clicked.connect(self.stop_music)
        self.controls_layout.addWidget(self.stop_music_button)

        self.controls_visible = False
        self.toggle_controls_visibility()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_scene)
        self.timer.start(16)
        pygame.mixer.init()
        self.current_song = os.path.join(os.path.dirname(__file__), 'bgm', 'TitleForGame.wav')

    def stop_music(self):
        pygame.mixer.music.stop()

    def get_song_list(self):
        bgm_path = os.path.join(os.path.dirname(__file__), 'bgm')
        return [f for f in os.listdir(bgm_path) if f.endswith('.wav')]

    def change_song(self, index):
        song = self.song_selector.itemText(index)
        song_path = os.path.join(os.path.dirname(__file__), 'bgm', song)
        pygame.mixer.music.load(song_path)
        pygame.mixer.music.play(-1)

    def load_textures(self):
        floor_path = os.path.join(os.path.dirname(__file__), 'tex', 'brick.png')
        wall_path = os.path.join(os.path.dirname(__file__), 'tex', 'sky.png')
        enemy_path = os.path.join(os.path.dirname(__file__), 'tex', 'enemy.gif')
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

            wall_img = Image.open(wall_path)
            wall_img = wall_img.convert("RGBA")
            wall_img = wall_img.resize((64, 64), Image.NEAREST)
            wall_data = wall_img.tobytes()
            self.wall_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.wall_texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, wall_img.width, wall_img.height, 
                         0, GL_RGBA, GL_UNSIGNED_BYTE, wall_data)

            enemy_img = Image.open(enemy_path)
            self.enemy_frames = []
            
            try:
                while True:
                    frame = enemy_img.convert("RGBA")
                    frame = frame.resize((64, 64), Image.NEAREST)
                    self.enemy_frames.append(frame.tobytes())
                    enemy_img.seek(enemy_img.tell() + 1)
            except EOFError:
                pass  # We've reached the end of the frames

            self.enemy_textures = []
            for frame_data in self.enemy_frames:
                texture = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, texture)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 64, 64, 0, GL_RGBA, GL_UNSIGNED_BYTE, frame_data)
                self.enemy_textures.append(texture)

            self.current_enemy_frame = 0
            self.enemy_frame_counter = 0
            self.enemy_frame_skip = 32
            
            return True
        except Exception as e:
            print(f"Error loading enemy texture: {e}")
            return False

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glShadeModel(GL_SMOOTH)
        glClearColor(0.2, 0.2, 0.2, 1.0)
        self.load_textures()

    def resizeGL(self, width, height):
        glViewport(0, 50, width, height - 50)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(90, width / (height - 50), 0.1, 1000.0)

    def update_stats(self):
        stats = f"Position: ({self.camera_pos[0]:.2f}, {self.camera_pos[1]:.2f}, {self.camera_pos[2]:.2f})\n"
        stats += f"Rotation: ({self.camera_rot[0]:.2f}, {self.camera_rot[1]:.2f})"
        self.stats_label.setText(stats)

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

        if self.wall_texture:
            glBindTexture(GL_TEXTURE_2D, self.wall_texture)
            # Front wall
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(-1000, 0, -1000)
            glTexCoord2f(50, 0); glVertex3f(1000, 0, -1000)
            glTexCoord2f(50, 50); glVertex3f(1000, 100, -1000)
            glTexCoord2f(0, 50); glVertex3f(-1000, 100, -1000)
            glEnd()

            # Back wall
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(-1000, 0, 1000)
            glTexCoord2f(50, 0); glVertex3f(1000, 0, 1000)
            glTexCoord2f(50, 50); glVertex3f(1000, 100, 1000)
            glTexCoord2f(0, 50); glVertex3f(-1000, 100, 1000)
            glEnd()

            # Left wall
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(-1000, 0, -1000)
            glTexCoord2f(50, 0); glVertex3f(-1000, 0, 1000)
            glTexCoord2f(50, 50); glVertex3f(-1000, 100, 1000)
            glTexCoord2f(0, 50); glVertex3f(-1000, 100, -1000)
            glEnd()

            # Right wall
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(1000, 0, -1000)
            glTexCoord2f(50, 0); glVertex3f(1000, 0, 1000)
            glTexCoord2f(50, 50); glVertex3f(1000, 100, 1000)
            glTexCoord2f(0, 50); glVertex3f(1000, 100, -1000)
            glEnd()

        if self.enemy_textures:
            for enemy in self.enemies:
                glPushMatrix()
                glTranslatef(enemy['pos'][0], 0, enemy['pos'][1])
                glRotatef(-self.camera_rot[1], 0, 1, 0)
                
                current_texture = self.enemy_textures[self.current_enemy_frame]
                glBindTexture(GL_TEXTURE_2D, current_texture)
                
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                
                enemy_height = min(50 + (self.camera_pos[1] - 20), 55)
                
                glBegin(GL_QUADS)
                glTexCoord2f(0, 0); glVertex3f(-enemy_height/2, 0, 0)
                glTexCoord2f(1, 0); glVertex3f(enemy_height/2, 0, 0)
                glTexCoord2f(1, 1); glVertex3f(enemy_height/2, enemy_height, 0)
                glTexCoord2f(0, 1); glVertex3f(-enemy_height/2, enemy_height, 0)
                glEnd()
                
                glDisable(GL_BLEND)
                
                glPopMatrix()

            self.enemy_frame_counter += 1
            if self.enemy_frame_counter >= self.enemy_frame_skip:
                self.current_enemy_frame = (self.current_enemy_frame + 1) % len(self.enemy_textures)
                self.enemy_frame_counter = 0

        self.update_stats()

    def update_scene(self):
        angle = math.radians(-self.camera_rot[1])
        forward = np.array([-math.sin(angle), 0, -math.cos(angle)])
        right = np.array([math.cos(angle), 0, -math.sin(angle)])
        
        current_move_speed = self.move_speed * (self.sprint_speed_multiplier if Qt.Key_Shift in self.keys else 1)
        
        new_pos = self.camera_pos.copy()
        if Qt.Key_W in self.keys:
            new_pos += forward * current_move_speed
        if Qt.Key_S in self.keys:
            new_pos -= forward * current_move_speed
        if Qt.Key_A in self.keys:
            new_pos -= right * current_move_speed
        if Qt.Key_D in self.keys:
            new_pos += right * current_move_speed

        if abs(new_pos[0]) < 990 and abs(new_pos[2]) < 990:
            self.camera_pos = new_pos

        if Qt.Key_Left in self.keys:
            self.camera_rot[1] -= self.rot_speed
        if Qt.Key_Right in self.keys:
            self.camera_rot[1] += self.rot_speed
        if Qt.Key_Up in self.keys:
            self.camera_rot[0] = max(-89, self.camera_rot[0] - self.rot_speed)
        if Qt.Key_Down in self.keys:
            self.camera_rot[0] = min(89, self.camera_rot[0] + self.rot_speed)

        # Filter out dead enemies
        self.enemies = [enemy for enemy in self.enemies if enemy['health'] > 0]

        # Existing enemy movement logic
        for enemy in self.enemies:
            direction = np.array([self.camera_pos[0] - enemy['pos'][0], 0, self.camera_pos[2] - enemy['pos'][1]])
            direction = direction / np.linalg.norm(direction)
            enemy['pos'][0] += direction[0] * 0.1
            enemy['pos'][1] += direction[2] * 0.1

            if np.linalg.norm(self.camera_pos[:2] - enemy['pos']) < 5:
                self.health -= 5
                self.health_bar.setValue(self.health)
                enemy['health'] = 0

        self.update()

    def keyPressEvent(self, event):
        self.keys.add(event.key())
        if event.key() == Qt.Key_QuoteLeft:  # ` key
            self.toggle_controls_visibility()
        if event.key() == Qt.Key_H:
            self.spawn_enemy()
        if event.key() == Qt.Key_Space:
            self.shoot_enemy()

    def keyReleaseEvent(self, event):
        self.keys.discard(event.key())

    def toggle_controls_visibility(self):
        self.controls_visible = not self.controls_visible
        self.stats_label.setVisible(self.controls_visible)
        self.song_selector.setVisible(self.controls_visible)
        self.stop_music_button.setVisible(self.controls_visible)

    def spawn_enemy(self):
        enemy_pos = self.camera_pos[:2] + np.array([100 * np.cos(math.radians(self.camera_rot[1])), 100 * np.sin(math.radians(self.camera_rot[1]))])
        self.enemies.append({'pos': enemy_pos, 'health': 100})

    def shoot_enemy(self):
        for enemy in self.enemies:
            direction = np.array([self.camera_pos[0] - enemy['pos'][0], 0, self.camera_pos[2] - enemy['pos'][1]])
            distance = np.linalg.norm(direction)
            if distance < 50:
                enemy['health'] -= 50
                break

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Py3D Game Demo")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #383434;")
        
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_widget)
        self.show_title_screen()

    def show_title_screen(self):
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), 'title.html')))
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
        self.layout.addLayout(self.scene.controls_layout)
        self.layout.addWidget(self.scene)
        self.scene.setFocus()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
