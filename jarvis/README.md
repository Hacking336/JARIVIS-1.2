# J.A.R.V.I.S. — Just A Rather Very Intelligent System

A personal AI control center for Windows 11 that monitors your computer, communicates through natural language and voice, and performs approved actions with clear user control.

## Features

### System Monitoring
- Real-time CPU, RAM, disk, battery, and network monitoring
- Process list with CPU/memory usage
- System alerts and health checks
- Bounded history buffers for graphs
- Configurable refresh intervals

### AI Assistant
- Provider-independent AI interface (local Ollama or cloud)
- Conversation history with SQLite persistence
- Intent classification and routing
- Tool-based action execution with permission checks
- Text and voice input/output

### Voice Integration
- Fish Audio TTS with selected voice model `14129c3e320149449d6bada6862f7338`
- Local TTS fallback via pyttsx3
- Speech recognition (Google, Vosk, or local)
- Interruptible speech playback
- Audio caching with cleanup

### Email Center
- Gmail and Outlook OAuth 2.0 support
- Inbox retrieval, search, and unread counts
- Draft creation and send confirmation
- Read/unread status tracking
- Secure token storage

### Application Monitor
- Running process list
- Approved application launcher
- Process termination with confirmation
- Protected process safeguards

### Reminders, Notes, and File Search
- SQLite-backed reminders with due dates
- Notes with tags and search
- File search within approved directories only
- Exclusion of sensitive system directories

### Security
- 127.0.0.1 binding by default
- CSRF protection and origin validation
- Secret redaction in logs
- Permission-based action authorization
- Audit logging for sensitive actions
- Confirmation dialogs for destructive operations

## Project Structure

```
jarvis/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration from environment
│   ├── api/
│   │   └── routes.py        # REST and WebSocket endpoints
│   ├── core/
│   │   ├── orchestrator.py  # Main JARVIS orchestrator
│   │   ├── conversation.py  # Conversation and provider factory
│   │   ├── intent_router.py # Intent classification
│   │   ├── permissions.py   # Permission manager
│   │   └── action_executor.py # Tool execution
│   ├── monitoring/
│   │   └── system_monitor.py # System telemetry
│   ├── voice/
│   │   ├── fish_audio.py    # Fish Audio TTS provider
│   │   ├── speech_input.py  # Speech recognition
│   │   └── speech_output.py # Audio playback
│   ├── integrations/
│   │   ├── ai/
│   │   │   └── providers.py # Local and cloud AI providers
│   │   ├── email/         # Email OAuth integration
│   │   ├── applications/  # Application launcher
│   │   └── notifications/ # Desktop notifications
│   ├── storage/
│   │   ├── database.py    # Database manager
│   │   └── repositories.py # Data access layer
│   ├── security/
│   │   ├── credentials.py # Credential storage
│   │   └── audit.py       # Audit logging
│   ├── models/            # SQLAlchemy models
│   └── dashboard/
│       ├── templates/     # HTML templates
│       └── static/        # CSS and JavaScript
├── tests/                 # Automated tests
├── data/                  # SQLite database
├── logs/                  # Application logs
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
├── start_jarvis.bat       # Windows startup script
└── README.md
```

## Setup

### Prerequisites
- Windows 11
- Python 3.10 or later
- pip (Python package manager)

### Installation

1. Clone or extract the project to `C:\JARVIS 1.2\jarvis`

2. Run the startup script:
   ```
   start_jarvis.bat
   ```

   This will:
   - Create a virtual environment
   - Install dependencies
   - Create the database
   - Start the server on http://127.0.0.1:8080

3. Open http://127.0.0.1:8080 in your browser

### Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
# Required: Set a secure secret key (32+ characters)
APP_SECRET_KEY=your-secure-random-string-here

# AI Provider: "local" or "cloud"
AI_PROVIDER=local
LOCAL_AI_BASE_URL=http://localhost:11434/v1
LOCAL_AI_MODEL=llama3.2:3b

# Fish Audio (optional)
FISH_AUDIO_API_KEY=your-fish-audio-api-key
FISH_AUDIO_VOICE_MODEL_ID=14129c3e320149449d6bada6862f7338

# Email OAuth (optional)
GMAIL_CLIENT_ID=your-gmail-client-id
GMAIL_CLIENT_SECRET=your-gmail-client-secret
```

## Usage

### System Monitoring
The dashboard shows live CPU, RAM, disk, battery, and network metrics. Refresh intervals are configurable in Settings.

### AI Assistant
Type a command or question in the assistant panel. Examples:
- "Give me a system status report"
- "How much RAM is available?"
- "Which applications are consuming the most memory?"
- "Check whether my internet connection is working"
- "Open Notepad"
- "Create a reminder for tomorrow"
- "Stop speaking"

### Voice
Click the microphone button to start voice input. Click the speaker button to speak the last response. Click the stop button to interrupt playback.

### Email
Connect a Gmail or Outlook account in Settings > Email. The assistant can list, search, and draft emails. Sending requires explicit confirmation.

### Applications
Approved applications can be launched from the Apps panel. Process termination requires confirmation and is blocked for protected system processes.

## Fish Audio Setup

1. Sign up at https://fish.audio
2. Obtain an API key from your account dashboard
3. Set `FISH_AUDIO_API_KEY` in `.env`
4. The voice model ID `14129c3e320149449d6bada6862f7338` is preconfigured
5. If no API key is set, the system falls back to local TTS (pyttsx3)

**Note:** Fish Audio requires a paid account for API access. The dashboard will show "Not configured" if no key is present.

## Email OAuth Setup

### Gmail
1. Go to Google Cloud Console
2. Create a project and enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Set `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` in `.env`
5. Use the "Connect Gmail" button in Settings

### Outlook
1. Go to Azure Portal
2. Register an application in Microsoft Identity Platform
3. Add Mail.Read and Mail.Send permissions
4. Set `OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET`, and `OUTLOOK_TENANT_ID` in `.env`
5. Use the "Connect Outlook" button in Settings

## Local AI Setup

### Ollama (Recommended)
1. Install Ollama from https://ollama.com
2. Pull a model: `ollama pull llama3.2:3b`
3. Set `AI_PROVIDER=local` and `LOCAL_AI_BASE_URL=http://localhost:11434/v1`

### Cloud AI
1. Set `AI_PROVIDER=cloud`
2. Set `CLOUD_AI_API_KEY` to your OpenAI or Anthropic API key
3. Optionally set `CLOUD_AI_BASE_URL` for custom endpoints

## Testing

Run the automated test suite:
```
python -m pytest tests/ -v
```

Tests cover:
- System telemetry parsing
- Missing metrics and unavailable sensors
- AI provider timeouts
- Fish Audio authentication and failure handling
- Email OAuth state and permission checks
- Draft creation and send confirmation
- Tool argument validation
- Unauthorized action rejection
- Cancellation
- Audit logging and secret redaction
- Local database operations
- API security boundaries

## Troubleshooting

### Server won't start
- Check that port 8080 is not in use
- Verify Python 3.10+ is installed
- Check `.env` for syntax errors

### No system metrics
- Ensure `psutil` is installed: `pip install psutil`
- Run as administrator for process details

### Voice not working
- For Fish Audio: verify API key and internet connection
- For local TTS: install `pyttsx3`
- For speech recognition: install `SpeechRecognition` and `pyaudio`
- Check microphone permissions in Windows Settings

### Email not connecting
- Verify OAuth credentials in `.env`
- Ensure redirect URI matches: `http://localhost:8080/auth/gmail/callback`
- Check firewall settings

### AI not responding
- For local: ensure Ollama is running and model is pulled
- For cloud: verify API key and internet connection
- Check `AI_PROVIDER` setting

## Security Notes

- The server binds to 127.0.0.1 only by default
- API keys are never exposed to the frontend
- Email tokens are encrypted at rest
- Sensitive actions require confirmation
- Audit logs record all sensitive operations
- Conversation history can be cleared in Settings

## Verified Working Features

- System telemetry (CPU, RAM, disk, battery, network, processes)
- Dashboard with live updates
- AI chat with local and cloud providers
- Intent classification
- Permission-based action execution
- Fish Audio TTS integration
- Local TTS fallback
- Speech recognition (Google, Vosk)
- Email OAuth flow (Gmail, Outlook)
- Reminder and note management
- File search in approved directories
- Application launcher
- Process termination with confirmation
- Audit logging
- WebSocket real-time updates

## Unimplemented Features / External Requirements

- Desktop-wide wake-word detection (requires additional dependencies)
- GPU monitoring (requires `pynvml` or `GPUtil`)
- Persistent background reminder service (requires Windows Task Scheduler)
- Email attachment download (requires additional OAuth scopes)
- Multi-user authentication (single-user design)
- Remote access (requires authentication and TLS setup)

## License

This project is provided as-is for personal use.