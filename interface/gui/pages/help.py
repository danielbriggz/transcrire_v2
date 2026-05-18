from nicegui import ui


@ui.page("/help")
def help_page() -> None:
    with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-4"):
        ui.label("Help & Documentation").classes("text-2xl font-bold")
        ui.separator()

        with ui.expansion("Getting Started", icon="rocket_launch").classes("w-full"):
            ui.markdown("""
**Step 1:** Go to **Settings** and enter your Groq and Gemini API keys.

**Step 2:** Click **New Episode** and paste your podcast RSS feed URL.

**Step 3:** Enter the episode number and click **Fetch Episode**.

**Step 4:** Use the stage buttons (Transcribe → Generate Captions → Create Image)
or click **Run Full Pipeline** to process everything unattended.
            """)

        with ui.expansion("Pipeline Stages", icon="account_tree").classes("w-full"):
            ui.markdown("""
| Stage | What It Does |
|---|---|
| **Fetch** | Downloads audio and cover art from your RSS feed |
| **Transcribe** | Converts audio to text using Groq (cloud) |
| **Generate Captions** | Creates Twitter, LinkedIn, and Facebook posts |
| **Create Image** | Produces a 1080×1080 quote card image |
            """)

        with ui.expansion("Output Files", icon="folder").classes("w-full"):
            ui.markdown("""
All files are saved to your output directory (configurable in Settings):

- `audio.mp3` — episode audio
- `transcript.txt` — plain text transcript
- `transcript_timestamped.txt` — transcript with timestamps
- `captions.json` — all platform captions
- `quote_card.jpg` — quote card image
            """)

        with ui.expansion("Troubleshooting", icon="build").classes("w-full"):
            ui.markdown("""
**Transcription fails immediately**
→ Check your Groq API key in Settings. Ensure it starts with `gsk_`.

**Captions are empty or wrong**
→ Check your Gemini API key. Regenerate individual captions using the Regenerate button.

**Quote card is blank**
→ Ensure the Transcribe stage completed successfully before running Create Image.

**App opens but shows a blank page**
→ Try refreshing the browser tab. If persistent, restart the app.
            """)

        ui.separator()
        ui.link("← Back to Dashboard", "/").classes("text-blue-500")