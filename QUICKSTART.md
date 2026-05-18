
# Transcrire — Quick Start Guide

## What You Need Before Starting

1. **Groq API Key** — free at https://console.groq.com
2. **Gemini API Key** — free at https://aistudio.google.com

## First Run

1. Double-click `Transcrire.exe`
2. Your browser opens at `http://localhost:7860`
3. Click **Settings** and paste your API keys
4. Click **Save**
5. Restart `Transcrire.exe`

## Processing Your First Episode

1. Click **New Episode**
2. Paste your podcast RSS feed URL
3. Enter the episode number
4. Click **Fetch Episode**
5. Once fetched, click **Transcribe**
6. Once transcribed, click **Generate Captions**
7. Once captions are ready, click **Create Quote Card**

Or click **Run Full Pipeline** to do all four steps unattended.

## Where Are My Files?

All output files are saved to:
C:\Users<YourName>\transcrire_output<episode-id>\


- `audio.mp3` — downloaded episode audio
- `transcript.txt` — plain transcript
- `transcript_timestamped.txt` — transcript with [MM:SS] timestamps
- `captions.json` — all three platform captions
- `quote_card.jpg` — 1080×1080 quote card image

## Troubleshooting

**Nothing happens after clicking Transcribe**
- Check your Groq API key in Settings
- Ensure you have internet access

**Quote card has no text**
- Make sure the Transcribe stage completed first

**App won't start**
- Try running as Administrator
- Check that port 7860 is not in use by another application