# OutreachBot — Discord Bot Setup Guide

## Step 1 — Create Discord Application

1. Go to https://discord.com/developers/applications
2. Click **"New Application"** → name it **"OutreachBot"**
3. Go to **"Bot"** tab → click **"Add Bot"** → confirm
4. Under **"Token"** → click **"Reset Token"** → copy it
5. Save in `.env` as `DISCORD_BOT_TOKEN=<your_token>`

## Step 2 — Enable Privileged Gateway Intents

In the **Bot** tab, scroll to **Privileged Gateway Intents** and enable ALL three:
- ✅ **PRESENCE INTENT**
- ✅ **SERVER MEMBERS INTENT**
- ✅ **MESSAGE CONTENT INTENT**

Click **Save Changes**.

## Step 3 — Bot Permissions & Invite URL

1. Go to **OAuth2 → URL Generator**
2. Under **Scopes**, check:
   - `bot`
   - `applications.commands`
3. Under **Bot Permissions**, check:
   - Send Messages
   - Read Messages / View Channels
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
   - Use Application Commands
   - Connect (voice)
   - Speak (voice)
   - Use Voice Activity
4. Copy the generated URL at the bottom
5. Open in browser → select your server → **Authorize**

## Step 4 — Create Discord Server Channels

In your server, create this structure (right-click server name → "Create Channel"):

```
Category: OUTREACH CRM
├── #general          (Text Channel)
├── #bot-commands     (Text Channel)
├── #alerts           (Text Channel) ← Bot posts here automatically
├── #daily-summary    (Text Channel) ← Bot posts 8 AM IST daily
├── #lead-updates     (Text Channel) ← Stage changes
├── #logs             (Text Channel) ← Pipeline logs
└── voice-control     (Voice Channel) ← Speak commands here
```

## Step 5 — Get Channel & Server IDs

Enable Developer Mode: **Settings → Advanced → Developer Mode ON**

Then right-click each channel → **"Copy Channel ID"**

Right-click your server icon → **"Copy Server ID"**

## Step 6 — Fill in .env

Add these to your `.env` file:

```bash
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
DISCORD_ALERTS_CHANNEL_ID=alerts_channel_id
DISCORD_DAILY_SUMMARY_CHANNEL_ID=daily_summary_channel_id
DISCORD_LEAD_UPDATES_CHANNEL_ID=lead_updates_channel_id
DISCORD_LOGS_CHANNEL_ID=logs_channel_id
DISCORD_COMMANDS_CHANNEL_ID=bot_commands_channel_id
DISCORD_VOICE_CHANNEL_ID=voice_control_channel_id
```

## Step 7 — Install Dependencies

```bash
pip install "discord.py[voice]" python-dotenv aiohttp aiofiles
pip install SpeechRecognition pydub   # voice commands
# For Groq-based transcription (recommended, free):
# Just use GROQ_API_KEY already in .env — no extra install needed
```

## Step 8 — Start the Bot

```bash
cd "/Users/mohit/Desktop/LinkedIn Outreach"
python3 discord_bot/start_bot.py
```

You should see: `✅ OutreachBot online: OutreachBot#XXXX`

## Step 9 — Test

In your Discord server, type:
```
!stats
!pipeline status
!leads ready
```

Bot should respond immediately.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `discord.errors.LoginFailure` | Token is wrong — regenerate in Developer Portal |
| `Missing intent` | Enable all 3 intents in Developer Portal → Bot tab |
| Bot doesn't respond to `!` | Make sure MESSAGE CONTENT INTENT is on |
| Voice not working | Install ffmpeg: `brew install ffmpeg` |
| No channels found | Set all DISCORD_*_CHANNEL_ID in .env |
