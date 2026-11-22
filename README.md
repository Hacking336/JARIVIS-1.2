# J.A.R.V.I.S. 1.2
### Just A Rather Very Intelligent System

A personal AI assistant and Windows control center with system monitoring, natural-language interaction, voice integration, and permission-controlled actions.

## Features

- Real-time CPU, memory, disk, network, battery, and process monitoring.
- Local and cloud AI provider integrations.
- llama.cpp integration for local GGUF models.
- Voice recognition and text-to-speech.
- Native Windows desktop interface using PySide6 and Qt WebEngine.
- Optional Gmail and Outlook OAuth integration.
- Application launching and process management.
- Permission checks and confirmation for sensitive actions.

## Project Structure

- `jarvis/app/` - Main application and dashboard.
- `jarvis/tests/` - Automated tests.
- `jarvis/requirements.txt` - Python dependencies.
- `jarvis/.env.example` - Configuration template.
- `jarvis/desktop_main.py` - Native desktop interface.
- `jarvis/start_jarvis.bat` - Web dashboard launcher.
- `jarvis/start_jarvis_desktop.bat` - Desktop launcher.

## Requirements

- Windows 11
- Python 3.10 or later
- pip

## Installation

Open PowerShell in the repository folder:

    cd jarvis
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt

Create your local configuration:

    Copy-Item .env.example .env

Edit `.env` and configure your application settings. Generate a secure application secret using:

    python -c "import secrets; print(secrets.token_urlsafe(32))"

Replace the APP_SECRET_KEY placeholder with the generated value.

## Start JARVIS

For the web dashboard:

    .\start_jarvis.bat

Open http://127.0.0.1:3000

For the native desktop interface, install PySide6 with Qt WebEngine:

    pip install PySide6

Then run:

    .\start_jarvis_desktop.bat

## Local AI

Local inference uses llama.cpp and a compatible GGUF model.

The llama.cpp server executable and model are not included in this source repository. Obtain compatible files separately and configure their paths. The desktop launcher expects the server executable and Qwen3 model in the JARVIS project directory.

## Voice and Email

Voice features support Vosk, local TTS, and optional Fish Audio.

Gmail and Outlook integrations require separately configured OAuth credentials.

Configure optional services in your local `.env` file.

## Tests

From the `jarvis` directory:

    python -m pytest tests/ -v

## Security

- The application binds to 127.0.0.1 by default.
- Never commit `.env` files, passwords, API keys, or OAuth secrets.
- Sensitive actions use permission checks and confirmations.
- Public network deployment requires additional authentication and security configuration.

## Project Status

This repository contains the JARVIS application source and tests. The complete portable Windows runtime, local AI models, and external runtime dependencies are distributed separately.

## License

No open-source license has been declared. All rights remain with the project owner.
