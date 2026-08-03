# Device Model Profiles

Device Model Profiles extend the original model-port knowledge database into a reusable device-intelligence library.

## Matching hierarchy

Rules are combined from least to most specific:

1. manufacturer defaults;
2. model-family profiles;
3. exact model profiles;
4. hardware and firmware constrained exact profiles;
5. a manually assigned profile;
6. device-specific local overrides.

The most specific applicable rule wins for the same port and protocol.

## Port classifications

- `expected`: normally present and reported as missing when absent;
- `optional`: accepted when present but not reported missing;
- `firmware-specific`: valid only for the configured firmware range;
- `local-configuration`: a known local addition rather than standard model behaviour;
- `investigate`: meaning is not yet sufficiently established;
- `deprecated`: known legacy service that should usually be removed or disabled;
- `unexpected`: explicitly documented as abnormal for the model.

Each rule can include exposure expectations, authentication and encryption expectations, risk, remediation, hardware/firmware applicability, source provenance, reliability, and confidence.

## Model library

Open `/models` to:

- create exact, family, or manufacturer profiles;
- add aliases and canonical identities;
- constrain profiles and rules to hardware revisions or firmware ranges;
- add and classify port rules;
- compare matching inventory devices;
- review common ports and firmware distributions;
- resolve conflicting source claims;
- inspect revision history and roll back;
- export privacy-clean community contributions.

## Client drift

IP client pages automatically show a Device Model Profile card. Drift compares observed ports with applicable profile rules and reports:

- unexpected ports;
- missing expected ports;
- deprecated services;
- remediation tasks;
- overall severity and score.

An unexpected service can be investigated with bounded safe probes or approved as a device-specific local override.

## Signed registries

Registries use schema `mobile-router-model-profiles-v2` and always contain a SHA-256 manifest digest. They can additionally be authenticated with HMAC-SHA256.

Configure a publisher and signing secret when exporting:

```powershell
$env:MOBILE_ROUTER_MODEL_REGISTRY_PUBLISHER = "my-lab"
$env:MOBILE_ROUTER_MODEL_REGISTRY_SIGNING_KEY = "replace-with-a-long-random-secret"
```

Configure trusted publisher keys for import and sync:

```powershell
$env:MOBILE_ROUTER_MODEL_REGISTRY_KEYS = '{"my-lab":"replace-with-a-long-random-secret"}'
```

Configure one or more HTTPS registry locations:

```powershell
$env:MOBILE_ROUTER_MODEL_REGISTRY_URLS = "https://example.org/device-model-registry.json"
```

Automatic sync requires trusted signatures unless the administrator explicitly selects unsigned import.

## Registry build pipeline

Build a release from contribution and registry JSON files:

```powershell
python build_model_registry.py `
  contributions\sky-sr203.json `
  contributions\synology.json `
  --output releases\device-model-registry.json `
  --publisher my-lab `
  --version 2026.08.1
```

The builder:

- validates input schemas;
- merges aliases;
- deduplicates identical profiles and rules;
- writes a separate conflict report;
- refuses conflicting releases by default;
- validates the completed registry;
- signs it when the configured signing key is present.

Use `--allow-conflicts` only when the generated conflict report has been reviewed and retaining the current preferred entries is intentional.

## Privacy-clean contributions

Contribution exports intentionally exclude IP addresses, MAC addresses, hostnames, serial numbers, credentials, and private device URLs. They contain only the reusable model profile, port rules, and aggregate observation counts.
