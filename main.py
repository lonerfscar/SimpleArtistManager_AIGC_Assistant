import sys
import os
import sqlite3
import shutil
import glob
import uuid
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QAbstractItemView,
    QHeaderView, QSizePolicy, QLineEdit, QMenu, QAction, QDialog, QGridLayout,
    QScrollArea, QTextEdit, QCheckBox, QProgressDialog
)
from PyQt5.QtCore import Qt, QSize, QMimeData, QPoint, QEvent, QTimer, QUrl, QThread, pyqtSignal, QRect
from PyQt5.QtGui import QPixmap, QImage, QIcon, QDrag, QKeyEvent, QClipboard, QMouseEvent, QPainter, QColor, \
    QDesktopServices, QTextCursor, QRegion


def resource_path(relative_path):
    """获取资源的绝对路径。在打包后，资源位于临时目录中；在开发环境中，则位于当前目录。"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_app_base_dir():
    """获取应用程序所在的基础目录"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))


# 获取基础目录
BASE_DIR = get_app_base_dir()


# 创建必要的目录
def ensure_directories():
    """确保必要的目录存在"""
    # 图片目录 - 相对于可执行文件位置
    image_dir = os.path.join(BASE_DIR, "artist_images")
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    # 缩略图目录
    thumb_dir = os.path.join(BASE_DIR, "artist_thumbs")
    if not os.path.exists(thumb_dir):
        os.makedirs(thumb_dir)

    # 数据库路径 - 相对于可执行文件位置
    db_path = os.path.join(BASE_DIR, "artists.db")

    return db_path, image_dir, thumb_dir


# 初始化目录和路径
DATABASE_NAME, IMAGE_DIR, THUMB_DIR = ensure_directories()


class ThumbnailGenerator(QThread):
    """缩略图生成线程"""
    finished = pyqtSignal(str, bool)  # 原图路径, 是否成功

    def __init__(self, src_path, dest_path, size=(300, 300), parent=None):
        super().__init__(parent)
        self.src_path = src_path
        self.dest_path = dest_path
        self.size = size

    def run(self):
        try:
            image = QImage(self.src_path)
            if not image.isNull():
                # 计算保持比例的缩放尺寸
                scaled = image.scaled(self.size[0], self.size[1],
                                      Qt.KeepAspectRatio, Qt.SmoothTransformation)
                scaled.save(self.dest_path)
                self.finished.emit(self.src_path, True)
                return
        except Exception as e:
            print(f"缩略图生成失败: {e}")
        self.finished.emit(self.src_path, False)


class PlainTextEdit(QTextEdit):
    """纯文本编辑框，粘贴时去除格式"""

    def insertFromMimeData(self, source):
        if source.hasText():
            # 获取纯文本
            text = source.text()
            # 插入纯文本
            self.textCursor().insertText(text)
        else:
            super().insertFromMimeData(source)


class ImageDisplayWidget(QLabel):
    """只用于展示图片的控件，支持缩略图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ddd; background-color: #f8f8f8;")
        self.setFixedSize(80, 80)
        self.image_path = None
        self.thread = None

    def setImage(self, path):
        # 使用相对路径或修正的绝对路径
        if path and not os.path.isabs(path):
            # 如果是相对路径，转换为相对于应用目录的绝对路径
            abs_path = os.path.join(IMAGE_DIR, path)
            if os.path.exists(abs_path):
                self.image_path = abs_path
            else:
                self.image_path = None
        else:
            # 如果是绝对路径，直接使用
            self.image_path = path if (path and os.path.exists(path)) else None

        if self.image_path:
            # 获取缩略图路径
            thumb_path = self.get_thumbnail_path(self.image_path)

            if os.path.exists(thumb_path):
                # 直接加载现有缩略图
                pixmap = QPixmap(thumb_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(pixmap)
                self.setCursor(Qt.PointingHandCursor)
            else:
                # 显示加载占位符
                self.set_placeholder("加载中...")

                # 启动线程生成缩略图
                self.thread = ThumbnailGenerator(self.image_path, thumb_path)
                self.thread.finished.connect(self.on_thumbnail_generated)
                self.thread.start()
        else:
            self.clear()
            self.setCursor(Qt.ArrowCursor)

    def set_placeholder(self, text):
        """显示加载占位符"""
        pixmap = QPixmap(80, 80)
        pixmap.fill(QColor(240, 240, 240))
        painter = QPainter(pixmap)
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(QRect(0, 0, 80, 80), Qt.AlignCenter, text)
        painter.end()
        self.setPixmap(pixmap)

    def on_thumbnail_generated(self, src_path, success):
        """缩略图生成完成回调"""
        if src_path == self.image_path:  # 确保当前显示的仍是同一图片
            if success:
                thumb_path = self.get_thumbnail_path(src_path)
                pixmap = QPixmap(thumb_path).scaled(80, 80,
                                                    Qt.KeepAspectRatio,
                                                    Qt.SmoothTransformation)
                self.setPixmap(pixmap)
                self.setCursor(Qt.PointingHandCursor)
            else:
                # 生成失败时尝试直接加载原图（小尺寸）
                try:
                    pixmap = QPixmap(src_path).scaled(80, 80,
                                                      Qt.KeepAspectRatio,
                                                      Qt.SmoothTransformation)
                    self.setPixmap(pixmap)
                    self.setCursor(Qt.PointingHandCursor)
                except:
                    self.set_placeholder("加载失败")

    def get_thumbnail_path(self, original_path):
        """生成缩略图路径"""
        if not original_path:
            return ""

        # 获取文件名和扩展名
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)

        # 缩略图保存在单独的缩略图目录
        return os.path.join(THUMB_DIR, f"{name}_thumb{ext}")

    def mouseDoubleClickEvent(self, event):
        """双击查看大图"""
        if self.image_path and os.path.exists(self.image_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.image_path))
        super().mouseDoubleClickEvent(event)

    def update_image(self):
        """强制刷新当前图片"""
        if self.image_path:
            # 删除旧缩略图
            thumb_path = self.get_thumbnail_path(self.image_path)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

            # 重新生成并显示
            self.setImage(self.image_path)


class ImageUploadWidget(QWidget):
    """用于编辑界面的图片上传控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(180, 120)
        self.images = []
        self.selected_index = -1
        self.setFocusPolicy(Qt.StrongFocus)
        self.initUI()

    def initUI(self):
        layout = QGridLayout()
        layout.setSpacing(5)
        self.setLayout(layout)
        self.image_labels = [QLabel() for _ in range(3)]

        for i, label in enumerate(self.image_labels):
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("border: 1px dashed #aaa; background-color: #f8f8f8;")
            label.setFixedSize(80, 80)
            layout.addWidget(label, 0, i)

            # 自定义鼠标点击事件
            label.mousePressEvent = lambda e, idx=i: self.select_image(idx)

            # 添加双击查看大图功能
            label.mouseDoubleClickEvent = lambda e, idx=i: self.showFullImage(idx)

    def select_image(self, index):
        """选择图片区域"""
        self.selected_index = index
        self.update_selection_style()

        # 设置焦点以便接收粘贴事件
        self.setFocus()

    def update_selection_style(self):
        """更新选中样式"""
        for i, label in enumerate(self.image_labels):
            if i == self.selected_index:
                label.setStyleSheet("border: 2px solid #0078D7; background-color: #e6f2ff;")
            else:
                if i < len(self.images) and self.images[i]:
                    label.setStyleSheet("border: 1px solid #ddd;")
                else:
                    label.setStyleSheet("border: 1px dashed #aaa; background-color: #f8f8f8;")

    def mousePressEvent(self, event):
        """点击空白区域取消选中"""
        # 检查是否点击在图片标签上
        clicked_on_label = False
        for label in self.image_labels:
            if label.geometry().contains(event.pos()):
                clicked_on_label = True
                break

        # 如果点击在空白区域，取消选中
        if not clicked_on_label:
            self.selected_index = -1
            self.update_selection_style()

        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            # 计算鼠标位置对应的格子索引
            pos = event.pos()
            index = -1
            for i, label in enumerate(self.image_labels):
                if label.geometry().contains(pos):
                    index = i
                    break

            # 如果找到格子，自动选中并添加图片
            if index >= 0:
                self.select_image(index)
                file = urls[0].toLocalFile()
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    self.addImage(file)

        event.acceptProposedAction()

    def keyPressEvent(self, event):
        # 处理Ctrl+V粘贴
        if event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            self.pasteImage()
        # 处理Delete键删除选中图片
        elif event.key() == Qt.Key_Delete and self.selected_index >= 0:
            self.delete_selected_image()
        else:
            super().keyPressEvent(event)

    def pasteImage(self):
        if self.selected_index < 0:
            return

        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            # 从剪贴板获取图片
            image = clipboard.image()
            if not image.isNull():
                # 确保图片目录存在
                os.makedirs(IMAGE_DIR, exist_ok=True)

                # 保存图片到本地
                filename = f"temp_{os.urandom(4).hex()}.png"
                save_path = os.path.join(IMAGE_DIR, filename)
                image.save(save_path)
                self.addImage(save_path)
        elif mime_data.hasUrls():
            # 处理从文件管理器复制的图片文件
            for url in mime_data.urls():
                if url.isLocalFile():
                    file = url.toLocalFile()
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        self.addImage(file)
                        break

    def addImage(self, file_path):
        if self.selected_index < 0:
            return

        # 如果该位置已有图片，先移除
        if self.selected_index < len(self.images):
            # 如果已有图片是临时文件，删除它
            if self.images[self.selected_index] and os.path.basename(self.images[self.selected_index]).startswith(
                    "temp_"):
                try:
                    # 只删除临时文件
                    if os.path.exists(self.images[self.selected_index]):
                        os.remove(self.images[self.selected_index])
                except:
                    pass
            self.images[self.selected_index] = file_path
        else:
            # 确保有足够的空间
            while len(self.images) < 3 and len(self.images) <= self.selected_index:
                self.images.append(None)
            self.images[self.selected_index] = file_path

        self.updateDisplay()

    def delete_selected_image(self):
        """删除当前选中的图片"""
        if self.selected_index < len(self.images) and self.images[self.selected_index]:
            # 如果是临时文件，删除文件
            if os.path.basename(self.images[self.selected_index]).startswith("temp_"):
                try:
                    os.remove(self.images[self.selected_index])
                except:
                    pass

            # 删除图片
            self.images[self.selected_index] = None
            self.updateDisplay()

    def updateDisplay(self):
        for i in range(3):
            if i < len(self.images) and self.images[i]:
                try:
                    # 检查文件是否存在
                    if os.path.exists(self.images[i]):
                        # 显示缩略图
                        thumb_path = self.get_thumbnail_path(self.images[i])
                        if os.path.exists(thumb_path):
                            pixmap = QPixmap(thumb_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        else:
                            # 生成临时缩略图用于显示
                            pixmap = QPixmap(self.images[i]).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.image_labels[i].setPixmap(pixmap)
                        # 设置鼠标指针为手型，表示可点击
                        self.image_labels[i].setCursor(Qt.PointingHandCursor)
                    else:
                        # 文件不存在，清除显示
                        self.image_labels[i].clear()
                        self.image_labels[i].setCursor(Qt.ArrowCursor)
                        self.images[i] = None
                except Exception as e:
                    print(f"加载图片错误: {e}")
                    self.image_labels[i].clear()
                    self.image_labels[i].setCursor(Qt.ArrowCursor)
                    self.images[i] = None
            else:
                self.image_labels[i].clear()
                self.image_labels[i].setCursor(Qt.ArrowCursor)

        self.update_selection_style()

    def get_thumbnail_path(self, original_path):
        """获取缩略图路径"""
        if not original_path:
            return ""

        # 获取文件名和扩展名
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)

        # 缩略图保存在单独的缩略图目录
        return os.path.join(THUMB_DIR, f"{name}_thumb{ext}")

    def showFullImage(self, index):
        if index < len(self.images) and self.images[index]:
            try:
                if os.path.exists(self.images[index]):
                    # 使用系统默认程序打开图片
                    QDesktopServices.openUrl(QUrl.fromLocalFile(self.images[index]))
                else:
                    QMessageBox.warning(self, "错误", "图片文件不存在")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"打开图片失败: {str(e)}")

    def getImagePaths(self):
        """获取有效的图片路径"""
        valid_paths = []
        for path in self.images:
            if path and os.path.exists(path):
                # 存储相对路径
                if os.path.isabs(path) and path.startswith(IMAGE_DIR):
                    rel_path = os.path.relpath(path, IMAGE_DIR)
                    valid_paths.append(rel_path)
                else:
                    valid_paths.append(path)
            else:
                valid_paths.append(None)
        return valid_paths

    def setImages(self, paths):
        """设置图片路径，只保留有效的路径"""
        self.images = []
        for path in paths:
            if path:
                # 如果是相对路径，转换为绝对路径
                if not os.path.isabs(path):
                    abs_path = os.path.join(IMAGE_DIR, path)
                    if os.path.exists(abs_path):
                        self.images.append(abs_path)
                    else:
                        self.images.append(None)
                elif os.path.exists(path):
                    self.images.append(path)
                else:
                    self.images.append(None)
            else:
                self.images.append(None)
        self.updateDisplay()

    def renameImages(self, artist_id):
        """重命名图片为画师ID格式，并确保文件在正确的位置"""
        if not artist_id:
            return self.images

        new_paths = []
        os.makedirs(IMAGE_DIR, exist_ok=True)

        for i, path in enumerate(self.images):
            if not path or not os.path.exists(path):
                new_paths.append(None)
                continue

            # 获取文件扩展名
            ext = os.path.splitext(path)[1].lower()
            # 新文件名
            new_filename = f"{artist_id}-{i + 1}{ext}"
            new_path = os.path.join(IMAGE_DIR, new_filename)

            try:
                # 如果文件已经在正确位置，不需要移动
                if os.path.normpath(path) == os.path.normpath(new_path):
                    new_paths.append(new_filename)
                    continue

                # 复制文件到新位置
                shutil.copy2(path, new_path)
                new_paths.append(new_filename)

                # 如果源文件是临时文件，删除它
                if os.path.basename(path).startswith("temp_"):
                    try:
                        os.remove(path)
                    except:
                        pass

                # 删除旧的缩略图
                thumb_path = self.get_thumbnail_path(path)
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception as e:
                print(f"重命名图片失败: {e}")
                # 出错时保留原路径
                new_paths.append(os.path.basename(path))

        return new_paths


class DatabaseManager:
    def __init__(self):
        # 清理临时图片
        self.clean_temp_images()

        self.conn = sqlite3.connect(DATABASE_NAME)
        self.cursor = self.conn.cursor()
        self.create_table()

    def clean_temp_images(self):
        """清理未使用的临时图片"""
        os.makedirs(IMAGE_DIR, exist_ok=True)
        temp_files = glob.glob(os.path.join(IMAGE_DIR, "temp_*"))
        for file in temp_files:
            try:
                os.remove(file)
            except:
                pass

        # 清理缩略图目录
        os.makedirs(THUMB_DIR, exist_ok=True)
        thumb_files = glob.glob(os.path.join(THUMB_DIR, "*_thumb.*"))
        for file in thumb_files:
            try:
                os.remove(file)
            except:
                pass

    def create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row_id TEXT UNIQUE,  -- 唯一行ID
            artist_id TEXT,
            common_name TEXT,
            introduction TEXT,
            image_paths TEXT,
            notes TEXT,
            marked BOOLEAN DEFAULT 0  -- 新增标记列
        )
        """)
        self.conn.commit()

    def add_artist(self, data):
        self.cursor.execute("""
        INSERT INTO artists (row_id, artist_id, common_name, introduction, image_paths, notes, marked)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()
        return self.cursor.lastrowid

    def update_artist(self, row_id, data):
        self.cursor.execute("""
        UPDATE artists
        SET artist_id=?, common_name=?, introduction=?, image_paths=?, notes=?, marked=?
        WHERE row_id=?
        """, (*data, row_id))
        self.conn.commit()

    def delete_artist(self, row_id):
        self.cursor.execute("DELETE FROM artists WHERE row_id=?", (row_id,))
        self.conn.commit()

    def get_all_artists(self):
        self.cursor.execute("""
        SELECT id, row_id, artist_id, common_name, introduction, image_paths, notes, marked
        FROM artists
        ORDER BY id
        """)
        return self.cursor.fetchall()

    def get_artist_by_id(self, db_id):
        """根据数据库ID获取艺术家记录"""
        self.cursor.execute("""
        SELECT id, row_id, artist_id, common_name, introduction, image_paths, notes, marked
        FROM artists
        WHERE id = ?
        """, (db_id,))
        return self.cursor.fetchone()

    def get_prev_artist_id(self, current_id):
        """获取前一个记录的ID"""
        self.cursor.execute("""
        SELECT id FROM artists 
        WHERE id < ? 
        ORDER BY id DESC 
        LIMIT 1
        """, (current_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_next_artist_id(self, current_id):
        """获取下一个记录的ID"""
        self.cursor.execute("""
        SELECT id FROM artists 
        WHERE id > ? 
        ORDER BY id ASC 
        LIMIT 1
        """, (current_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def import_from_excel(self, file_path):
        """从Excel文件导入数据"""
        try:
            df = pd.read_excel(file_path)
            if df.empty:
                return False

            # 确保列名正确
            required_columns = ['画师ID', '常用名', '简介', '备注', '标记']
            if not all(col in df.columns for col in required_columns):
                return False

            for _, row in df.iterrows():
                artist_id = str(row['画师ID']) if pd.notna(row['画师ID']) else ""
                common_name = str(row['常用名']) if pd.notna(row['常用名']) else ""
                introduction = str(row['简介']) if pd.notna(row['简介']) else ""
                notes = str(row['备注']) if pd.notna(row['备注']) else ""
                marked = bool(row['标记']) if pd.notna(row['标记']) else False

                # 查找图片
                image_paths = []
                for i in range(1, 4):
                    possible_paths = [
                        os.path.join(IMAGE_DIR, f"{artist_id}-{i}.png"),
                        os.path.join(IMAGE_DIR, f"{artist_id}-{i}.jpg"),
                        os.path.join(IMAGE_DIR, f"{artist_id}-{i}.jpeg")
                    ]

                    found = False
                    for path in possible_paths:
                        if os.path.exists(path):
                            # 存储相对路径
                            rel_path = os.path.relpath(path, IMAGE_DIR)
                            image_paths.append(rel_path)
                            found = True
                            break

                    if not found:
                        image_paths.append(None)

                # 生成唯一行ID
                row_id = str(uuid.uuid4())

                # 添加到数据库
                self.cursor.execute("""
                INSERT INTO artists (row_id, artist_id, common_name, introduction, image_paths, notes, marked)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_id, artist_id, common_name, introduction, ";".join(p for p in image_paths if p), notes, marked))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"导入失败: {e}")
            return False


class EditArtistDialog(QDialog):
    """编辑画师对话框，添加了上一个/下一个功能"""

    def __init__(self, main_window, db_id, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.db_id = db_id
        self.setWindowTitle("编辑画师")
        self.setMinimumSize(700, 600)
        self.initUI()
        self.load_data()

    def initUI(self):
        layout = QVBoxLayout(self)

        # 所有字段初始化为空
        # ID输入
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("画师ID:"))
        self.id_edit = QLineEdit()
        id_layout.addWidget(self.id_edit)

        # 名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("常用名:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)

        # 简介输入 - 改为多行文本框
        intro_layout = QVBoxLayout()
        intro_layout.addWidget(QLabel("简介:"))
        self.intro_edit = PlainTextEdit()  # 使用纯文本编辑框
        self.intro_edit.setMinimumHeight(80)
        intro_layout.addWidget(self.intro_edit)

        # 图片上传 - 使用可编辑的上传控件
        img_layout = QVBoxLayout()
        img_layout.addWidget(QLabel("作品展示:"))
        self.img_edit = ImageUploadWidget()
        img_layout.addWidget(self.img_edit)

        # 备注输入 - 改为多行文本框
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(QLabel("备注:"))
        self.notes_edit = PlainTextEdit()  # 使用纯文本编辑框
        self.notes_edit.setMinimumHeight(80)
        notes_layout.addWidget(self.notes_edit)

        # 标记复选框
        mark_layout = QHBoxLayout()
        self.mark_checkbox = QCheckBox("标记")
        mark_layout.addWidget(self.mark_checkbox)
        mark_layout.addStretch()

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一个")
        self.prev_btn.setFixedHeight(40)
        self.prev_btn.clicked.connect(self.prev_artist)
        self.next_btn = QPushButton("下一个")
        self.next_btn.setFixedHeight(40)
        self.next_btn.clicked.connect(self.next_artist)

        self.save_btn = QPushButton("保存")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.save_data)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.cancel_edit)

        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.next_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        # 组装布局
        layout.addLayout(id_layout)
        layout.addLayout(name_layout)
        layout.addLayout(intro_layout)
        layout.addLayout(img_layout)
        layout.addLayout(notes_layout)
        layout.addLayout(mark_layout)
        layout.addLayout(btn_layout)

    def load_data(self):
        artist = self.main_window.db.get_artist_by_id(self.db_id)
        if artist:
            db_id, row_id, artist_id, common_name, intro, image_paths, notes, marked = artist
            paths = image_paths.split(';') if image_paths else []

            self.row_id = row_id
            self.id_edit.setText(artist_id)
            self.name_edit.setText(common_name)
            self.intro_edit.setPlainText(intro)
            self.notes_edit.setPlainText(notes)
            self.mark_checkbox.setChecked(bool(marked))
            self.img_edit.setImages(paths)

            # 更新按钮状态
            self.update_nav_buttons()

    def update_nav_buttons(self):
        """更新导航按钮状态"""
        # 检查是否有上一个记录
        prev_id = self.main_window.db.get_prev_artist_id(self.db_id)
        self.prev_btn.setEnabled(prev_id is not None)

        # 检查是否有下一个记录
        next_id = self.main_window.db.get_next_artist_id(self.db_id)
        self.next_btn.setEnabled(next_id is not None)

    def save_data(self):
        artist_id = self.id_edit.text().strip()
        common_name = self.name_edit.text().strip()

        if not artist_id or not common_name:
            QMessageBox.warning(self, "错误", "画师ID和常用名不能为空")
            return

        intro = self.intro_edit.toPlainText()
        notes = self.notes_edit.toPlainText()
        marked = 1 if self.mark_checkbox.isChecked() else 0

        # 重命名图片
        renamed_paths = self.img_edit.renameImages(artist_id)
        image_paths = ";".join(p for p in renamed_paths if p)

        # 更新数据库
        self.main_window.db.update_artist(self.row_id, (
            artist_id,
            common_name,
            intro,
            image_paths,
            notes,
            marked
        ))

        # 更新主界面
        self.main_window.load_data()
        self.accept()

    def cancel_edit(self):
        # 删除编辑过程中上传的临时图片
        for path in self.img_edit.getImagePaths():
            if path and os.path.basename(path).startswith("temp_"):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except:
                    pass
        self.reject()

    def prev_artist(self):
        """切换到上一个画师"""
        # 先保存当前编辑
        self.save_data()

        # 获取上一个画师的ID
        prev_id = self.main_window.db.get_prev_artist_id(self.db_id)
        if prev_id:
            # 关闭当前对话框
            self.accept()
            # 打开上一个画师的编辑对话框
            self.main_window.edit_row_by_db_id(prev_id)

    def next_artist(self):
        """切换到下一个画师"""
        # 先保存当前编辑
        self.save_data()

        # 获取下一个画师的ID
        next_id = self.main_window.db.get_next_artist_id(self.db_id)
        if next_id:
            # 关闭当前对话框
            self.accept()
            # 打开下一个画师的编辑对话框
            self.main_window.edit_row_by_db_id(next_id)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画师资料管理器")
        self.setGeometry(100, 100, 1200, 700)

        # 设置窗口图标
        try:
            icon_path = resource_path("app_icon.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"设置图标失败: {e}")

        self.db = DatabaseManager()
        # 存储行ID到行索引的映射
        self.row_id_map = {}
        self.initUI()
        self.load_data()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 筛选区域 - 改为单行搜索框
        filter_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索画师ID、常用名、简介、备注...")
        self.search_edit.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("搜索:"))
        filter_layout.addWidget(self.search_edit)

        main_layout.addLayout(filter_layout)

        # 表格设置
        self.table = QTableWidget()
        self.table.setColumnCount(7)  # 增加标记列
        self.table.setHorizontalHeaderLabels(["标记", "画师ID", "常用名", "简介", "作品展示", "备注", "操作"])

        # 设置列宽
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 标记列
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # ID列
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 常用名列
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # 简介列
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)  # 图片列
        self.table.horizontalHeader().resizeSection(4, 260)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)  # 备注列
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)  # 操作列
        self.table.horizontalHeader().resizeSection(6, 140)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 完全禁用编辑
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # 启用Ctrl+C复制功能
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.table.installEventFilter(self)

        # 设置行高
        self.table.verticalHeader().setDefaultSectionSize(100)

        # 启用列排序
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_click)

        main_layout.addWidget(self.table)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加新画师")
        self.add_btn.clicked.connect(self.add_artist)
        btn_layout.addWidget(self.add_btn)

        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self.export_data)
        btn_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("导入数据")
        self.import_btn.clicked.connect(self.import_data)
        btn_layout.addWidget(self.import_btn)

        # 添加图片管理按钮
        self.scan_btn = QPushButton("扫描图片")
        self.scan_btn.clicked.connect(self.scan_missing_images)
        btn_layout.addWidget(self.scan_btn)

        self.refresh_btn = QPushButton("刷新图片")
        self.refresh_btn.clicked.connect(self.refresh_images)
        btn_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(btn_layout)

    def handle_header_click(self, logical_index):
        """处理表头点击排序事件"""
        # 排序完成后更新行ID映射
        QTimer.singleShot(100, self.update_row_id_map)

    def update_row_id_map(self):
        """更新行ID映射关系"""
        self.row_id_map.clear()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)  # 画师ID列
            if item:
                row_id = item.data(Qt.UserRole)
                if row_id:
                    self.row_id_map[row_id] = row

    def eventFilter(self, source, event):
        """处理Ctrl+C快捷键"""
        if event.type() == QEvent.KeyPress and source is self.table:
            if event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
                # 获取选中的行
                selected_rows = self.table.selectionModel().selectedRows(1)  # 第1列是画师ID列
                if selected_rows:
                    # 获取所有选中的画师ID
                    artist_ids = [self.table.item(row.row(), 1).text() for row in selected_rows]
                    # 复制到剪贴板
                    clipboard = QApplication.clipboard()
                    clipboard.setText("\n".join(artist_ids))
                    return True
        return super().eventFilter(source, event)

    def load_data(self):
        artists = self.db.get_all_artists()
        self.table.setRowCount(len(artists))
        self.row_id_map.clear()

        for row_idx, artist in enumerate(artists):
            db_id, row_id, artist_id, common_name, intro, image_paths, notes, marked = artist
            paths = image_paths.split(';') if image_paths else []

            # 存储行ID到行索引的映射
            self.row_id_map[row_id] = row_idx

            # 标记列 - 复选框
            mark_item = QTableWidgetItem()
            mark_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            mark_item.setCheckState(Qt.Checked if marked else Qt.Unchecked)
            mark_item.setData(Qt.UserRole, db_id)  # 存储数据库ID
            self.table.setItem(row_idx, 0, mark_item)

            # 画师ID - 不可编辑
            id_item = QTableWidgetItem(artist_id)
            id_item.setData(Qt.UserRole, row_id)  # 存储row_id
            id_item.setData(Qt.UserRole + 1, db_id)  # 存储数据库ID
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row_idx, 1, id_item)

            # 常用名
            name_item = QTableWidgetItem(common_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row_idx, 2, name_item)

            # 简介
            intro_item = QTableWidgetItem(intro)
            intro_item.setFlags(intro_item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row_idx, 3, intro_item)

            # 作品展示 - 使用只读的图片展示控件
            img_container = QWidget()
            img_layout = QHBoxLayout(img_container)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.setSpacing(5)

            for i in range(3):
                img_widget = ImageDisplayWidget()
                path = paths[i] if i < len(paths) else None
                img_widget.setImage(path)
                img_layout.addWidget(img_widget)

            self.table.setCellWidget(row_idx, 4, img_container)

            # 备注
            notes_item = QTableWidgetItem(notes)
            notes_item.setFlags(notes_item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row_idx, 5, notes_item)

            # 操作按钮 - 使用row_id确保正确绑定
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(5, 5, 5, 5)

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedHeight(35)
            # 使用lambda传递数据库ID
            edit_btn.clicked.connect(lambda _, id=db_id: self.edit_row_by_db_id(id))

            delete_btn = QPushButton("删除")
            delete_btn.setFixedHeight(35)
            # 使用lambda传递row_id而不是行索引
            delete_btn.clicked.connect(lambda _, id=row_id: self.delete_row_by_id(id))

            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 6, btn_widget)

    def add_artist(self):
        """添加新画师"""
        # 创建编辑对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("添加新画师")
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)

        # 所有字段初始化为空
        # ID输入
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("画师ID:"))
        id_edit = QLineEdit()
        id_layout.addWidget(id_edit)

        # 名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("常用名:"))
        name_edit = QLineEdit()
        name_layout.addWidget(name_edit)

        # 简介输入 - 改为多行文本框
        intro_layout = QVBoxLayout()
        intro_layout.addWidget(QLabel("简介:"))
        intro_edit = PlainTextEdit()  # 使用纯文本编辑框
        intro_edit.setMinimumHeight(80)
        intro_layout.addWidget(intro_edit)

        # 图片上传 - 使用可编辑的上传控件
        img_layout = QVBoxLayout()
        img_layout.addWidget(QLabel("作品展示:"))
        img_edit = ImageUploadWidget()
        img_layout.addWidget(img_edit)

        # 备注输入 - 改为多行文本框
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(QLabel("备注:"))
        notes_edit = PlainTextEdit()  # 使用纯文本编辑框
        notes_edit.setMinimumHeight(80)
        notes_layout.addWidget(notes_edit)

        # 标记复选框
        mark_layout = QHBoxLayout()
        mark_checkbox = QCheckBox("标记")
        mark_layout.addWidget(mark_checkbox)
        mark_layout.addStretch()

        # 按钮区域
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(40)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(40)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        # 组装布局
        layout.addLayout(id_layout)
        layout.addLayout(name_layout)
        layout.addLayout(intro_layout)
        layout.addLayout(img_layout)
        layout.addLayout(notes_layout)
        layout.addLayout(mark_layout)
        layout.addLayout(btn_layout)

        # 按钮事件
        def save_data():
            artist_id = id_edit.text().strip()
            common_name = name_edit.text().strip()

            # 如果只输入了画师ID，没有输入常用名，则常用名=画师ID
            if artist_id and not common_name:
                common_name = artist_id

            if not artist_id or not common_name:
                QMessageBox.warning(dialog, "错误", "画师ID和常用名不能为空")
                return

            intro = intro_edit.toPlainText()
            notes = notes_edit.toPlainText()
            marked = 1 if mark_checkbox.isChecked() else 0

            # 重命名图片
            renamed_paths = img_edit.renameImages(artist_id)
            image_paths = ";".join(p for p in renamed_paths if p)

            # 生成唯一行ID
            row_id = str(uuid.uuid4())

            # 保存到数据库
            self.db.add_artist((row_id, artist_id, common_name, intro, image_paths, notes, marked))

            # 添加到表格
            self.load_data()

            dialog.accept()

        def cancel_edit():
            # 删除编辑过程中上传的临时图片
            for path in img_edit.getImagePaths():
                if path and os.path.basename(path).startswith("temp_"):
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass
            dialog.reject()

        save_btn.clicked.connect(save_data)
        cancel_btn.clicked.connect(cancel_edit)

        dialog.exec_()

    def find_existing_images(self, artist_id):
        """查找图片文件夹中符合命名规则的图片"""
        if not artist_id:
            return []

        images = []
        for i in range(1, 4):
            possible_paths = [
                os.path.join(IMAGE_DIR, f"{artist_id}-{i}.png"),
                os.path.join(IMAGE_DIR, f"{artist_id}-{i}.jpg"),
                os.path.join(IMAGE_DIR, f"{artist_id}-{i}.jpeg")
            ]

            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    # 存储相对路径
                    rel_path = os.path.relpath(path, IMAGE_DIR)
                    images.append(rel_path)
                    found = True
                    break

            if not found:
                images.append(None)

        return images

    def get_row_index_by_id(self, row_id):
        """根据行ID获取当前行索引"""
        return self.row_id_map.get(row_id, -1)

    def edit_row_by_db_id(self, db_id):
        """根据数据库ID编辑行"""
        dialog = EditArtistDialog(self, db_id)
        dialog.exec_()

    def delete_row_by_id(self, row_id):
        """根据行ID删除行"""
        row_idx = self.get_row_index_by_id(row_id)
        if row_idx == -1:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这条记录吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 从数据库删除
            self.db.delete_artist(row_id)

            # 从表格删除
            self.table.removeRow(row_idx)

            # 从映射中删除
            if row_id in self.row_id_map:
                del self.row_id_map[row_id]

            # 更新映射中的行索引
            for id, idx in list(self.row_id_map.items()):
                if idx > row_idx:
                    self.row_id_map[id] = idx - 1

    def apply_filters(self):
        search_text = self.search_edit.text().lower()

        for row in range(self.table.rowCount()):
            # 获取各列内容
            artist_id = self.table.item(row, 1).text().lower() if self.table.item(row, 1) else ""
            common_name = self.table.item(row, 2).text().lower() if self.table.item(row, 2) else ""
            intro = self.table.item(row, 3).text().lower() if self.table.item(row, 3) else ""
            notes = self.table.item(row, 5).text().lower() if self.table.item(row, 5) else ""

            # 检查任意一列是否包含搜索文本
            match = (search_text in artist_id or
                     search_text in common_name or
                     search_text in intro or
                     search_text in notes)

            self.table.setRowHidden(row, not match)

    def export_data(self):
        file, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "", "Excel文件 (*.xlsx)"
        )

        if not file:
            return

        try:
            # 收集所有数据
            data = []
            for row in range(self.table.rowCount()):
                if not self.table.isRowHidden(row):
                    artist_id = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                    common_name = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                    intro = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
                    notes = self.table.item(row, 5).text() if self.table.item(row, 5) else ""
                    marked = self.table.item(row, 0).checkState() == Qt.Checked

                    data.append({
                        "画师ID": artist_id,
                        "常用名": common_name,
                        "简介": intro,
                        "备注": notes,
                        "标记": marked
                    })

            # 创建DataFrame并导出为Excel
            df = pd.DataFrame(data)
            df.to_excel(file, index=False)

            QMessageBox.information(self, "导出成功", "数据已成功导出为Excel文件")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中出错: {str(e)}")

    def import_data(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "Excel文件 (*.xlsx)"
        )

        if not file:
            return

        # 直接导入，不显示确认弹窗
        # 清空当前表格
        self.table.setRowCount(0)
        self.row_id_map.clear()

        # 导入数据
        if self.db.import_from_excel(file):
            self.load_data()
            QMessageBox.information(self, "导入成功", "数据导入成功")
        else:
            QMessageBox.critical(self, "导入失败", "导入过程中出错，请检查文件格式")

    def refresh_images(self):
        """刷新所有图片并重新生成缩略图"""
        reply = QMessageBox.question(
            self, "确认刷新",
            "这将重新生成所有缩略图，可能需要较长时间。继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 创建进度对话框
        progress = QProgressDialog("刷新图片中...", "取消", 0, self.table.rowCount(), self)
        progress.setWindowTitle("图片刷新")
        progress.setWindowModality(Qt.WindowModal)

        # 清理缩略图目录
        for thumb_file in glob.glob(os.path.join(THUMB_DIR, "*_thumb.*")):
            try:
                os.remove(thumb_file)
            except:
                pass

        # 重新生成所有缩略图
        for row in range(self.table.rowCount()):
            progress.setValue(row)
            QApplication.processEvents()  # 处理事件循环，避免界面冻结

            if progress.wasCanceled():
                break

            # 获取图片容器
            img_container = self.table.cellWidget(row, 4)
            if img_container and img_container.layout():
                for i in range(img_container.layout().count()):
                    widget = img_container.layout().itemAt(i).widget()
                    if isinstance(widget, ImageDisplayWidget):
                        widget.update_image()  # 强制刷新图片

        progress.setValue(self.table.rowCount())
        QMessageBox.information(self, "完成", "所有缩略图已重新生成")

    def scan_missing_images(self):
        """扫描缺失图片并尝试重新匹配"""
        missing_count = 0
        found_count = 0

        # 创建进度对话框
        progress = QProgressDialog("扫描图片中...", "取消", 0, self.table.rowCount(), self)
        progress.setWindowTitle("图片扫描")
        progress.setWindowModality(Qt.WindowModal)

        for row in range(self.table.rowCount()):
            progress.setValue(row)
            QApplication.processEvents()  # 处理事件循环，避免界面冻结

            if progress.wasCanceled():
                break

            artist_id = self.table.item(row, 1).text()
            if not artist_id:
                continue

            # 获取图片容器
            img_container = self.table.cellWidget(row, 4)
            if img_container and img_container.layout():
                for i in range(img_container.layout().count()):
                    widget = img_container.layout().itemAt(i).widget()
                    if isinstance(widget, ImageDisplayWidget):
                        if not widget.image_path or not os.path.exists(widget.image_path):
                            # 尝试查找匹配图片
                            possible_paths = [
                                os.path.join(IMAGE_DIR, f"{artist_id}-{i + 1}.png"),
                                os.path.join(IMAGE_DIR, f"{artist_id}-{i + 1}.jpg"),
                                os.path.join(IMAGE_DIR, f"{artist_id}-{i + 1}.jpeg")
                            ]

                            found = False
                            for path in possible_paths:
                                if os.path.exists(path):
                                    widget.setImage(path)
                                    found = True
                                    found_count += 1
                                    break

                            if not found:
                                missing_count += 1

        progress.setValue(self.table.rowCount())
        msg = f"扫描完成:\n找到 {found_count} 张图片\n缺失 {missing_count} 张图片"
        QMessageBox.information(self, "扫描结果", msg)

    def show_context_menu(self, position):
        menu = QMenu()
        row = self.table.rowAt(position.y())

        if row >= 0:
            # 查看图片选项
            img_container = self.table.cellWidget(row, 4)
            if img_container and img_container.layout():
                img_menu = menu.addMenu("查看图片")
                for i in range(img_container.layout().count()):
                    widget = img_container.layout().itemAt(i).widget()
                    if isinstance(widget, ImageDisplayWidget) and widget.image_path:
                        action = img_menu.addAction(f"图片 {i + 1}")
                        action.triggered.connect(lambda _, r=row, idx=i: self.view_image(r, idx))

            copy_id_action = QAction("复制画师ID", self)
            copy_id_action.triggered.connect(lambda: self.copy_to_clipboard(row, 1))  # 画师ID在第1列
            menu.addAction(copy_id_action)

            copy_name_action = QAction("复制常用名", self)
            copy_name_action.triggered.connect(lambda: self.copy_to_clipboard(row, 2))  # 常用名在第2列
            menu.addAction(copy_name_action)

            menu.addSeparator()

        menu.exec_(self.table.viewport().mapToGlobal(position))

    def copy_to_clipboard(self, row, column):
        item = self.table.item(row, column)
        if item:
            text = item.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def view_image(self, row, index):
        """查看指定行的图片"""
        img_container = self.table.cellWidget(row, 4)
        if img_container and img_container.layout():
            widget = img_container.layout().itemAt(index).widget()
            if isinstance(widget, ImageDisplayWidget) and widget.image_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(widget.image_path))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
