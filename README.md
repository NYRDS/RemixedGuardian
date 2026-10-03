# RemixedGuardian

Community bots for Remixed Dungeon (NYRDS):

- `remixed_guardian_discord.py` — Discord moderation, Google Play reviews
  relay (`#reviews`), git-commit monitor, and community feedback/Q&A intake
  via direct messages.
- `community_tg.py` — Telegram long-poll bot: player questions/feedback via
  DMs, answers delivered back to the same chat.
- `announce.py` — post an announcement to Discord and Telegram at once.
- `rat_king_tg.py` — LLM text-RPG (dormant).

## Feedback & Q&A flow

Everything players write to the bots in DMs (plus every Google Play review)
is stored in `feedback.db` (sqlite). New questions are pushed to the admins
as a Discord DM.

Answers are composed manually and sent with an admin command — LLM
auto-drafts are suspended (see `utils/feedback.py` make_draft note):

    answer <id> <text>    send the answer to the player (same platform)
    fb                    latest entries
    fb <id>               entry details
    dismiss <id>          close without answering

Admins = `GOOGLE_PLAY_ADMINS` on Discord (DM the bot) and `TG_ADMINS` on
Telegram. GPlay reviews are answered the old way: reply to the relayed
message in `#reviews`.

## Announcements

    python3 announce.py -m "text"              # Discord + Telegram
    python3 announce.py -f post.md --pin       # + pin on Discord
    python3 announce.py -m "text" --tg-only
    python3 announce.py --dry-run              # check tokens/targets only

Targets: `CHANNEL_ANN` (Discord), `TG_ANNOUNCE_CHAT`/`TG_ANNOUNCE_THREAD`
(Telegram). Overrides: `--discord-channel`, `--tg-chat`, `--tg-thread`.

## conf.py (gitignored)

BOT_TOKEN, TG_API_TOKEN, MISTRAL_API_KEY (+ other LLM keys), Google Play
service account, channel ids, and the community settings:

    CHANNEL_ANN        # Discord announcements channel
    CHANNEL_FEEDBACK   # optional: channel for Q&A notifications (None = DM admins)
    TG_ANNOUNCE_CHAT   # Telegram chat for announcements
    TG_ANNOUNCE_THREAD # Telegram topic/thread id (or None)
    TG_ADMINS          # Telegram user ids allowed to run feedback commands
