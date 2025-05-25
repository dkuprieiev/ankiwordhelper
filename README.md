# 🎯 Anki Telegram Bot

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-20.0+-blue.svg)](https://python-telegram-bot.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A powerful Telegram bot that automatically generates high-quality Anki flashcards from English words. Simply send a word, and the bot creates a comprehensive flashcard with Ukrainian translations, IPA pronunciations, explanations, and example sentences.

## ✨ Features

### 🚀 Core Functionality
- **Instant Flashcard Generation**: Send any English word to create a detailed Anki card
- **AI-Powered Content**: Uses Ollama (Gemma2:9b) for intelligent card generation
- **Quality Assurance**: Multi-attempt generation with validation and merging for best results
- **Auto-Sync**: Automatically syncs your Anki collection after adding cards

### 📝 Card Content
Each flashcard includes:
- 🌐 **Ukrainian Translations** with part of speech
- 🔊 **IPA Pronunciation** (British & American)
- 📖 **Detailed Explanations** in English and Ukrainian
- 💡 **Example Sentences** with translations
- 🏷️ **Part of Speech** classification

### 🛡️ Security Features
- **Single-User Authentication**: Secure access with authentication code
- **Access Control**: Only one authorized user at a time
- **Security Logging**: Track all unauthorized access attempts
- **Admin Commands**: Monitor and manage security status

### 🔧 Smart Features
- **Spell Checking**: Automatic spell correction with suggestions
- **Duplicate Detection**: Prevents adding existing words
- **Session Management**: Maintains user state and preferences
- **Error Recovery**: Robust error handling and retry logic

## 📋 Prerequisites

- Python 3.8 or higher
- [Anki](https://apps.ankiweb.net/) desktop application
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed
- [Ollama](https://ollama.ai/) with Gemma2:9b model
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

## 🚀 Quick Start

You can run the bot either using Docker (recommended) or manually.

### 🐳 Option 1: Docker (Recommended)

#### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

#### Steps

1. **Clone the Repository**
```bash
git clone https://github.com/yourusername/anki-bot.git
cd anki-bot
```

2. **Configure Environment**
```bash
# Copy example environment file
cp env.example .env

# Edit .env with your settings
vim .env  # or use your preferred editor
```

3. **Generate Secure Auth Code**
```bash
# Generate a secure authentication code
make auth-code
# Or manually:
openssl rand -hex 16
```

4. **Start with Docker**
```bash
# Build and start all services
make up

# Or using docker-compose directly
docker-compose up -d

# View logs to get auth code if not set
make logs-bot
```

5. **Pull Ollama Model** (first time only)
```bash
make pull-model
```

The bot will automatically:
- Start Ollama service
- Pull the Gemma2:9b model
- Start Anki with AnkiConnect
- Start the Telegram bot

#### Useful Docker Commands
```bash
# View logs
make logs          # All services
make logs-bot      # Bot only

# Restart services
make restart

# Stop services
make down

# Clean everything (including data)
make clean

# Development mode with hot reload
make dev
```

### 💻 Option 2: Manual Installation

#### Prerequisites
- Python 3.8+
- [Anki](https://apps.ankiweb.net/) desktop application
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on
- [Ollama](https://ollama.ai/)

#### Steps

1. **Clone the Repository**
```bash
git clone https://github.com/yourusername/anki-bot.git
cd anki-bot
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Set Up Ollama**
```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the Gemma2:9b model
ollama pull gemma2:9b

# Start Ollama service
ollama serve
```

4. **Configure AnkiConnect**
   - Open Anki
   - Go to Tools → Add-ons → Get Add-ons
   - Enter code: `2055492159`
   - Restart Anki

5. **Configure Environment**
```bash
# Copy example environment file
cp env.example .env

# Edit .env with your settings
vim .env  # or use your preferred editor
```

6. **Start the Bot**
```bash
python main.py
```

### 📋 Required Environment Variables

```env
# Telegram Bot Token (required)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Security (required)
AUTH_CODE=your_secure_authentication_code_here

# Optional: Pre-authorize a user
AUTHORIZED_USER_ID=

# Ollama settings (Docker will override these)
OLLAMA_MODEL=gemma2:9b
OLLAMA_URL=http://localhost:11434/api/generate

# Anki settings
ANKI_DECK_NAME=Default
```

## 📱 Usage

### First-Time Setup
1. Start a chat with your bot on Telegram
2. Authenticate with: `/start YOUR_AUTH_CODE`
3. The bot will confirm successful authentication

### Daily Usage

#### Adding Words
Simply send any English word:
```
philosophy
```

The bot will:
1. Check spelling (suggest corrections if needed)
2. Verify the word doesn't already exist
3. Generate a comprehensive flashcard
4. Add it to your Anki deck
5. Auto-sync your collection

#### Available Commands
- `/start` - Initialize bot and start Anki
- `/sync` - Manually sync Anki collection
- `/stats` - View deck statistics
- `/security` - Check security status
- `/help` - Show help message

### Spell Correction Flow
When you send a misspelled word:
```
User: recieve
Bot: 🔍 Did you mean receive instead of 'recieve'?

Reply with:
• yes - to use 'receive'
• no - to keep 'recieve'
• cancel - to cancel

User: yes
Bot: ✅ Using corrected word: receive
```

## 🏗️ Project Structure

```
anki_bot/
├── main.py                 # Entry point with security
├── config.py               # Configuration management
├── anki_client.py          # AnkiConnect API wrapper
├── card_generator.py       # AI-powered card generation
├── validators.py           # Content validation logic
├── security_middleware.py  # Authentication & security
├── handlers/
│   ├── commands.py         # Command handlers
│   └── messages.py         # Message processing
└── utils/
    ├── spell_checker.py    # Advanced spell checking
    └── session_manager.py  # User session management
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | - | ✅ |
| `AUTH_CODE` | Secure authentication code | - | ✅ |
| `AUTHORIZED_USER_ID` | Pre-authorized Telegram user ID | - | ❌ |
| `OLLAMA_MODEL` | Ollama model to use | `gemma2:9b` | ❌ |
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434/api/generate` | ❌ |
| `ANKI_DECK_NAME` | Target Anki deck | `Default` | ❌ |
| `MAX_GENERATION_ATTEMPTS` | Max card generation retries | `4` | ❌ |
| `LOG_LEVEL` | Logging verbosity | `INFO` | ❌ |

### Customization Options

#### Change Ollama Model
```env
# Use a different model
OLLAMA_MODEL=llama2:13b
```

#### Target Different Deck
```env
# Use custom deck name
ANKI_DECK_NAME=English Vocabulary
```

#### Adjust Timeouts
```env
GENERATION_TIMEOUT=90
SYNC_TIMEOUT=45
SPELL_CHECK_TIMEOUT=30
```

## 🔒 Security

### Authentication Flow
1. Bot starts without authorized user
2. First user must authenticate with auth code
3. User ID is stored as the only authorized user
4. All other users receive "Unauthorized Access" message

### Security Commands (Authorized User Only)
- `/security` - View current security status and unauthorized attempts
- `/revoke` - Revoke your own access (requires confirmation)
- `/confirm_revoke` - Confirm access revocation

### Best Practices
- Use a strong, random authentication code (minimum 16 characters)
- Never commit your auth code to version control
- Regularly check unauthorized access attempts
- Rotate auth codes periodically
- Keep your server and dependencies updated

## 🐛 Troubleshooting

### Common Issues

#### "Anki is not running"
```bash
# Make sure Anki is installed
which anki

# Start Anki manually
anki &

# Or let the bot start it
/start
```

#### "Failed to connect to Ollama"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

#### "AnkiConnect error"
1. Ensure AnkiConnect add-on is installed
2. Check Anki → Tools → Add-ons → AnkiConnect → Config
3. Verify `http://localhost:8765` is accessible

#### Authentication Issues
- Verify `AUTH_CODE` in `.env` matches exactly (case-sensitive)
- Check for trailing spaces or special characters
- Ensure the bot was restarted after changing `.env`

### Debug Mode
Enable detailed logging:
```env
LOG_LEVEL=DEBUG
ENABLE_SECURITY_LOGS=true
```

## 🚀 Advanced Usage

### Pre-Authorizing Users
If you know your Telegram user ID:
```env
# Get your ID from @userinfobot
AUTHORIZED_USER_ID=123456789
```

### Custom Card Format
Modify `card_generator.py` to customize the flashcard format:
```python
# In format_for_anki() method
formatted_content = f"""<your custom HTML template>"""
```

### Multiple Environments
```bash
# Development
cp .env.dev .env
python main.py

# Production
cp .env.prod .env
python main.py
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for the excellent Telegram Bot API wrapper
- [AnkiConnect](https://github.com/FooSoft/anki-connect) for enabling Anki automation
- [Ollama](https://ollama.ai/) for providing local LLM capabilities
- [Anki](https://apps.ankiweb.net/) for the amazing spaced repetition software

## 📧 Support

If you encounter any issues or have questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Search existing [Issues](https://github.com/yourusername/anki-bot/issues)
3. Create a new issue with detailed information

---

<p align="center">Made with ❤️ for language learners</p>