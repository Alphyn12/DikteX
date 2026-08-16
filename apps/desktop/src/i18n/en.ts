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
  'engineStrip.detail': 'groq whisper-large-v3-turbo · pre-roll 1000 ms · gemini-2.5-flash-lite',
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

  'aside.actionItems': 'ACTION ITEMS',
  'aside.scratchpad': 'VOICE SCRATCHPAD',
  'aside.vocabulary': 'VOCABULARY SUGGESTIONS',
  'aside.rawIdeas': '{count} raw ideas',
  'aside.compile': 'Compile end of day',
  'aside.vocabNote': 'Misspelled {count} times this week.',
  'aside.batteryNotice': 'Switched to battery mode — dynamic selector dropped to {model}.',
  'aside.undo': 'Undo',

  // ── Settings ─────────────────────────────────────────────────────────────
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

  'toggle.dynamicModel': 'Dynamic model selector',
  'toggle.dynamicModel.desc': 'Switches between model sizes based on battery / network state',
  'toggle.dynamicModel.meta': 'threshold 35% battery',
  'toggle.preflight': 'Pre-flight preview',
  'toggle.preflight.desc': 'Opens an edit window before the output is pasted',
  'toggle.preflight.meta': 'required for mega-prompt',
  'toggle.pii': 'PII masking',
  'toggle.pii.desc': 'National ID, card and API key redacted before leaving the device',
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
  'tray.show': 'Show OmniVoice',
  'tray.startDictation': 'Start dictation',
  'tray.quit': 'Quit',

  // ── HUD ──────────────────────────────────────────────────────────────────
  'hud.listening': 'Listening',
  'hud.preRoll': '{seconds} s taken from buffer',
  'hud.quickDictation': 'QUICK DICTATION',
  'hud.escCancel': 'Esc to cancel',
  'hud.stopHint': 'Finish: same shortcut · Cancel: Ctrl+Alt+Esc',
  'hud.processing': 'Processing',
  'hud.step.stt': 'transcribing speech',
  'hud.step.llm': 'cleaning up text',
  'hud.step.transcribe': 'Speech recognition',
  'hud.step.fillers': 'Filler removal · {count} sounds',
  'hud.step.polish': 'Punctuation and context',
  'hud.readyToPaste': 'Ready to paste',
  'hud.paste': 'Paste',
  'hud.cancel': 'Cancel',
  'hud.fillersRemoved': '{count} fillers removed',
  'hud.localOnly': 'local only',
  'hud.error': 'Dictation failed',
  'hud.dismiss': 'Dismiss',

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
  'vocab.title': 'CUSTOM VOCABULARY',
  'vocab.add': 'Add term',
  'vocab.placeholder': 'new term',
  'vocab.empty': 'No terms yet',
  'vocab.count': '{count} terms',
  'vocab.hint': 'These terms are passed to both speech recognition and text processing',

  // ── Common ───────────────────────────────────────────────────────────────
  'lang.switch': 'Language',
  'common.mockNotice': 'Sample data — engine connects in Phase 2',
}