"""Shared, script-free navigation for the seven application workspaces."""

LINKS = (
    ("status", "Live-Status"),
    ("studio", "Missionen"),
    ("media", "Medien"),
    ("operations", "Übersicht"),
)
ANALYSIS = (
    ("thermal", "Thermal"),
    ("multispectral", "Multispektral"),
    ("results", "Ergebnisraster"),
)

CSS = """
nav.app-nav{display:flex;align-items:center;gap:4px;flex-wrap:wrap;font-size:13px}
nav.app-nav a,nav.app-nav summary{display:block;padding:9px 12px;border:1px solid transparent;border-radius:8px;color:#b8c9dd;background:transparent;text-decoration:none;line-height:1.4;cursor:pointer;font-weight:600}
nav.app-nav a:hover,nav.app-nav summary:hover{background:#172740;color:#eaf3ff}
nav.app-nav a[aria-current="page"],nav.app-nav details[data-current] summary{background:#23496b;color:#fff;border-color:#3c5875}
nav.app-nav a:focus-visible,nav.app-nav summary:focus-visible{outline:2px solid #7ccaff;outline-offset:2px}
nav.app-nav details{position:relative;margin:0;padding:0;border:0;background:transparent}
nav.app-nav summary{list-style:none}nav.app-nav summary::-webkit-details-marker{display:none}
nav.app-nav summary::after{content:" ▾"}nav.app-nav details[open] summary::after{content:" ▴"}
nav.app-nav .app-nav-menu{position:absolute;top:calc(100% + 5px);right:0;z-index:2000;min-width:190px;padding:6px;background:#111e31;border:1px solid #2c425c;border-radius:9px;box-shadow:0 8px 24px #0006}
@media(max-width:700px){nav.app-nav{width:100%;gap:2px}nav.app-nav a,nav.app-nav summary{padding:10px 9px}nav.app-nav .app-nav-menu{position:static;margin-top:5px;box-shadow:none}nav.app-nav details[open]{flex-basis:100%}}
"""


def navigation(current: str) -> str:
    """Native disclosure keeps every analysis page reachable with a keyboard."""
    def link(path: str, label: str) -> str:
        selected = ' aria-current="page"' if path == current else ""
        return f'<a href="/{path}"{selected}>{label}</a>'

    selected = ' data-current="true"' if current in dict(ANALYSIS) else ""
    return (
        '<nav class="app-nav" aria-label="Hauptnavigation">'
        + "".join(link(*item) for item in LINKS)
        + f'<details{selected}><summary>Auswertungen</summary><div class="app-nav-menu">'
        + "".join(link(*item) for item in ANALYSIS)
        + "</div></details></nav>"
    )


def with_navigation(html: str, current: str) -> str:
    """Apply the same navigation and tokens without adding another script."""
    return html.replace("__APP_NAVIGATION__", navigation(current)).replace(
        "</style>", CSS + "</style>", 1
    )
