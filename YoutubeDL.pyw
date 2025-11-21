import sys
import subprocess
import json
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QRadioButton, QScrollArea, QGroupBox, QButtonGroup, QMessageBox, QComboBox, QProgressBar
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import requests
from io import BytesIO
import datetime

class VideoItem(QWidget):
    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.info = info
        self.proc = None
        layout = QHBoxLayout()
        # Miniature
        thumb_url = info.get('thumbnail')
        if thumb_url:
            try:
                response = requests.get(thumb_url)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                thumb_label = QLabel()
                thumb_label.setPixmap(pixmap.scaled(384, 216, Qt.KeepAspectRatio))
                layout.addWidget(thumb_label)
            except Exception:
                layout.addWidget(QLabel('(miniature indisponible)'))
        # Infos
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"Titre : {info.get('title', 'Inconnu')}"))
        # Estimation taille et durée
        size, duration, size_bytes = self.estimate_size_duration(info)
        # Estimation durée téléchargement (débit moyen 10 Mo/s)
        download_speed = 10 * 1024 * 1024  # 10 Mo/s en octets
        if size_bytes:
            seconds = int(size_bytes / download_speed)
            if seconds < 60:
                download_est = f"~{seconds}s"
            else:
                download_est = f"~{seconds//60}m{seconds%60:02d}s"
        else:
            download_est = 'inconnue'
        info_layout.addWidget(QLabel(f"Taille estimée : {size} | Durée : {duration} | Téléchargement : {download_est}"))
        # Type choix
        self.type_group = QButtonGroup(self)
        self.radio_video = QRadioButton('Vidéo')
        self.radio_audio = QRadioButton('Audio')
        self.radio_video.setChecked(True)
        self.type_group.addButton(self.radio_video)
        self.type_group.addButton(self.radio_audio)
        type_layout = QHBoxLayout()
        type_layout.addWidget(self.radio_video)
        type_layout.addWidget(self.radio_audio)
        info_layout.addLayout(type_layout)
        # Qualité
        self.quality_combo = QComboBox()
        qualities = self.extract_qualities(info)
        self.quality_combo.addItems(qualities)
        # Sélectionne la meilleure qualité (la plus haute) par défaut
        if qualities and len(qualities) > 1:
            self.quality_combo.setCurrentIndex(len(qualities) - 1)
        info_layout.addWidget(QLabel('Qualité disponible :'))
        info_layout.addWidget(self.quality_combo)
        # Progression
        self.progress = QProgressBar()
        self.progress.setValue(0)
        info_layout.addWidget(self.progress)
        # Bouton annuler
        self.cancel_btn = QPushButton('Annuler')
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        info_layout.addWidget(self.cancel_btn)
        layout.addLayout(info_layout)
        self.setLayout(layout)

    def estimate_size_duration(self, info):
        # Taille
        size = 'inconnue'
        duration = 'inconnue'
        size_bytes = None
        try:
            # Prend la plus grande taille dispo
            sizes = [f.get('filesize') for f in info.get('formats', []) if f.get('filesize')]
            if sizes:
                size_bytes = max(sizes)
                size = f"{round(size_bytes/1024/1024, 1)} Mo"
            # Durée
            if info.get('duration'):
                mins = int(info['duration']) // 60
                secs = int(info['duration']) % 60
                duration = f"{mins}m{secs:02d}s"
        except Exception:
            pass
        return size, duration, size_bytes

    def set_progress(self, percent):
        self.progress.setValue(percent)

    def set_cancel_enabled(self, enabled):
        self.cancel_btn.setEnabled(enabled)

    def set_proc(self, proc):
        self.proc = proc
        self.set_cancel_enabled(True)

    def cancel_download(self):
        if self.proc:
            self.proc.terminate()
            self.set_cancel_enabled(False)

    def extract_qualities(self, info):
        qualities = []
        formats = info.get('formats', [])
        for f in formats:
            if f.get('vcodec') != 'none':
                height = f.get('height')
                if height:
                    qualities.append(str(height))
        qualities = sorted(set(qualities), key=lambda x: int(x))
        if not qualities:
            qualities = ['audio']
        return qualities

    def get_choice(self):
        return {
            'type': 'audio' if self.radio_audio.isChecked() else 'video',
            'quality': self.quality_combo.currentText()
        }

class MainWindow(QWidget):
    CONFIG_FILE = "output_dir.txt"

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Téléchargement multi-vidéos')
        self.resize(780, 450)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText('Collez un ou plusieurs liens (séparés par des retours à la ligne)')
        self.layout.addWidget(self.url_edit)
        self.fetch_btn = QPushButton('Analyser les liens')
        self.fetch_btn.clicked.connect(self.fetch_infos)
        self.layout.addWidget(self.fetch_btn)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.layout.addWidget(self.scroll)
        self.items = []

        # Choix du dossier de sortie (restaure depuis config si dispo)
        self.output_dir = self.load_output_dir()
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"Dossier de sortie : {self.output_dir}")
        dir_layout.addWidget(self.dir_label)
        self.dir_btn = QPushButton('Choisir dossier...')
        self.dir_btn.clicked.connect(self.choose_output_dir)
        dir_layout.addWidget(self.dir_btn)
        self.layout.addLayout(dir_layout)

        self.download_btn = QPushButton('Télécharger la sélection')
        self.download_btn.clicked.connect(self.download_all)
        self.layout.addWidget(self.download_btn)

    def load_output_dir(self):
        try:
            with open(self.CONFIG_FILE, encoding="utf-8") as f:
                path = f.read().strip()
                if path and os.path.isdir(path):
                    return path
        except Exception:
            pass
        return self.get_default_downloads()

    def save_output_dir(self):
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(self.output_dir)
        except Exception:
            pass

    def get_default_downloads(self):
        # Dossier Téléchargements utilisateur
        return os.path.join(os.path.expanduser('~'), 'Downloads')

    def choose_output_dir(self):
        from PySide6.QtWidgets import QFileDialog
        dir = QFileDialog.getExistingDirectory(self, 'Choisir le dossier de sortie', self.output_dir)
        if dir:
            self.output_dir = dir
            self.dir_label.setText(f"Dossier de sortie : {self.output_dir}")
            self.save_output_dir()

    def fetch_infos(self):
        links = [l.strip() for l in self.url_edit.text().splitlines() if l.strip()]
        if not links:
            QMessageBox.warning(self, 'Erreur', 'Veuillez entrer au moins un lien.')
            return
        content = QWidget()
        vbox = QVBoxLayout()
        self.items = []
        for link in links:
            info = self.get_video_info(link)
            if info:
                item = VideoItem(info)
                self.items.append((link, item))
                vbox.addWidget(item)
            else:
                vbox.addWidget(QLabel(f'Impossible d\'analyser : {link}'))
        content.setLayout(vbox)
        self.scroll.setWidget(content)

    def get_video_info(self, url):
        try:
            cmd = [sys.executable, '-m', 'yt_dlp', '-j', url]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except Exception:
            return None

    def download_all(self):
        import threading
        today = datetime.date.today().strftime('%d-%m-%Y')
        dated_dir = os.path.join(self.output_dir, today)
        os.makedirs(dated_dir, exist_ok=True)
        self.active_threads = []
        for link, item in self.items:
            t = threading.Thread(target=self.download_one, args=(link, item, dated_dir))
            t.start()
            self.active_threads.append(t)
        # Thread pour ouvrir le dossier à la fin
        threading.Thread(target=self.open_folder_when_done, args=(dated_dir,)).start()

    def open_folder_when_done(self, dated_dir):
        import time, platform
        for t in self.active_threads:
            t.join()
        # Ouvre le dossier de téléchargement
        if platform.system() == 'Windows':
            os.startfile(dated_dir)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', dated_dir])
        else:
            subprocess.Popen(['xdg-open', dated_dir])

    def download_one(self, link, item, dated_dir):
        import re
        choice = item.get_choice()
        outtmpl = os.path.join(dated_dir, '%(title)s.%(ext)s')
        cmd = [sys.executable, '-m', 'yt_dlp', link, '-o', outtmpl, '--progress']
        is_video = choice['type'] == 'video' and choice['quality'] != 'audio'
        if choice['type'] == 'audio':
            cmd += ['-f', 'bestaudio[ext=m4a]/bestaudio/best', '--extract-audio', '--audio-format', 'mp3']
        elif is_video:
            cmd += ['-f', f'bestvideo[height<={choice["quality"]}]+bestaudio/best[height<={choice["quality"]}]']
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            item.set_proc(proc)
            filename = None
            for line in proc.stdout:
                # yt-dlp affiche la progression sous forme : [download]   0.0% ...
                m = re.search(r'(\d{1,3}\.\d)%', line)
                if m:
                    percent = float(m.group(1))
                    item.set_progress(int(percent))
                # Cherche le nom du fichier téléchargé
                if not filename:
                    m2 = re.search(r'Destination: (.+)', line)
                    if m2:
                        filename = m2.group(1).strip()
            proc.wait()
            item.set_cancel_enabled(False)
            item.set_progress(100)
            # Conversion en mp4 si possible (si vidéo et pas déjà mp4)
            if is_video and filename and not filename.lower().endswith('.mp4'):
                mp4_name = os.path.splitext(filename)[0] + '.mp4'
                try:
                    ffmpeg_cmd = [
                        'ffmpeg', '-y', '-i', filename, '-c:v', 'copy', '-c:a', 'copy', mp4_name
                    ]
                    subprocess.run(ffmpeg_cmd, check=True)
                    # Optionnel : supprimer l'ancien fichier si conversion réussie
                    if os.path.exists(mp4_name):
                        os.remove(filename)
                except Exception as e:
                    QMessageBox.warning(self, 'Conversion mp4', f'Impossible de convertir en mp4 : {e}')
        except Exception as e:
            QMessageBox.critical(self, 'Erreur', f'Erreur pour {link} : {e}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
