import subprocess
import sys
import os

def install_pip():
    try:
        import pip
    except ImportError:
        print("pip non trouvé, installation...")
        subprocess.check_call([sys.executable, '-m', 'ensurepip', '--upgrade'])
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])


def is_installed(package):
    try:
        import importlib.metadata
        importlib.metadata.version(package)
        return True
    except Exception:
        return False

def install_package(package):
    if is_installed(package):
        print(f"{package} déjà installé.")
        return
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        print(f"{package} installé avec succès.")
    except subprocess.CalledProcessError:
        print(f"Erreur lors de l'installation de {package}")

def installer_requirment():
    # Installation de pip si besoin
    install_pip()

    # Recherche le fichier requirment.txt dans le dossier du script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    req_path = os.path.join(script_dir, "requirment.txt")

    if os.path.exists(req_path):
        with open(req_path, encoding="utf-8") as f:
            packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        for pkg in packages:
            install_package(pkg)
        print("Vérification/installation de toutes les dépendances terminée !")
    else:
        print(f"Erreur : {req_path} non trouvé, aucune dépendance installée.")

    # Propose de créer un raccourci sur le bureau vers YoutubeDL.py (Windows uniquement)
    import platform
    popup_success = False
    if platform.system() == 'Windows':
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            import ctypes
            import time
            app = QApplication.instance() or QApplication([])
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            shortcut_path = os.path.join(desktop, 'YoutubeDL.lnk')
            script_path = os.path.join(script_dir, 'YoutubeDL.pyw')
            # Toujours demander à l'utilisateur, même si le raccourci existe déjà
            if os.path.exists(shortcut_path):
                msg = "Un raccourci YoutubeDL existe déjà sur le bureau. Voulez-vous le remplacer ?"
            else:
                msg = "Voulez-vous créer un raccourci sur le bureau pour YoutubeDL ?"
            rep = QMessageBox.question(None, 'Créer un raccourci ?', msg, QMessageBox.Yes | QMessageBox.No)
            if rep == QMessageBox.Yes and os.path.exists(script_path):
                try:
                    import pythoncom
                    from win32com.client import Dispatch
                    target = sys.executable
                    wDir = script_dir
                    icon = target
                    shell = Dispatch('WScript.Shell')
                    shortcut = shell.CreateShortCut(shortcut_path)
                    shortcut.Targetpath = target
                    shortcut.Arguments = f'"{script_path}"'
                    shortcut.WorkingDirectory = wDir
                    shortcut.IconLocation = icon
                    shortcut.save()
                    print(f"Raccourci créé : {shortcut_path}")
                except Exception as e:
                    print(f"Erreur lors de la création du raccourci : {e}")
            # Affiche le popup de succès à la fin
            QMessageBox.information(None, 'Installation terminée', "Toutes les dépendances ont été installées avec succès !")
            popup_success = True
        except Exception as e:
            print(f"Erreur PySide6 ou création raccourci : {e}")
    # Si pas Windows ou si PySide6 non dispo, affiche un print
    if not popup_success:
        print("Toutes les dépendances ont été installées avec succès !")

if __name__ == "__main__":
    installer_requirment()
