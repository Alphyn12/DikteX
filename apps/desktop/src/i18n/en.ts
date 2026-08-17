import type { Messages } from './tr'

/** İngilizce metinler. Şekli `tr` belirler; eksik anahtar derleme hatasıdır. */
export const en: Messages = {
  // ── Title bar ────────────────────────────────────────────────────────────
  'titlebar.minimize': 'Minimize',
  'titlebar.maximize': 'Maximize',
  'titlebar.restore': 'Restore',
  'titlebar.close': 'Close',

  // ── Navigation ───────────────────────────────────────────────────────────
  'nav.panel': 'Dashboard',
  'nav.history': 'History',
  'nav.settings': 'Settings',
  'nav.modules': 'MODULES',
  'nav.label': 'Main navigation',

  'module.audio': 'Audio & STT',
  'module.prompt': 'Prompt Studio',
  'module.meeting': 'Meetings',
  'module.automation': 'Automation',
  'module.vault': 'Vault & Privacy',

  'vault.unlocked': 'Vault unlocked',
  'vault.locked': 'Vault locked',
  'vault.summary': '{count} keys in Credential Manager · PII masking on',

  // ── Dashboard ────────────────────────────────────────────────────────────
  'panel.title': 'Today',
  'panel.subtitle': '{dictations} dictations · {apps} apps · {meetings} meeting',
  'panel.startDictation': 'Start dictation',
  'panel.recordMeeting': 'Record meeting',
  'panel.stopDictation': 'Stop dictation',
  'stat.dictations': 'DICTATIONS',
  'stat.dictations.unit': 'today',
  'stat.audio': 'AUDIO CAPTURED',
  'stat.audio.unit': 'seconds',
  'engineStrip.ready': 'Ready · waiting for shortcut',
  'engineStrip.detail': 'groq whisper-large-v3-turbo · pre-roll 1000 ms · gemini-3.5-flash-lite',
  'feed.empty': 'No dictations yet. Press Ctrl+Alt+Space to start.',
  'feed.pasted': 'pasted',

  'stat.words': 'WORDS DICTATED',
  'stat.words.unit': 'words',
  'stat.timeSaved': 'TIME SAVED',
  'stat.timeSaved.unit': 'minutes',
  'stat.fillers': 'FILLERS REMOVED',
  'stat.fillers.unit': '“uh / um”',
  'stat.latency': 'AVG. LATENCY',
  'stat.latency.unit': 'ms',

  'engineStrip.title': 'Hybrid processing · cloud',
  'engineStrip.note': 'no leading syllable lost',

  'feed.title': 'Recent dictations',
  'feed.viewAll': 'All · local SQLite search',

  'style.title': 'PERSONAL STYLE',
  'style.on': 'on',
  'style.off': 'off',
  'style.desc':
    'Edits you make in pre-flight are stored and added to later prompts as examples, so the model gradually writes like you.',
  'style.privacy':
    'This mode carries past dictation content into new requests — a note you wrote ' +
    'yesterday can appear in today’s prompt. That is why it is off by default. ' +
    'While on, every stored example is listed below, sensitive data is masked, and one button clears them.',
  'style.count': '{count} examples stored',
  'style.clear': 'clear all',
  'style.empty': 'No examples yet — edit some text in pre-flight',
  'style.hint': 'The {count} most recent examples are added to the prompt.',

  'replace.title': 'AUTO-CORRECT',
  'replace.count': '{count} rules',
  'replace.find': 'Find',
  'replace.findPlaceholder': 'omni voice',
  'replace.replace': 'Replace with',
  'replace.replacePlaceholder': 'DikteX',
  'replace.wholeWord': 'Match whole word (suffixes preserved)',
  'replace.duplicate': 'This rule already exists, or find and replace are identical',
  'replace.empty': 'No rules yet',
  'replace.remove': 'Delete rule',
  'replace.used': '{count}×',
  'replace.try': 'Test',
  'replace.tryPlaceholder': 'type a sentence to see the result',
  'replace.hint':
    'Different from the vocabulary: the vocabulary is a hint to speech recognition, ' +
    'these rules always apply. If Whisper keeps misspelling a name the same way, ' +
    'fix it here once.',

  'appModes.title': 'MODE PER APP',
  'appModes.refresh': 'refresh',
  'appModes.empty': 'No rules yet',
  'appModes.remove': 'Remove rule',
  'appModes.addFocused': 'Currently open: {app}',
  'appModes.pickMode': 'pick a mode…',
  'appModes.hint':
    'Rules apply only to the generic shortcut (Ctrl+Alt+Space). Pressing a mode ' +
    'shortcut directly keeps your choice — the rule does not override it.',

  'models.title': 'MODELS',
  'models.provider': 'Provider',
  'models.provider.openrouter': 'OpenRouter (paid · no training)',
  'models.provider.gemini': 'Gemini — direct (free · trains on data)',
  'models.provider.trainsWarning':
    'Gemini’s free tier uses the text you send for model training. The same ' +
    'model via OpenRouter does not. Prefer OpenRouter for sensitive content.',
  'models.provider.noKey': 'No key for this provider — add one under API VAULT.',
  'models.role.llm': 'Text processing',
  'models.role.vision': 'Vision (screen eye)',
  'models.source.user': 'selected',
  'models.source.default': 'default',
  'models.source.llm': 'from text model',
  'models.useDefault': '— use default —',
  'models.refresh': 'refresh list',
  'models.loading': 'loading…',
  'models.price': '${input} / ${output} · 1M tokens (in / out)',
  'models.priceUnknown': 'price unknown',
  'models.batchWarning':
    'This is a batch model — requests are queued and replies can take hours. Not suitable for dictation.',
  'models.hint':
    '{count} models listed, fetched live from OpenRouter. Batch models are hidden because they cannot serve interactive dictation.',
  'models.hintEmpty': 'Press “refresh list” to load models.',

  'queue.title': 'UNSENT RECORDINGS',
  'queue.count': '{count} waiting',
  'queue.attempts': '{count} attempts',
  'queue.retry': 'Retry',
  'queue.sending': 'Sending…',
  'queue.clear': 'Delete all',
  'queue.remove': 'Delete this recording',
  'queue.flushResult': '{sent} sent · {failed} waiting · {dropped} dropped',
  'queue.privacyNote':
    'Audio for these recordings is held on disk temporarily — something the app ' +
    'otherwise avoids. Sent recordings are deleted immediately; anything older than ' +
    '7 days is dropped. Text is written to history, not pasted.',

  'aside.actionItems': 'ACTION ITEMS',
  'aside.scratchpad': 'VOICE SCRATCHPAD',
  'aside.vocabulary': 'VOCABULARY SUGGESTIONS',
  'aside.rawIdeas': '{count} raw ideas',
  'aside.compile': 'Compile end of day',
  'aside.vocabNote': 'Misspelled {count} times this week.',
  'aside.batteryNotice': 'Switched to battery mode — dynamic selector dropped to {model}.',
  'aside.undo': 'Undo',

  // ── Settings ─────────────────────────────────────────────────────────────
  'history.eyebrow': 'HISTORY',
  'history.title': 'Search dictations',
  'history.subtitle': 'Search runs entirely locally — SQLite full-text index, nothing leaves the device',
  'history.search': 'Search history',
  'history.placeholder': 'search…',
  'history.clear': 'Clear search',
  'history.searching': 'searching…',
  'history.results': '{count} records',
  'history.empty': 'No dictations yet',
  'history.noMatch': 'No matching records',
  'history.export': 'Export',
  'history.exportMd': 'Markdown',
  'history.exportJson': 'JSON',
  'history.exported': '{count} records saved',
  'history.exportNote':
    'The exported file contains raw text — no masking is applied. Know what is inside before moving it elsewhere.',
  'history.copy': 'Copy to clipboard',
  'history.copied': 'Copied — press Ctrl+V',
  'history.delete': 'Delete',
  'history.deleteConfirm': 'Delete it?',
  'history.cancel': 'Cancel',
  'history.deleteAll': 'Delete all',
  'history.deleteAllConfirm': 'Delete all history?',
  'history.deletedAll': '{count} records deleted',
  'history.copyFailed': 'Clipboard is locked — another app may be using it',

  'settings.eyebrow': 'SETTINGS',
  'settings.title': 'Models & Shortcuts',
  'settings.subtitle': 'Each mode carries its own model, provider and global shortcut',

  'table.mode': 'MODE',
  'table.model': 'MODEL',
  'table.provider': 'PROVIDER',
  'table.latency': 'LATENCY',
  'unit.seconds': 's',
  'latency.stream': 'stream',
  'table.shortcut': 'SHORTCUT',
  'table.active': 'ACTIVE',


  'provider.groq': 'Groq',
  'provider.openrouter': 'OpenRouter',
  'provider.gemini': 'Gemini',
  'provider.hybrid': 'Hybrid',

  'toggle.preflight': 'Pre-flight preview',
  'toggle.preflight.desc': 'Opens an edit window before the output is pasted',
  'toggle.preflight.meta': 'required for mega-prompt',
  'toggle.autoStop': 'Auto-finish on silence',
  'toggle.autoStop.desc':
    'Recording ends by itself when silence follows speech — no need to reach for the keyboard',
  'toggle.autoStop.meta': '{seconds} s threshold',
  'toggle.autostart': 'Start with Windows',
  'toggle.autostart.desc':
    'Starts minimised to the tray — no window opens, shortcuts are ready.',
  'toggle.autostart.meta': 'starts in tray',
  'toggle.autostart.dev': 'installed builds only',
  'toggle.numbers': 'Convert numbers to digits',
  'toggle.numbers.desc':
    '“fifteen minutes” → “15 minutes”. Local and deterministic; ordinals are left alone.',
  'toggle.numbers.meta': 'local',
  'toggle.ptt': 'Push to talk',
  'toggle.ptt.desc':
    'Records while Ctrl+Alt+Space is held and stops on release. When off, the shortcut toggles.',
  'toggle.ptt.meta': 'installs a keyboard hook',
  'toggle.ptt.failed': 'Hook could not be installed — security software may be blocking it.',
  'toggle.ptt.privacy':
    'This mode installs a low-level keyboard hook that sees every key on the system. ' +
    'DikteX only tracks whether Ctrl, Alt and Space are held; no other key is stored, ' +
    'logged, or swallowed. The hook is never installed while the mode is off.',
  'toggle.pii': 'PII masking',
  'toggle.pii.desc':
    'National ID, card, IBAN and API keys are redacted before text processing',
  'toggle.pii.limit':
    'Audio still reaches the speech provider unmasked — the text to mask comes from there. Reading a password aloud sends that audio to the provider.',
  'toggle.pii.badge': 'LOCAL',

  'aside.chorded': 'CHORDED SHORTCUT',
  'aside.chorded.desc': 'Hold → pick a mode.',
  'aside.chorded.legend': '{k} code, {e} English, {m} mega-prompt.',
  'aside.chorded.status': 'no conflicts · {count} modes bound',
  'aside.apiVault': 'API VAULT',
  'aside.addKey': 'add',
  'aside.localServer': 'LOCAL SERVER',
  'aside.localServer.desc': 'REST + webhook open — external scripts can trigger the engine.',

  'training.badge': 'trains on data',
  'training.tooltip':
    "This provider's free tier uses submitted data for model training. Do not route sensitive content here.",

  // ── Engine status ────────────────────────────────────────────────────────
  'engine.starting': 'Starting engine',
  'engine.connected': 'Engine connected',
  'engine.disconnected': 'Engine disconnected',
  'engine.failed': 'Engine failed to start',
  'engine.retry': 'Retry',
  'engine.retrying': 'Reconnecting',
  'engine.port': 'port',

  // ── Tray menu ────────────────────────────────────────────────────────────
  'tray.show': 'Show DikteX',
  'tray.startDictation': 'Start dictation',
  'tray.quit': 'Quit',

  // ── HUD ──────────────────────────────────────────────────────────────────
  'hud.listening': 'Listening',
  'hud.preRoll': '{seconds} s taken from buffer',
  'hud.quickDictation': 'QUICK DICTATION',
  'hud.escCancel': 'Esc to cancel',
  'hud.stopHint': 'Finish: same shortcut · Pause: Ctrl+Alt+P · Cancel: Ctrl+Alt+Esc',
  'hud.paused': 'Paused',
  'hud.paused.hint': 'recording is on hold — paused time is not recorded',
  'hud.resumeHint': 'Resume: Ctrl+Alt+P · Finish: Ctrl+Alt+Space',
  'hud.processing': 'Processing',
  'hud.step.stt': 'transcribing speech',
  'hud.step.llm': 'cleaning up text',
  'hud.step.transcribe': 'Speech recognition',
  'hud.step.fillers': 'Filler removal · {count} sounds',
  'hud.step.polish': 'Punctuation and context',
  'hud.readyToPaste': 'Ready to paste',
  'hud.refine.hint': 'Refine by voice: Ctrl+Alt+Space → “make it shorter”',
  'hud.refine.listening': 'Listening for your change',
  'hud.refine.working': 'Rewriting…',
  'hud.paste': 'Paste',
  'hud.cancel': 'Cancel',
  'hud.fillersRemoved': '{count} fillers removed',
  'hud.localOnly': 'local only',
  'hud.error': 'Dictation failed',
  'hud.dismiss': 'Dismiss',
  'hud.noSignal': 'No sound from the microphone',
  'hud.silent': 'No speech detected',
  'hud.silent.hint': 'The recording contained no speech, so nothing was sent. Try speaking louder or closer to the microphone.',
  'hud.clipboard': 'Text is on the clipboard — press Ctrl+V',
  'hud.clipboard.hint':
    '{count} characters were copied to the clipboard but could not be sent to the target window. Nothing was lost; place your cursor and press Ctrl+V.',
  'hud.clipboard.retryHint':
    'Click the window you want the text in, then press Ctrl+Alt+V. ' +
    'Your edits here are kept.',
  'hud.deadMic': 'Microphone produces no sound',
  'hud.deadMic.hint': 'The selected microphone sends no signal at all. Pick a working device under Settings → MICROPHONE. (Virtual microphones such as NVIDIA Broadcast output silence when their own app is closed.)',

  'meeting.recording': 'Recording meeting',
  'meeting.recording.hint': 'microphone + system audio together',
  'meeting.channel.mine': 'Me',
  'meeting.channel.theirs': 'Other participants',
  'meeting.channel.silent': 'no sound',
  'meeting.stopHint': 'Finish: Record meeting button · Cancel: Esc',
  'meeting.transcribing': 'Transcribing',
  'meeting.summarizing': 'Summarizing',
  'meeting.working.hint': 'this may take a few minutes',
  'meeting.chunkProgress': 'chunk {done}/{total}',
  'meeting.done': 'Meeting summary ready',
  'meeting.noSummary': 'No summary was produced, but the full transcript is saved.',
  'meeting.copySummary': 'Copy summary',
  'meeting.copyTranscript': 'Copy transcript',
  'meeting.error': 'Meeting could not be processed',
  'meeting.start': 'Record meeting',
  'meeting.stop': 'Finish recording',
  'meeting.blockedByDictation': 'Cannot start a meeting recording while dictating',

  // ── Microphone ───────────────────────────────────────────────────────────
  'mic.title': 'MICROPHONE',
  'mic.systemDefault': 'System default',
  'mic.systemDefaultHint': 'Uses the device selected in Windows',
  'mic.refresh': 'Refresh',
  'mic.streaming': 'stream open',
  'mic.stopped': 'stream closed',
  'mic.noDevices': 'No microphone found',
  'mic.alwaysListening': 'Microphone listens continuously for zero latency',
  'mic.alwaysListeningHint':
    'The last second is kept in memory only, never written to disk, and never sent anywhere unless you press the shortcut.',

  // ── Spend ────────────────────────────────────────────────────────────────
  'spend.title': 'SPEND',
  'spend.today': 'today',
  'spend.month': 'this month',
  'spend.budget': 'budget',
  'spend.calls': '{count} calls',

  'mode.quick': 'Quick dictation',
  'mode.code': 'Code & refactor',
  'mode.translate_en': 'English translation',
  'mode.mega_prompt': 'Mega-prompt',
  'mode.image_prompt': 'Image prompt',
  'mode.sql': 'SQL',
  'mode.commit': 'Commit message',
  'mode.quick.desc': 'Cleans up speech and pastes it in a fitting format',
  'mode.code.desc': 'Reads the selected code and applies the requested change',
  'mode.translate_en.desc': 'Speak Turkish, paste English',
  'mode.mega_prompt.desc': 'Turns a rough idea into a structured prompt',
  'mode.image_prompt.desc': 'Builds a prompt for image generation models',
  'mode.sql.desc': 'Turns a described query into SQL',
  'mode.commit.desc': 'Produces a conventional commit message',
  'region.hint': 'Drag to select the area you want to ask about',
  'region.cancel': 'cancel',
  'mode.screen': 'Screen eye',
  'mode.screen.desc': 'Select a screen region, ask by voice',
  'hud.screenRegion': 'screen {width}×{height}',
  'hud.step.selection': 'Selected text · {count} characters',
  'hud.selectionUsed': 'selection {count} chars',
  'profile.code': 'code',
  'profile.chat': 'chat',
  'profile.document': 'document',
  'profile.terminal': 'terminal',
  'profile.spreadsheet': 'spreadsheet',
  'profile.email': 'email',
  'profile.browser': 'browser',
  'profile.plain': 'plain text',
  'table.shortcutConflict': 'conflict',
  'table.shortcutMoved': '{from} taken → moved',
  'hud.format.plain': 'plain',
  'hud.format.markdown': 'Markdown',
  'hud.format.plain_from_markdown': 'strip to plain',
  'hud.format.json_string': 'JSON string',
  'hud.format.html': 'HTML',
  'hud.format.code_block': 'code block',

  'hud.piiMasked': '{count} sensitive values hidden',

  'vocab.title': 'CUSTOM VOCABULARY',
  'vocab.add': 'Add term',
  'vocab.placeholder': 'new term',
  'vocab.empty': 'No terms yet',
  'vocab.count': '{count} terms',
  'vocab.hint': 'These terms are passed to both speech recognition and text processing',

  'snippets.title': 'TEMPLATE LIBRARY',
  'snippets.count': '{count} templates',
  'snippets.name': 'Template name',
  'snippets.namePlaceholder': 'template name — say this while dictating',
  'snippets.body': 'Template text',
  'snippets.bodyPlaceholder': 'Review this code and suggest improvements:',
  'snippets.triggers': 'Extra triggers',
  'snippets.triggersPlaceholder': 'extra triggers, comma separated (optional)',
  'snippets.duplicate': 'A template with this name already exists',
  'snippets.empty': 'No templates yet',
  'snippets.used': '{count}×',
  'snippets.try': 'Test',
  'snippets.tryPlaceholder': 'type a sentence to see which template matches',
  'snippets.tryHit': '“{name}” will trigger',
  'snippets.tryMiss': 'No template will trigger',
  'snippets.hint':
    'When a template name appears in your speech, the template is added to ' +
    'the prompt. Matching is fuzzy — “code review” also matches “review this code”.',

  // ── Common ───────────────────────────────────────────────────────────────
  'lang.switch': 'Language',
  'common.mockNotice': 'Sample data — engine connects in Phase 2',
}