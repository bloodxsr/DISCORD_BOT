# Discord AI Moderation Bot
## A multipurpose Discord bot featuring automated moderation, AI-powered responses, and advanced blacklist management. Built with discord.py, Google Gemini AI, and SQLite, this bot helps manage communities efficiently by automating moderation and enhancing conversations with advanced AI capabilities.

# Features
1. Automated moderation: Detect and delete messages with blacklisted words, escalating punishments.

2. Blacklist management: Easily add, remove, and view banned words from a shared file.

3. AI responses: Ask questions and get AI-powered replies via the Google Gemini API.

4. Persistent warnings: Tracks user offenses with SQLite and handles escalating actions (warning, kick, etc.).

5. Admin tools: Slash commands and context commands for easy server management.

6. Uptime support: Optional keep-alive server for use with services like Replit.


# Requirements
### Add these lines to your requirements.txt:
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

### kindly review this one before pasting    
SQLite3 is part of the Python standard library.



# Project Structure:
### /bot2.py            # Main bot launcher
### /keepAlive.py       # Optional: Keep-alive script for hosting platforms
### /token.txt          # Discord bot token file (DO NOT SHARE)
### /cogs/
     ai.py           # AI-powered commands (Google Gemini integration)
     moderation.py   # Manual moderation tools and commands
     automode.py     # Automated moderation (blacklist, warnings, punishments)
     utils.py        # Blacklist management utilities
     words.py        # List of blacklisted words
     blacklist.py
### /requirements.txt   # Python package requirements



# Setup Instructions
1. Clone the repository and navigate to the project folder.
2. Install dependencies.
(pip install -r requirements.txt)
3. Add your Discord bot token in a file named token.txt (one line, no extra spaces).
4. (Optional) Add your Google API key in google.txt for AI features in ai.py.
5. Customize your blacklist by editing words.py.
6. Launch the bot
(python bot2.py)



# Usage
-> Add the bot to your server and ensure it has the correct permissions (Manage Messages, Kick Members, Ban Members, etc.).

-> Use /commands in Discord for available admin/mod tools.

-> AI features and moderation will be active immediately.

-> The bot will automatically moderate according to your words.py blacklist.

# Credits
-> Built with discord.py, Google Gemini AI, and open source tools.

-> By your amazing lufy..
