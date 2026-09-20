# Maintenance — 21 September 2026

Hardcoded initial passwords were removed from reachable history. Export SETPRICE_INITIAL_ADMIN_PASSWORD (unique, 16+ characters) before initial account creation; do not commit it. Environment variables are configuration, not encryption. Existing accounts are NOT reset: change their passwords separately. Password storage already uses bcrypt. The legacy Excel importer has not been fully validated.

Old external clones, GitHub cached commits and provider sessions are not erased by rewriting this repository.
