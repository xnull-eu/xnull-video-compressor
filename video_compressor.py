import os
import sys
import subprocess
import math
import time
import re
import signal
import psutil
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QComboBox, QFileDialog, QMessageBox, QProgressBar,
                            QStatusBar, QTextEdit, QSplitter, QFrame, QSlider, QSizeGrip)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
import ffmpeg
from moviepy.editor import VideoFileClip

# Modern dark theme style
DARK_STYLE = """
QWidget {
    background-color: #2D2D30;
    color: #E1E1E1;
    font-family: Segoe UI, Arial, sans-serif;
    font-size: 10pt;
}

QMainWindow {
    background-color: #1E1E1E;
}

QLabel {
    color: #E1E1E1;
}

QPushButton {
    background-color: #0078D7;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 3px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1C97EA;
}

QPushButton:pressed {
    background-color: #00559B;
}

QPushButton:disabled {
    background-color: #3D3D3D;
    color: #787878;
}

QPushButton:checked {
    background-color: #00559B;
}

QLineEdit, QComboBox {
    background-color: #3D3D3D;
    color: #E1E1E1;
    border: 1px solid #555555;
    padding: 4px;
    border-radius: 2px;
}

QComboBox::drop-down {
    border: none;
    background-color: #505050;
    width: 20px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #3D3D3D;
    color: #E1E1E1;
    selection-background-color: #0078D7;
    selection-color: white;
}

QProgressBar {
    border: 1px solid #555555;
    border-radius: 2px;
    background-color: #3D3D3D;
    color: white;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #0078D7;
    width: 10px;
    margin: 0.5px;
}

QSlider {
    height: 20px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #555555;
    margin: 0 10px;
}

QSlider::handle:horizontal {
    background: #0078D7;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #1C97EA;
}

QTextEdit {
    background-color: #252526;
    color: #E1E1E1;
    border: 1px solid #555555;
    font-family: "Consolas", monospace;
}

QSplitter::handle {
    background-color: #3D3D3D;
}

QStatusBar {
    background-color: #007ACC;
    color: white;
}

QStatusBar::item {
    border: none;
}

/* Hide the resize grip in the bottom right corner */
QSizeGrip {
    background: transparent;
    width: 0px;
    height: 0px;
}

QScrollBar:vertical {
    border: none;
    background: #3D3D3D;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #666666;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QMessageBox {
    background-color: #2D2D30;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""

class VideoCompressorThread(QThread):
    """Worker thread for video compression to keep UI responsive"""
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    log_update = pyqtSignal(str)
    compression_finished = pyqtSignal(bool, str)
    
    def __init__(self, input_file, output_file, target_size, cpu_usage="auto"):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.target_size = target_size  # in bytes
        self.cpu_usage = cpu_usage  # "auto" or a percentage (1-100)
        self.cancelled = False
        self.process = None
        self.progress_timer = None
    
    def run(self):
        try:
            # Get video info
            self.status_update.emit("Analyzing video...")
            video = VideoFileClip(self.input_file)
            duration = video.duration
            original_size = os.path.getsize(self.input_file)
            
            # Calculate target bitrate (bits per second)
            # Formula: bitrate = target_size_in_bits / duration_in_seconds
            # Reduce by 5% to ensure we don't exceed the target size
            target_bitrate = int((self.target_size * 8 * 0.95) / duration)
            
            # Close the video to release resources
            video.close()
            
            # Check if the input is already MP4
            input_ext = os.path.splitext(self.input_file)[1].lower()
            is_mp4 = input_ext == '.mp4'
            
            # If it's already MP4 and the target size is close to original, just copy
            if is_mp4 and abs(original_size - self.target_size) / original_size < 0.05:
                self.status_update.emit("Original file already meets size requirements, copying...")
                import shutil
                shutil.copy2(self.input_file, self.output_file)
                self.compression_finished.emit(True, "Video copied successfully as it already meets size requirements.")
                return
            
            # Set up FFmpeg command
            self.status_update.emit(f"Compressing video with target bitrate: {target_bitrate/1000:.2f} kbps...")
            
            # Use single-pass encoding instead of two-pass to avoid getting stuck
            self.status_update.emit("Encoding video...")
            
            # Set CPU usage
            cpu_threads = ""
            if self.cpu_usage != "auto":
                # Get total CPU cores
                import multiprocessing
                total_cores = multiprocessing.cpu_count()
                # Calculate threads based on percentage
                threads = max(1, int((int(self.cpu_usage) / 100) * total_cores))
                cpu_threads = f"-threads {threads}"
                self.log_update.emit(f"Using {threads} CPU threads ({self.cpu_usage}% of {total_cores} cores)")
            
            # Create temporary file for stderr output
            stderr_file = os.path.join(os.path.dirname(self.output_file), "ffmpeg_stderr.txt")
            
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', self.input_file
            ]
            
            # Add CPU thread limit if specified
            if cpu_threads:
                ffmpeg_cmd.extend(cpu_threads.split())
                
            ffmpeg_cmd.extend([
                '-c:v', 'libx264', '-b:v', f'{target_bitrate}',
                '-c:a', 'aac', '-b:a', '128k',
                '-stats',  # Show stats on stderr
                self.output_file
            ])
            
            self.log_update.emit(f"Running command: {' '.join(ffmpeg_cmd)}")
            
            # Use CREATE_NO_WINDOW flag on Windows to prevent console window
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Start process with stderr redirected to file
            with open(stderr_file, 'w') as stderr_output:
                self.process = subprocess.Popen(
                    ffmpeg_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=stderr_output,
                    universal_newlines=True,
                    bufsize=1,  # Line buffered
                    startupinfo=startupinfo  # Hide console window
                )
            
            # Set up a timer to read progress from stderr file
            self.progress_timer = QTimer()
            self.progress_timer.timeout.connect(lambda: self.check_progress(stderr_file, duration))
            self.progress_timer.start(500)  # Check every 500ms
            
            # Wait for process to complete
            while self.process.poll() is None:
                if self.cancelled:
                    # Force kill the process and its children
                    self.kill_process_tree(self.process.pid)
                    self.status_update.emit("Compression cancelled.")
                    self.log_update.emit("Process terminated by user.")
                    self.compression_finished.emit(False, "Compression was cancelled.")
                    
                    # Clean up temporary file
                    try:
                        if os.path.exists(stderr_file):
                            os.remove(stderr_file)
                    except:
                        pass
                        
                    # Delete partial output file
                    try:
                        if os.path.exists(self.output_file):
                            os.remove(self.output_file)
                            self.log_update.emit(f"Deleted partial output file: {self.output_file}")
                    except:
                        self.log_update.emit(f"Failed to delete partial output file: {self.output_file}")
                    
                    return
                
                # Small sleep to prevent CPU hogging
                time.sleep(0.1)
            
            # Stop the progress timer
            if self.progress_timer:
                self.progress_timer.stop()
            
            # Read the entire stderr file for log
            try:
                with open(stderr_file, 'r') as f:
                    stderr_content = f.read()
                    if stderr_content:
                        self.log_update.emit(f"FFmpeg output:\n{stderr_content}")
            except:
                self.log_update.emit("Could not read FFmpeg output file.")
            
            # Clean up temporary file
            try:
                if os.path.exists(stderr_file):
                    os.remove(stderr_file)
            except:
                pass
            
            # Check if compression was successful
            if self.process.returncode == 0:
                # Ensure the file exists and has size
                if not os.path.exists(self.output_file) or os.path.getsize(self.output_file) == 0:
                    self.log_update.emit("Error: Output file is empty or missing.")
                    self.compression_finished.emit(False, "Compression failed: Output file is empty or missing.")
                    return
                
                final_size = os.path.getsize(self.output_file)
                
                # Ensure the file isn't larger than target size
                if final_size > self.target_size:
                    self.log_update.emit(f"Warning: Final size {self.format_size(final_size)} exceeds target size {self.format_size(self.target_size)}.")
                    self.log_update.emit("Attempting to reduce size further...")
                    
                    # Try again with lower bitrate if needed
                    if not self.cancelled and final_size > self.target_size * 1.05:
                        # Delete the output file
                        try:
                            os.remove(self.output_file)
                        except:
                            pass
                        
                        # Reduce bitrate by the ratio of final/target and try again
                        reduced_bitrate = int(target_bitrate * (self.target_size / final_size) * 0.95)
                        self.log_update.emit(f"Retrying with reduced bitrate: {reduced_bitrate/1000:.2f} kbps")
                        
                        # Create new temporary file for stderr
                        stderr_file = os.path.join(os.path.dirname(self.output_file), "ffmpeg_stderr_retry.txt")
                        
                        ffmpeg_cmd = [
                            'ffmpeg', '-y', '-i', self.input_file
                        ]
                        
                        # Add CPU thread limit if specified
                        if cpu_threads:
                            ffmpeg_cmd.extend(cpu_threads.split())
                            
                        ffmpeg_cmd.extend([
                            '-c:v', 'libx264', '-b:v', f'{reduced_bitrate}',
                            '-c:a', 'aac', '-b:a', '96k',  # Also reduce audio bitrate
                            '-stats',  # Show stats on stderr
                            self.output_file
                        ])
                        
                        self.log_update.emit(f"Running command: {' '.join(ffmpeg_cmd)}")
                        
                        # Start process with stderr redirected to file
                        with open(stderr_file, 'w') as stderr_output:
                            # Use CREATE_NO_WINDOW flag on Windows to prevent console window
                            startupinfo = None
                            if os.name == 'nt':
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                startupinfo.wShowWindow = 0  # SW_HIDE
                                
                            self.process = subprocess.Popen(
                                ffmpeg_cmd, 
                                stdout=subprocess.PIPE,
                                stderr=stderr_output,
                                universal_newlines=True,
                                bufsize=1,
                                startupinfo=startupinfo  # Hide console window
                            )
                        
                        # Reset progress timer for second pass
                        if self.progress_timer:
                            self.progress_timer.stop()
                        self.progress_timer = QTimer()
                        self.progress_timer.timeout.connect(lambda: self.check_progress(stderr_file, duration))
                        self.progress_timer.start(500)
                        
                        # Wait for process to complete
                        while self.process.poll() is None:
                            if self.cancelled:
                                # Force kill the process and its children
                                self.kill_process_tree(self.process.pid)
                                self.status_update.emit("Compression cancelled.")
                                self.log_update.emit("Process terminated by user.")
                                self.compression_finished.emit(False, "Compression was cancelled.")
                                
                                # Clean up temporary file
                                try:
                                    if os.path.exists(stderr_file):
                                        os.remove(stderr_file)
                                except:
                                    pass
                                
                                # Delete partial output file
                                try:
                                    if os.path.exists(self.output_file):
                                        os.remove(self.output_file)
                                        self.log_update.emit(f"Deleted partial output file: {self.output_file}")
                                except:
                                    self.log_update.emit(f"Failed to delete partial output file: {self.output_file}")
                                
                                return
                            
                            # Small sleep to prevent CPU hogging
                            time.sleep(0.1)
                        
                        # Stop the progress timer
                        if self.progress_timer:
                            self.progress_timer.stop()
                        
                        # Read the entire stderr file for log
                        try:
                            with open(stderr_file, 'r') as f:
                                stderr_content = f.read()
                                if stderr_content:
                                    self.log_update.emit(f"FFmpeg output (retry):\n{stderr_content}")
                        except:
                            self.log_update.emit("Could not read FFmpeg output file.")
                        
                        # Clean up temporary file
                        try:
                            if os.path.exists(stderr_file):
                                os.remove(stderr_file)
                        except:
                            pass
                        
                        # Check if file exists after retry
                        if not os.path.exists(self.output_file) or os.path.getsize(self.output_file) == 0:
                            self.log_update.emit("Error: Output file is empty or missing after retry.")
                            self.compression_finished.emit(False, "Compression failed: Output file is empty or missing after retry.")
                            return
                        
                        final_size = os.path.getsize(self.output_file)
                
                # Final result
                size_diff_percent = abs(final_size - self.target_size) / self.target_size * 100
                compression_ratio = original_size / final_size
                
                self.log_update.emit(f"Original size: {self.format_size(original_size)}")
                self.log_update.emit(f"Final size: {self.format_size(final_size)}")
                self.log_update.emit(f"Target size: {self.format_size(self.target_size)}")
                self.log_update.emit(f"Compression ratio: {compression_ratio:.2f}x")
                
                # Force progress to 100%
                self.progress_update.emit(100)
                
                if final_size > self.target_size:
                    self.status_update.emit("Compression complete, but target size not achieved.")
                    self.compression_finished.emit(True, 
                        f"Video compressed to {self.format_size(final_size)}, which is {((final_size/self.target_size)-1)*100:.1f}% "
                        f"larger than the target. Compression ratio: {compression_ratio:.2f}x")
                else:
                    self.status_update.emit("Compression complete!")
                    self.compression_finished.emit(True, 
                        f"Video compressed successfully to {self.format_size(final_size)} "
                        f"({compression_ratio:.2f}x smaller than original).")
            else:
                self.status_update.emit("Compression failed.")
                self.compression_finished.emit(False, "Compression failed. Check the log for details.")
                
        except Exception as e:
            self.log_update.emit(f"Exception: {str(e)}")
            self.status_update.emit(f"Error: {str(e)}")
            self.compression_finished.emit(False, f"Error during compression: {str(e)}")
            
            # Clean up any partial output file
            try:
                if os.path.exists(self.output_file):
                    os.remove(self.output_file)
                    self.log_update.emit(f"Deleted partial output file: {self.output_file}")
            except:
                pass
    
    def check_progress(self, stderr_file, duration):
        """Read the stderr file to update progress"""
        try:
            if not os.path.exists(stderr_file):
                return
                
            with open(stderr_file, 'r') as f:
                content = f.read()
            
            # Store file size for progress estimation
            if not hasattr(self, 'last_file_size'):
                self.last_file_size = 0
                self.last_progress_time = time.time()
                self.last_progress_value = 0
                self.progress_count = 0
            
            # Check if output file exists and has size
            if os.path.exists(self.output_file):
                current_size = os.path.getsize(self.output_file)
                if current_size > 0 and current_size != self.last_file_size:
                    # Calculate progress based on file size growth
                    # This is an approximation but gives visual feedback
                    size_progress = min(int((current_size / self.target_size) * 90), 90)
                    self.last_file_size = current_size
                    self.progress_update.emit(size_progress)
                    self.log_update.emit(f"Progress: ~{size_progress}% (File size: {self.format_size(current_size)})")
                    self.last_progress_time = time.time()
                    self.last_progress_value = size_progress
                    return
                
            # Look for frame= and time= information as backup
            frame_match = re.search(r'frame=\s*(\d+)', content)
            time_match = re.search(r'time=\s*(\d+):(\d+):(\d+)\.(\d+)', content)
            
            if time_match:
                # Calculate progress based on time
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = int(time_match.group(3))
                milliseconds = int(time_match.group(4))
                
                current_time = hours * 3600 + minutes * 60 + seconds + milliseconds / 100
                progress = min(int((current_time / duration) * 100), 99)
                
                # Only update if progress has changed
                if progress > self.last_progress_value:
                    self.progress_update.emit(progress)
                    self.last_progress_value = progress
                    
                    # Also update log with progress
                    if frame_match:
                        frame = frame_match.group(1)
                        self.log_update.emit(f"Progress: {progress}% (frame {frame}, time {time_match.group(0)})")
                    
                    self.last_progress_time = time.time()
            elif frame_match:
                # If we only have frame information, try to estimate progress
                fps_match = re.search(r'fps=\s*([\d.]+)', content)
                if fps_match:
                    fps = float(fps_match.group(1))
                    if fps > 0:
                        frame = int(frame_match.group(1))
                        estimated_total_frames = fps * duration
                        progress = min(int((frame / estimated_total_frames) * 100), 99)
                        
                        # Only update if progress has changed
                        if progress > self.last_progress_value:
                            self.progress_update.emit(progress)
                            self.last_progress_value = progress
                            self.log_update.emit(f"Progress: {progress}% (frame {frame}, fps {fps})")
                            self.last_progress_time = time.time()
            
            # If no progress for 2 seconds, show simulated progress
            if time.time() - self.last_progress_time > 2:
                self.progress_count += 1
                # Simulate progress from 1% to 90% over time
                simulated_progress = min(1 + self.progress_count, 90)
                if simulated_progress > self.last_progress_value:
                    self.progress_update.emit(simulated_progress)
                    self.last_progress_value = simulated_progress
                    self.log_update.emit(f"Estimated progress: ~{simulated_progress}%")
                    self.last_progress_time = time.time()
                
        except Exception as e:
            self.log_update.emit(f"Error reading progress: {str(e)}")
    
    def kill_process_tree(self, pid):
        """Kill a process and all its children"""
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except:
                    pass
            parent.kill()
        except:
            # If psutil fails, try direct signal
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                if self.process.poll() is None:  # If still running
                    os.kill(pid, signal.SIGKILL)
            except:
                pass
    
    def cancel(self):
        self.cancelled = True
        if self.progress_timer:
            self.progress_timer.stop()
    
    def format_size(self, size_bytes):
        """Format bytes into human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/1024**2:.2f} MB"
        else:
            return f"{size_bytes/1024**3:.2f} GB"


class VideoCompressorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XNull Video Compressor")
        self.setMinimumSize(600, 400)
        
        # Set window flags to enable custom title bar styling
        if os.name == 'nt':  # Windows only
            try:
                # This helps with taskbar icon and dark title bar on Windows 10/11
                from ctypes import windll, c_int, byref, sizeof
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                windll.dwmapi.DwmSetWindowAttribute(
                    int(self.winId()), 
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    byref(c_int(1)), 
                    sizeof(c_int)
                )
            except:
                pass
        
        self.input_file = None
        self.output_file = None
        self.compression_thread = None
        self.log_expanded = False
        
        self.init_ui()
    
    def init_ui(self):
        # Main splitter to allow resizing between main controls and log
        self.main_splitter = QSplitter(Qt.Vertical)
        self.setCentralWidget(self.main_splitter)
        
        # Top widget for controls
        top_widget = QWidget()
        main_layout = QVBoxLayout()
        top_widget.setLayout(main_layout)
        self.main_splitter.addWidget(top_widget)
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)
        select_btn = QPushButton("Select Video")
        select_btn.clicked.connect(self.select_video)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(select_btn)
        main_layout.addLayout(file_layout)
        
        # File info
        self.info_label = QLabel("File info: N/A")
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)
        
        # Target size input
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Target Size:"))
        self.size_input = QLineEdit()
        self.size_input.setPlaceholderText("Enter target size")
        size_layout.addWidget(self.size_input)
        
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["KB", "MB", "GB"])
        self.unit_combo.setCurrentText("MB")
        size_layout.addWidget(self.unit_combo)
        main_layout.addLayout(size_layout)
        
        # CPU usage options
        cpu_layout = QVBoxLayout()
        cpu_group_layout = QHBoxLayout()
        
        cpu_label = QLabel("CPU Usage:")
        cpu_group_layout.addWidget(cpu_label)
        
        # Auto option
        self.auto_cpu_radio = QPushButton("Auto")
        self.auto_cpu_radio.setCheckable(True)
        self.auto_cpu_radio.setChecked(True)
        self.auto_cpu_radio.clicked.connect(self.toggle_cpu_mode)
        cpu_group_layout.addWidget(self.auto_cpu_radio)
        
        # Manual option
        self.manual_cpu_radio = QPushButton("Manual")
        self.manual_cpu_radio.setCheckable(True)
        self.manual_cpu_radio.clicked.connect(self.toggle_cpu_mode)
        cpu_group_layout.addWidget(self.manual_cpu_radio)
        
        cpu_layout.addLayout(cpu_group_layout)
        
        # CPU percentage slider
        cpu_slider_layout = QHBoxLayout()
        self.cpu_slider = QSlider(Qt.Horizontal)
        self.cpu_slider.setRange(10, 100)
        self.cpu_slider.setValue(50)
        self.cpu_slider.setTickPosition(QSlider.TicksBelow)
        self.cpu_slider.setTickInterval(10)
        self.cpu_slider.setEnabled(False)
        
        self.cpu_value_label = QLabel("50%")
        self.cpu_slider.valueChanged.connect(self.update_cpu_value)
        
        cpu_slider_layout.addWidget(self.cpu_slider)
        cpu_slider_layout.addWidget(self.cpu_value_label)
        
        cpu_layout.addLayout(cpu_slider_layout)
        main_layout.addLayout(cpu_layout)
        
        # Compression button
        button_layout = QHBoxLayout()
        self.compress_btn = QPushButton("Compress Video")
        self.compress_btn.clicked.connect(self.compress_video)
        self.compress_btn.setEnabled(False)
        button_layout.addWidget(self.compress_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_compression)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)
        
        # Log toggle button
        self.log_btn = QPushButton("▼ Show Log")
        self.log_btn.clicked.connect(self.toggle_log)
        button_layout.addWidget(self.log_btn)
        
        main_layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Log area (initially hidden)
        self.log_widget = QWidget()
        log_layout = QVBoxLayout()
        self.log_widget.setLayout(log_layout)
        
        log_label = QLabel("Log Output:")
        log_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        log_layout.addWidget(self.log_text)
        
        self.main_splitter.addWidget(self.log_widget)
        self.log_widget.hide()  # Initially hidden
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def toggle_log(self):
        if self.log_expanded:
            self.log_widget.hide()
            self.log_btn.setText("▼ Show Log")
            self.log_expanded = False
        else:
            self.log_widget.show()
            self.log_btn.setText("▲ Hide Log")
            self.log_expanded = True
    
    def toggle_cpu_mode(self):
        # Ensure only one button is checked at a time
        sender = self.sender()
        if sender == self.auto_cpu_radio and sender.isChecked():
            self.manual_cpu_radio.setChecked(False)
            self.cpu_slider.setEnabled(False)
        elif sender == self.manual_cpu_radio and sender.isChecked():
            self.auto_cpu_radio.setChecked(False)
            self.cpu_slider.setEnabled(True)
        
        # If both are unchecked, default to auto
        if not self.auto_cpu_radio.isChecked() and not self.manual_cpu_radio.isChecked():
            self.auto_cpu_radio.setChecked(True)
            self.cpu_slider.setEnabled(False)
    
    def update_cpu_value(self):
        value = self.cpu_slider.value()
        self.cpu_value_label.setText(f"{value}%")
    
    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Video File", 
            "", 
            "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm);;All Files (*)"
        )
        
        if file_path:
            self.input_file = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
            self.compress_btn.setEnabled(True)
            
            # Get file info
            try:
                video = VideoFileClip(file_path)
                file_size = os.path.getsize(file_path)
                duration = video.duration
                width, height = video.size
                
                # Format file size
                if file_size < 1024**2:
                    size_str = f"{file_size/1024:.2f} KB"
                elif file_size < 1024**3:
                    size_str = f"{file_size/1024**2:.2f} MB"
                else:
                    size_str = f"{file_size/1024**3:.2f} GB"
                
                # Format duration
                minutes, seconds = divmod(duration, 60)
                hours, minutes = divmod(minutes, 60)
                duration_str = f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
                
                self.info_label.setText(
                    f"File info: {size_str}, {duration_str}, {width}x{height}, "
                    f"{os.path.splitext(file_path)[1][1:].upper()}"
                )
                
                # Set default target size to 80% of original
                default_size = file_size * 0.8
                if default_size < 1024**2:
                    self.size_input.setText(f"{default_size/1024:.2f}")
                    self.unit_combo.setCurrentText("KB")
                elif default_size < 1024**3:
                    self.size_input.setText(f"{default_size/1024**2:.2f}")
                    self.unit_combo.setCurrentText("MB")
                else:
                    self.size_input.setText(f"{default_size/1024**3:.2f}")
                    self.unit_combo.setCurrentText("GB")
                
                # Close the video to release resources
                video.close()
                
                # Clear log
                self.log_text.clear()
                self.add_to_log(f"Selected file: {file_path}")
                self.add_to_log(f"Size: {size_str}, Duration: {duration_str}, Resolution: {width}x{height}")
                
            except Exception as e:
                self.info_label.setText(f"Error reading file: {str(e)}")
                self.compress_btn.setEnabled(False)
                self.add_to_log(f"Error reading file: {str(e)}")
    
    def compress_video(self):
        if not self.input_file:
            QMessageBox.warning(self, "Error", "Please select a video file first.")
            return
        
        # Get target size
        try:
            size_value = float(self.size_input.text())
            if size_value <= 0:
                raise ValueError("Size must be positive")
            
            # Convert to bytes based on selected unit
            unit = self.unit_combo.currentText()
            if unit == "KB":
                target_size_bytes = size_value * 1024
            elif unit == "MB":
                target_size_bytes = size_value * 1024**2
            else:  # GB
                target_size_bytes = size_value * 1024**3
            
            # Check if target size is larger than original
            original_size = os.path.getsize(self.input_file)
            if target_size_bytes > original_size:
                QMessageBox.warning(
                    self, 
                    "Invalid Target Size", 
                    "Target size cannot be larger than the original file size."
                )
                return
            
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Please enter a valid number: {str(e)}")
            return
        
        # Get output file path
        input_basename = os.path.basename(self.input_file)
        input_name, _ = os.path.splitext(input_basename)
        
        self.output_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Compressed Video",
            f"{input_name}_compressed.mp4",
            "MP4 Files (*.mp4)"
        )
        
        if not self.output_file:
            return  # User cancelled
        
        # Ensure the output file has .mp4 extension
        if not self.output_file.lower().endswith('.mp4'):
            self.output_file += '.mp4'
        
        # Clear log and show it
        self.log_text.clear()
        if not self.log_expanded:
            self.toggle_log()
        
        # Update UI
        self.compress_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # Add initial log entries
        self.add_to_log(f"Starting compression of: {self.input_file}")
        self.add_to_log(f"Output file: {self.output_file}")
        self.add_to_log(f"Target size: {self.format_size(target_size_bytes)}")
        
        # Get CPU usage setting
        cpu_usage = "auto"
        if self.manual_cpu_radio.isChecked():
            cpu_usage = str(self.cpu_slider.value())
            self.add_to_log(f"Using manual CPU usage: {cpu_usage}%")
        else:
            self.add_to_log("Using automatic CPU usage")
            
        # Start compression in a separate thread
        self.compression_thread = VideoCompressorThread(
            self.input_file,
            self.output_file,
            target_size_bytes,
            cpu_usage
        )
        self.compression_thread.progress_update.connect(self.update_progress)
        self.compression_thread.status_update.connect(self.update_status)
        self.compression_thread.log_update.connect(self.add_to_log)
        self.compression_thread.compression_finished.connect(self.compression_done)
        self.compression_thread.start()
    
    def cancel_compression(self):
        if self.compression_thread and self.compression_thread.isRunning():
            self.compression_thread.cancel()
            self.status_bar.showMessage("Cancelling compression...")
            self.add_to_log("Cancelling compression...")
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_status(self, message):
        self.status_bar.showMessage(message)
    
    def add_to_log(self, message):
        self.log_text.append(message)
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def compression_done(self, success, message):
        self.compress_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        if success:
            # Ensure progress bar shows 100% when done
            self.progress_bar.setValue(100)
            # Update status to show completion
            self.status_bar.showMessage("Compression complete")
            QMessageBox.information(self, "Success", message)
        else:
            self.progress_bar.setValue(0)
            QMessageBox.warning(self, "Error", message)
            
            # If output file was created but compression failed, try to delete it
            if self.output_file and os.path.exists(self.output_file):
                try:
                    os.remove(self.output_file)
                    self.add_to_log(f"Deleted incomplete output file: {self.output_file}")
                except:
                    self.add_to_log(f"Failed to delete incomplete output file: {self.output_file}")
        
        self.add_to_log(f"Compression finished: {message}")
        self.status_bar.showMessage("Ready")
    
    def format_size(self, size_bytes):
        """Format bytes into human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/1024**2:.2f} MB"
        else:
            return f"{size_bytes/1024**3:.2f} GB"
    
    def closeEvent(self, event):
        # Cancel any ongoing compression when closing the app
        if self.compression_thread and self.compression_thread.isRunning():
            self.compression_thread.cancel()
            self.compression_thread.wait(2000)  # Wait up to 2 seconds
        event.accept()


if __name__ == "__main__":
    # Check if FFmpeg is installed
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("Error: FFmpeg is not installed or not in PATH.")
        print("Please install FFmpeg and make sure it's in your system PATH.")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    
    # Apply dark style
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    
    # Set dark palette as fallback
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(45, 45, 48))
    dark_palette.setColor(QPalette.WindowText, QColor(225, 225, 225))
    dark_palette.setColor(QPalette.Base, QColor(37, 37, 38))
    dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 48))
    dark_palette.setColor(QPalette.ToolTipText, QColor(225, 225, 225))
    dark_palette.setColor(QPalette.Text, QColor(225, 225, 225))
    dark_palette.setColor(QPalette.Button, QColor(45, 45, 48))
    dark_palette.setColor(QPalette.ButtonText, QColor(225, 225, 225))
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(0, 120, 215))
    dark_palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    dark_palette.setColor(QPalette.HighlightedText, Qt.white)
    dark_palette.setColor(QPalette.Active, QPalette.Button, QColor(45, 45, 48))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(120, 120, 120))
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    dark_palette.setColor(QPalette.Disabled, QPalette.Light, QColor(45, 45, 48))
    app.setPalette(dark_palette)
    
    # Set application icon - try multiple approaches to ensure it works
    # First try to find the icon in various locations
    possible_icon_paths = [
        'app_icon.png',                          # Current directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png'),  # Script directory
        os.path.join(sys.path[0], 'app_icon.png'),                                 # Another way to get script directory
        os.path.join('icons', 'icon_128x128.png'),                                 # Icons directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'icon_128x128.png'),  # Full path to icons
        os.path.join(sys._MEIPASS, 'app_icon.png') if hasattr(sys, '_MEIPASS') else None  # PyInstaller bundle
    ]
    
    icon_path = None
    for path in possible_icon_paths:
        if path and os.path.exists(path):
            icon_path = path
            break
    
    if icon_path:
        # Set app icon
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    else:
        print("Warning: Icon file not found")
    
    window = VideoCompressorApp()
    
    # Set window icon directly as well
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))
    
    window.show()
    sys.exit(app.exec_()) 