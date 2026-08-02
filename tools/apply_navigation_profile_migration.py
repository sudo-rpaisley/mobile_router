"""One-shot migration for navigation and account profile improvements."""

import base64
import json
import zlib
from pathlib import Path


# This temporary runner removes itself after applying the atomic migration.
def replace_once(source, old, new, label):
    if source.count(old) != 1:
        raise RuntimeError(f"Expected exactly one {label} block, found {source.count(old)}")
    return source.replace(old, new, 1)


def main():
    payload_paths = sorted(Path("tools").glob("nav_payload_*.txt"))
    payload = "".join(path.read_text(encoding="utf-8") for path in payload_paths)
    files = json.loads(zlib.decompress(base64.b64decode(payload)).decode())
    app_path = Path("app.py")
    source = app_path.read_text(encoding="utf-8")
    source = replace_once(
        source,
        "from services import social_auth as social_auth_service\n",
        "from services import social_auth as social_auth_service\nfrom app_support import navigation as navigation_service\n",
        "navigation import",
    )
    source = replace_once(
        source,
        """@app.context_processor
def inject_application_auth():
    return {'app_user': current_app_user(), 'app_csrf_token': social_csrf_token()}
""",
        """@app.context_processor
def inject_application_auth():
    record = current_user_record()
    app_user = social_auth_service.public_user(record) if record else current_app_user()

    def app_navigation(title=''):
        return navigation_service.build_navigation_context(
            request.path,
            title,
            request.endpoint,
            app_user,
            networkTechnologies,
            network_interfaces,
        )

    return {
        'app_user': app_user,
        'app_csrf_token': social_csrf_token(),
        'app_navigation': app_navigation,
    }
""",
        "application auth context processor",
    )
    app_path.write_text(source, encoding="utf-8")

    for relative_path, content in files.items():
        path = Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    for temporary in [
        Path("tools/apply_navigation_profile_migration.py"),
        Path(".github/workflows/apply-navigation-profile.yml"),
        *payload_paths,
    ]:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
