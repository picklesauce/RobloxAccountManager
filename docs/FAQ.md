# ❓ FAQ

[← Back to README](../README.md)

Common questions from new users of Roblox Account Manager.

## Safety & Trust

**Is this a virus? Why does Windows Defender / my antivirus flag it?**
It's not. The `.exe` is unsigned (code-signing certificates are expensive), and account managers that automate logins commonly trip heuristic antivirus flags. The whole project is open source — every line is in this repo, and the released `.exe` is compiled directly from this code with no changes. If you don't trust the `.exe`, run it from source instead (Method 2 in the [README](../README.md#-installation)). To get past Defender SmartScreen: **More info → Run anyway**.

**Will I get banned for using this?**
Possibly — multi-accounting and automation can violate Roblox's Terms of Service. This tool is provided for educational purposes and you use it at your own risk. Use accounts you're willing to lose.

**Are my cookies/passwords sent anywhere?**
No. There's no telemetry or analytics. Network traffic is limited to Roblox's own APIs (account/game features), GitHub (update checks), and Discord (only if *you* configure a webhook/bot). Your cookies stay in the local `AccountManagerData/` folder, encrypted.

## Installation & Requirements

**What do I need to run it?**
Windows, and Google Chrome installed. That's it for the EXE. If you run from source you also need Python 3.7+ and the packages in `requirements.txt`.

**Does it work on Mac or Linux?**
No. It's Windows-only — it relies heavily on Windows APIs for window management, Multi Roblox, and anti-AFK.

**I don't have Chrome / can't install it. Can I still use it?**
Yes — go to **Settings → Tools → Browser Engine** and download the bundled Chromium. Firefox/Edge are not supported; the automation is built around Chrome/Chromium.

**How do I update?**
The app auto-checks for new releases on startup and shows a notification with an **Auto Update** button. You can also just download the latest `.exe` from the Releases page and replace your old one.

## Accounts & Cookies

**How do I add accounts?**
Several ways via the **Add Account** button/dropdown: log in through a real Chrome window (**Browser Login**, which also captures your password), paste a `.ROBLOSECURITY` **cookie** (single or multiple at once), or use the **JavaScript** bulk-add option.

**Where is my data stored, and is it safe to move?**
In the `AccountManagerData/` folder next to the EXE (`accounts.json`, `settings.json`, etc.), encrypted. To back up or move your accounts, copy this folder — but see the encryption questions below first.

**There's a warning icon next to an account — what does it mean?**
That account's `.ROBLOSECURITY` cookie has expired or is invalid. Re-add the account (browser login or fresh cookie) to fix it.

## Launching & Multi Roblox

**How do I open more than one Roblox at the same time?**
Enable **Multi Roblox**. *Default* mode handles the mutex lock for you. *Handle64* mode is more advanced (works alongside already-running instances) but must be run as administrator.

**The windows all stack on top of each other — can I auto-arrange them?**
Yes. In **Settings → QOL tab**, turn on **Auto Tile Windows** and/or **Auto Minimize Windows** (they're independent — with both on, windows tile first, then minimize). There are also manual **Tile / Minimize** buttons for instances that are already open.

**Which launcher should I pick (Bloxstrap, Fishstrap, etc.)?**
Default works for most people. If you already use a custom bootstrapper, pick it in **Settings → Roblox tab** so launches go through it. Handle64 Multi Roblox works with Bloxstrap/Fishstrap/Froststrap.

## Captcha & Auto-Rejoin

**Roblox keeps showing "Verifying you're not a bot" when I join — how do I get past it?**
Roblox flags some accounts and forces a captcha on the normal (API) join. The way around it is **Join Off Friend**: in the Auto-Rejoin Add/Edit dialog, enter a friend's username instead of a Place ID. The flagged account then joins by opening that friend's profile in a real browser and clicking **Join** — a trusted click that isn't captcha'd, so it lands in whatever game the friend is in. (Place ID and Join Off Friend are mutually exclusive — fill one or the other.)

**What does "auto-kill captcha instances" do?**
While auto-rejoin is running, it watches for instances that get stuck on that "Verifying you're not a bot" security screen (Roblox sometimes still reports the account as "in game"). When it detects one, it kills that instance and relaunches it fresh automatically.

**What is Auto-Rejoin and how do I set it up?**
It keeps accounts in a game by detecting disconnects and rejoining automatically. Open **Auto-Rejoin → Add**, pick an account, set either a Place ID *or* a friend to join off, then tune the check interval / max retries. Use **Start All** / **Stop All** to run everything. You can get Discord webhook alerts on rejoin events and even hourly screenshots.

## Encryption

**Which encryption mode should I choose?**
- **Hardware** — easiest; no password, but tied to *this* PC.
- **Password** — portable across PCs, but you must enter the password each startup.
- **None** — not recommended; cookies stored in plain text.

You can switch later via **Settings → Tool tab → Switch Encryption Method**.

**I forgot my encryption password — can I recover my accounts?**
No. The password is what decrypts your cookies; without it the data can't be recovered. You'd need to wipe and re-add your accounts.

**I copied my AccountManagerData folder to a new PC and my accounts won't load.**
That's expected with **Hardware** encryption — it's tied to the original machine. Before moving, switch to **Password** encryption (Settings → Tool tab), then copy the folder. With Password mode it'll work on any PC.

## Misc / Troubleshooting

**Can I keep an account from going AFK?**
Yes — open the **Anti-AFK** window (Roblox tab), record a key/mouse action, and set how often it runs.

**Where do I get help?**
Join the [Discord Server](https://discord.gg/TYnJXyEhgY) linked in the [README](../README.md#-support) and in the app's About tab.
