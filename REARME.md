# Anki Bot Project Structure

```
anki_bot/
├── .env.example
├── requirements.txt
├── main.py
├── config.py
├── anki_client.py
├── card_generator.py
├── validators.py
├── handlers/
│   ├── __init__.py
│   ├── commands.py
│   └── messages.py
└── utils/
    ├── __init__.py
    ├── spell_checker.py
    └── session_manager.py
```

## Setup Instructions

1. Clone the project
2. Copy `.env.example` to `.env` and fill in your tokens
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main.py`