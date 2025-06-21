# XNull Video Compressor

A desktop application that allows you to compress videos to a specific target size while maintaining the best possible quality.

## Features

- Compress videos to a custom target size (KB, MB, or GB)
- Prevents setting a target size larger than the original video
- Supports various video formats
- Automatically converts videos to MP4 during compression (unless already in MP4 format)
- CPU usage control (automatic or manual percentage)
- Detailed log output for monitoring compression progress
- Simple and intuitive user interface
- Automatic retry with lower bitrate if target size is not achieved on first attempt
- Progress bar showing real-time compression status
- Cross-platform support with consistent icon display on Windows, macOS, and Linux

## Installation

1. Make sure you have Python 3.7+ installed
2. Install FFmpeg on your system:
   - **Windows:**
     1. Download FFmpeg from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (recommended) or [ffmpeg.org](https://ffmpeg.org/download.html)
     2. For gyan.dev, choose "ffmpeg-git-full.7z" for the full version
     3. Extract the downloaded archive to a location like `C:\ffmpeg`
     4. Add FFmpeg to your PATH environment variable:
        - Right-click on "This PC" or "My Computer" and select "Properties"
        - Click on "Advanced system settings"
        - Click the "Environment Variables" button
        - Under "System variables", find the "Path" variable and click "Edit"
        - Click "New" and add the path to the FFmpeg bin folder (e.g., `C:\ffmpeg\bin`)
        - Click "OK" on all dialogs to save changes
     5. Verify installation by opening Command Prompt and typing `ffmpeg -version`
   - **macOS:** `brew install ffmpeg`
   - **Linux:** `sudo apt install ffmpeg`
3. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the application using one of these methods:

1. **Direct Python execution:**
   ```
   python video_compressor.py
   ```

2. **Using convenience scripts:**
   - On Windows: Double-click `run_compressor.bat`
   - On macOS/Linux: Run `./run_compressor.sh` (make it executable first with `chmod +x run_compressor.sh`)

### Compressing a Video

1. Click "Select Video" to choose a video file
2. Enter your desired target size
3. Select the size unit (KB, MB, or GB)
4. Choose CPU usage mode:
   - Auto: Let FFmpeg determine optimal CPU usage
   - Manual: Set a specific percentage of CPU cores to use
5. Click "Compress Video"
6. Choose where to save the compressed video
7. Monitor progress in the log section (click "Show Log" to expand)

## Building Standalone Executable

The application can be packaged as a standalone executable using the included build script:

```
# Install PyInstaller if you don't have it already
pip install pyinstaller

# Run the build script
python build.py
```

This will:
1. Check for and install required dependencies
2. Create a standalone executable for your current platform
3. Include the app icon and all necessary resources

Note: PyInstaller is not included in requirements.txt since it's only needed for building the executable, not for running the application. The build script will attempt to install it automatically if missing.

### Build Options

You can specify the target platform:

```
python build.py --platform windows  # Build for Windows
python build.py --platform macos    # Build for macOS
python build.py --platform linux    # Build for Linux
```

The executable will be created in the `dist` directory.

**Note:** Cross-platform building (building for a platform different from your current OS) may not work correctly in all cases.

## Requirements

- Python 3.7+
- FFmpeg (system installation)
- PyQt5
- ffmpeg-python
- moviepy
- psutil

## License

MIT 
