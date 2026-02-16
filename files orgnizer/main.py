import os
import shutil

path = input("Enter the path of the folder you want to clean: ")

# create category folders INSIDE the given path
folders = ["Images", "Videos", "Music", "Documents"]

for folder in folders:
    folder_path = os.path.join(path, folder)

    # if something exists with same name but is NOT folder
    if os.path.exists(folder_path) and not os.path.isdir(folder_path):
        os.remove(folder_path)

    os.makedirs(folder_path, exist_ok=True)


if os.path.exists(path):
    for file in os.listdir(path):
        file_path = os.path.join(path, file)

        # skip directories
        if os.path.isdir(file_path):
            continue

        if file.lower().endswith((".jpg", ".png", ".gif")):
            shutil.move(file_path, os.path.join(path, "Images", file))

        elif file.lower().endswith((".mp3", ".wav", ".ogg")):
            shutil.move(file_path, os.path.join(path, "Music", file))

        elif file.lower().endswith((".mp4", ".avi", ".mkv")):
            shutil.move(file_path, os.path.join(path, "Videos", file))

        elif file.lower().endswith((".txt", ".docx", ".pdf")):
            shutil.move(file_path, os.path.join(path, "Documents", file))

print("✅ Files organized successfully!")
