# Third Chair Development Roadmap

Development priorities and feature tracking for Third Chair legal discovery tool.

---

## Priority 1: Critical Gaps

Features identified as critical for comprehensive legal discovery support.

| Feature | Status | Description |
|---------|--------|-------------|
| Miranda Warning Detection | Complete | Pattern detection for rights administration, waiver, and invocation |
| Cross-Statement Discrepancy Detection | Planned | Compare conflicting accounts between parties (victim vs. defendant) |

### Miranda Warning Detection
- [x] Design pattern detection approach
- [x] Add ReviewFlag enums (MIRANDA_WARNING, MIRANDA_WAIVER, MIRANDA_INVOCATION)
- [x] Implement regex patterns for reading/waiver/invocation
- [x] Add detect_miranda_events() function
- [x] Update TranscriptSummary with miranda_events
- [x] Add Miranda section to attorney reports
- [x] Write unit tests (28 tests passing)

### Cross-Statement Discrepancy Detection
- [x] Design proposition conflict detection in Skanda framework
- [x] Implement Evidence Workbench for fact extraction
- [x] Create embedding pipeline for semantic similarity
- [x] Build inconsistency detection using LLM analysis
- [x] Add timeline conflict detection
- [ ] Identify key claim categories (who initiated, physical contact, weapon use)
- [ ] Add discrepancy flagging to reports

---

## Priority 2: Enhancement Opportunities

Features that would significantly improve attorney workflow efficiency.

| Feature | Status | Description |
|---------|--------|-------------|
| Case Encryption (Vault) | Complete | AES-256 encryption for case directories with master password |
| GUI Application | Planned | Desktop GUI for Third Chair with case browser and evidence viewer |
| Defense Interview Parser | Planned | Recognize PD interview note formats (client bio, contacts, case notes) |
| Self-Defense Proposition Seeds | Planned | Auto-extract defensive claim indicators from transcripts |
| External Evidence Reference Detection | Planned | Flag mentions of Ring cameras, dashcams, surveillance footage |

### Case Encryption (Vault)
- [x] Core encryption module (AES-256-GCM for streaming, Fernet for small files)
- [x] PBKDF2-HMAC-SHA256 key derivation (480,000 iterations)
- [x] Session management with configurable timeout
- [x] CLI commands (vault-init, vault-unlock, vault-lock, vault-export, vault-status, vault-verify, vault-rotate)
- [x] TUI password dialog integration
- [x] Transparent Case.load/save with encryption support
- [x] EncryptedPath wrapper for subprocess compatibility (FFmpeg)
- [x] Migration tools (encrypt existing, export decrypted, verify integrity, rotate password)
- [x] Unit tests (36 tests passing)

### GUI Application
- [ ] Desktop GUI framework selection (PyQt6 or similar)
- [ ] Case browser and selection interface
- [ ] Evidence viewer with video playback
- [ ] Transcript editor with speaker assignment
- [ ] Report generation interface
- [ ] Vault password dialog integration

### Defense Interview Parser
- [ ] Analyze common PD interview document formats
- [ ] Extract client biographical information
- [ ] Parse bond hearing witness contacts
- [ ] Identify mental health/special needs flags
- [ ] Extract case notes and immediate tasks

### Self-Defense Proposition Seeds
- [ ] Define self-defense indicator patterns
- [ ] Detect provocation claims ("she came at me", "he swung first")
- [ ] Identify retreat impossibility statements
- [ ] Flag fear/threat perception statements
- [ ] Auto-generate Skanda proposits for self-defense issues

### External Evidence Reference Detection
- [ ] Pattern detection for surveillance mentions (Ring, Nest, dashcam)
- [ ] Flag timestamps when additional evidence is referenced
- [ ] Track potential exculpatory evidence sources
- [ ] Add to evidence inventory with "Referenced Evidence" section

---

## Priority 3: Future Enhancements

Features for consideration in future development cycles.

| Feature | Status | Description |
|---------|--------|-------------|
| Credibility Indicators | Backlog | Extract consistency/inconsistency markers from statements |
| Charge Assessment Suggestions | Backlog | AI-assisted potential charge identification |
| Prior Incident Detection | Backlog | Flag mentions of restraining orders, prior arrests, history |
| Witness Impeachment Prep | Backlog | Identify contradictions for cross-examination |

---

## Completed Features

Core functionality already implemented in Third Chair.

- [x] **Axon ZIP Ingestion** - Extract and classify files from Axon evidence packages
- [x] **Media Transcription** - Whisper-based speech-to-text with timestamps
- [x] **Speaker Diarization** - pyannote.audio speaker identification
- [x] **Spanish/English Translation** - Ollama-based translation with aya-expanse
- [x] **Language Detection** - FastText per-segment language classification
- [x] **Code-Switching Detection** - Bilingual segment flagging
- [x] **Threat Keyword Flagging** - Automatic detection of threat-related statements
- [x] **Violence Keyword Flagging** - Automatic detection of violence-related statements
- [x] **Admission Detection** - Flag potential admission statements
- [x] **Timeline Construction** - Chronological event ordering from all evidence
- [x] **Multi-Camera Sync** - Synchronized timeline across BWC sources
- [x] **Speaker Role Detection** - Officer/Victim/Suspect/Witness classification
- [x] **Witness Management** - Import, track, and match witnesses across evidence
- [x] **Document Processing** - PDF/DOCX/Image text extraction with OCR
- [x] **Axon Transcript Parser** - Native parsing of Axon-generated transcripts
- [x] **Bates-Numbered Reports** - Attorney-ready PDF with sequential numbering
- [x] **DOCX Report Generation** - Word document case reports
- [x] **Evidence Inventory** - Comprehensive evidence listing with metadata
- [x] **Viewing Guide** - Recommended timestamps for video review
- [x] **Skanda Framework** - Evidence-backed legal proposition evaluation
- [x] **Interactive Chat** - Natural language case research interface
- [x] **Terminal UI** - Split-panel case exploration interface
- [x] **Vision Analysis** - Ollama vision model for evidence photos
- [x] **Miranda Warning Detection** - Pattern-based detection of Miranda readings, waivers, and invocations
- [x] **Case Encryption (Vault)** - AES-256 encryption with master password protection
- [x] **Evidence Workbench** - LLM-based fact extraction, embedding, and inconsistency detection
- [x] **Work Item Management** - Attorney task tracking (investigations, actions, objectives)

---

## Version History

| Version | Date | Notable Changes |
|---------|------|-----------------|
| 0.1.0 | 2025 | Initial release with core pipeline |
| 0.2.0 | 2025-01 | Miranda detection, case encryption vault |
| 0.3.0 | 2026-01 | Evidence Workbench, work item management |
| 0.4.0 | TBD | GUI application, enhanced discrepancy analysis |

---

*Last updated: January 2026*
