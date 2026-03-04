# Blog Pattern Mining

Use this workflow when adding a non-RSS blog source.

## Goal

Generate reusable `site_profile` YAML and validate extraction quality.

## Steps

1. Copy `templates/site_profile.template.yaml` to `backend/app/collectors/site_profiles/<site_key>.yaml`.
2. Fill list/detail selectors for the target site.
3. Run:
   - `python backend/scripts/validate_site_profile.py --profile backend/app/collectors/site_profiles/<site_key>.yaml`
4. Check P0 coverage:
   - `python backend/scripts/validate_site_profile.py --check-p0`
5. Record results in `checklists/validation.md`.
