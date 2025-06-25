# Creator's Toolkit for Windows 11  
**Professional Media Processing & Automation Suite**  

## 🚀 Project Overview  
The "Creator's Toolkit" is a desktop application designed for content creators, offering a unified graphical interface (GUI) for automating common media processing tasks. Built with Python 3.11 and leveraging powerful libraries like FFmpeg, MoviePy, OpenCV, and Rembg, this application aims to provide a streamlined, efficient, and high-quality solution for video conversions, audio enhancements, background removal, and more, specifically optimized for Windows 11.

This project evolved from a collection of command-line scripts previously used on Fedora, now being re-engineered to deliver a native, clean, and intuitive user experience on Windows. Our primary focus is on performance efficiency, especially on systems with less powerful CPUs but ample RAM, ensuring smooth operation and superior output quality.

## ✨ Key Features (Planned & In Progress)  
- **Video Conversion**: Seamlessly convert .mpg videos to optimized .mp4 format, and potentially other formats.  
- **Social Media Video Processing**: Intelligent cropping, subtitle generation, silent segment removal, and automatic enhancements tailored for social media platforms.  
- **Audio Cleaning & Enhancement**: Professional-grade noise reduction and vocal clarity improvements for audio files.  
- **Image Background Removal**: Quickly remove backgrounds from images with enhanced quality output.  
- **Video Background Removal**: Tools for removing backgrounds from video footage.  
- **Video Enhancement**: Advanced video styling, including optimized face tracking and quality enhancements.  

## 🛠️ Installation & Setup  
To get the Creator's Toolkit up and running on your Windows 11 machine, follow these steps:  

### 1. Prerequisites  
- **Python 3.11+**: Download and install Python from the [official Python website](https://www.python.org/). Ensure you add Python to your PATH during installation.  
- **FFmpeg**: This tool is crucial for video and audio processing.  
  - Download a static build for Windows from [FFmpeg's official site](https://ffmpeg.org/).  
  - Extract the downloaded archive to a location like `C:\ffmpeg`.  
  - Add the `bin` directory (e.g., `C:\ffmpeg\bin`) to your system's PATH environment variable.  
  - Verify installation by opening Command Prompt and typing `ffmpeg -version`.  

### 2. Clone the Repository  
```bash
git clone https://github.com/CodeWithBotina/creators-toolkit.git
cd creators-toolkit
```

### 3. Set Up Virtual Environment & Install Dependencies  
It's highly recommended to use a virtual environment to manage project dependencies.  

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux (if applicable, though project is Windows-focused):
source venv/bin/activate

# Install required Python packages
pip install -r requirements.txt
```

## 📂 Project Structure  
```
.
├── src/                       # Main application source code
│   ├── core/                  # Core services (logging, config management, font management)
│   │   ├── logger.py
│   │   ├── config_manager.py
│   │   └── font_manager.py    # Placeholder for font handling if needed
│   ├── gui/                   # User Interface (CustomTkinter frames/pages)
│   │   ├── video_converter_page.py
│   │   ├── audio_enhancement_page.py
│   │   ├── image_tools_page.py
│   │   ├── video_enhancement_page.py
│   │   ├── video_bg_removal_page.py
│   │   ├── social_media_post_page.py
│   │   └── main_window.py     # Potentially a main window or layout manager
│   ├── modules/               # Encapsulated logic for each processing type (video, audio, image)
│   │   ├── video_converter.py
│   │   ├── social_media_video_processor.py
│   │   ├── video_enhancer.py  # Placeholder/future module
│   │   ├── audio_processor.py # Placeholder/future module
│   │   ├── image_bg_remover.py # Placeholder/future module
│   │   └── video_bg_remover.py # Placeholder/future module
│   ├── utils/                 # Helper functions (file dialogs, path handling)
│   └── main.py                # Main application entry point
├── assets/                    # UI icons, images, styling
├── logs/                      # Application logs
├── config/                    # Configuration files
├── docs/                      # Documentation, design notes
├── tests/                     # Unit and integration tests
├── requirements.txt           # Python dependencies
├── README.md                  # Project overview and instructions
├── CONTRIBUTING.md            # Guidelines for contributions
├── CODE_OF_CONDUCT.md         # Community Code of Conduct
├── LICENSE                    # Project license (MIT)
└── .gitignore                 # Files to ignore in Git
```

## 🤝 Contributing  
Contributions are welcome! Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to contribute.  

## 🐞 Bug Reports & Feature Requests  
Please report any bugs or suggest new features via the [GitHub Issues](https://github.com/your-username/creators-toolkit/issues) page for this repository.  

## 📄 License  
This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.  

## 🙏 Acknowledgments  
Special thanks to the developers of:  
- Python  
- CustomTkinter  
- FFmpeg  
- MoviePy  
- OpenCV  
- Rembg  
...and all other open-source libraries that make this project possible.  
