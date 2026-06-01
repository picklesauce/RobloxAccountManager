# ✨ Features

[← Back to README](../README.md)

A complete, categorized list of everything Roblox Account Manager can do.

## Account Management

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Browser Login** | Add accounts by logging in manually through Chrome | Click "Add Account" → browser opens → login to Roblox |
| **Cookie Import** | Import accounts using `.ROBLOSECURITY` cookie | Click "Add Account" dropdown → "Import Cookie" → paste cookie |
| **Multiple Cookie Import** | Import multiple accounts at once | Click "Add Account" dropdown → "Import Cookie" → paste multiple cookies |
| **JavaScript Automation** | Bulk add accounts with custom JavaScript execution (up to 10 instances) | Click "Add Account" dropdown → "Javascript" → choose amount, website, and code |
| **Password Capture** | Automatically captures and saves passwords during browser login | Automatic during browser login; right-click account → "Copy Password" |
| **Cookie Validity Indicator** | Warning icon next to accounts with expired or invalid cookies | Automatically shown in the account list |
| **Account Notes** | Add custom notes/tags to accounts for organization | Right-click account → "Edit Note" |
| **Account Deletion** | Remove accounts from your saved list | Right-click account → "Delete" → confirm |
| **Multi-Select Mode** | Select and manage multiple accounts at once | Enable in Settings → QOL tab → "Multi Select"; use Ctrl+Click to select multiple |
| **Drag & Drop Reordering** | Reorder accounts by dragging and dropping in the list | Click & hold account for 0.5s, then drag to new position |
| **Keyboard Shortcuts** | Delete selected accounts with the Delete key | Select account(s) → press Delete |

## Game Launching

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Single Game Launch** | Launch Roblox game with one account | Enter Place ID → Click "Join Place" |
| **Multi-Account Launch** | Launch the same game with multiple accounts simultaneously | Enable Multi-Select → Select accounts → Enter Place ID → Click "Join Place" |
| **Auto Window Tiling** | Automatically arranges Roblox windows in a tiled grid when launching multiple instances | Enable in Settings → QOL tab → "Auto Tile Windows"; applies automatically when launching 2+ accounts |
| **Auto Minimize Windows** | Automatically minimizes Roblox windows after launching multiple instances; can be combined with Auto Tile (windows are tiled first, then minimized) | Enable in Settings → QOL tab → "Auto Minimize Windows" |
| **Manual Tile / Minimize** | Tile or minimize all currently-open Roblox windows on demand | Settings → QOL tab → "Tile Windows" / "Minimize Windows" buttons |
| **Confirm Before Launch** | Show a confirmation prompt before launching a game | Settings → QOL tab → "Confirm Before Launch" |
| **Private Server Support** | Save and launch private servers (marked with [P]) | Enter Private Server ID → Game automatically joins private server |
| **VIP Link Parsing** | Paste a full Roblox VIP URL into the Private Server field to auto-extract Place ID and server code | Paste VIP URL into "Private Server" field |
| **Join User** | Join a specific user's current game; last-used account saved across sessions | Select account → "Join Place" dropdown → "Join User" → enter username |
| **Join by Job-ID** | Join a specific server instance using Job-ID | Enter Place ID & Job-ID → "Join Place" dropdown → "Job-ID" |
| **Join Smallest Server** | Automatically join the server with the lowest player count | "Join Place" dropdown → "Small Server" |
| **Favorite Games** | Save and quickly launch favorite games with optional notes | Click ⭐ next to Recent Games → add favorites |
| **Game List (Recently Played)** | Auto-save recently played games for quick access | Games auto-save on launch (configurable 5-50 games) |
| **Game Name Lookup** | Auto-fetch and display game names from Place IDs | Automatic when Place ID changes |
| **Launch Popup Disable** | Disable success notification popups | Settings → QOL tab → "Disable Launch Success Popup" |
| **Roblox Launcher Selection** | Choose your preferred Roblox launcher | Settings → Roblox tab → select Default, Bloxstrap, Fishstrap, Froststrap, or Roblox Client |
| **Launch Roblox Home (App / Browser)** | Dropdown on the homepage: launch the Roblox client to home, or open a detached Chrome to roblox.com/home logged in as the selected account | Click "Launch Roblox Home  ▼" → pick **Launch in App** or **Launch in Browser** |

## Multi Roblox

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Multi Roblox (Default Mode)** | Run multiple Roblox instances with mutex lock | Enable "Multi Roblox" → select "Default" method |
| **Multi Roblox (Handle64 Mode)** | Advanced mode using handle64.exe — works alongside already-running instances | Enable "Multi Roblox" → select "Handle64" → run as administrator |
| **Admin Relaunch Prompt** | Prompts to relaunch as admin when switching to Handle64 without elevated privileges | Automatic when selecting Handle64 without admin rights |
| **Handle64 Custom Launcher Support** | Handle64 method works correctly with Bloxstrap, Fishstrap, and Froststrap | Automatic when custom launcher is selected |
| **Error 773 Prevention** | Automatic lock of `RobloxCookies.dat` to prevent Error 773 | Activates when Multi Roblox is enabled |
| **Running Instance Check** | Warns if Roblox is already running when enabling Multi Roblox | Prompts to close existing instances |

## Auto-Rejoin System

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Auto-Rejoin Setup** | Configure automatic game rejoin for accounts | Click "Auto-Rejoin" → "Add" → select account & Place ID *or* a friend to join off |
| **Rejoin Configuration** | Set check interval, private server ID, job ID, and max retries | In Auto-Rejoin window → "Edit" existing config |
| **Presence Check Toggle** | Optionally rejoin only when player is not in the target Place ID | In Auto-Rejoin config → enable "Check if player is in target Place ID" (auto-disabled when "Join Off Friend" is set) |
| **Join Off Friend (captcha bypass)** | **The way to bypass the join captcha.** Roblox flags some accounts and forces a "Verifying you're not a bot" captcha on the normal (API) join path. Instead, the account joins by opening a friend's Roblox profile in a real browser and clicking **Join** — that trusted in-browser click isn't captcha'd, so the account gets into the game. Mutually exclusive with Place ID — fill one or the other | In Auto-Rejoin Add/Edit dialog → enter the friend's Roblox username in "Join Off Friend" |
| **Join-Off Ordering** | Dependent accounts wait until their target friend is in-game before launching. Start order doesn't matter — workers self-coordinate via presence checks | Automatic |
| **Join-Off Cycle Detection** | Saves are rejected if a `join_off_username` chain would form a loop (A → B → A) | Automatic at save time |
| **Auto-Kill Captcha Instances** | Watchdog that detects when a running instance is stuck on Roblox's "Verifying you're not a bot" security screen (even though presence still reports in-game) and automatically kills it, so the rejoin path relaunches it fresh | Automatic while auto-rejoin is active |
| **Multi-Select Auto-Rejoin** | Select multiple accounts at once in the Auto-Rejoin window | Hold Ctrl or Shift to select multiple accounts |
| **Start/Stop Individual** | Control rejoin status per account | Select account → "Start Selected" / "Stop Selected" |
| **Start/Stop All** | Bulk start/stop all rejoin configurations | Click "Start All" / "Stop All" buttons |
| **Active Status Display** | See which accounts are actively monitored | [ACTIVE] / [INACTIVE] status shown in list |
| **Remove Configuration** | Delete rejoin setup for an account | Select account → "Remove" |
| **Webhook Notifications** | Send Discord webhook alerts on rejoin events, errors, and failures | Configure webhook URL in Settings → Integrations |
| **Hourly Screenshot Webhook** | Automatically sends a screenshot to Discord every hour while auto-rejoin is active | Configure in webhook settings |
| **Ping on Error** | Ping a specific Discord user when a rejoin failure occurs | Set User ID in webhook settings |

## Settings & Tools

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Active Instances Window** | View all running Roblox instances in real time with username, Place ID, and PID | Settings → Tool tab → "Active Instances" |
| **Roblox Settings Editor** | Edit Roblox's local settings file directly from the app | Settings → Tool tab → "Roblox Setting" |
| **Lock Roblox Settings** | Sets the Roblox settings file read-only on every launch to prevent Roblox overwriting it | Settings → Tool tab → Roblox Settings → enable "Lock settings" |
| **Roblox Version Downloader** | Download and install any Roblox version by version hash | Settings → Tool tab → "Roblox Version" |
| **Switch Encryption Method** | Seamlessly switch between Hardware and Password encryption | Settings → Tool tab → "Switch Encryption Method" |
| **Wipe Data** | Securely overwrite all data in `AccountManagerData` | Settings → Tool tab → "Wipe Data" |
| **Window Position Memory** | Saves and restores the position of main window, Settings, Favorites, Auto-Rejoin, and Console Output | Automatic |
| **Start Menu Shortcut** | Add or remove a Windows Start Menu shortcut for the app | Settings → General tab → "Add to Start Menu" |
| **Rename Roblox Windows** | Automatically renames Roblox window titles to the account's username | Settings → Roblox tab → "Rename Roblox Windows with Account Name" |
| **Console Output** | Real-time color-coded log of all operations with timestamps | Settings → "Console Output" button; supports Copy All & Clear |
| **Update Checker** | Auto-checks for new releases on startup | Automatic; shows notification if update is available |
| **Auto Update** | Download and install the latest version automatically | Click "Auto Update" in the update notification |
| **About Tab** | View app version and access Discord/GitHub links | Settings → About tab |

## UI Customization

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Dark Theme System** | Fully customizable dark theme | Settings → Theme tab |
| **Color Customization** | 5 color pickers: Background Dark/Mid/Light, Text, Accent | Settings → Theme tab → click color picker icons |
| **Font Selection** | Choose from 7 preset fonts (Segoe UI, Arial, Calibri, etc.) | Settings → Theme tab → font dropdown |
| **Font Size Adjustment** | Adjust font size (8–16px) | Settings → Theme tab → size controls |
| **Always on Top** | Keep the window above all other windows | Settings → QOL tab → "Enable Topmost" |
| **Discord Quick Link** | Project Discord invite link (no in-app button) | Visit the Discord server link in the About tab or README |

## Encryption & Data Security

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Hardware Encryption** | Encryption tied to your PC's hardware — no password needed | Setup Wizard → choose "Hardware" |
| **Password Encryption** | Portable encryption requiring a password — works on any PC | Setup Wizard → choose "Password" |
| **No Encryption** | Store accounts unencrypted (not recommended) | Setup Wizard → choose "No Encryption" |
| **Encryption Status Indicator** | Shows encryption type in the UI | Displayed as [HARDWARE ENCRYPTED] / [PASSWORD ENCRYPTED] / [NOT ENCRYPTED] |
| **Password Prompt** | Prompts for password on startup when using password encryption | Automatic |
| **Portable Chromium** | Built-in Chromium browser download for environments without Chrome | Settings → Tools → "Browser Engine" → download Chromium |

## Anti-AFK

| Feature | Description | How to Use |
| :--- | :--- | :--- |
| **Anti-AFK Window** | Opens a dedicated maintenance window for anti-AFK controls | Roblox tab → click **Anti-AFK** |
| **Key Recording** | Record any keyboard or mouse input as the maintenance action | Anti-AFK window → click the action key button |
| **Press Time** | Set how long the chosen input is held during maintenance | Anti-AFK window → set press time |
| **Configurable Interval** | Set how often maintenance runs | Anti-AFK window → set interval |
| **30s Countdown Tooltip** | Shows a countdown before each maintenance cycle | Automatic while Anti-AFK is enabled |
| **Roblox RAM Trim** | Clears the working set of newly detected Roblox processes | Roblox tab → enable **Optimize Roblox Ram** |
