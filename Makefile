.DEFAULT_GOAL := check
.PHONY: check validate dogfood hooks clean

check:
	./scripts/check.sh

hooks:
	./scripts/setup-hooks

validate:
	@if [ -e ./setup ]; then \
		if [ ! -x ./setup ]; then echo "setup exists but is not executable" >&2; exit 1; fi; \
		./setup validate; \
	else \
		echo "setup CLI not installed yet"; \
	fi

dogfood:
	@if [ -e ./scripts/dogfood.sh ]; then \
		if [ ! -x ./scripts/dogfood.sh ]; then echo "dogfood.sh exists but is not executable" >&2; exit 1; fi; \
		./scripts/dogfood.sh; \
	else \
		echo "dogfood suite not installed yet"; \
	fi

clean:
	find . \( -path './.git' -o -path './.worktrees' -o -path './.clones' -o -path './node_modules' \) -prune \
		-o \( -name '__pycache__' -type d -exec rm -rf {} + -prune \) \
		-o \( -name '*.pyc' -type f -delete \)
