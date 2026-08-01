"""Replace absolute filesystem imports generated during route extraction."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
MODULES = (
    "social_auth",
    "social_profiles",
    "social_profile_resources",
    "social_profile_transfer",
)


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    for module in MODULES:
        suffix = f"routes.{module} import"
        lines = []
        for line in source.splitlines():
            if line.startswith("from ") and suffix in line:
                line = "from " + line[line.index(suffix):]
            lines.append(line)
        source = "\n".join(lines) + "\n"
    APP_PATH.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
