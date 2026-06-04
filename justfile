alias l := lint
alias t := test
alias fs := fmt-self

[private]
default:
    just --list

[group("dev")]
sync:
    uv sync

[private]
@lint-yaml:
    git ls-files -z -- "*.yaml" "*.yml" | xargs -0 uv run check-yaml

[private]
@lint-toml:
    git ls-files -z -- "*.toml" | xargs -0 uv run check-toml

[private]
@lint-ruff:
    uv run ruff check --quiet --fix .
    uv run ruff format --quiet .

[private]
@lint-mypy:
    uv run mypy --no-error-summary .

[private]
@lint-large-files:
    git ls-files -z | xargs -0 uv run check-added-large-files

[private]
@lint-whitespace:
    git ls-files -z | xargs -0 uv run trailing-whitespace-fixer

[private]
@lint-eol:
    git ls-files -z | xargs -0 uv run end-of-file-fixer

[private]
@lint-lf:
    git ls-files -z | xargs -0 uv run mixed-line-ending --fix=lf

[group("dev")]
[parallel]
lint: lint-yaml lint-toml lint-large-files lint-ruff lint-mypy lint-whitespace lint-eol lint-lf

[group("dev")]
test *args:
    uv run coverage erase
    uv run coverage run -m pytest {{ args }}
    uv run coverage report

[group("just")]
fmt-self:
    just --fmt --unstable
