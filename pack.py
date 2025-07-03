import os
import PyInstaller.__main__
import shutil
import sys


def package_application():
    # 手动设置版本号
    version = "1.0.0"  # 直接在这里修改版本号

    # 1. 清理之前的打包结果
    build_dir = "build"
    dist_dir = "dist"
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)

    # 2. 创建版本文件
    version_file = "version.txt"
    with open(version_file, "w") as f:
        f.write(version)

    # 3. 设置打包参数
    script = "main.py"
    app_name = "ArtistManager"
    icon = "app_icon.ico"

    # 4. 执行打包 (新增版本文件参数)
    PyInstaller.__main__.run([
        script,
        '--name=%s' % app_name,
        '--onefile',
        '--windowed',
        '--icon=%s' % icon,
        f'--add-data={version_file};.',  # 包含版本文件
        '--add-data=app_icon.ico;.',
    ])

    # 5. 复制文件到dist目录
    dist_app_dir = os.path.join(dist_dir, app_name)
    shutil.copy(icon, dist_app_dir)
    print(f"打包完成！应用程序版本 {version} 位于: {dist_app_dir}")


if __name__ == "__main__":
    package_application()