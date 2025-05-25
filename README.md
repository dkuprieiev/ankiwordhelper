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




# Anki Bot Security Setup Guide

This guide explains how to set up and use the single-user security system for your Anki Telegram Bot.

## Overview

The security system ensures that only one authorized user can access and use the bot. It includes:

- **Authentication via secure code**: Users must provide a valid auth code to gain access
- **Single user restriction**: Only one user can be authorized at a time
- **Security logging**: All unauthorized access attempts are logged
- **Admin commands**: The authorized user can view security status and revoke access

## Initial Setup

### 1. Generate a Secure Authentication Code

Create a strong, unique authentication code. You can generate one using:

```bash
# Generate a 32-character random code
openssl rand -hex 16

# Or use Python
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 2. Configure Environment Variables

Update your `.env` file with security settings:

```env
# Required: Your secure authentication code
AUTH_CODE=your_generated_secure_code_here

# Optional: Pre-authorize a specific Telegram user ID
# Leave empty to require authentication on first use
AUTHORIZED_USER_ID=

# Enable security logging (recommended)
ENABLE_SECURITY_LOGS=true

# Maximum failed auth attempts
MAX_AUTH_ATTEMPTS=3
```

### 3. Update Your Code

Replace the following files with the secure versions:

1. Add `security_middleware.py` to your project root
2. Replace `main.py` with the secure version (`secure_main.py`)
3. Update `config.py` to include security settings

### 4. Deploy the Bot

Start the bot as usual:

```bash
python main.py
```

## Usage

### First-Time Authentication

When a user first interacts with the bot:

1. They will receive an "Unauthorized Access" message
2. They must authenticate using: `/start YOUR_AUTH_CODE`
3. Once authenticated, their Telegram user ID is stored as the authorized user

### Daily Usage

After authentication:
- The authorized user can use all bot commands normally
- No re-authentication needed unless access is revoked
- All commands work as before, but only for the authorized user

### Security Commands

The authorized user has access to these security commands:

- `/security` - View current security status and unauthorized attempts
- `/revoke` - Revoke own access (requires confirmation)
- `/confirm_revoke` - Confirm access revocation

### Handling Unauthorized Access

When unauthorized users try to use the bot:
1. They receive an "Unauthorized Access" message
2. The attempt is logged with timestamp and user info
3. The authorized user can view these attempts via `/security`

## Security Best Practices

### 1. Protect Your Auth Code

- **Never** commit the auth code to version control
- Use environment variables or secure key management
- Rotate the code periodically
- Use a strong, random code (minimum 16 characters)

### 2. Monitor Access Attempts

Regularly check unauthorized access attempts:

```
/security
```

This shows:
- Current authorized user ID
- Number of unauthorized attempts
- Recent attempt details

### 3. Secure Deployment

When deploying your bot:

- Use HTTPS for all communications
- Keep your server/VPS secure and updated
- Use a process manager (like systemd) with proper permissions
- Consider using Docker for isolation

### 4. Backup Considerations

- The authorized user ID is stored in memory
- If the bot restarts without `AUTHORIZED_USER_ID` set, re-authentication is required
- Consider persisting the authorized user ID securely if needed

## Troubleshooting

### "No authorized user configured yet"

This means no one has authenticated yet. Use:
```
/start YOUR_AUTH_CODE
```

### "Invalid authentication code"

- Check that your auth code matches exactly (case-sensitive)
- Ensure the `AUTH_CODE` environment variable is set correctly
- Check for trailing spaces or special characters

### Lost Access

If you lose access (e.g., changed Telegram account):

1. Stop the bot
2. Clear the `AUTHORIZED_USER_ID` in `.env`
3. Restart the bot
4. Authenticate again with the auth code

### Security Logs

To enable detailed security logging:

```env
LOG_LEVEL=DEBUG
ENABLE_SECURITY_LOGS=true
```

## Advanced Configuration

### Pre-Authorizing a User

If you know your Telegram user ID, you can pre-authorize it:

1. Get your Telegram user ID (send any message to @userinfobot)
2. Add to `.env`:
   ```env
   AUTHORIZED_USER_ID=123456789
   ```
3. Restart the bot

### Changing the Auth Code

To change the authentication code:

1. Update `AUTH_CODE` in `.env`
2. The current authorized user remains authorized
3. New authentications will require the new code

### Multiple Environment Support

For different environments (dev/prod):

```bash
# Development
cp .env.dev .env
python main.py

# Production
cp .env.prod .env
python main.py
```

## Security Considerations

### What This Protects Against

- ✅ Unauthorized users accessing your bot
- ✅ Multiple users using the bot simultaneously
- ✅ Unauthorized command execution
- ✅ Access attempt tracking

### What This Doesn't Protect Against

- ❌ Man-in-the-middle attacks (use HTTPS)
- ❌ Telegram account compromise
- ❌ Server-level security breaches
- ❌ Auth code exposure through logs

### Additional Security Measures

Consider implementing:

1. **Rate limiting**: Limit authentication attempts per IP/user
2. **IP whitelisting**: Restrict bot access to specific IPs
3. **Two-factor authentication**: Require additional verification
4. **Audit logging**: Log all bot actions for compliance

## Example Workflow

1. **Initial Setup**
   ```bash
   # Generate auth code
   AUTH_CODE=$(openssl rand -hex 16)
   echo "AUTH_CODE=$AUTH_CODE" >> .env

   # Start bot
   python main.py
   ```

2. **First Authentication**
   ```
   User: /start
   Bot: 🚫 Unauthorized Access...

   User: /start abc123def456...
   Bot: ✅ Authentication successful!
   ```

3. **Normal Usage**
   ```
   User: philosophy
   Bot: 🔄 Generating flashcard...
   ```

4. **Security Check**
   ```
   User: /security
   Bot: 🔒 Security Status
        Authorized User ID: 123456789
        Unauthorized Attempts: 2
   ```

## Conclusion

This security system provides a simple but effective way to restrict your Anki bot to a single authorized user. Remember to:

- Keep your auth code secure
- Monitor unauthorized attempts
- Update your code regularly
- Follow security best practices

For additional security needs or multi-user support, consider implementing a more robust authentication system with database storage and role-based access control.