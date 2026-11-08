# Video skill installation and connection setup

Source: https://www.youtube.com/watch?v=9M8pYsnDFes

Installed 62 new skill directories into `C:\Users\Divansh Kapoor\.codex\skills`; all 62 are still present. The Codebase Memory installer subsequently added its own `codebase-memory` skill and Codex integration. Completed the companion runtime and connection setup described below. Video Use transcription is intentionally unconfigured at the user's request.

| Video entry | Result |
| --- | --- |
| Codex Slides | Installed all 7 skills and the official plugin. Installed runtime dependencies, completed the production build, repaired native Windows launching, and passed the official live MCP probe: 38 tools, live APIs and Browser link. HTTP readiness returned 200. |
| Oh My Codex | Installed 29 published skills and runtime 0.21.44; completed user-level setup, native hooks, prompts and agent profiles. Installed psmux 3.4.0. General doctor reported 20 passed, 1 informational non-OMX-session warning and 0 failed; final team diagnostics passed. |
| Codebase Memory MCP | Installed 0.12.1 and configured Codex only, including skill, profiles and additive hooks. MCP handshake exposed 17 tools. No repository indexing was requested or performed as a test. |
| Research Workflow | Description points to a prompt post and the OpenAI plugin catalog, rather than a standalone skill package. No replacement skill was invented. |
| First Customer Finder | Installed `first-customer-finder`. Installed Python 3.12.10; both report and history helper CLI checks passed. |
| Lazy Web | Installed all 15 skills. Connected the official public endpoint and verified its 9 tools. Also connected the account endpoint: OAuth login completed and Codex reports OAuth authentication. The user explicitly approved read/write workspace access and selected the login email. No paid report or compute-credit operation was run; available report depth remains subject to the account plan. |
| Text to Lottie | Installed `text-to-lottie`. Its project-specific Skottie player is set up when creating an animation project. |
| Hostinger Connector | Connected the official hosted endpoint. OAuth login completed and Codex reports OAuth authentication. No deployment, billing change or hosting mutation was performed. |
| Transitions.dev | Installed `transitions-dev`, `transitions-polish`, `transitions-ui-generation`, and `refine-live`. |
| The Three Mega Lists | Discovery catalogs, not single installable skills. Their entire transitive catalogs were not bulk-installed. |
| Work In Progress | Resource website, not an installable skill. |
| Hypershots | Installed `hypershots` and ImageMagick 7.1.2-35. Repaired native Windows file URLs and isolated Chrome profile handling. A real synthetic panel rendered and validated at 1290 x 2796 with no alpha and valid fit metadata. Optional paid image-generation services were not added. |
| Email Draft | Installed the published skill, then generalized its user name and repaired its instructions for the live Gmail MIME schema and draft/message IDs. Added the missing summary checker. The official skill validator and 20-word positive/negative checks passed; an independent review found no actionable issue. Gmail authentication was verified via its profile endpoint; no email or draft was created. |
| Make Your Own Skill | The built-in `skill-creator` was already installed. Linked prompt posts were not converted into new skills. |
| The Loop Stack | Installed the directly linked `maintainer-orchestrator` skill. |
| Video Use | Installed the full skill and an isolated Python dependency environment; dependency checks and a one-second synthetic timeline render passed using FFmpeg 9.0.2. The user chose to leave transcription unconfigured, so no ElevenLabs key was added and no transcription was run. |
| Open Design | Installed official Windows release 0.26.1, started its loopback-only daemon with the bundled Electron runtime, and registered its Codex MCP server. Verified 22 exposed tools, a read-only project-list call and HTTP health 200. No project or model generation was started. |
| Honourable mention: Hatch Pet | Installed `hatch-pet` and Pillow 13.0.0. WebP support and all 8 helper CLI checks passed. No image or pet was generated. |
| Honourable mention: Graphify | Preserved the existing skill. Verified its upstream package name and installed graphifyy 0.9.100; CLI, parser imports and dependency checks passed. No indexing or model call was run. |
| Honourable mentions: Figma and official catalogs | Figma is connected and its authenticated identity endpoint succeeded. The OpenAI skills/plugins links remain discovery catalogs; their entire transitive contents were not bulk-installed. |

The original per-file check is in `video-skills-installed-verification.json`; repository paths are in `video-skills-install-manifest.json`; sanitized MCP status is in `video-tool-setup/connections-verification.json`. No credentials are included in these reports.

Native Windows repairs have adjacent `.upstream` backups in the installed Email Draft, HyperShots and Codex Slides packages. Package updates may overwrite these local compatibility repairs. User PATH entries now cover the installed Python tools, FFmpeg, ImageMagick, Git Bash and psmux; new app processes pick up those changes.

Official installer SHA256 checks passed. Public installers and extracted source were moved out of this workspace into `C:\Users\Divansh Kapoor\AppData\Local\CodexTools\video-install-downloads`. The original Codex configuration was privately backed up beside `config.toml` before setup. Unrelated workspace changes were preserved.
