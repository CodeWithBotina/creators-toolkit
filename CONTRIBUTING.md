# 🤝 Contributing to Creator's Toolkit for Windows 11

We welcome contributions from everyone! Whether you're fixing bugs, adding new features, improving documentation, or suggesting enhancements, your input is valuable. This document outlines guidelines to help you contribute effectively to the Creator's Toolkit project.

## Code of Conduct

Please note that this project adheres to a Contributor Code of Conduct. By participating in this project, you agree to abide by its terms.

## How Can I Contribute?

There are many ways to contribute to the Creator's Toolkit:

- **Reporting Bugs**: If you find a bug, please open an issue on the GitHub Issues page.
- **Suggesting Enhancements**: Have an idea for a new feature or an improvement? Open an issue to discuss it.
- **Writing Code**: Implement new features, fix bugs, or improve existing code.
- **Improving Documentation**: Enhance this CONTRIBUTING.md, the README.md, or add comments to the code.
- **Reviewing Pull Requests**: Help review code submitted by others.

## Getting Started with Code Contributions

To contribute code, please follow these steps:

### 1. Fork the Repository
First, fork the Creator's Toolkit repository to your own GitHub account.  

### 2. Clone Your Fork
Clone your forked repository to your local machine:

```bash
git clone https://github.com/CodeWithBotina/creators-toolkit.git
cd creators-toolkit
```

### 3. Set Up Your Development Environment
Ensure you have Python 3.11 (or a compatible version) installed. We recommend using a virtual environment.

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux (if applicable):
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Important**: This project relies on FFmpeg being installed and accessible in your system's PATH. You can download FFmpeg from [ffmpeg.org](https://ffmpeg.org).

### 4. Create a New Branch
Create a new branch for your feature or bug fix. Use a descriptive name:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-description
```

### 5. Make Your Changes
Implement your changes, keeping in mind the project's structure and best practices:

- **Single Responsibility Principle**: Each module should have a single, clear responsibility. Avoid overloading files.
- **Optimization & Performance**: Aim for efficient and fast code, especially for media processing tasks.
- **Readability & Comments**: Write clean, readable code and add comprehensive comments to explain logic, algorithms, and function headers.
- **Error Handling**: Implement robust error handling using try/catch blocks.
- **No alert() or confirm()**: Use custom UI dialogs (e.g., messagebox from tkinter or CustomTkinter dialogs) instead of native JavaScript-like alerts for user interaction.
- **Python Type Hints**: Use type hints for function arguments and return values.

### 6. Test Your Changes
Before submitting, ensure your changes work as expected and don't introduce new bugs. Run relevant tests or manually test the affected functionality.

The project includes `if __name__ == "__main__":` blocks in many modules for isolated testing. You can run these:

```bash
python -m src.modules.video_converter # Example
python -m src.gui.social_media_post_page # Example
# ... and other relevant modules/pages
```

### 7. Commit Your Changes
Commit your changes with clear, concise commit messages. Follow conventional commit guidelines if possible:

```bash
git add .
git commit -m "feat: Implement intelligent cropping for social media processor"
# or
git commit -m "fix: Resolve crash on file dialog"
```

### 8. Push Your Changes
Push your new branch to your forked repository on GitHub:

```bash
git push origin feature/your-feature-name
```

### 9. Create a Pull Request (PR)
Go to the original Creator's Toolkit repository on GitHub. You should see a prompt to create a new pull request from your recently pushed branch.

- **Describe Your Changes**: Provide a clear and detailed description of your changes in the PR description.
- **Reference Issues**: Link to any relevant issues (e.g., `Fixes #123`, `Closes #456`).
- **Screenshots/Gifs**: If your PR involves UI changes, include screenshots or GIFs to demonstrate the changes.

## Code Review Process

All pull requests will be reviewed by the maintainers. Be prepared to receive feedback and make further adjustments to your code based on the review.

## Licensing

By contributing, you agree that your contributions will be licensed under the MIT License, as per the project's LICENSE file.

**Thank you for contributing to the Creator's Toolkit!** Your efforts help make this project better for everyone.
