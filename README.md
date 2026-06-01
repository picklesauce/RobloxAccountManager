[![Version](https://img.shields.io/github/v/release/picklesauce/RobloxAccountManager)](https://github.com/picklesauce/RobloxAccountManager/releases/latest)
![License](https://img.shields.io/github/license/picklesauce/RobloxAccountManager)
[![Discord](https://img.shields.io/discord/1436930121897476140?label=Discord)](https://discord.gg/TYnJXyEhgY)
![DownloadCount](https://img.shields.io/github/downloads/picklesauce/RobloxAccountManager/total)
[![Website](https://img.shields.io/badge/website-online-1F58FF
)](https://picklesauces-roblox-account-manager.gitbook.io/picklesauces-ram/homepage)<br>
[![Download](https://img.shields.io/badge/Download-280ab?style=for-the-badge)](https://github.com/picklesauce/RobloxAccountManager/releases/latest/download/RobloxAccountManager.exe)

> [!IMPORTANT]
> Before you see this as a **"Virus"** or **"Unofficial,"** please read:
> - **Project Status:** This is the current active version of picklesauce's Roblox Account Manager. While the original C# tool by **ic3w0lf22** is a classic, it has been discontinued. I (picklesauce) have built this in Python to keep the project alive and updated.<br><br>
> - **100% Open Source:** Every line of code is transparent and available for everyone. If you don't trust the .exe, you are encouraged to run the script directly from the source code.<br><br>
> - **Integrity:** The standalone .exe in the releases is compiled directly from this code with zero alterations.

# 🚀 Roblox Account Manager

A powerful tool for managing multiple Roblox accounts with secure cookie extraction and modern UI interface.

**Created by picklesauce** · **Get Help:** [Discord Server](https://discord.gg/TYnJXyEhgY)<br>

⭐ If you like this project, please consider starring the repository! ⭐<br>
Or support the creator by donating on Roblox: [hands001](https://www.roblox.com/users/profile?username=hands001) ♥️

<img width="447" height="544" alt="image" src="https://github.com/user-attachments/assets/7296d21f-4026-486b-a9fd-ea75515be930" />
<img width="295" height="412" alt="image" src="https://github.com/user-attachments/assets/7a5acb0d-3b65-470e-ac90-7d022570df5b" />

## 📑 Table of Contents

- [Installation](#-installation)
- [Requirements](#-requirements)
- [Disclaimer](#-disclaimer)
- [Privacy Policy](#privacy-policy)
- [System Changes and Uninstallation](#system-changes-and-uninstallation)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)
- [FAQ](#-faq)
- [Features](#-features)

## 🛠️ Installation

### Method 1: Direct EXE (Recommended for Users)

**Quick & Easy - No Python Required!**

1. Go to [Releases](https://github.com/picklesauce/RobloxAccountManager/releases)
2. Download `RobloxAccountManager.exe` from the latest release
3. Put it in a folder
4. Double-click to run - that's it!

**Requirements:**
- **Google Chrome browser**
- **Windows** (currently optimized for Windows)

> ⚠️ Windows Defender may flag the EXE as untrusted since it's not signed. Click "More info" → "Run anyway" to proceed.

### Method 2: Clone Repository (For Developers, or for people that dont trust the EXE)

**Full source code access and customization**

**Requirements:**
- **Python 3.7+**
- **Google Chrome browser**
- **Windows** (currently optimized for Windows)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/picklesauce/RobloxAccountManager
   cd RobloxAccountManager
   ```

2. **Install dependencies**
   ```bash
   py -m pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   py main.py
   ```
   
## 📋 Requirements

The following Python packages are required:
- `selenium` - Browser automation
- `requests` - HTTP requests for account validation and game info
- `webdriver-manager` - Automatic ChromeDriver management
- `pycryptodome` - Encryption and cookie handling
- `pywin32` - Windows API access for Multi Roblox feature
- `pywinauto` - UI Automation for dismissing Chrome's protocol dialog during profile-join
- `psutil` - Process monitoring for Multi Roblox handle64 mode
- `pyautoit` - Window rotation and maintenance actions for Anti-AFK
- `Pillow` - Image handling for embedded resources

## ⚠️ Disclaimer

This tool is for educational purposes only. Users are responsible for complying with Roblox's Terms of Service. The developers are not responsible for any consequences resulting from the use of this tool.

### Team Roles

- Committers and reviewers: [picklesauce](https://github.com/picklesauce)
- Approvers: [picklesauce](https://github.com/picklesauce)

## Privacy Policy

This program does not include hidden telemetry, ad SDKs, or analytics tracking.

Network communication is limited to documented functionality:

- Roblox API calls required for Roblox account and game features.
- GitHub API/release checks for update-related features.
- Discord webhook/bot endpoints only when Discord integration is configured by the operator.
- Optional connectivity checks used by auto-rejoin safety logic.

If Discord/webhook/auto-update features are not enabled, those related network requests are not performed.

## System Changes and Uninstallation

The program may make local system changes based on enabled settings:

- Creates/updates local application data under AccountManagerData.
- Can create/remove a Start Menu shortcut.
- Can set Roblox settings files as read-only when the lock option is enabled.
- Can download optional dependencies/features only when requested by the user.

Uninstallation:

1. Close the application.
2. Delete the application folder containing RobloxAccountManager.exe.
3. Delete AccountManagerData if you want to remove local data.
4. Remove the Start Menu shortcut if it exists.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the [GPL 3.0 License](LICENSE).

## 📞 Support

Have questions or need help? Join our **[Discord Server](https://discord.gg/TYnJXyEhgY)** where the community and developers can assist you!

## ❓ FAQ

New to the app? The FAQ covers safety & trust, requirements, adding accounts, Multi Roblox, the join captcha, encryption, and common troubleshooting.

**👉 Read the full FAQ in [docs/FAQ.md](docs/FAQ.md).**

## ✨ Features

Every feature, grouped by category — account management, game launching, Multi Roblox, the auto-rejoin system, settings & tools, UI customization, encryption, and anti-AFK.

**👉 See the complete feature list in [docs/FEATURES.md](docs/FEATURES.md).**
