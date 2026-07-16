import quopri
import re
from datetime import datetime


VCARD_BLOCK_RE = re.compile(
    r"BEGIN:VCARD\s*(.*?)\s*END:VCARD",
    flags=re.IGNORECASE | re.DOTALL,
)
CALL_TYPE_MAP = {
    "RECEIVED": "incoming",
    "DIALED": "outgoing",
    "MISSED": "missed",
}


def _payload_text(payload):
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return str(payload or "")


def unfold_vcard_lines(payload):
    lines = _payload_text(payload).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        elif unfolded and unfolded[-1].upper().endswith("ENCODING=QUOTED-PRINTABLE:"):
            unfolded[-1] += line
        elif unfolded and unfolded[-1].endswith("="):
            unfolded[-1] = unfolded[-1][:-1] + line
        else:
            unfolded.append(line)
    return unfolded


def _split_escaped(value, delimiter=";"):
    values = []
    buffer = []
    escaped = False
    for character in value:
        if escaped:
            buffer.append("\\")
            buffer.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == delimiter:
            values.append("".join(buffer))
            buffer = []
        else:
            buffer.append(character)
    if escaped:
        buffer.append("\\")
    values.append("".join(buffer))
    return values


def _unescape_vcard_value(value):
    replacements = {
        "\\n": "\n",
        "\\N": "\n",
        "\\,": ",",
        "\\;": ";",
        "\\\\": "\\",
    }
    result = value
    for escaped, replacement in replacements.items():
        result = result.replace(escaped, replacement)
    return result


def _parse_property(line):
    if ":" not in line:
        return None
    header, value = line.split(":", 1)
    header_parts = header.split(";")
    name = header_parts[0].split(".")[-1].upper()
    parameters = {}
    bare_types = []
    for parameter in header_parts[1:]:
        if "=" in parameter:
            key, parameter_value = parameter.split("=", 1)
            values = [item.strip('"') for item in parameter_value.split(",") if item]
            parameters.setdefault(key.upper(), []).extend(values)
        elif parameter:
            bare_types.append(parameter)
    if bare_types:
        parameters.setdefault("TYPE", []).extend(bare_types)

    if "QUOTED-PRINTABLE" in [item.upper() for item in parameters.get("ENCODING", [])]:
        value = quopri.decodestring(value).decode(
            parameters.get("CHARSET", ["utf-8"])[0],
            errors="replace",
        )
    return {
        "name": name,
        "raw_value": value,
        "value": _unescape_vcard_value(value),
        "parameters": parameters,
    }


def parse_vcard_properties(vcard_body):
    properties = {}
    for line in unfold_vcard_lines(vcard_body):
        parsed = _parse_property(line)
        if not parsed or parsed["name"] in {"BEGIN", "END"}:
            continue
        properties.setdefault(parsed["name"], []).append(parsed)
    return properties


def _first_value(properties, name, default=""):
    values = properties.get(name, [])
    return values[0]["value"] if values else default


def _name_components(properties):
    values = properties.get("N", [])
    if not values:
        return []
    return [
        _unescape_vcard_value(component)
        for component in _split_escaped(values[0].get("raw_value", ""))
    ]


def _display_name(properties):
    formatted_name = _first_value(properties, "FN").strip()
    if formatted_name:
        return formatted_name
    name_components = _name_components(properties)
    family = name_components[0] if name_components else ""
    given = name_components[1] if len(name_components) > 1 else ""
    additional = name_components[2] if len(name_components) > 2 else ""
    return " ".join(
        component for component in (given, additional, family) if component
    ).strip()


def _typed_values(properties, name, value_key):
    return [
        {
            value_key: item["value"],
            "types": [value.lower() for value in item["parameters"].get("TYPE", [])],
        }
        for item in properties.get(name, [])
        if item["value"]
    ]


def contact_from_vcard(vcard_body):
    properties = parse_vcard_properties(vcard_body)
    name_components = _name_components(properties)
    return {
        "display_name": _display_name(properties),
        "family_name": name_components[0] if name_components else "",
        "given_name": name_components[1] if len(name_components) > 1 else "",
        "additional_name": name_components[2] if len(name_components) > 2 else "",
        "prefix": name_components[3] if len(name_components) > 3 else "",
        "suffix": name_components[4] if len(name_components) > 4 else "",
        "phones": _typed_values(properties, "TEL", "number"),
        "emails": _typed_values(properties, "EMAIL", "address"),
        "organisation": _first_value(properties, "ORG"),
        "title": _first_value(properties, "TITLE"),
        "birthday": _first_value(properties, "BDAY"),
        "note": _first_value(properties, "NOTE"),
        "uid": _first_value(properties, "UID"),
    }


def _normalise_call_timestamp(value):
    timestamp = value.strip()
    for format_string in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(timestamp, format_string).isoformat()
        except ValueError:
            continue
    return timestamp


def call_from_vcard(vcard_body):
    properties = parse_vcard_properties(vcard_body)
    call_property = (properties.get("X-IRMC-CALL-DATETIME") or [{}])[0]
    call_types = [
        value.upper()
        for value in call_property.get("parameters", {}).get("TYPE", [])
    ]
    raw_call_type = next(
        (value for value in call_types if value in CALL_TYPE_MAP),
        "UNKNOWN",
    )
    phone_values = _typed_values(properties, "TEL", "number")
    return {
        "display_name": _display_name(properties),
        "number": phone_values[0]["number"] if phone_values else "",
        "call_type": CALL_TYPE_MAP.get(raw_call_type, "unknown"),
        "timestamp": _normalise_call_timestamp(call_property.get("value", "")),
    }


def parse_pbap_vcards(payload, record_type="contacts"):
    text = _payload_text(payload)
    blocks = VCARD_BLOCK_RE.findall(text)
    if record_type == "contacts":
        return [contact_from_vcard(block) for block in blocks]
    if record_type == "calls":
        return [call_from_vcard(block) for block in blocks]
    raise ValueError("record_type must be contacts or calls")
