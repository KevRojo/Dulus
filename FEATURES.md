# What Dulus does

What the Dulus desktop app does — never how it does it. Everything on this page ships in the app you [download from dulus.ai](https://dulus.ai/download/).

**At a glance:** 117 built-in tools · 123 commands · 26 model provider integrations · up to 26 agents at one table · ~1,800 MCP servers in the market · 17 themes · replies in 22 languages.

Every count on this page was rechecked against the edition customers download on November 16, 2026 — see [the audit](AUDIT.md).

---

## The Round Table

- **Up to 26 seats, any mix of models.** Put different models at one table, on the same problem, at the same time.
- **A shared task board.** Seats claim, update and finish tasks you can see and edit.
- **A table that organizes itself.** Leaders plan and assign, so seats stop stepping on each other's work.
- **Call a seat with an @.** A seat that already finished its turn comes back in the same round when another seat @-mentions it, and only then: a name in a list or a summary wakes no one.
- **Decisions to make.** What only you can decide arrives as a card: the question, the context, numbered options with their consequences, a recommended pick and what it's holding up. Answer one by one from the keyboard; the seat that asked hears your answer live. Also from the terminal, and from Telegram by command.
- **The live view.** A drawing of the table built only from real events — words flowing from each seat, messages crossing the table, tasks traveling to their owners, decisions rising to you. Take a photo, record a video, or hide the text before you share it.
- **The Tasks board.** Group by status or by seat, drag a card to reassign it, chain dependencies, see what's waiting on you, and jump back to the same live table.
- **When Dulus calls a table, you see it.** A table Dulus convenes from the chat sits in the Round Table view, every round followed live, and Dulus never takes over a table you seated.
- **Smooth at scale.** Tested with 25 agents and 60,000 history entries on one page.

## Hands on your computer

- **See, click and type in any app** — in any language, accents, ñ and emoji included — on Windows, macOS and Linux (under X11).
- **Sees the controls, not just the text.** Inputs, buttons, dropdowns, checkboxes and switches, empty ones included, each named by its label; every click and keystroke reports what changed, or that nothing did.
- **Reads the screen in light and dark mode**, and finds the word you asked for even with small misreads.
- **A live overlay while it drives.** Follow the conversation over full-screen apps without it ever stealing your keyboard.
- **Approve or stop from the overlay.** Permission prompts appear on top of whatever app is open; the stop button ends the turn.
- **A real browser.** A Chromium pane inside the app where you watch the agent browse. It uploads files and folders into a page and answers the page's own alerts and confirmations.
- **A live terminal panel.** Watch the actual shell the agent is using, command by command.
- **Long jobs in the background.** Hand off long tasks and keep chatting; the job wakes Dulus up when it's done.
- **A persistent Python console.** Working memory that lives outside the context window.

## Voice

- **Astral Voice.** A hands-free conversation: it listens, thinks and starts talking before the reply is finished.
- **Cut in with a tap.** Tap the orb mid-sentence and it stops to listen.
- **A real transcript.** Full messages beside the orb, with formatting, timestamps and the message being spoken highlighted.
- **Dictation in the chat box.** Talk into the composer; your words stay a draft until you send them.

## Your phone

- **Telegram bridge.** The same conversation from your phone: text, voice notes (transcribed even with no local speech engine), photos, albums and files.
- **Live progress with a stop button**, approvals and questions as buttons, and generated images delivered as photos.
- **Pair with a link or a QR code.** It keeps answering even while the desktop window is hidden.
- **WebChat.** The same chat in a browser on your computer.

## Memory

- **Profiles.** Memories stay with the profile they came from, so separate profiles never mix. Switching profile or workspace starts a fresh conversation at once.
- **Facts with a lifecycle.** A newer memory on the same subject replaces the old one, facts that go stale get flagged for re-checking, and old memories are archived — never silently deleted.
- **Crash-proof.** A crash in the middle of a write can't corrupt your memories; damage is detected and repaired on boot.
- **Loopback.** The whole conversation stays searchable after it's compacted. Ask "where were we?" and get a real answer.
- **Search everywhere.** Reach the memories of every other workspace when you ask for it.

## Models

- **26 provider integrations**, including Anthropic, OpenAI, Google Gemini and Vertex, AWS Bedrock, Azure, DeepSeek, Kimi, Qwen, GLM, MiniMax, Meta, Perplexity, Cloudflare Workers AI and Runware.
- **Local models** with Ollama and LM Studio.
- **Dulus's own hosted models**, paid by the token in Fuel. No keys needed.
- **One reasoning dial.** A single 0–4 thinking setting that works the same on every model.
- **Big windows.** Up to a million tokens where the provider offers it — every Claude at the window it really has — and a context meter that counts everything actually sent.
- **An honest cost meter.** Every current Claude model at its list price, cache reads and writes included.
- **It sees images.** Models that can see get the actual pixels of an image, a frame or a screenshot; models that can't get a description, clearly marked as one.
- **Cache-friendly by design.** Requests stay stable across tools and turns, so providers can cache them and long sessions cost less.
- **Learned models.** Any model you use for more than ten replies joins the autocomplete on its own.
- **Batch jobs** at batch prices where the provider offers them.
- **Honest errors.** When a provider is overloaded or a stream drops, you get the reason — never an empty reply. A malformed tool call or a stray backslash never jams the conversation.

## Create

- **Astral Images.** Generate with FLUX.2, GPT Image, Gemini and Imagen, Meta Muse or Runware models — or type any `provider/model` id. Add references, and drag any result back in as a reference to keep iterating.
- **Astral Video.** Video with your own keys — Veo, Sora 2 and Runware models — in a view of its own: only the ratios and lengths each model can do, a first frame, up to three renders at once.
- **Images from any chat.** Any chat model that can use tools can generate an image mid-conversation.
- **Knows what your keys unlock.** From the first message, Dulus knows which image, video and voice capabilities your keys enable — it only checks which keys exist, never their values.
- **Artifacts.** A library for the documents and mini apps the agent builds: versions, previews, source and downloads. Mini apps run isolated, and your images, videos and reports show up there too.
- **Reports.** Rich HTML reports that open in their own window and stay linked in the chat history.

## Extend

- **MCP market.** About 1,800 servers with complete setup recipes, runtimes included, with servers and secrets kept per profile and secrets encrypted at rest.
- **AutoAdapter.** Point it at a GitHub repo and get tools — each one verified before it's switched on.
- **Plugins** you can toggle and reload live, per profile.
- **Skills** — bundled ones, plus skill directories you can search and install from.
- **Skill packs.** Curated skill repos by task — Video, Design, 3D, Motion and Games — installed into a workspace and profile of their own, or the ones you use.
- **Tool packs.** Switch optional packs on and off — Mr. Dulus, Solana, live data feeds and a codebase graph — and see what each one costs in tokens before you do.
- **Live data with sources.** Markets, crypto and economic indicators, each value with its unit, date and source.
- **Sub-agents.** Delegate work to background agents — up to five at once, nested five deep, optionally each in its own git worktree.

## Control

- **Permission modes:** auto, manual, accept-all and plan.
- **Approvals everywhere** — in the app, the pet, the overlay and Telegram. The first answer wins.
- **Always allow.** Approve a command for good — by prefix, or exactly for anything that deletes, moves, reaches the network or runs another command — and find or forget the rules in Settings. Never in plan mode.
- **Steer mid-task.** A bubble over the chat box lets you message Dulus while it works; it reads your note before its next step. Whatever you were typing when it finished moves into the chat box.
- **A Stop that really stops.** A hung command is killed the moment you press Stop, and your next message goes straight through.
- **Checkpoints, undo and fork.** Rewind a conversation or branch it, and back sessions up to a secret GitHub Gist.
- **Audit trail and budgets.** See what the agent wrote, edited, ran and clicked, and cap the tokens and tool calls it can use.
- **Proactive check-ins and reminders.** Dulus can come back to you on its own.

## The desktop app

- **A native app** for Windows, with macOS and Linux builds published on the download page as they're ready.
- **Dulus OS** — a web desktop with its own apps, inside the app.
- **A desktop pet** — a small companion with its own chat, approvals and a stop button.
- **A nudge when the reply is ready.** If you switched away, the taskbar (Windows), the Dock (macOS) or the window (Linux) lets you know. No notifications.
- **Keyboard-first.** Start typing in the chat view and it goes straight to the box.
- **Tidy tool calls.** Consecutive tool calls fold into one row you can open.
- **Fuel wallet.** Balance, a deposit address with a QR code, and your history.
- **One-click updates** on Windows.
- **17 themes**, light and dark, with Match system and your own accent on any of them.
- **Replies in 22 languages**, 34 regional settings.
- **Your cloud PC in the Workspace menu.** With a plan that includes one, Dulus works on its files with all of its tools, kept in step before and after every turn.
- **Dulus Work.** A Worker tab with paid offers — a bug, a test or a doc, each with a "done when" and a reward in Fuel. Only verified work is paid, once.
- **Closing the window closes everything.** No orphan processes left behind.

---

<sub>$DULUS is a utility and community token used to pay for Fuel on Dulus. Nothing here is financial advice.</sub>
