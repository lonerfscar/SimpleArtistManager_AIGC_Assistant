import os
import PyInstaller.__main__
import shutil
import sys


def package_application():
    # 1. 清理之前的打包结果
    build_dir = "build"
    dist_dir = "dist"
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)

    # 2. 设置打包参数
    script = "main.py"
    app_name = "ArtistManager"
    icon = "app_icon.ico"  # 替换为您的图标文件路径

    # 3. 执行打包
    PyInstaller.__main__.run([
        script,
        '--name=%s' % app_name,
        '--onefile',
        '--windowed',
        '--icon=%s' % icon,
        '--add-data=artist_images;artist_images',  # 包含图片目录
        '--add-data=artists.db;.',  # 包含数据库文件
        '--add-data=app_icon.ico;.',  # 包含图标文件
        '--add-data=app_icon.ico;.',  # 再次包含图标文件，确保在打包环境中可用
    ])

    # 4. 复制必要的文件到dist目录
    dist_app_dir = os.path.join(dist_dir, app_name)

    # 创建必要的目录
    artist_images_dir = os.path.join(dist_app_dir, "artist_images")
    os.makedirs(artist_images_dir, exist_ok=True)

    # 复制数据库文件（如果不存在）
    db_dest = os.path.join(dist_app_dir, "artists.db")
    if not os.path.exists(db_dest):
        shutil.copy("artists.db", db_dest)

    # 复制图标文件
    shutil.copy(icon, dist_app_dir)

    print(f"打包完成！应用程序位于: {dist_app_dir}")


if __name__ == "__main__":
    package_application()
