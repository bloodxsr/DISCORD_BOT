# Discord AI Moderation Bot

A multipurpose Discord bot featuring automated moderation, AI-powered responses, and advanced blacklist management. Built with `discord.py`, Google Gemini AI, and SQLite, this bot helps manage communities efficiently by automating moderation and enhancing conversations with advanced AI capabilities.

---

## Features

1. **Automated Moderation:**  
   Detects and deletes messages with blacklisted words and escalates punishments automatically through warnings, final warnings, and kicking after repeated offenses.

2. **Blacklist Management:**  
   Easily add, remove, view, and reload blacklisted words from a shared `words.py` file. Supports paginated viewing and button navigation for convenient management.

3. **AI Responses:**  
   Ask questions and get AI-powered replies via the Google Gemini API with commands like `/ask` and `/joke`. Features rate limiting and message length restrictions for robust interaction.

4. **Persistent Warnings:**  
   Tracks user offenses persistently using SQLite (`warnings.db`) and handles escalating actions (warnings, final warnings, kicks).

5. **Manual Moderation Tools:**  
   Slash and context commands for kicking, banning, muting, unmuting, and managing roles with permission checks and user confirmation prompts.

6. **Welcome Messaging:**  
   Sends custom welcome messages on new user join with interactive embedded buttons linking to rules, chat, help, about, and perks.

7. **Admin Tools:**  
   Commands for server management with caching, permission controls, and easy command access via slash and context menus.

8. **Uptime Support:**  
   Optional keep-alive server support for hosted environments like Replit.

9. **syncing**
   commands are synced globally so pls be waty abt it. if uwanty faster syncing goforg particular guild ayncing

---

## Requirements

##### Add the following to your `requirements.txt`:
    aiohappyeyeballs==2.6.1
    aiohttp==3.12.15
    aiosignal==1.4.0
    annotated-types==0.7.0
    anyio==4.11.0
    asttokens==3.0.0
    async-timeout==5.0.1
    attrs==25.3.0
    blinker==1.9.0
    cachetools==5.5.2
    certifi==2025.8.3
    charset-normalizer==3.4.3
    click==8.3.0
    colorama==0.4.6
    comm==0.2.3
    debugpy==1.8.17
    decorator==5.2.1
    discord.py==2.6.3
    exceptiongroup==1.3.0
    executing==2.2.1
    Flask==3.1.2
    frozenlist==1.7.0
    google-ai-generativelanguage==0.6.15
    google-api-core==2.25.1
    google-api-python-client==2.83.0
    google-auth==2.40.3
    google-auth-httplib2==0.2.0
    google-genai==1.38.0
    google-generativeai==0.8.5
    googleapis-common-protos==1.70.0
    grpcio==1.75.1
    grpcio-status==1.71.2
    h11==0.16.0
    httpcore==1.0.9
    httplib2==0.31.0
    httpx==0.28.1
    idna==3.10
    itsdangerous==2.2.0
    Jinja2==3.1.6
    MarkupSafe==3.0.3
    multidict==6.6.4
    propcache==0.3.2
    proto-plus==1.26.1
    protobuf==5.29.5
    pyasn1==0.6.1
    pyasn1_modules==0.4.2
    pydantic==2.11.9
    pydantic_core==2.33.2
    pyparsing==3.2.5
    python-dotenv==1.1.1
    requests==2.32.5
    rsa==4.9.1
    sniffio==1.3.1
    tenacity==9.1.2
    tqdm==4.67.1
    typing-inspection==0.4.1
    typing_extensions==4.15.0
    uritemplate==4.2.0
    urllib3==2.5.0
    websockets==15.0.1
    Werkzeug==3.1.3
    yarl==1.20.1


SQLite3 is included as part of Python's standard library.

---

## Setup Instructions

1. Clone the repository and navigate to the project folder.
2. Install dependencies:  
   `pip install -r requirements.txt`
3. Add your Discord bot token in a file named `token.txt` (one line, no extra spaces).
4. (Optional) Add your Google API key in a file named `google.txt` or set it as an environment variable for AI features.
5. Customize your blacklist by editing `words.py` or using bot commands.
6. Launch the bot:  
   `python bot2.py`

---

## Usage

- Add the bot to your Discord server with permissions:  
  Manage Messages, Kick Members, Ban Members, Manage Roles, etc.
  
- Use `/commands` in Discord to view available admin and moderation commands.
  
- Automated moderation activates immediately, deleting blacklisted words and warning offenders.

- Use `/ask` for AI-powered chat responses and `/joke` for fun.

- Manage the blacklist dynamically with commands like `/addbadword`, `/removebadword`.

- Monitor user offenses with `/warnings`.

---

## Project Structure

##### /bot2.py # Main bot launcher
##### /keepAlive.py # Optional keep-alive server script
##### /cogs/
    ai.py # AI-powered commands (Google Gemini API)
    moderation.py # Manual moderation commands (kick, ban, etc.)
    automod.py # Automated moderation (blacklist, warnings)
    utils.py # Blacklist manager utility
    blacklist.py # Blacklist commands and list viewer
    words.py # Blacklist words list (editable)
    fun.py # for fun things where more issto be added. 
    welcome.py # just for the welcome thing 
##### /requirements.txt # Python dependencies


### please keep in mind that the welcome and the chat thing are case sensitive update it according to your own use. thank you.

## best regards lufy.
---

# UPDATES-
1. containers are added with the help of new UI style but it is advised to update them accordingly
2. to add leveling and achievement system.
