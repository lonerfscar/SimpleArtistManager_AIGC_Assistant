import sys
import os
import sqlite3
import shutil
import glob
import uuid
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QAbstractItemView,
    QHeaderView, QSizePolicy, QLineEdit, QMenu, QAction, QDialog, QGridLayout,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QSize, QMimeData, QPoint, QEvent, QTimer, QUrl
from PyQt5.QtGui import QPixmap, QImage, QIcon, QDrag, QKeyEvent, QClipboard, QMouseEvent, QPainter, QColor, QDesktopServices


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

    # 数据库路径 - 相对于可执行文件位置
    db_path = os.path.join(BASE_DIR, "artists.db")

    return db_path, image_dir


# 初始化目录和路径
DATABASE_NAME, IMAGE_DIR = ensure_directories()


class ImageDisplayWidget(QLabel):
    """只用于展示图片的控件，不支持上传操作"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ddd; background-color: #f8f8f8;")
        self.setFixedSize(80, 80)
        self.image_path = None

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
            pixmap = QPixmap(self.image_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(pixmap)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.clear()
            self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        """双击查看大图"""
        if self.image_path and os.path.exists(self.image_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.image_path))
        super().mouseDoubleClickEvent(event)


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

    def create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row_id TEXT UNIQUE,  -- 唯一行ID
            artist_id TEXT,
            common_name TEXT,
            introduction TEXT,
            image_paths TEXT,
            notes TEXT
        )
        """)
        self.conn.commit()

    def add_artist(self, data):
        self.cursor.execute("""
        INSERT INTO artists (row_id, artist_id, common_name, introduction, image_paths, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()
        return self.cursor.lastrowid

    def update_artist(self, row_id, data):
        self.cursor.execute("""
        UPDATE artists
        SET artist_id=?, common_name=?, introduction=?, image_paths=?, notes=?
        WHERE row_id=?
        """, (*data, row_id))
        self.conn.commit()

    def delete_artist(self, row_id):
        self.cursor.execute("DELETE FROM artists WHERE row_id=?", (row_id,))
        self.conn.commit()

    def get_all_artists(self):
        self.cursor.execute("""
        SELECT row_id, artist_id, common_name, introduction, image_paths, notes
        FROM artists
        ORDER BY id
        """)
        return self.cursor.fetchall()

    def import_from_txt(self, file_path):
        """从TXT文件导入数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 跳过标题行
                headers = f.readline().strip().split('\t')

                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) < 4:  # 现在有4列数据
                        continue

                    artist_id = parts[0]
                    common_name = parts[1]
                    introduction = parts[2]
                    notes = parts[3]

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
                    INSERT INTO artists (row_id, artist_id, common_name, introduction, image_paths, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (row_id, artist_id, common_name, introduction, ";".join(p for p in image_paths if p), notes))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"导入失败: {e}")
            return False


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

        # 筛选区域
        filter_layout = QHBoxLayout()
        self.id_filter = QLineEdit()
        self.id_filter.setPlaceholderText("画师ID筛选")
        self.id_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("ID筛选:"))
        filter_layout.addWidget(self.id_filter)

        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("常用名筛选")
        self.name_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("名称筛选:"))
        filter_layout.addWidget(self.name_filter)

        main_layout.addLayout(filter_layout)

        # 表格设置
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["画师ID", "常用名", "简介", "作品展示", "备注", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(3, 260)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(5, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.table.itemChanged.connect(self.handle_text_edit)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # 设置行高
        self.table.verticalHeader().setDefaultSectionSize(100)

        # 启用列排序
        self.table.setSortingEnabled(True)

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

        main_layout.addLayout(btn_layout)

    def load_data(self):
        artists = self.db.get_all_artists()
        self.table.setRowCount(len(artists))
        self.row_id_map.clear()

        for row_idx, artist in enumerate(artists):
            row_id, artist_id, common_name, intro, image_paths, notes = artist
            paths = image_paths.split(';') if image_paths else []

            # 存储行ID到行索引的映射
            self.row_id_map[row_id] = row_idx

            # 画师ID - 不可编辑
            id_item = QTableWidgetItem(artist_id)
            id_item.setData(Qt.UserRole, row_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row_idx, 0, id_item)

            # 常用名
            name_item = QTableWidgetItem(common_name)
            self.table.setItem(row_idx, 1, name_item)

            # 简介
            intro_item = QTableWidgetItem(intro)
            intro_item.setFlags(intro_item.flags() | Qt.TextEditable)
            self.table.setItem(row_idx, 2, intro_item)

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

            self.table.setCellWidget(row_idx, 3, img_container)

            # 备注
            notes_item = QTableWidgetItem(notes)
            notes_item.setFlags(notes_item.flags() | Qt.TextEditable)
            self.table.setItem(row_idx, 4, notes_item)

            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(5, 5, 5, 5)

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedHeight(35)
            edit_btn.clicked.connect(lambda _, id=row_id: self.edit_row_by_id(id))

            delete_btn = QPushButton("删除")
            delete_btn.setFixedHeight(35)
            delete_btn.clicked.connect(lambda _, id=row_id: self.delete_row_by_id(id))

            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 5, btn_widget)

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

        # 简介输入
        intro_layout = QVBoxLayout()
        intro_layout.addWidget(QLabel("简介:"))
        intro_edit = QLineEdit()
        intro_layout.addWidget(intro_edit)

        # 图片上传 - 使用可编辑的上传控件
        img_layout = QVBoxLayout()
        img_layout.addWidget(QLabel("作品展示:"))
        img_edit = ImageUploadWidget()
        img_layout.addWidget(img_edit)

        # 备注输入
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(QLabel("备注:"))
        notes_edit = QLineEdit()
        notes_layout.addWidget(notes_edit)

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

            intro = intro_edit.text()
            notes = notes_edit.text()

            # 检查图片文件夹中是否存在符合命名规则的图片
            existing_images = self.find_existing_images(artist_id)
            if existing_images:
                img_edit.setImages(existing_images)

            # 重命名图片
            renamed_paths = img_edit.renameImages(artist_id)
            image_paths = ";".join(p for p in renamed_paths if p)

            # 生成唯一行ID
            row_id = str(uuid.uuid4())

            # 保存到数据库
            self.db.add_artist((row_id, artist_id, common_name, intro, image_paths, notes))

            # 添加到表格
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            # 存储行ID到行索引的映射
            self.row_id_map[row_id] = row_idx

            # 画师ID - 不可编辑
            id_item = QTableWidgetItem(artist_id)
            id_item.setData(Qt.UserRole, row_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row_idx, 0, id_item)

            # 常用名
            self.table.setItem(row_idx, 1, QTableWidgetItem(common_name))

            # 简介
            intro_item = QTableWidgetItem(intro)
            intro_item.setFlags(intro_item.flags() | Qt.TextEditable)
            self.table.setItem(row_idx, 2, intro_item)

            # 作品展示 - 使用只读的图片展示控件
            img_container = QWidget()
            img_layout = QHBoxLayout(img_container)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.setSpacing(5)

            for i in range(3):
                img_widget = ImageDisplayWidget()
                path = renamed_paths[i] if i < len(renamed_paths) else None
                img_widget.setImage(path)
                img_layout.addWidget(img_widget)

            self.table.setCellWidget(row_idx, 3, img_container)

            # 备注
            notes_item = QTableWidgetItem(notes)
            notes_item.setFlags(notes_item.flags() | Qt.TextEditable)
            self.table.setItem(row_idx, 4, notes_item)

            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(5, 5, 5, 5)

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedHeight(35)
            edit_btn.clicked.connect(lambda _, id=row_id: self.edit_row_by_id(id))

            delete_btn = QPushButton("删除")
            delete_btn.setFixedHeight(35)
            delete_btn.clicked.connect(lambda _, id=row_id: self.delete_row_by_id(id))

            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(delete_btn)
            self.table.setCellWidget(row_idx, 5, btn_widget)

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

    def edit_row_by_id(self, row_id):
        """根据行ID编辑行"""
        row_idx = self.get_row_index_by_id(row_id)
        if row_idx == -1:
            return

        # 创建编辑对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑记录")
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)

        # 获取当前数据
        artist_id = self.table.item(row_idx, 0).text()
        common_name = self.table.item(row_idx, 1).text()
        intro = self.table.item(row_idx, 2).text()
        notes = self.table.item(row_idx, 4).text()

        # 获取图片路径
        image_paths = []
        img_container = self.table.cellWidget(row_idx, 3)
        if img_container and img_container.layout():
            for i in range(img_container.layout().count()):
                widget = img_container.layout().itemAt(i).widget()
                if isinstance(widget, ImageDisplayWidget) and widget.image_path:
                    # 存储相对路径
                    if os.path.isabs(widget.image_path):
                        rel_path = os.path.relpath(widget.image_path, IMAGE_DIR)
                        image_paths.append(rel_path)
                    else:
                        image_paths.append(widget.image_path)

        # ID输入
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("画师ID:"))
        id_edit = QLineEdit(artist_id)
        id_layout.addWidget(id_edit)

        # 名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("常用名:"))
        name_edit = QLineEdit(common_name)
        name_layout.addWidget(name_edit)

        # 简介输入
        intro_layout = QVBoxLayout()
        intro_layout.addWidget(QLabel("简介:"))
        intro_edit = QLineEdit(intro)
        intro_layout.addWidget(intro_edit)

        # 图片上传 - 使用可编辑的上传控件
        img_layout = QVBoxLayout()
        img_layout.addWidget(QLabel("作品展示:"))
        img_edit = ImageUploadWidget()
        img_edit.setImages(image_paths)
        img_layout.addWidget(img_edit)

        # 备注输入
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(QLabel("备注:"))
        notes_edit = QLineEdit(notes)
        notes_layout.addWidget(notes_edit)

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
        layout.addLayout(btn_layout)

        # 按钮事件
        def save_data():
            new_id = id_edit.text().strip()
            new_name = name_edit.text().strip()

            if not new_id or not new_name:
                QMessageBox.warning(dialog, "错误", "画师ID和常用名不能为空")
                return

            # 更新图片并重命名
            renamed_paths = img_edit.renameImages(new_id)

            # 更新表格数据
            self.table.item(row_idx, 0).setText(new_id)
            self.table.item(row_idx, 1).setText(new_name)
            self.table.item(row_idx, 2).setText(intro_edit.text())
            self.table.item(row_idx, 4).setText(notes_edit.text())

            # 更新图片展示
            img_container = QWidget()
            img_layout = QHBoxLayout(img_container)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.setSpacing(5)

            for i in range(3):
                img_widget = ImageDisplayWidget()
                path = renamed_paths[i] if i < len(renamed_paths) else None
                img_widget.setImage(path)
                img_layout.addWidget(img_widget)

            self.table.setCellWidget(row_idx, 3, img_container)

            # 更新数据库
            image_paths_str = ";".join(p for p in renamed_paths if p)
            self.db.update_artist(row_id, (
                new_id,
                new_name,
                intro_edit.text(),
                image_paths_str,
                notes_edit.text()
            ))

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
            del self.row_id_map[row_id]

            # 更新映射中的行索引
            for id, idx in self.row_id_map.items():
                if idx > row_idx:
                    self.row_id_map[id] = idx - 1

    def handle_text_edit(self, item):
        """处理文字编辑（双击格子编辑后保存）"""
        # 获取行和列
        row = item.row()
        col = item.column()

        # 只处理可编辑的列（1,2,4）
        if col not in [1, 2, 4]:
            return

        # 获取行ID
        row_id_item = self.table.item(row, 0)
        if not row_id_item:
            return
        row_id = row_id_item.data(Qt.UserRole)
        if not row_id:
            return

        # 获取该行的所有数据
        artist_id = self.table.item(row, 0).text() if self.table.item(row, 0) else ""

        common_name_item = self.table.item(row, 1)
        common_name = common_name_item.text() if common_name_item else ""

        intro_item = self.table.item(row, 2)
        intro = intro_item.text() if intro_item else ""

        notes_item = self.table.item(row, 4)
        notes = notes_item.text() if notes_item else ""

        # 图片路径
        image_paths = []
        img_container = self.table.cellWidget(row, 3)
        if img_container and img_container.layout():
            for i in range(img_container.layout().count()):
                widget = img_container.layout().itemAt(i).widget()
                if isinstance(widget, ImageDisplayWidget) and widget.image_path:
                    # 存储相对路径
                    if os.path.isabs(widget.image_path):
                        rel_path = os.path.relpath(widget.image_path, IMAGE_DIR)
                        image_paths.append(rel_path)
                    else:
                        image_paths.append(widget.image_path)
        image_paths_str = ";".join(p for p in image_paths if p)

        # 更新数据库
        self.db.update_artist(row_id, (
            artist_id,
            common_name,
            intro,
            image_paths_str,
            notes
        ))

    def apply_filters(self):
        id_filter = self.id_filter.text().lower()
        name_filter = self.name_filter.text().lower()

        for row in range(self.table.rowCount()):
            artist_id_item = self.table.item(row, 0)
            common_name_item = self.table.item(row, 1)

            artist_id = artist_id_item.text().lower() if artist_id_item else ""
            common_name = common_name_item.text().lower() if common_name_item else ""

            id_match = id_filter in artist_id if id_filter else True
            name_match = name_filter in common_name if name_filter else True

            self.table.setRowHidden(row, not (id_match and name_match))

    def export_data(self):
        file, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "", "文本文件 (*.txt)"
        )

        if not file:
            return

        try:
            with open(file, 'w', encoding='utf-8') as f:
                # 写入表头
                headers = ["画师ID", "常用名", "简介", "备注"]
                f.write("\t".join(headers) + "\n")

                # 写入数据
                for row in range(self.table.rowCount()):
                    if not self.table.isRowHidden(row):
                        artist_id = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
                        common_name = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                        intro = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                        notes = self.table.item(row, 4).text() if self.table.item(row, 4) else ""

                        row_data = [
                            artist_id,
                            common_name,
                            intro,
                            notes
                        ]
                        f.write("\t".join(row_data) + "\n")

            QMessageBox.information(self, "导出成功", "数据已成功导出")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中出错: {str(e)}")

    def import_data(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "文本文件 (*.txt)"
        )

        if not file:
            return

        reply = QMessageBox.question(
            self, "确认导入",
            "导入数据将覆盖现有数据，是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        # 清空当前表格
        self.table.setRowCount(0)
        self.row_id_map.clear()

        # 导入数据
        if self.db.import_from_txt(file):
            QMessageBox.information(self, "导入成功", "数据导入成功")
            self.load_data()
        else:
            QMessageBox.critical(self, "导入失败", "导入过程中出错")

    def show_context_menu(self, position):
        menu = QMenu()
        row = self.table.rowAt(position.y())

        if row >= 0:
            # 获取行ID
            row_id_item = self.table.item(row, 0)
            if not row_id_item:
                return
            row_id = row_id_item.data(Qt.UserRole)

            # 查看图片选项
            img_container = self.table.cellWidget(row, 3)
            if img_container and img_container.layout():
                img_menu = menu.addMenu("查看图片")
                for i in range(img_container.layout().count()):
                    widget = img_container.layout().itemAt(i).widget()
                    if isinstance(widget, ImageDisplayWidget) and widget.image_path:
                        action = img_menu.addAction(f"图片 {i + 1}")
                        action.triggered.connect(lambda _, r=row, idx=i: self.view_image(r, idx))

            copy_id_action = QAction("复制画师ID", self)
            copy_id_action.triggered.connect(lambda: self.copy_to_clipboard(row, 0))
            menu.addAction(copy_id_action)

            copy_name_action = QAction("复制常用名", self)
            copy_name_action.triggered.connect(lambda: self.copy_to_clipboard(row, 1))
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
        img_container = self.table.cellWidget(row, 3)
        if img_container and img_container.layout():
            widget = img_container.layout().itemAt(index).widget()
            if isinstance(widget, ImageDisplayWidget) and widget.image_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(widget.image_path))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
