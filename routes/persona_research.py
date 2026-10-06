"""Research-document, factoid, affinity, and persona routes."""

import hashlib
import io
import os
import uuid

from pypdf import PdfReader

from app_support.context import bind_context


MAX_RESEARCH_DOCUMENT_BYTES = 20 * 1024 * 1024
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf"}


def _extract_text(filename, content):
    extension = os.path.splitext(filename)[1].casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Use a PDF, TXT, Markdown, CSV, JSON, or log file.")
    if extension == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = []
            for index, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                pages.append(f"--- Page {index} ---\n{page_text}")
            return "\n\n".join(pages)
        except Exception as exc:
            raise ValueError("The PDF could not be read or does not contain extractable text.") from exc
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("The document text encoding could not be read.")


def _highlight_segments(text, highlights):
    ranges = []
    for item in highlights:
        start = max(0, int(item.get("start") or 0))
        end = min(len(text), int(item.get("end") or 0))
        if end > start:
            ranges.append((start, end))
    ranges.sort()
    merged = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    segments = []
    cursor = 0
    for start, end in merged:
        if start > cursor:
            segments.append({"text": text[cursor:start], "highlighted": False})
        segments.append({"text": text[start:end], "highlighted": True})
        cursor = end
    if cursor < len(text):
        segments.append({"text": text[cursor:], "highlighted": False})
    return segments or [{"text": text, "highlighted": False}]


def register_persona_research_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    def owner():
        return current_app_user()["username"]

    def document_map():
        return {
            item["id"]: item
            for item in persona_research_service.list_records(
                persona_research, "documents", owner()
            )
        }

    @app.route("/social-engineering/research")
    @social_login_required()
    @_refresh_context
    def persona_research_page():
        username = owner()
        documents = persona_research_service.list_records(
            persona_research, "documents", username
        )
        factoids = persona_research_service.list_records(
            persona_research, "factoids", username
        )
        groups = [
            persona_research_service.affinity_group_view(
                item, persona_research, username
            )
            for item in persona_research_service.list_records(
                persona_research, "affinity_groups", username
            )
        ]
        personas = [
            persona_research_service.persona_view(
                item["id"], persona_research, username
            )
            for item in persona_research_service.list_records(
                persona_research, "personas", username
            )
        ]
        docs = {item["id"]: item for item in documents}
        profiles = {item["id"]: item for item in owned_social_profiles()}
        for factoid in factoids:
            factoid["document"] = docs.get(factoid.get("document_id"))
            factoid["source_profile"] = profiles.get(
                factoid.get("source_profile_id")
            )
        assigned = {
            factoid_id
            for group in groups
            for factoid_id in group.get("factoid_ids", [])
        }
        return render_template(
            "persona_research.html",
            title="Research & Personas",
            documents=documents,
            factoids=factoids,
            groups=groups,
            personas=personas,
            ungrouped_factoids=[
                item for item in factoids if item["id"] not in assigned
            ],
            profile_choices=owned_social_profiles(),
            categories=persona_research_service.DEFAULT_CHARACTERISTIC_CATEGORIES,
            csrf_token=social_csrf_token(),
            social_user=session.get("social_user"),
            **current_context(),
        )

    @app.route("/social-engineering/research/documents", methods=["POST"])
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def add_persona_research_document():
        upload = request.files.get("document")
        if not upload or not upload.filename:
            return json_error("Choose a document to upload.")
        safe_name = secure_filename(upload.filename) or "document"
        content = upload.read(MAX_RESEARCH_DOCUMENT_BYTES + 1)
        if len(content) > MAX_RESEARCH_DOCUMENT_BYTES:
            return json_error("Research documents must be 20 MB or smaller.")
        try:
            extracted_text = _extract_text(safe_name, content)
        except ValueError as exc:
            return json_error(str(exc))
        extension = os.path.splitext(safe_name)[1].casefold()
        stored_name = f"{uuid.uuid4()}{extension}"
        os.makedirs(PERSONA_RESEARCH_DOCUMENT_DIR, exist_ok=True)
        metadata = {
            "title": request.form.get("title") or safe_name,
            "original_name": safe_name,
            "filename": stored_name,
            "content_type": upload.mimetype or "",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "source_key": request.form.get("source_key"),
            "source_label": request.form.get("source_label"),
            "participant_profile_id": request.form.get("participant_profile_id"),
            "notes": request.form.get("notes"),
        }
        try:
            document = persona_research_service.create_document(
                metadata,
                extracted_text,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except ValueError as exc:
            return json_error(str(exc))
        with open(
            os.path.join(PERSONA_RESEARCH_DOCUMENT_DIR, stored_name), "wb"
        ) as handle:
            handle.write(content)
        record_social_audit(
            "persona.document.create", detail=document["id"]
        )
        save_runtime_state("persona-document-create")
        return redirect(
            url_for("persona_research_document", document_id=document["id"])
        )

    @app.route("/social-engineering/research/documents/<document_id>")
    @social_login_required()
    @_refresh_context
    def persona_research_document(document_id):
        username = owner()
        document = persona_research_service.get_record(
            persona_research, "documents", document_id, username
        )
        if not document:
            return json_error("Document not found.", 404)
        highlights = persona_research_service.document_highlights(
            document_id, persona_research, username
        )
        return render_template(
            "persona_document.html",
            title=document["title"],
            document=document,
            highlights=highlights,
            segments=_highlight_segments(
                document.get("extracted_text") or "", highlights
            ),
            csrf_token=social_csrf_token(),
            **current_context(),
        )

    @app.route(
        "/social-engineering/research/documents/<document_id>/file"
    )
    @social_login_required()
    @_refresh_context
    def persona_research_document_file(document_id):
        document = persona_research_service.get_record(
            persona_research, "documents", document_id, owner()
        )
        if not document:
            return "", 404
        return send_from_directory(
            PERSONA_RESEARCH_DOCUMENT_DIR,
            document["filename"],
            as_attachment=True,
            download_name=document["original_name"],
        )

    @app.route(
        "/social-engineering/research/documents/<document_id>/factoids",
        methods=["POST"],
    )
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def create_persona_factoid(document_id):
        try:
            factoid = persona_research_service.create_factoid(
                document_id,
                request.form,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except KeyError:
            return json_error("Document not found.", 404)
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit(
            "persona.factoid.create", detail=factoid["id"]
        )
        save_runtime_state("persona-factoid-create")
        return redirect(
            url_for("persona_research_document", document_id=document_id)
            + f"#factoid-{factoid['id']}"
        )

    @app.route(
        "/social-engineering/profiles/<profile_id>/research/factoids",
        methods=["POST"],
    )
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def create_profile_evidence_factoid(profile_id):
        profile = owned_social_profile(profile_id)
        if not profile:
            return json_error("Profile not found.", 404)
        candidates = {
            item["ref"]: item
            for item in persona_research_service.profile_evidence_candidates(
                profile
            )
        }
        source = candidates.get(request.form.get("source_ref") or "")
        if not source:
            return json_error("Choose a valid profile evidence source.")
        try:
            factoid = persona_research_service.create_profile_factoid(
                profile_id,
                source,
                request.form,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit(
            "persona.profile-factoid.create",
            profile_id,
            factoid["id"],
        )
        save_runtime_state("persona-profile-factoid-create")
        return redirect(
            url_for("social_profile_detail", profile_id=profile_id)
            + "#research-evidence"
        )

    @app.route(
        "/social-engineering/research/affinity-groups", methods=["POST"]
    )
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def create_persona_affinity_group():
        try:
            group = persona_research_service.create_affinity_group(
                request.form,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit(
            "persona.affinity.create", detail=group["id"]
        )
        save_runtime_state("persona-affinity-create")
        return redirect(url_for("persona_research_page") + "#affinity")

    @app.route(
        "/social-engineering/research/factoids/<factoid_id>/group",
        methods=["POST"],
    )
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def move_persona_factoid(factoid_id):
        try:
            persona_research_service.assign_factoid_to_group(
                factoid_id,
                request.form.get("group_id") or "",
                persona_research,
                persona_research_lock,
                owner(),
            )
        except KeyError:
            return json_error("Factoid or affinity group not found.", 404)
        record_social_audit(
            "persona.factoid.group", detail=factoid_id
        )
        save_runtime_state("persona-factoid-group")
        return redirect(url_for("persona_research_page") + "#affinity")

    @app.route("/social-engineering/research/personas", methods=["POST"])
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def create_research_persona():
        try:
            persona = persona_research_service.create_persona(
                request.form,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit(
            "persona.create", detail=persona["id"]
        )
        save_runtime_state("persona-create")
        return redirect(
            url_for("research_persona_detail", persona_id=persona["id"])
        )

    @app.route("/social-engineering/research/personas/<persona_id>")
    @social_login_required()
    @_refresh_context
    def research_persona_detail(persona_id):
        username = owner()
        persona = persona_research_service.persona_view(
            persona_id, persona_research, username
        )
        if not persona:
            return json_error("Persona not found.", 404)
        docs = document_map()
        profiles = {item["id"]: item for item in owned_social_profiles()}
        contributor_ids = set()
        for characteristic in persona.get("characteristics", []):
            for factoid in characteristic.get("factoids", []):
                factoid["document"] = docs.get(factoid.get("document_id"))
                source_profile_id = persona_research_service.factoid_profile_id(
                    factoid, persona_research
                )
                factoid["source_profile"] = profiles.get(source_profile_id)
                if source_profile_id:
                    contributor_ids.add(source_profile_id)
        persona["contributors"] = [
            profiles[profile_id]
            for profile_id in sorted(
                contributor_ids,
                key=lambda item: (
                    profiles.get(item, {}).get("full_name") or item
                ).casefold(),
            )
            if profile_id in profiles
        ]
        groups = persona_research_service.list_records(
            persona_research, "affinity_groups", username
        )
        factoids = persona_research_service.list_records(
            persona_research, "factoids", username
        )
        linked_profile = (
            owned_social_profile(persona.get("linked_profile_id"))
            if persona.get("linked_profile_id")
            else None
        )
        return render_template(
            "persona_detail.html",
            title=persona["name"],
            persona=persona,
            linked_profile=linked_profile,
            groups=groups,
            factoids=factoids,
            categories=persona_research_service.DEFAULT_CHARACTERISTIC_CATEGORIES,
            csrf_token=social_csrf_token(),
            **current_context(),
        )

    @app.route(
        "/social-engineering/research/personas/<persona_id>/characteristics",
        methods=["POST"],
    )
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def create_persona_characteristic(persona_id):
        values = request.form.to_dict(flat=True)
        values["affinity_group_ids"] = request.form.getlist(
            "affinity_group_ids"
        )
        values["factoid_ids"] = request.form.getlist("factoid_ids")
        try:
            characteristic = persona_research_service.add_characteristic(
                persona_id,
                values,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except KeyError:
            return json_error("Persona not found.", 404)
        except ValueError as exc:
            return json_error(str(exc))
        record_social_audit(
            "persona.characteristic.create",
            detail=characteristic["id"],
        )
        save_runtime_state("persona-characteristic-create")
        return redirect(
            url_for("research_persona_detail", persona_id=persona_id)
        )

    @app.route(
        "/social-engineering/research/personas/<persona_id>/characteristics/"
        "<characteristic_id>/delete",
        methods=["POST"],
    )
    @social_login_required({"editor", "admin"})
    @_refresh_context
    def delete_persona_characteristic(persona_id, characteristic_id):
        try:
            removed = persona_research_service.delete_characteristic(
                persona_id,
                characteristic_id,
                persona_research,
                persona_research_lock,
                owner(),
            )
        except KeyError:
            return json_error("Persona not found.", 404)
        if not removed:
            return json_error("Characteristic not found.", 404)
        record_social_audit(
            "persona.characteristic.delete", detail=characteristic_id
        )
        save_runtime_state("persona-characteristic-delete")
        return redirect(
            url_for("research_persona_detail", persona_id=persona_id)
        )

    return {
        "persona_research_page": persona_research_page,
        "persona_research_document": persona_research_document,
        "research_persona_detail": research_persona_detail,
    }
