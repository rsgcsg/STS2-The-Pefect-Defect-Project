# Reuse qualified dependency layers without treating the old environment as final.
# Omitting EXPECTED_NEW_LOCK_SHA256 retains the unchanged-lock offline fast path.
ARG QUALIFIED_WORKER_IMAGE
FROM ${QUALIFIED_WORKER_IMAGE}
ARG QUALIFIED_WORKER_IMAGE
ARG STPD_SOURCE_REVISION
ARG QUALIFIED_SOURCE_REVISION=
ARG QUALIFIED_LOCK_SHA256=
ARG EXPECTED_NEW_LOCK_SHA256=
WORKDIR /opt/stpd/python
RUN set -eu; \
    printf '%s' "$QUALIFIED_WORKER_IMAGE" | grep -Eq '@sha256:[0-9a-f]{64}$'; \
    printf '%s' "$STPD_SOURCE_REVISION" | grep -Eq '^[0-9a-f]{40}$'; \
    test -z "$(git status --porcelain)"; \
    case "$STPD_IMAGE_PROFILE" in \
      hub) stpd_refresh_extras="--extra cloud --extra research" ;; \
      worker) stpd_refresh_extras="--all-extras" ;; \
      *) echo "Qualified monorepo image profile required" >&2; exit 1 ;; \
    esac; \
    stpd_refresh_lock=$(sha256sum uv.lock | cut -d ' ' -f 1); \
    if test -n "$EXPECTED_NEW_LOCK_SHA256"; then \
        printf '%s' "$QUALIFIED_SOURCE_REVISION" | grep -Eq '^[0-9a-f]{40}$'; \
        printf '%s' "$QUALIFIED_LOCK_SHA256" | grep -Eq '^[0-9a-f]{64}$'; \
        printf '%s' "$EXPECTED_NEW_LOCK_SHA256" | grep -Eq '^[0-9a-f]{64}$'; \
        test "$(git rev-parse HEAD)" = "$QUALIFIED_SOURCE_REVISION"; \
        test "$stpd_refresh_lock" = "$QUALIFIED_LOCK_SHA256"; \
    fi; \
    test "$(git remote get-url origin)" = "https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project.git"; \
    git fetch origin "$STPD_SOURCE_REVISION"; \
    git checkout --detach "$STPD_SOURCE_REVISION"; \
    if test -n "$EXPECTED_NEW_LOCK_SHA256"; then \
        test "$(sha256sum uv.lock | cut -d ' ' -f 1)" = "$EXPECTED_NEW_LOCK_SHA256"; \
        uv sync --locked $stpd_refresh_extras; \
    else \
        test "$stpd_refresh_lock" = "$(sha256sum uv.lock | cut -d ' ' -f 1)"; \
        uv sync --locked $stpd_refresh_extras --offline; \
    fi; \
    uv pip check --python .venv/bin/python; \
    test "$(git rev-parse HEAD)" = "$STPD_SOURCE_REVISION"; \
    test -z "$(git status --porcelain)"
