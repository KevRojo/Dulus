# Build log

What landed in the codebase, newest first — releases of the app follow on their own schedule. This is a cleaned-up public version of the shared log that every agent working on the Dulus desktop app signs at the end of a session: product changes only — no code, no internals. The *italic* lines are how each change was verified.

---

## November 2026

**Nov 16 · Every current Claude, at its real price.** The cost meter priced Opus 4.6 and 4.8 at the old Opus 4 rate, three times too high, and Fable 5.1 at nothing at all. Every current Claude model now carries its list price, Fable 5.1 and Opus 5.5 their own cache-read prices, and Haiku 5.5 its long-prompt rate. *17 new tests, 16 of them failing on the old table · 5 of 5 mutations caught.*

**Nov 16 · When Dulus calls a Round Table, you see it.** A table Dulus convenes from the chat now sits in the Round Table view — its questions under Dulus's name, every round followed live even if the page opened midway, seats' permissions answered right there — and when Dulus adjourns, the page keeps what was said. Dulus hears back only about its own questions, once the whole table has finished, and never takes over a table you seated. *37 new tests, 7 of them in Chromium against the real server · 20 of the first 21 fail on the old code.*

**Nov 16 · Themes.** Settings → Appearance now has 17 themes — Daylight and Solarized Light among them — and "Match system": browse the list to preview the whole app live, press Escape to put yours back, and set your own accent on any theme, nudged for contrast when it would be hard to read. A view that crashes no longer takes the others down with it. *28 new tests, the interface ones in Chromium against the real build · 6 of 6 mutations caught · screenshots of all 17 themes.*

**Nov 16 · Switching starts fresh, right away.** Changing workspace or profile — from the menus, Settings or the terminal — saves the conversation where it happened and starts a new one there at once. Each profile keeps its own Loopback history and pinned memories, so nothing from the last workspace or profile leaks into the next. *26 tests on the real backend and agent loop, 5 in Chromium against the built interface · 18 of 18 mutations caught.*

**Nov 16 · Every Claude gets its real window.** Each Claude model now gets the context and output it actually has — up to a million tokens in and 128K out for the newest — through Anthropic, Bedrock or Runware, so long chats stop compacting early. And after a compaction, the summary that opens the compacted chat now actually reaches the model. *23 Claude model ids checked across routes and spellings · end to end against a stand-in Claude: the compacted chat opens with its summary, with zero rejections.*

**Nov 16 · Long Claude sessions stay up.** Long sessions with the newest Claude models — through Anthropic, Bedrock or Runware — no longer fail with a signature error once compaction or the sliding context window has trimmed old turns: Dulus sends back only the reasoning that still matches, and each turn keeps its text and tool calls. If a request is refused anyway, it goes again once without old reasoning, with a notice. *29 new tests against a stand-in Claude that enforces the signing rule and returns the exact reported error · 6 of 6 mutations caught.*

**Nov 16 · The shell safety check reads what actually runs.** The hard block on dangerous shell commands no longer trips on text the shell never executes — a docstring, a README or a commit message that shows an install one-liner — so those files can be written from the shell again, while anything a shell would run is still checked in full. *64 new tests, 17 of them failing on the old code · about 3,400 generated commands run through real bash, and nothing the check skipped was something bash executed · 18 of 20 mutations caught, the other 2 redundant.*

**Nov 16 · The live table keeps its pace.** The live Round Table view now lowers its resolution when frames slow down — as they did in the Mac's window — and raises it again when there's room; photos still come out at full size and recordings never change size. A covered window no longer leaves a finished seat stuck "typing", and a view left open overnight wakes up on time. *6 new tests in Chromium, all failing on the old page · on WebKit with a CPU-drawn canvas, from about 10 to about 21 frames per second.*

**Nov 14–16 · Always allow.** A command you keep approving can now be approved for good, in the app or the terminal — matched by prefix, or exactly for anything that deletes, moves, reaches the network or runs another command, and never in plan mode — and Settings keeps the list in check with a Manage dialog to find and forget rules. Along the way, a few commands that only looked read-only stopped being approved without asking, and permission cards wrap long paths instead of spilling off screen. *81 new tests for the rules · 4 new Chromium cases for the interface, 3 of them failing on the old one.*

**Nov 15 · Only an @ wakes a seat.** At the Round Table, a seat's letter in a list or a summary no longer wakes it — only an @ does — and every seat now knows each wake-up costs a whole turn: leaders @ each assignment, nobody @s to say thanks. *67 wake-rule tests, 3 new, one through the table's real routes · the old rule fails 12 of them, the old wording 2 more.*

**Nov 15 · A Meta error is an error.** When a Meta model's stream reports a failure partway through, the turn now ends as an error — the note still shows — instead of passing for the answer, and half-finished tool calls are dropped. *2 new tests.*

**Nov 14 · A stray backslash can't jam the chat.** When a model half-escapes a Windows path or a regex in a tool call, Dulus reads it anyway; a call that's still unreadable doesn't run, and the model is told why. Broken calls are never sent back in the history, so a conversation that had started failing on every turn — with any model — heals itself on the next message. *19 new tests, 3 through the app's own chat route against a server that rejects like the real ones · on the old code they reproduce both reported errors word for word · 6 of 6 mutations caught.*

**Nov 13 · Your cloud PC in the Workspace menu.** If your plan includes a cloud PC, it's the first choice in the Workspace menu, and Dulus on your desktop works on its files with all of its tools, kept in step before and after every turn. When both sides changed a file you keep both, deleting never wins over an edit, and what the desktop deletes lands in a trash folder on the cloud PC; commands still run on your computer. *26 tests with the real app on both ends, 4 in Chromium against the built interface · confirmed live against a real cloud PC: "Synced just now".*

**Nov 13 · Background jobs report into the running turn.** When a background job finishes while Dulus is mid-turn, the notice joins that turn like a steer — a "Background work finished" row in the reply — instead of starting a separate wake-up afterward that mostly repeated old news, and output already read inline is never announced again. *13 new tests on the real agent loop, 2 in Chromium · the cached prefix stays byte-identical in the requests the real provider SDKs build.*

**Nov 13 · The last seat gets to finish.** At the Round Table, the last seat still working is no longer stopped after two minutes just for being alone: the clock only runs while it isn't using a tool, up to fifteen minutes of solo work. The leaders, A and B, can be woken past the usual three times, within a cap per table, so reports and handoffs reach them in the same round. *7 new tests through the table's real route, 16 new wake-rule cases · 7 of 7 mutations caught.*

**Nov 12 · Dulus sees images, not just their text.** A new tool hands the actual pixels of an image — an ad, a video frame, a screenshot, something it generated — to the model that asked, with a crop to zoom in on small print, and opening an image file does the same. A model that can't see gets a description from a vision model you pick, or a clear note that it didn't see it, and an image never jams a conversation: if a provider refuses it, the request goes again without it. *66 new tests · end to end over real HTTP with the official OpenAI and Anthropic SDKs, against stand-in servers.*

**Nov 11 · Computer use sees the controls.** Reading the screen now finds the inputs, buttons, dropdowns, checkboxes and switches that text recognition misses — empty fields included, with their state — names each by its label and numbers them, so the agent acts on exactly the one it means and refuses if the screen changed. Every click and keystroke reports what changed, or that nothing did, a look-alike word inside a sentence is no longer taken for the button, and it can scroll. *27 new tests · on a real Linux desktop, the 5 steps of a form that used to fail now land, each confirmed by what the field shows.*

**Nov 11 · A malformed question can't crash the chat.** When a model sends a question's options in the wrong shape, Dulus still turns them into buttons — in the app, the terminal and Telegram — and if nothing is left to click, you can answer in your own words. *5 new tests, all failing on the old code; in Chromium against the built interface, the chat stays up.*

**Nov 10 · Dulus Work.** A new Worker tab lists paid offers — a bug, a test or a doc, each with a "done when" and a reward in Fuel: "Work on it with Dulus" puts the brief in your chat box without sending it, and "Submit work" sends your real changes with their evidence. Secret files never leave, anything that looks like a credential waits for your OK, and only verified work is paid — once. *47 server tests, 18 desktop tests on real git and 6 in Chromium · an adversarial review's 9 findings, each fixed with a test · the first real offer paid out the same day — once, even when verified twice.*

**Nov 10 · Astral Video.** Video gets its own view, with your own keys: pick a model and only the ratios and lengths it can do are offered, add a first frame, run up to three renders at once with Stop, then play the result or open it in its folder or in Artifacts. Choosing a video model for chat now tells you where video is made instead of failing with a provider error. *4 tests in Chrome against the real app routes: a render followed to the player, Stop, and the ratios and lengths each model offers.*

**Nov 10 · Skill packs.** A Packs tab in the Skills Market groups skill repos by task — Video, Design, 3D, Motion and Games — and asks first where they go: a new workspace and profile for the pack, or the ones you're using. A skill of the same name you got elsewhere is left alone, and the MCP servers a pack pairs with go through the MCP tab, which offers to review their code first. *21 new tests, 4 in Chromium against the built interface and the real routes.*

**Nov 9 · Stop lets go of the chat.** If a tool ignores Stop, the chat is handed back to you five seconds later anyway, and /save, /exit and a few other commands run at once even while a turn is stopping. Python cells (restarting the console), browser steps and skills now stop too. *16 new tests through the real app, 15 of them failing on the old code · 13 of 13 mutations caught.*

**Nov 9 · The browser agent handles uploads and pop-ups.** Dulus uploads files — or a whole folder — straight into a page without the system file picker, so the browser never stops to ask for confirmation, and it sees and answers the page's alerts and confirmations instead of having them silently dismissed. No more prompt to restore pages after a restart. *19 new tests, the browser ones in a real Chromium · 7 of 7 mutations caught · checked in a real browser window on a Linux desktop.*

**Nov 9 · One turn per seat.** A Round Table seat that's still busy finishes its turn before starting the next — its column says it's queued — so Meta models no longer reject the seat's history and drop it for the rest of the table. In the terminal's table, a seat's letter no longer ends up in the model name. *5 new tests through the real routes, against a stand-in for Meta's API that validates the same way.*

**Nov 9 · Telegram voice notes just work.** They're transcribed even on a computer with no local speech engine, and spoken replies use the voice of the language they're in — Spanish when it can't tell — instead of the phone's interface language.

**Nov 9 · Tab offers only real commands.** In the terminal, Tab completes just the commands in the catalog — the same list /help shows — while aliases and retired names still work when typed. *In processes posing as the shipped app: 123 suggestions instead of 179, exactly the catalog.*

**Nov 7 · Name a seat, and it wakes up.** At the Round Table, a seat that already finished its turn comes back in the same round when another seat calls on it — and only that seat. *54 new tests · 13 of 13 mutations caught · verified end to end in Chromium against the real server.*

**Nov 7 · Small hosted models get their real window.** Dulus-hosted models with smaller context windows are now sized correctly, so long chats compact in time instead of failing.

**Nov 4 · The Round Table, live.** A new button opens a drawing of the table built only from real events: words flowing from each seat, messages crossing the table, tasks traveling to their owners, decisions rising to you. Take a photo or record an MP4 — and hide the text before you share it. *51 new tests · 17 of 17 mutations caught · checked at 5, 12 and 26 seats.*

**Nov 4 · Drag an image back in.** Anything Astral Images generates can be dragged into the references — or added with one click — to keep iterating on a frame.

**Nov 4 · More Dulus-hosted models.** A second family of hosted models, paid in Fuel like the rest.

**Nov 3 · Context changes keep the cache warm.** Editing the context panel between turns no longer throws away the prompt cache, and long reasoning that arrives in one piece is never dropped.

**Nov 2 · Local models, tighter.** Local models with strict chat templates now work — Dulus adapts the request and remembers what each model accepts. Compaction keeps your question, and the context bar uses a realistic scale.

**Nov 1 · One way of reading the screen.** Computer use now reads the screen the same way on Windows, macOS and Linux — dark mode included — and lands on the word you asked for even with accents or small misreads. *Against a real app on a Linux X server: 6 of 6 clicks in light mode, 5 of 5 in dark mode.*

## October 2026

**Oct 31 · Decisions to make.** When the Round Table needs you, the question arrives as a card — context, options with their consequences, a recommended pick, what it's holding up — in its own panel above the task board. Keyboard shortcuts, a "decide one by one" mode, and the seat that asked hears your answer live. Also from the terminal and Telegram. *25 new tests, two of them in Chromium against the built interface.*

**Oct 25–31 · Security sweep.** Three high-severity findings from automated static analysis — in the MCP market, the plugin adapter and background jobs on Windows — fixed at the root, each pinned by regression tests that fail on the old code.

**Oct 30 · Big tables don't stall together.** Large Round Tables in tool-heavy loops no longer get stopped all at once under heavy load. *8 seats in parallel: 200 of 200 calls through.*

**Oct 30 · Crash-proof memory.** A crash in the middle of a write can no longer leave garbage that gets loaded as a memory. Damaged files are set aside and rebuilt on boot.

**Oct 29 · Bigger windows, lighter requests.** Hosted models get their documented context windows — some above a million tokens. Tools are no longer sent twice, and tool definitions — MCP servers included — are adapted to what Kimi models accept.

**Oct 28 · Memories land where they belong.** Every memory goes to your active profile, and recall finds what you just saved.

**Oct 27 · A nudge when the reply is ready.** If you switched away, the taskbar (Windows), the Dock (macOS) or the window (Linux) lets you know 30 seconds after Dulus finishes. No notifications.

**Oct 27 · An honest context meter.** It counts everything that's actually sent, long single requests compact correctly, and million-token windows are used where providers offer them.

**Oct 27 · Better installers.** A native macOS installer package, and on Windows a Program Files install — or just for you.

**Oct 26 · Artifacts.** A library for the documents and mini apps the agent builds: versions, previews, source and downloads. Mini apps run isolated, and images, videos and reports show up there too.

**Oct 26 · The MCP market, rebuilt.** About 1,800 servers with complete setup recipes, runtimes bundled with the app, servers and secrets kept per profile, and secrets encrypted at rest.

**Oct 26 · No more stalls after long thinking.** Models that reason in several steps keep going until they answer, and transient errors retry safely without running anything twice.

**Oct 25 · Updates clean up after themselves.** Every update used to leave a full copy of the app's assets behind. Old copies are now removed safely.

**Oct 24 · Telegram bridge.** The same conversation from your phone: text, voice notes, photos and files, live progress with a stop button, approvals as buttons. Pair with a link or a QR code.

**Oct 24 · Round Table seats stop running out of room.** Reasoning models no longer all hit their output limit at the same moment.

**Oct 23 · Models you use show up on their own.** After ten real replies, a model joins the autocomplete and the model pickers.

**Oct 23 · Honest errors.** When a provider drops the stream, you get the reason instead of an empty answer.

**Oct 22 · Stop means stop.** A hung command is killed the moment you press Stop, and your next message goes through instead of "a turn is still running". *14 new tests; after Stop, the next command answers in 0.11 s.*

**Oct 22 · Voice no longer closes the app.** The crash only happened in the compiled app. We traced it to a regression in the Python-to-native compiler, pinned the last good release and added a test that refuses to build with a bad one. *300 iterations and 400+ voice calls without a crash.*

**Oct 21 · Images and video with any key.** FLUX.2, GPT Image, Gemini and Imagen, Meta Muse and Runware for images; Veo, Sora 2 and Runware for video. Pick a model or type any `provider/model` id. From the first message, Dulus knows what your keys unlock.

**Oct 21 · Tables that organize themselves.** Every Round Table now has leaders who plan and assign, so seats stop stepping on each other's work.

**Oct 21 · The live overlay is back.** A merge had quietly removed it. Its tests now drive the real agent loop, so that can't happen silently again.

**Oct 21 · Plugins install into their own environment** instead of the system's Python.

**Oct 20 · Memories with a lifecycle.** Stale facts stop passing for truth: a newer memory on the same subject replaces the old one, volatile facts are flagged for re-checking, and nothing is ever silently deleted. *108 new tests.*

**Oct 20 · Prompt caching on more providers**, so long conversations cost less in more places.

**Oct 20 · Stop keeps the work already done.** Results that finished before you pressed Stop are kept, and the agent is told what might have started.

**Oct 19 · Computer use gets a real keyboard and a live overlay.** Dulus types native Unicode in any app and a small overlay follows along over full-screen apps, with approvals and a stop button. *In a real app on a Linux X server it typed «¿Qué tal? Él dijo: «Ñandú, Árbol, ÜBER» — mañana 😀» exactly, and the stop button cut the turn in 0.14 s.*

**Oct 19 · The Tasks board.** A native view of the Round Table's tasks: group by status or seat, drag to reassign, dependencies, and back to the same live table.

**Oct 19 · "Where were we?" works.** Loopback now includes your latest messages, even across compactions and resumed sessions.

**Oct 19 · SOCKS proxies just work.**

**Oct 18 · Snappier after long sessions.** Abandoned streams and connections are released, nothing is re-sent behind your back, Stop works before the first word arrives, and the tray icon closes with its window. *740 tests across 35 files in the focused run.*

**Oct 18 · Runware joins the model list.**

**Oct 16 · Keeps going after a reasoning-only reply** instead of stopping halfway.

**Oct 15 · Turn a repo into tools — verified.** AutoAdapter now proves every tool works before switching it on, and never hides a failure to look successful.

**Oct 15 · Plugins reload live**, per profile.

**Oct 15 · Images from any chat.** Any chat model that can use tools can generate images, with references you upload or paste.

**Oct 15 · Menus that work everywhere.** Command menus answer with buttons or numbers in the desktop app, WebChat and Telegram.

**Oct 15 · No orphaned browsers.** The browser the agent uses is reused while it's alive and cleaned up when it's done.

**Oct 14 · Fork, undo and Gist sync.** Branch a conversation, undo the last turn, and keep each conversation synced to its own private Gist.

**Oct 14 · Newer Gemini models** on Vertex and the Gemini API.

**Oct 13 · The cursor comes back.** After opening a report or switching views, typing goes straight to the chat box.

**Oct 2 · A warm cache across tools and turns.** Requests stay stable while the agent works, so long sessions are cheaper and faster.

**Oct 2 · Your steer draft is never lost.** Whatever you were typing in the steer bubble moves to the chat box when Dulus finishes.

**Oct 1 · Astral Voice speaks while it writes.** Speech starts before the reply is finished, and you can dictate straight into the chat box.

## September 2026

**Sep 30 · Tool packs with live switches.** Turn optional packs off from Settings, see what each one weighs in tokens, and the next request is lighter — no restart.

**Sep 30 · Live data with sources.** Markets, crypto and economic indicators, each value with its unit, date and source.

**Sep 30 · Meta's reasoning models, done right.** Reasoning summaries you can see, and reasoning that carries over between tool calls.

**Sep 27 · Tools that report honestly.** Failed commands keep their exit code and output, and parallel tool calls never lose their arguments.

**Sep 26 · The steer bubble.** Message Dulus while it works; it reads your note before its next step, without stopping.

**Sep 26 · Astral Voice speaks through the app**, with a big, readable transcript.

**Sep 26 · Background jobs follow your profile and workspace.**

**Sep 25 · Tidy tool calls and beautiful reports.** Consecutive tool calls fold into one row, and reports open as rich HTML in their own window.

**Sep 24 · Twenty-five agents, still smooth.** The Round Table draws only what you can see. *25 agents × 40 rounds: from 6,000 history elements and 5,001 layouts to 411 elements and 32 layouts.*

**Sep 24 · Closing the window closes everything.** No processes left behind.

**Sep 23 · Each workspace gets its own memory**, and you can still search across all of them.

## August 2026

**Aug 26 · The first pull request is merged.** From here on every change lands as a pull request merged by a human — 424 so far.

**Aug 18 · A silent retry when a provider is overloaded.**

**Aug 16 · Fuel goes live.** Pay for Dulus-hosted models by the token, topped up with $DULUS on Solana.

**Aug 15 · A live terminal panel.** Watch the commands the agent runs, as it runs them.

**Aug 15 · The shared log begins.** Every agent that works on the codebase signs an entry — 219 so far.

**Aug 10 · Native builds and installers** for Windows, macOS and Linux.

**Aug 6 · A real Stop button**, and the Round Table opens inside the app.

**Aug 5 · A browser pane inside the app.** Watch the agent browse in a real Chromium window.

## June – July 2026

**Jul 28 · A persistent Python console** — working memory outside the context window.

**Jul 24 · The Round Table loses its five-seat cap**, and the voice speaks three times faster.

**Jul 15 · Lookback.** The whole conversation stays searchable after it's compacted.

**Jul 14 · Astral Voice on its own stack**, hands-free.

**Jul 11 · The MCP market.**

**Jul 5 · Seats talk to each other.** An internal chat for Round Table seats and sub-agents.

**Jul 1 · The desktop app and the pet.**

**Jun 21 · The private tree begins.** "Hello world" — with 882 test functions on day one.

---

<sub>$DULUS is a utility and community token used to pay for Fuel on Dulus. Nothing here is financial advice.</sub>
